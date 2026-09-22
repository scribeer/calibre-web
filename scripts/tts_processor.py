#!/usr/bin/env python3
# ============================================================================
# tts_processor.py — озвучка TXT через edge-tts со сборкой в M4B с главами
#
# CHANGELOG:
# 2026-08-18 v5
#   - Разбиение текста на главы (маркеры + эвристика по заголовкам)
#   - Чанки не пересекают границу главы -> старт главы совпадает с чанком
#   - Замер длительности каждого чанка (ffprobe), кэш в durations.json
#   - Сборка в M4B (AAC) с главами, тегами и обложкой одним проходом ffmpeg
#   - manifest.json + sha256 текста: защита резюма от подмены TXT
#   - Фолбэк: если глав не найдено — нарезка по времени (FALLBACK_MINUTES)
#   - Режим --preview: показать найденные главы, не тратя озвучку
#   - Выход только M4B
#
# Раньше (v4 и ниже) — см. историю в 3au-tts_directory.sh
# ============================================================================

import os
import sys
import re
import json
import time
import shutil
import hashlib
import asyncio
import argparse
import subprocess
import traceback
import math
import stat
from datetime import datetime
from pathlib import Path

edge_tts = None  # импортируется лениво: --preview работает и без venv


def require_edge_tts():
    global edge_tts
    if edge_tts is None:
        try:
            import edge_tts as _et
        except Exception as e:  # noqa: BLE001
            print(f"[FATAL] Не удалось импортировать edge_tts: {e}")
            sys.exit(1)
        edge_tts = _et
    return edge_tts


# ========================= ПУТИ =========================

SYSTEM_USER = os.environ.get("USER", "unknown")
BASE_AUBOOKS_DIR = Path(os.environ.get("BASE_AUBOOKS_DIR", f"/home/{SYSTEM_USER}/aubooks"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", f"/home/{SYSTEM_USER}/to_upload"))

JPG_DIR = BASE_AUBOOKS_DIR / "jpg"
HTML_DIR = BASE_AUBOOKS_DIR / "html"
OPF_DIR = BASE_AUBOOKS_DIR / "opf"
TEMP_BASE_DIR = UPLOAD_DIR
FINAL_DIR = UPLOAD_DIR


# ========================= НАСТРОЙКИ =========================

# Два голоса на язык: пользователь выбирает 1 или 2 на телефоне при отправке.
VOICE_RU_MAIN = os.environ.get("VOICE_RU_MAIN", "ru-RU-SvetlanaNeural")   # 1
VOICE_RU_ALT = os.environ.get("VOICE_RU_ALT", "ru-RU-DmitryNeural")       # 2
VOICE_UA_MAIN = os.environ.get("VOICE_UA_MAIN", "uk-UA-PolinaNeural")     # 1
VOICE_UA_ALT = os.environ.get("VOICE_UA_ALT", "uk-UA-OstapNeural")        # 2
VOICE_CHOICE = os.environ.get("VOICE_CHOICE", "1").strip()
if VOICE_CHOICE not in ("1", "2"):
    VOICE_CHOICE = "1"

# --- Английские вставки ---
# Абзацы, целиком набранные латиницей, читает отдельный голос.
# Переключение только на границе абзаца: внутри фразы edge-tts делает
# каждый запрос отдельным высказыванием, и речь распадается на куски.
EN_DETECT = os.environ.get("EN_DETECT", "off").lower()   # on | off
VOICE_EN_MAIN = os.environ.get("VOICE_EN_MAIN", "en-US-AriaNeural")
EN_MIN_RATIO = float(os.environ.get("EN_MIN_RATIO", 0.85))
EN_MIN_CHARS = int(os.environ.get("EN_MIN_CHARS", 40))

# --- URL detection for EN voice ---
# Candidate matching is deliberately ASCII-only for bare domains, so Russian
# abbreviations and dotted prose are not mistaken for URLs.
_URL_HOST = r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}"
URL_RE = re.compile(
    rf"(?<![\w@])(?:(?:https?://|www\.)[^\s<>'\"]+|{_URL_HOST}(?:/[^\s<>'\"]*)?)"
)

MAX_CHUNK_SIZE = int(os.environ.get("MAX_CHUNK_SIZE", 3000))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 90))
MAX_RETRIES_PER_CHUNK = int(os.environ.get("MAX_RETRIES_PER_CHUNK", 3))
MAX_CONSECUTIVE_FAILURES = int(os.environ.get("MAX_CONSECUTIVE_FAILURES", 3))
DELAY_BETWEEN_REQUESTS = float(os.environ.get("DELAY_BETWEEN_REQUESTS", 0.5))
CONCURRENCY = int(os.environ.get("CONCURRENCY", 4))
TASK_WINDOW = int(os.environ.get("TASK_WINDOW", 16))

LOG_HEAD_TAIL = 120
PROGRESS_BAR_WIDTH = 22

# --- Главы ---
# Явный маркер в тексте имеет наивысший приоритет:  <<<CHAPTER:Название>>>
CH_USE_HEURISTIC = os.environ.get("CH_USE_HEURISTIC", "1") == "1"
# Считать ли одинокие числа/римские цифры заголовком (опасно на списках)
CH_BARE_NUMBERS = os.environ.get("CH_BARE_NUMBERS", "0") == "1"
CH_MAX_HEADING_LEN = int(os.environ.get("CH_MAX_HEADING_LEN", 80))
# Если глав не найдено — резать по времени, минут на фрагмент (0 = выключено)
FALLBACK_MINUTES = int(os.environ.get("FALLBACK_MINUTES", 15))
# Предохранитель: слишком много глав ломает часть плееров
CH_MAX_COUNT = int(os.environ.get("CH_MAX_COUNT", 600))

# --- Громкость ---
# Двухпроходная нормализация по EBU R128: сначала замер, потом точное
# применение. Так все книги в библиотеке звучат одинаково громко.
LOUDNORM = os.environ.get("LOUDNORM", "on").lower()      # on | off
LOUDNORM_I = os.environ.get("LOUDNORM_I", "-16")          # целевая громкость, LUFS
LOUDNORM_TP = os.environ.get("LOUDNORM_TP", "-1.5")       # потолок пиков, dBTP
LOUDNORM_LRA = os.environ.get("LOUDNORM_LRA", "11")       # разброс громкости
# Замер по выборке частей: речь синтезатора однородна, полный проход
# по 13-часовой книге занял бы минут десять. 0 — мерить всё целиком.
LOUDNORM_SAMPLE = int(os.environ.get("LOUDNORM_SAMPLE", 60))
# Выравнивать ли громкость между голосами (актуально при EN_DETECT=on)
VOICE_BALANCE = os.environ.get("VOICE_BALANCE", "on").lower()

# --- Выход (только M4B) ---
M4B_BITRATE = os.environ.get("M4B_BITRATE", "64k")
M4B_SAMPLERATE = os.environ.get("M4B_SAMPLERATE", "24000")

# Скорость речи для оценки в --preview (символов в секунду)
PREVIEW_CPS = float(os.environ.get("PREVIEW_CPS", 14.5))


CHAPTER_MARKER_RE = re.compile(r"^\s*<<<CHAPTER:(.*?)>>>\s*$")

# «Глава 12», «Розділ IV», «Часть 2», «Том 1» — ключевое слово ОБЯЗАНО
# сопровождаться номером, иначе «Часть меня хотела уйти» станет заголовком.
CH_KEYWORD_RE = re.compile(
    r"^(?:глава|розділ|раздел|часть|частина|книга|том)"
    r"\s*[№#]?\s*"
    r"(?:\d{1,3}|[ivxlcIVXLC]{1,7})\b",
    re.IGNORECASE | re.UNICODE,
)

# Самостоятельные заголовки без номера
CH_STANDALONE_RE = re.compile(
    r"^(?:пролог|эпилог|епілог|вступление|вступ|введение|предисловие|передмова|"
    r"послесловие|післямова|интерлюдия|інтерлюдія|заключение|висновок|"
    r"от\s+автора|від\s+автора|приложение|додаток)\b",
    re.IGNORECASE | re.UNICODE,
)

CH_BARE_NUM_RE = re.compile(r"^(?:\d{1,3}|[ivxlcIVXLC]{1,7})[.)]?$", re.UNICODE)


# ========================= УТИЛИТЫ =========================


def fmt_hms(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    s = int(seconds)
    h, m, ss = s // 3600, (s % 3600) // 60, s % 60
    return f"{h:02d}:{m:02d}:{ss:02d}" if h > 0 else f"{m:02d}:{ss:02d}"


class LiveProgress:
    def __init__(self, total: int):
        self.total = max(1, total)
        self.start = time.time()
        self.done = 0
        self.failed = 0
        self.current_part = 0
        self.current_status = "init"
        self._last_render = 0.0

    def set_current(self, part: int, status: str):
        self.current_part = part
        self.current_status = status

    def inc_done(self):
        self.done += 1

    def inc_failed(self):
        self.failed += 1

    def render(self, force: bool = False):
        now = time.time()
        if (not force) and (now - self._last_render < 0.15):
            return
        self._last_render = now
        elapsed = now - self.start
        frac = self.done / self.total
        rate = self.done / elapsed if elapsed > 0 else 0.0
        eta = (self.total - self.done) / rate if rate > 0 else 0.0
        filled = int(PROGRESS_BAR_WIDTH * frac)
        bar = ("=" * filled) + ("." * (PROGRESS_BAR_WIDTH - filled))
        line = (
            f"\r[{bar}] {frac*100:6.2f}% {self.done}/{self.total} "
            f"failed={self.failed} {rate*60:5.1f} ch/min "
            f"ETA {fmt_hms(eta)} part {self.current_part}: {self.current_status}   "
        )
        sys.stdout.write(line[:200])
        sys.stdout.flush()

    def println(self, msg: str):
        sys.stdout.write("\r" + (" " * 220) + "\r")
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
        self.render(force=True)


def clean_text(text: str) -> str:
    text = text.encode("utf-8", errors="replace").decode("utf-8")
    return "\n".join([" ".join(line.split()) for line in text.split("\n")])


def split_into_chunks(text: str, max_size: int = MAX_CHUNK_SIZE):
    """Режет текст на чанки <= max_size, стараясь не рвать абзацы и предложения."""
    paragraphs = text.split("\n\n")
    if len(paragraphs) == 1:
        paragraphs = [p for p in text.split("\n") if p.strip()]
    else:
        exp = []
        for p in paragraphs:
            lines = [l.strip() for l in p.split("\n") if l.strip()]
            if lines:
                exp.append("\n".join(lines))
        paragraphs = exp

    chunks, curr = [], ""
    sent_split_re = re.compile(r"(?<=[.!?…])\s+")
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(p) > max_size:
            if curr:
                chunks.append(curr.strip())
                curr = ""
            for s in sent_split_re.split(p):
                if len(s) > max_size:
                    tmp = ""
                    for w in s.split():
                        if len(tmp) + len(w) + 1 <= max_size:
                            tmp += w + " "
                        else:
                            if tmp:
                                chunks.append(tmp.strip())
                            tmp = w + " "
                    if tmp:
                        chunks.append(tmp.strip())
                else:
                    if len(curr) + len(s) + 2 <= max_size:
                        curr += s + " "
                    else:
                        if curr:
                            chunks.append(curr.strip())
                        curr = s + " "
        else:
            test = curr + "\n\n" + p if curr else p
            if len(test) <= max_size:
                curr = test
            else:
                if curr:
                    chunks.append(curr.strip())
                curr = p
    if curr:
        chunks.append(curr.strip())
    return [c for c in chunks if c.strip()]


def excerpt(text: str):
    head = text[:LOG_HEAD_TAIL].replace("\n", "\\n")
    tail = text[-LOG_HEAD_TAIL:].replace("\n", "\\n") if len(text) > LOG_HEAD_TAIL else ""
    return head, tail


# ========================= ГЛАВЫ =========================


def _looks_like_heading(line: str) -> bool:
    if not line or len(line) > CH_MAX_HEADING_LEN:
        return False
    if CH_KEYWORD_RE.match(line):
        return True
    if CH_STANDALONE_RE.match(line):
        return True
    if CH_BARE_NUMBERS and CH_BARE_NUM_RE.match(line):
        return True
    return False


def detect_chapters(text: str):
    """
    Возвращает список [{"title": str, "body": str}].

    Приоритет:
      1. Явный маркер <<<CHAPTER:Название>>> — если встретился хоть один,
         эвристика полностью отключается (доверяем разметке).
      2. Эвристика по заголовкам: строка отделена сверху пустой строкой
         и похожа на заголовок главы.
      3. Ничего не нашли -> одна глава на всю книгу.
    """
    lines = text.split("\n")

    marker_hits = []
    for i, raw in enumerate(lines):
        m = CHAPTER_MARKER_RE.match(raw)
        if m:
            title = m.group(1).strip()
            marker_hits.append((i, title, True))

    if marker_hits:
        hits = marker_hits
    elif CH_USE_HEURISTIC:
        hits = []
        for i, raw in enumerate(lines):
            line = raw.strip()
            if not line:
                continue
            prev_blank = (i == 0) or (lines[i - 1].strip() == "")
            if not prev_blank:
                continue
            if _looks_like_heading(line):
                hits.append((i, line, False))
    else:
        hits = []

    if len(hits) > CH_MAX_COUNT:
        print(f"[CH] найдено {len(hits)} заголовков (> {CH_MAX_COUNT}) — похоже на ложные срабатывания, главы отключены")
        hits = []

    if not hits:
        return [{"title": "", "body": text}]

    chapters = []

    # Текст до первого заголовка (титул, аннотация) — отдельной главой
    first_idx = hits[0][0]
    if first_idx > 0:
        head_body = "\n".join(lines[:first_idx]).strip()
        if head_body:
            chapters.append({"title": "Начало", "body": head_body})

    for n, (idx, title, is_marker) in enumerate(hits):
        end = hits[n + 1][0] if n + 1 < len(hits) else len(lines)
        if is_marker:
            # саму строку-маркер не озвучиваем
            body_lines = lines[idx + 1 : end]
        else:
            # заголовок оставляем в тексте, чтобы диктор его прочитал
            body_lines = lines[idx:end]
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        chapters.append({
            "title": title if title else f"Глава {len(chapters) + 1}",
            "body": body,
            "structural_boundary": is_marker and not title,
        })

    return chapters if chapters else [{"title": "", "body": text}]


LAT_RE = re.compile(r'[A-Za-z]')
CYR_RE = re.compile(r'[А-Яа-яЁёІіЇїЄєҐґ]')


def latin_ratio(s: str) -> float:
    lat = len(LAT_RE.findall(s))
    cyr = len(CYR_RE.findall(s))
    total = lat + cyr
    return (lat / total) if total else 0.0


def is_english_para(p: str) -> bool:
    """Абзац целиком на латинице и достаточно длинный."""
    t = p.strip()
    if len(t) < EN_MIN_CHARS:
        return False          # короткие вставки читает основной голос
    return latin_ratio(t) >= EN_MIN_RATIO


def split_by_voice(body: str, default_voice: str):
    """
    Режет тело главы на куски по языку.
    Соседние абзацы одного языка объединяются, чтобы не плодить
    лишних границ и не рвать интонацию.

    URLs всегда читаются английским голосом (VOICE_EN_MAIN),
    независимо от EN_DETECT.
    """
    paras = [p for p in re.split(r"\n\s*\n", body)]
    runs = []
    for p in paras:
        if not p.strip():
            continue
        default_for_paragraph = (
            VOICE_EN_MAIN if EN_DETECT == "on" and is_english_para(p)
            else default_voice
        )
        segments = _split_urls_from_text(p, default_for_paragraph)
        has_url = any(True for _ in _iter_urls(p))
        if not has_url:
            text, voice = segments[0]
            if runs and runs[-1][1] == voice and not runs[-1][2]:
                runs[-1][0].append(text)
            else:
                runs.append(([text], voice, False))
        else:
            # Keep URL boundaries even when the surrounding paragraph is also EN.
            runs.extend(([text], voice, True) for text, voice in segments)
    return [("\n\n".join(ps), voice) for ps, voice, _ in runs] or [(body, default_voice)]


def _trim_url_candidate(value: str) -> str:
    previous = None
    while value != previous:
        previous = value
        value = value.rstrip(".,!?;:…")
        for closing, opening in (
                (")", "("), ("]", "["), ("}", "{"),
                ("»", "«"), ("”", "“"), ("’", "‘")):
            while value.endswith(closing) and value.count(closing) > value.count(opening):
                value = value[:-1]
    return value


def _iter_urls(text: str):
    for match in URL_RE.finditer(text):
        value = _trim_url_candidate(match.group())
        if value:
            yield match.start(), match.start() + len(value), value


def _split_urls_from_text(text: str, default_voice: str):
    """Split a paragraph into (segment, voice) pairs.
    URLs get VOICE_EN_MAIN; surrounding text gets default_voice."""
    matches = list(_iter_urls(text))
    if not matches:
        return [(text, default_voice)]
    segments = []
    last = 0
    for start, end, value in matches:
        if start > last:
            segments.append((text[last:start], default_voice))
        segments.append((value, VOICE_EN_MAIN))
        last = end
    if last < len(text):
        segments.append((text[last:], default_voice))
    return segments


def _chunk_voice_segment(text: str, voice: str):
    cleaned = clean_text(text)
    urls = list(_iter_urls(cleaned))
    is_url = len(urls) == 1 and urls[0][0] == 0 and urls[0][1] == len(cleaned)
    if is_url and len(cleaned) > MAX_CHUNK_SIZE:
        return [cleaned[i:i + MAX_CHUNK_SIZE]
                for i in range(0, len(cleaned), MAX_CHUNK_SIZE)]
    return split_into_chunks(cleaned)


def build_chunk_plan(text: str, default_voice: str = ""):
    """
    Текст -> (chunks, chapter_map).
    chapter_map: [{"title": str, "first": int, "last": int}] (номера чанков, 1-based)
    Чанки никогда не пересекают границу главы.
    """
    chapters = detect_chapters(text)
    chunks = []          # список (текст, голос)
    chapter_map = []
    for ch in chapters:
        first = len(chunks) + 1
        for body, voice in split_by_voice(ch["body"], default_voice):
            for c in _chunk_voice_segment(body, voice):
                chunks.append((c, voice))
        if ch.get("structural_boundary"):
            if chapter_map:
                chapter_map[-1]["structural_boundary_after"] = True
            continue
        if len(chunks) < first:
            continue
        chapter_map.append(
            {"title": ch["title"] or f"Часть {len(chapter_map) + 1}",
             "first": first, "last": len(chunks)}
        )
    return chunks, chapter_map


def _has_structural_boundary(chapter_map) -> bool:
    return any(ch.get("structural_boundary_after") for ch in chapter_map)


# ========================= ДЛИТЕЛЬНОСТИ =========================


def probe_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return 0.0
        duration = float(r.stdout.strip())
        return duration if math.isfinite(duration) and duration > 0 else 0.0
    except (OSError, TypeError, ValueError, subprocess.SubprocessError):
        return 0.0


def is_valid_chunk(path: Path, min_size: int = 1000) -> bool:
    try:
        file_stat = path.lstat()
    except OSError:
        return False
    if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size <= min_size:
        return False
    return probe_duration(path) > 0.0


def _remove_invalid_chunk(path: Path, log_fp=None) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError as exc:
        if log_fp is not None:
            log_fp.write(
                f"[{datetime.now().isoformat()}] failed to remove invalid chunk "
                f"{path}: {type(exc).__name__}: {exc}\n"
            )
            log_fp.flush()
        return False


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def save_json(path: Path, data):
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:  # noqa: BLE001
        pass


def time_based_chapters(durations, total_chunks: int, minutes: int):
    """Нарезка по времени, когда настоящих глав нет."""
    if minutes <= 0:
        return []
    limit = minutes * 60
    result = []
    acc = 0.0
    first = 1
    for n in range(1, total_chunks + 1):
        acc += durations.get(str(n), durations.get(n, 0.0))
        if acc >= limit and n < total_chunks:
            result.append({"title": f"Фрагмент {len(result) + 1}", "first": first, "last": n})
            first = n + 1
            acc = 0.0
    if first <= total_chunks:
        result.append({"title": f"Фрагмент {len(result) + 1}", "first": first, "last": total_chunks})
    return result


def esc_ffmeta(s: str) -> str:
    return re.sub(r"([=;#\\\n])", r"\\\1", s)


def write_ffmetadata(path: Path, chapter_map, durations, total_chunks: int) -> int:
    """Пишет ffmetadata с главами. Возвращает количество глав."""
    # накопительные смещения по чанкам, мс
    offsets = {}
    acc = 0.0
    for n in range(1, total_chunks + 1):
        offsets[n] = int(round(acc * 1000))
        acc += durations.get(str(n), durations.get(n, 0.0))
    total_ms = int(round(acc * 1000))

    lines = [";FFMETADATA1"]
    written = 0
    for ch in chapter_map:
        start = offsets.get(ch["first"], 0)
        nxt = ch["last"] + 1
        end = offsets.get(nxt, total_ms) if nxt <= total_chunks else total_ms
        if end <= start:
            end = start + 1000  # защита от нулевых глав
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start}",
            f"END={end}",
            f"title={esc_ffmeta(ch['title'])}",
        ]
        written += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


# ========================= МЕТАДАННЫЕ КНИГИ =========================


def extract_tags_and_lang_from_opf(opf_path: Path):
    autor, title, lang = "Unknown", "Unknown", "rus"
    try:
        content = opf_path.read_text(encoding="utf-8", errors="ignore")
        am = re.search(r"<dc:creator.*?>(.*?)</dc:creator>", content, re.DOTALL)
        if am:
            autor = " ".join(re.sub(r"<[^>]+>", "", am.group(1)).split())
        tm = re.search(r"<dc:title.*?>(.*?)</dc:title>", content, re.DOTALL)
        if tm:
            title = " ".join(re.sub(r"<[^>]+>", "", tm.group(1)).split())
        lm = re.search(r"<dc:language.*?>(.*?)</dc:language>", content, re.DOTALL)
        if lm:
            lang = lm.group(1).strip().lower()
    except Exception:  # noqa: BLE001
        pass
    return autor, title, lang


def get_file_size(file_path: Path) -> str:
    try:
        return f"{file_path.stat().st_size / (1024*1024):.2f} Мб"
    except Exception:  # noqa: BLE001
        return "0 Мб"


def update_html_file(html_path: Path, duration: str, size: str, lp: LiveProgress) -> bool:
    try:
        c = html_path.read_text(encoding="utf-8", errors="ignore")
        c = re.sub(r"TIME", duration, c)
        c = re.sub(r"SIZE", size, c)
        html_path.write_text(c, encoding="utf-8")
        lp.println(f"[HTML] TIME={duration} SIZE={size}")
        return True
    except Exception as e:  # noqa: BLE001
        lp.println(f"[HTML-FAIL] {e}")
        return False


# ========================= СИНТЕЗ =========================


async def tts_save(text: str, voice: str, out_path: Path, timeout: int = REQUEST_TIMEOUT) -> None:
    et = require_edge_tts()
    cm = et.Communicate(text, voice)
    await asyncio.wait_for(cm.save(str(out_path)), timeout=timeout)


async def synth_chunk_with_retries(text, voice, out_path, part_num, log_fp, lp) -> bool:
    last_err = ""
    for attempt in range(1, MAX_RETRIES_PER_CHUNK + 1):
        try:
            await tts_save(text, voice, out_path, timeout=REQUEST_TIMEOUT)
        except asyncio.CancelledError:
            if not is_valid_chunk(out_path):
                _remove_invalid_chunk(out_path, log_fp)
            raise
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            if is_valid_chunk(out_path):
                log_fp.write(
                    f"[{datetime.now().isoformat()}] recovered valid chunk after "
                    f"{type(e).__name__}: {e}\n"
                )
                log_fp.flush()
                return True
        else:
            if is_valid_chunk(out_path):
                return True
            last_err = "Generated audio empty/small"

        if not _remove_invalid_chunk(out_path, log_fp):
            last_err = f"{last_err}; could not remove invalid chunk"
            break
        if attempt < MAX_RETRIES_PER_CHUNK:
            await asyncio.sleep(0.7 + attempt * 0.3)

    h, t = excerpt(text)
    log_fp.write(
        f"[{datetime.now().isoformat()}] FAIL p={part_num} "
        f"after {MAX_RETRIES_PER_CHUNK} attempts\n  err={last_err}\n  head={h}\n"
    )
    if t:
        log_fp.write(f"  tail={t}\n")
    log_fp.flush()
    lp.println(f"[FAIL] part {part_num}: {last_err} (after {MAX_RETRIES_PER_CHUNK} attempts)")
    return False


# ========================= СБОРКА =========================


def write_filelist(parts, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '%s'\n" % str(p).replace("'", "'\\''"))
    return path


def measure_mean_volume(parts, temp_dir: Path, tag: str):
    """Средняя громкость набора частей, dB. None — измерить не удалось."""
    if not parts:
        return None
    fl = write_filelist(parts, temp_dir / f"vol_{tag}.txt")
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-f", "concat", "-safe", "0",
         "-i", str(fl), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", r.stderr or "")
    return float(m.group(1)) if m else None


def apply_gain_inplace(path: Path, gain_db: float) -> bool:
    """Меняет громкость одной части. Используется для выравнивания голосов."""
    tmp = path.with_suffix(".gain.mp3")
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-af", f"volume={gain_db:.2f}dB",
         "-ar", "24000", "-ac", "1", "-b:a", "48k", str(tmp), "-y"],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(path)
    return True


def balance_voices(part_voice: dict, produced: dict, temp_dir: Path, lp):
    """
    Подтягивает громкость второстепенного голоса к основному.
    Иначе на стыке русской и английской речи слышен перепад.
    """
    voices = {}
    for num, v in part_voice.items():
        if num in produced:
            voices.setdefault(v, []).append(produced[num])
    if len(voices) < 2:
        return

    # основной голос — тот, которым озвучено больше частей
    main_voice = max(voices, key=lambda v: len(voices[v]))
    main_vol = measure_mean_volume(voices[main_voice], temp_dir, "main")
    if main_vol is None:
        lp.println("[BALANCE] не удалось измерить громкость, пропускаю")
        return

    for v, files in voices.items():
        if v == main_voice:
            continue
        vol = measure_mean_volume(files, temp_dir, "alt")
        if vol is None:
            continue
        delta = main_vol - vol
        if abs(delta) < 1.0:
            lp.println(f"[BALANCE] {v}: разница {delta:+.1f} dB — выравнивание не нужно")
            continue
        lp.println(f"[BALANCE] {v}: {delta:+.1f} dB, правлю {len(files)} частей...")
        ok = sum(1 for f in files if apply_gain_inplace(f, delta))
        lp.println(f"[BALANCE] выровнено {ok} из {len(files)}")


def measure_loudnorm(parts, temp_dir: Path, lp):
    """Первый проход loudnorm: замеряем параметры книги."""
    sample = parts
    if 0 < LOUDNORM_SAMPLE < len(parts):
        step = len(parts) / LOUDNORM_SAMPLE
        idx = sorted({int(i * step) for i in range(LOUDNORM_SAMPLE)})
        sample = [parts[i] for i in idx if i < len(parts)]
        lp.println(f"[LOUDNORM] замер по выборке: {len(sample)} из {len(parts)} частей")

    fl = write_filelist(sample, temp_dir / "ln_list.txt")
    flt = (f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
           f":print_format=json")
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-f", "concat", "-safe", "0",
         "-i", str(fl), "-af", flt, "-f", "null", "-"],
        capture_output=True, text=True,
    )
    err = r.stderr or ""
    start = err.rfind("{")
    end = err.rfind("}")
    if start == -1 or end == -1 or end < start:
        lp.println("[LOUDNORM] замер не удался, нормализация пропущена")
        return None
    try:
        data = json.loads(err[start:end + 1])
    except Exception:  # noqa: BLE001
        lp.println("[LOUDNORM] не разобрать результат замера")
        return None

    need = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if not all(k in data for k in need):
        return None
    lp.println(f"[LOUDNORM] измерено: {data['input_i']} LUFS, "
               f"пик {data['input_tp']} dBTP -> цель {LOUDNORM_I} LUFS")
    return data


def build_m4b(parts, ffmeta_path: Path, cover: Path, out_path: Path,
              autor: str, title: str, lp: LiveProgress, temp_dir: Path,
              ln_data: dict = None) -> bool:
    filelist = write_filelist(parts, temp_dir / "filelist.txt")

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
           "-f", "concat", "-safe", "0", "-i", str(filelist),
           "-i", str(ffmeta_path)]

    has_cover = cover is not None and cover.exists()
    if has_cover:
        cmd += ["-i", str(cover)]

    cmd += ["-map", "0:a", "-map_metadata", "1", "-map_chapters", "1"]
    if has_cover:
        cmd += ["-map", "2:v", "-c:v", "copy", "-disposition:v", "attached_pic"]

    # Нормализация громкости вторым проходом, с измеренными значениями
    if ln_data:
        af = (f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
              f":measured_I={ln_data['input_i']}"
              f":measured_TP={ln_data['input_tp']}"
              f":measured_LRA={ln_data['input_lra']}"
              f":measured_thresh={ln_data['input_thresh']}"
              f":offset={ln_data['target_offset']}"
              f":linear=true:print_format=summary,"
              f"aresample={M4B_SAMPLERATE}")
        cmd += ["-af", af]

    cmd += [
        "-c:a", "aac", "-b:a", M4B_BITRATE, "-ar", M4B_SAMPLERATE, "-ac", "1",
        "-metadata", f"artist={autor}",
        "-metadata", f"title={title}",
        "-metadata", f"album={autor} - {title}",
        "-metadata", f"album_artist={autor}",
        "-metadata", "genre=Audiobook",
        "-metadata", f"date={datetime.now().year}",
        "-metadata", "comment=Источник - au-books.net",
        "-movflags", "+faststart",
        "-f", "mp4", str(out_path), "-y",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        lp.println(f"[M4B-FAIL] {res.stderr.strip()[:400]}")
        return False
    return True


# ========================= ОБРАБОТКА ФАЙЛА =========================


async def process_file(directory: Path, filename: str):
    input_path = directory / filename
    output_base = input_path.stem
    temp_dir = TEMP_BASE_DIR / f"temp_{output_base}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # --- метаданные ---
    opf_path = OPF_DIR / f"{output_base}.opf"
    if not opf_path.exists():
        local_opf = input_path.parent / f"{output_base}.opf"
        if local_opf.exists():
            opf_path = local_opf

    autor, title, lang_code = "Unknown", "Unknown", "rus"
    if opf_path.exists():
        autor, title, lang_code = extract_tags_and_lang_from_opf(opf_path)

    if "ukr" in lang_code or "ua" in lang_code:
        voice = VOICE_UA_ALT if VOICE_CHOICE == "2" else VOICE_UA_MAIN
        lang_label = "UA"
    else:
        voice = VOICE_RU_ALT if VOICE_CHOICE == "2" else VOICE_RU_MAIN
        lang_label = "RU"

    print(f"\n[{lang_label}] Язык: {lang_code} -> Голос {VOICE_CHOICE}: {voice}")

    # --- план чанков и глав ---
    text = input_path.read_text(encoding="utf-8", errors="ignore")
    text_sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    chunks, chapter_map = build_chunk_plan(text, voice)

    if not chunks:
        print("⚠ пустой")
        return

    total = len(chunks)

    # --- проверка резюма: не подменили ли TXT ---
    manifest_path = temp_dir / "manifest.json"
    durations_path = temp_dir / "durations.json"
    # В подпись плана входят и голоса: если сменили голос или включили
    # английский, старые части больше не подходят.
    plan_sig = hashlib.sha256(
        (text_sha + "|" + "|".join(v for _, v in chunks)).encode("utf-8")
    ).hexdigest()

    manifest = load_json(manifest_path, {})
    if manifest and manifest.get("plan_sig", manifest.get("text_sha")) != plan_sig:
        print("[RESUME] текст или голоса изменились — старые части невалидны, начинаю заново")
        for old in temp_dir.glob("part_*.mp3"):
            old.unlink(missing_ok=True)
        durations_path.unlink(missing_ok=True)
        manifest = {}

    voices_used = sorted(set(v for _, v in chunks))
    save_json(manifest_path, {
        "text_sha": text_sha,
        "plan_sig": plan_sig,
        "total_chunks": total,
        "chapters": chapter_map,
        "voices": voices_used,
        "updated": datetime.now().isoformat(),
    })

    if len(voices_used) > 1:
        n_en = sum(1 for _, v in chunks if v == VOICE_EN_MAIN)
        print(f"[VOICE] английским голосом: {n_en} из {total} частей ({VOICE_EN_MAIN})")

    durations = load_json(durations_path, {})

    # --- уже готовые части ---
    existing_parts = {}
    for p in sorted(temp_dir.glob("part_*.mp3")):
        m = re.match(r"part_(\d{4})\.mp3$", p.name)
        if m:
            num = int(m.group(1))
            if 1 <= num <= total and is_valid_chunk(p):
                existing_parts[num] = p
            else:
                _remove_invalid_chunk(p)
                durations.pop(str(num), None)

    lp = LiveProgress(total=total)
    ready_nums = sorted(existing_parts.keys())
    if ready_nums:
        lp.done = len(ready_nums)
        lp.println(f"[RESUME] найдено готовых частей: {len(ready_nums)}/{total}")
    else:
        lp.println(f"[FILE] {filename} ({lang_label}) chunks={total} chapters={len(chapter_map)}")

    log_path = FINAL_DIR / f"{output_base}.tts.log"
    log_fp = open(log_path, "a", encoding="utf-8")
    if log_fp.tell() == 0:
        log_fp.write(f"START {filename} lang={lang_code} chapters={len(chapter_map)}\n")
    log_fp.write(f"RESUME: ready parts: {len(ready_nums)}\n")
    log_fp.flush()

    statuses = {}
    produced_parts = {}
    any_chunk_failed = False
    file_failed_consec = False

    for n in ready_nums:
        statuses[n] = True
        produced_parts[n] = existing_parts[n]

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def bounded(part_num: int, part_text: str, part_voice: str):
        nonlocal any_chunk_failed
        async with semaphore:
            if part_num in statuses:
                return part_num
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS * ((part_num - 1) % CONCURRENCY))
            out_path = temp_dir / f"part_{part_num:04d}.mp3"
            lp.set_current(part_num, "synth")
            lp.render()

            ok = await synth_chunk_with_retries(part_text, part_voice, out_path,
                                                part_num, log_fp, lp)

            if ok:
                lp.inc_done()
                lp.set_current(part_num, "done")
                lp.render(force=True)
                statuses[part_num] = True
                produced_parts[part_num] = out_path
                durations[str(part_num)] = probe_duration(out_path)
            else:
                any_chunk_failed = True
                lp.inc_failed()
                lp.set_current(part_num, "failed")
                lp.render(force=True)
                statuses[part_num] = False
            return part_num

    for start in range(0, total, TASK_WINDOW):
        if file_failed_consec:
            break
        end = min(start + TASK_WINDOW, total)
        tasks = [bounded(i + 1, chunks[i][0], chunks[i][1])
                 for i in range(start, end) if (i + 1) not in statuses]
        if tasks:
            await asyncio.gather(*tasks)
        save_json(durations_path, durations)

        consec = 0
        for idx in range(1, total + 1):
            if idx not in statuses:
                break
            if statuses[idx]:
                consec = 0
            else:
                consec += 1
                if consec >= MAX_CONSECUTIVE_FAILURES:
                    file_failed_consec = True
                    lp.println(f"[SKIP FILE] {MAX_CONSECUTIVE_FAILURES} подряд неудачных чанков на {idx}")
                    log_fp.write(
                        f"[{datetime.now().isoformat()}] SKIPPED FILE: "
                        f"{MAX_CONSECUTIVE_FAILURES} consecutive failures at chunk {idx}\n"
                    )
                    log_fp.flush()
                    break

    sys.stdout.write("\n")
    sys.stdout.flush()
    save_json(durations_path, durations)

    if file_failed_consec:
        lp.println("[SKIP] Файл пропущен, TXT остаётся")
        log_fp.close()
        return

    if any_chunk_failed:
        lp.println("[SKIP] Файл неполный: часть чанков не озвучена, TXT остаётся")
        log_fp.write(f"[{datetime.now().isoformat()}] SKIPPED FILE: incomplete\n")
        log_fp.close()
        return

    # --- все чанки готовы ---
    ordered_parts = [produced_parts[i] for i in sorted(produced_parts.keys())]

    # добираем длительности для частей, оставшихся с прошлых запусков
    missing = [n for n in sorted(produced_parts) if str(n) not in durations]
    if missing:
        lp.println(f"[PROBE] замер длительности для {len(missing)} частей...")
        for n in missing:
            durations[str(n)] = probe_duration(produced_parts[n])
        save_json(durations_path, durations)

    # если глав нет — режем по времени
    effective_chapters = chapter_map
    if not _has_structural_boundary(chapter_map) \
            and len(chapter_map) <= 1 and FALLBACK_MINUTES > 0:
        tb = time_based_chapters(durations, total, FALLBACK_MINUTES)
        if len(tb) > 1:
            effective_chapters = tb
            lp.println(f"[CH] глав не найдено — нарезка по {FALLBACK_MINUTES} мин: {len(tb)} фрагментов")

    # --- выравнивание голосов до замера общей громкости ---
    if VOICE_BALANCE == "on":
        part_voice = {i + 1: chunks[i][1] for i in range(total)}
        balance_voices(part_voice, produced_parts, temp_dir, lp)

    ffmeta_path = temp_dir / "ffmeta.txt"
    n_ch = write_ffmetadata(ffmeta_path, effective_chapters, durations, total)
    total_sec = sum(durations.get(str(n), 0.0) for n in range(1, total + 1))
    lp.println(f"[CH] глав в файле: {n_ch}, общая длительность {fmt_hms(total_sec)}")

    jpg_path = JPG_DIR / f"{output_base}.jpg"
    if not jpg_path.exists():
        local_jpg = input_path.parent / f"{output_base}.jpg"
        if local_jpg.exists():
            jpg_path = local_jpg
    cover = jpg_path if jpg_path.exists() else None
    if not cover:
        lp.println("[COVER] обложка не найдена")

    ln_data = None
    if LOUDNORM == "on":
        lp.println("[LOUDNORM] замеряю громкость книги...")
        t0 = time.time()
        ln_data = measure_loudnorm(ordered_parts, temp_dir, lp)
        lp.println(f"[LOUDNORM] замер занял {fmt_hms(time.time() - t0)}")

    tmp_m4b = temp_dir / f"{output_base}.m4b"
    lp.println(f"[M4B] сборка из {len(ordered_parts)} частей...")
    if not build_m4b(ordered_parts, ffmeta_path, cover, tmp_m4b, autor, title,
                     lp, temp_dir, ln_data):
        lp.println("[FAIL] сборка не удалась, temp сохранён для повтора")
        log_fp.close()
        return

    final_path = FINAL_DIR / f"{output_base}.m4b"
    shutil.move(str(tmp_m4b), str(final_path))
    lp.println(f"[OK] m4b -> {final_path.name} ({get_file_size(final_path)})")

    # HTML-заглушки TIME/SIZE (если ещё используются)
    html_path = HTML_DIR / f"{output_base}.html"
    if html_path.exists():
        update_html_file(html_path, fmt_hms(total_sec), get_file_size(final_path), lp)

    if cover:
        try:
            cover.unlink()
            lp.println("[COVER] removed")
        except Exception:  # noqa: BLE001
            pass
    if opf_path.exists():
        try:
            opf_path.unlink()
            lp.println("[OPF] removed")
        except Exception:  # noqa: BLE001
            pass

    input_path.unlink(missing_ok=True)
    lp.println("[OK] txt deleted")
    log_fp.close()
    log_path.unlink(missing_ok=True)
    shutil.rmtree(temp_dir, ignore_errors=True)


# ========================= PREVIEW =========================


def preview(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks, chapter_map = build_chunk_plan(text, VOICE_RU_MAIN)
    total_chars = sum(len(c) for c, _ in chunks)

    print(f"\nФайл: {path.name}")
    print(f"Символов: {total_chars}   Чанков: {len(chunks)}   Глав: {len(chapter_map)}")
    print(f"Оценка длительности: ~{fmt_hms(total_chars / PREVIEW_CPS)} (при {PREVIEW_CPS} симв/сек)")
    print("-" * 70)
    for i, ch in enumerate(chapter_map, 1):
        n_chunks = ch["last"] - ch["first"] + 1
        chars = sum(len(chunks[j - 1][0]) for j in range(ch["first"], ch["last"] + 1))
        print(f"{i:3d}. {ch['title'][:52]:<52} чанки {ch['first']}-{ch['last']} "
              f"(~{fmt_hms(chars / PREVIEW_CPS)})")
    if len(chapter_map) <= 1:
        print(f"\n⚠ Главы не распознаны. При озвучке сработает нарезка "
              f"по {FALLBACK_MINUTES} мин (FALLBACK_MINUTES).")

    # --- разбивка по голосам ---
    if EN_DETECT == "on":
        en = [(i + 1, c) for i, (c, v) in enumerate(chunks) if v == VOICE_EN_MAIN]
        print(f"\nАнглийский голос ({VOICE_EN_MAIN}): {len(en)} из {len(chunks)} частей")
        for num, c in en[:8]:
            snippet = " ".join(c.split())[:70]
            print(f"  часть {num}: {snippet}...")
        if len(en) > 8:
            print(f"  ... и ещё {len(en) - 8}")
        if not en:
            print("  (английских абзацев не найдено)")
    else:
        n_lat = sum(1 for p in re.split(r"\n\s*\n", text) if is_english_para(p))
        if n_lat:
            print(f"\nНайдено {n_lat} абзацев на латинице. "
                  f"Включить отдельный голос: EN_DETECT=on")
    print()


# ========================= MAIN =========================


async def run_directory(directory: Path):
    txt_files = sorted(f.name for f in directory.iterdir() if f.is_file() and f.name.endswith(".txt"))
    if not txt_files:
        return
    for f in txt_files:
        print("\n" + "=" * 60 + f"\nSTART FILE: {f}\n" + "=" * 60)
        try:
            await process_file(directory, f)
        except Exception as e:  # noqa: BLE001
            print(f"❌ CRITICAL ERROR {f}: {e}")
            traceback.print_exc()


def main():
    ap = argparse.ArgumentParser(description="Озвучка TXT в M4B с главами")
    ap.add_argument("--preview", metavar="FILE", help="показать найденные главы, не озвучивая")
    ap.add_argument("--folder", metavar="DIR", help="папка с TXT (иначе берётся CURRENT_FOLDER)")
    args = ap.parse_args()

    if args.preview:
        preview(Path(args.preview))
        return

    folder = args.folder or os.environ.get("CURRENT_FOLDER", "")
    if not folder:
        print("ОШИБКА: не указана папка (--folder или CURRENT_FOLDER)")
        sys.exit(1)

    for d in (FINAL_DIR, TEMP_BASE_DIR):
        d.mkdir(parents=True, exist_ok=True)

    asyncio.run(run_directory(Path(folder)))


if __name__ == "__main__":
    main()
