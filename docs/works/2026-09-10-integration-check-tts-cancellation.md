# Интеграционная проверка TTS cancellation (до изменения продукта)
## Статус
Проверка выполнялась, пока web-отмена была включена. Последующим продуктовым решением пользовательская отмена из Calibre-Web удалена, оставлена только runtime/admin-отмена — см. `docs/works/2026-09-10-keep-audiobook-cancellation-admin-only.md`.
## Цель
Верифицировать всю цепочку отмены озвучивания end-to-end (web → dispatcher → runtime) и политики владения/завершения переходов. Только audit/test, без изменений кода.
## Что было изучено
- `cps/web.py` `cancel_audio_job`, `cps/aubooks_tts.py` `queue_book`/`cancel_job`, `cps/tasks_status.py` can_cancel/JSON.
- `/home/feninf/bin/tts-dispatcher.py` `/queue` (требует `requested_by_user_id>0`) и `/cancel/<job_id>` (safe path, exact-job).
- `/home/feninf/bin/aubook-remote.sh` `cancel-job` (cmd_cancel): CAS через audio_index `mark-cancelled`, файн identity-снапшот (PID+PGID+SID+start+boot_id+argv маркер), `kill -TERM/-KILL -- "-$pgid"`, только для собственных `setsid`-групп, `--all` запрещён.
- `/home/feninf/aubooks/audio_index.py`: CAS-переходы, `queue_job` ON CONFLICT...WHERE status IN ('failed','cancelled'), owner column CHECK (>0 или NULL legacy).
- Старые пути: `admin.py /ajax/canceltask` — WorkerThread (upload/convert), аудио не трогает.
## Ход работы
- Аудит цепочки callers: единственный `queue_book` caller `web.py:1912` (owner=current_user.id); единственный `/queue` client — `aubooks_tts.dispatch_book`; единственный cancel caller — `web.cancel_audio_job`/`tasks_status.cancel_url`.
- Запущены сьюты (все на temp DB/fixtures, реальный runtime не затрагивался):
  - aubooks: `test_audio_index` 27 OK, `test_audio_index_cancellation` 21 OK, `test_audio_index_pipeline` 39 OK.
  - bin: `test_tts_cancellation` 15 OK (включая dispatcher cancel mapping + runtime cancel на синтетических temp-заданиях).
  - calibre-web (требуемые): tts_cancellation, tts_transport, audio, generate_audio, user_permissions, opendrive_download: 217 passed + 13 subtests.
- py_compile: cps, aubooks, bin — OK. `git diff --check` — чисто.
- Дополнительно прогнан `tests/test_tts_dispatcher.py` (копия dispatcher-сьюта): 11 OK / 10 FAIL — устаревшая копия, payload `{book_id}` без `requested_by_user_id` (dispatcher корректно требует owner с Stage 2A). Runtime-бага нет; актуальный контракт покрыт bin-сьютом.
## Изменения
Кода и системы не изменялось. Создан только журнал `docs/works/2026-09-10-integration-check-tts-cancellation.md` (не коммитится).
## Проверки
- Ownership: A cancel=да, B=нет(403), admin=да, legacy NULL=admin-only, stale job_id=404, requeue→новый owner.
- Терминальность: cancelled не → ready (mark_ready требует processing); ready не → cancelled.
- Process isolation: start_new_session/setsid; PID reuse защита identity-снапшотом; neighbor safety — только "-PGID" своей группы.
- Guest → login redirect; hidden book → 404 до lookup; error leakage — generic message.
## Git
Ветка `aubooks`, коммиты `3b11cb5c`, `b6e4e1ef`. Commit/push не выполнялись. Рабочее дерево: только untracked `audit_ui_final.py`.
## Риски и ограничения
- Устаревший `tests/test_tts_dispatcher.py` (копия pre-owner) — 10 тестов требуют обновления payload (`requested_by_user_id`) или удаления в пользу bin-сьюта. Рекомендация для отдельной задачи.
- Browser smoke не выполнялся (безопасных активных jobs в реальной базе нет; dev разделяет реальный dispatcher).
## Итог
Задача выполнена: цепочка P1 (A→generate→queued→processing→cancel→cancelled→Отменено→Озвучить) и P2 (B requeue, новый owner, stale/чужой cancel отклонены) подтверждены. Вердикт READY с замечанием про устаревший тест.