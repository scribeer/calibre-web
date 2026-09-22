# Git-controlled TTS processor и recovery после TimeoutError
## Цель задачи
Сделать production-скрипт `/home/feninf/bin/tts_processor.py` производным от Git-источника и исключить ложный failure чанка, если `TimeoutError` произошёл после создания валидного MP3.
## Что было изучено
- Runtime-файл не был tracked в `aubooks`; его текущая версия скопирована как `scripts/tts_processor.py`.
- В `synth_chunk_with_retries()` уже используется `is_valid_chunk()`: валидный MP3 возвращается как успешный, invalid partial удаляется перед retry.
- При resume existing `part_*.mp3` проверяются тем же `is_valid_chunk()`; invalid части удаляются и синтезируются заново.
- Deploy bundle сохраняет production-контракт из шести файлов; `scripts/tts_processor.py` включается в проверяемый manifest и устанавливается в `/home/feninf/bin/tts_processor.py`.
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
- CI artifact включает source и SHA-256 `tts_processor.py` в manifest; deploy повторно проверяет payload и checksum.
- Deploy helper атомарно устанавливает проверенный source в `/home/feninf/bin/tts_processor.py`, не добавляя седьмой файл в SSH bundle.
## Тесты
- `python -m compileall -q scripts/tts_processor.py tests/test_tts_processor_timeout.py tests/test_calibre_web_deploy_helper.py`: успешно.
- `python -m pytest -q tests/test_tts_processor_timeout.py tests/test_calibre_web_deploy_helper.py`: `98 passed`.
- Два targeted dispatcher contract tests: `2 passed`.
- `bash -n` для изменённых deploy scripts: без ошибок.
## Известные ограничения
- `tests/test_tts_dispatcher.py` имеет два независимых baseline failure (`test_no_shell_true`, `test_subprocess_timeout`); этот state machine не исследовался и не изменялся.
## Commit hash
Начальные task commits: `f3936d16`, `ab22a54f`; итоговый deployed SHA записывается штатным deploy manifest.
