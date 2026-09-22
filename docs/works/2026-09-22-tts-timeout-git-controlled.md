# Git-controlled TTS processor и recovery после TimeoutError
## Цель задачи
Сделать production-скрипт `/home/feninf/bin/tts_processor.py` производным от Git-источника и исключить ложный failure чанка, если `TimeoutError` произошёл после создания валидного MP3.
## Что было изучено
- Runtime-файл не был tracked в `aubooks`; его текущая версия скопирована как `scripts/tts_processor.py`.
- В `synth_chunk_with_retries()` уже используется `is_valid_chunk()`: валидный MP3 возвращается как успешный, invalid partial удаляется перед retry.
- При resume existing `part_*.mp3` проверяются тем же `is_valid_chunk()`; invalid части удаляются и синтезируются заново.
- Существующий deploy bundle принимает фиксированный набор файлов; mapping расширен на `scripts/tts_processor.py` и установку в `/home/feninf/bin/tts_processor.py`.
## Изменённые файлы
- `scripts/tts_processor.py`
- `tests/test_tts_processor_timeout.py`
- `tests/test_calibre_web_deploy_helper.py`
- `deploy/vps2/aubooks-deploy-dispatcher.sh`
- `deploy/vps2/deploy-calibre-web-release.sh`
- `.github/workflows/ci-aubooks.yml`
- `.github/workflows/deploy-production.yml`
## Что именно изменено
- Production TTS-скрипт добавлен в Git как executable source; содержание синхронизировано с runtime-версией.
- Добавлены пять targeted regression tests: valid MP3 после `TimeoutError`, timeout без файла, invalid partial retry, valid existing part resume и invalid existing part resynth.
- CI artifact, deploy artifact contract, SSH upload и deploy helper теперь передают и checksum-проверяют `tts_processor.py`.
- Deploy helper атомарно устанавливает script в `/home/feninf/bin/tts_processor.py` из bundle.
## Тесты
- `python -m compileall -q scripts/tts_processor.py tests/test_tts_processor_timeout.py`: успешно.
- `python -m pytest -q tests/test_tts_processor_timeout.py`: `5 passed`.
- Exact CI hermetic list: `244 passed, 7 subtests passed`.
- `tests/test_calibre_web_deploy_helper.py`: `93 passed`.
- `bash -n` для изменённых deploy scripts и `git diff --check`: без ошибок.
## Известные ограничения
- `tests/test_tts_dispatcher.py` имеет два независимых baseline failure (`test_no_shell_true`, `test_subprocess_timeout`); этот state machine не исследовался и не изменялся.
## Commit hash
`f3936d16` (TTS code commit; документация добавлена отдельным task commit).
