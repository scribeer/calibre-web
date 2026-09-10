# Права пользователей на скачивание и TTS
## Цель
Привести AU-Books к модели, в которой каталог доступен гостям, действия скачивания и озвучивания ведут гостя на вход, а любой зарегистрированный пользователь может скачать ebook, запустить TTS и скачать готовую аудиокнигу без отдельных role bits.
## Что было изучено
Проверены `UserBase.role_download()` и `UserBase.role_tts()`, default roles регистрации, `download_required`, ebook/audio download routes, TTS generate/status routes, фильтрация скрытых книг, TTS tasks API, AU detail/login templates, Flask-Login `next` и локальный redirect helper. Отдельно проверены ограничения из commit `0da869f1` на status/jobs endpoints и отсутствие утечки внутренних ошибок.
## Старая модель
- Ebook download требовал `ROLE_DOWNLOAD`; guest без роли получал 403, normal user без роли также не мог скачать книгу.
- TTS generate требовал authentication и `ROLE_GENERATE_TTS`; normal user без отдельной роли получал 403.
- Audio download использовал только `login_required_if_no_ano`, поэтому при разрешённом anonymous browsing guest мог обратиться к route напрямую. Canonical visibility filter на этом route отсутствовал.
- AU detail скрывал ebook/TTS controls от guest и пользователей без соответствующих ролей.
- Status API не выдавал generate URL гостю, но download URL зависел от download role и мог учитывать роль Guest.
- Login сохранял `next`, но helper не выполнял явную same-origin проверку и мог принять POST-only target, приводящий после входа к GET 405.
## Новая модель
Добавлен небольшой AU-specific policy layer `cps/aubooks_permissions.py`. При активной теме AU-Books `can_download()` и `can_generate_tts()` разрешают действие любому authenticated user. Для других тем сохраняются существующие `role_download()` и `role_tts()`. Глобальные role constants, admin logic и роли других функций не менялись. Отдельное право загрузки собственной книги не реализовывалось; изолированный policy layer позволяет позже добавить его независимо от download/TTS.
## Guest behavior
- Каталог и canonical detail pages остаются публичными.
- На detail видна обычная кнопка «Скачать книгу». Для `not_available` видна «Озвучить», для `failed` — «Озвучить повторно», для `ready` — «Скачать аудиокнигу»; queued/processing сохраняют disabled status controls.
- Guest buttons ведут на login с canonical book page в `next`, а не вызывают download или TTS endpoint.
- Direct ebook и audio download requests перенаправляются на login. Guest POST generate блокируется authentication/CSRF и не доходит до dispatcher.
- Polling status API возвращает guest только status и null action URLs. Если статус меняется во время polling, JS восстанавливает соответствующую login-ссылку из безопасного `data-login-url`.
## Authenticated behavior
- Normal authenticated user скачивает ebook без `ROLE_DOWNLOAD`.
- Normal authenticated user запускает TTS без `ROLE_GENERATE_TTS`.
- Normal authenticated user скачивает ready M4B без `ROLE_DOWNLOAD`.
- Status и tasks APIs возвращают разрешённые generate/download URLs согласно состоянию.
- При standard theme прежние download/TTS role checks сохраняются.
## Server-side guards
- Ebook route использует отдельный `aubooks_download_required`, не меняющий общий `download_required` для send-to-eReader, Kobo и standard theme.
- Audio download использует `user_login_required`, AU download policy и `calibre_db.get_filtered_book(..., allow_show_archived=True)` до чтения `audio.db` и запуска rclone.
- Generate route сохраняет `user_login_required`, POST-only, canonical filtered-book lookup и проверки queued/processing/ready, но AU policy больше не требует TTS role.
- Status endpoint сохраняет canonical filtered-book lookup и не возвращает action URLs guest.
- Audio download повторно выбрасывает HTTP errors без преобразования 404 в 500; неожиданные exceptions логируются server-side, а пользователю показывается generic message без внутренних путей.
- Redirect helper принимает только same-origin targets существующих GET routes. External, protocol-relative, неизвестные и POST-only targets заменяются безопасным fallback.
## Login page
В `cps/themes/aubooks/templates/login.html` существующая условная ссылка «Нет аккаунта? Зарегистрироваться» сделана заметнее через `strong`. Она рендерится только при `config_public_reg`. Standard login template не изменялся.
## Проверки
Выполнены:
```bash
python3 -m unittest tests.test_aubooks_user_permissions tests.test_aubooks_audio -v
python3 -m unittest tests.test_aubooks_generate_audio.TestAuthAndPermissions tests.test_aubooks_generate_audio.TestRouteSignature tests.test_aubooks_generate_audio.TestTemplateFormStructure.test_authentication_gates_not_available_button -v
python3 -m py_compile cps/aubooks_permissions.py cps/redirect.py cps/web.py cps/tasks_status.py tests/test_aubooks_user_permissions.py tests/test_aubooks_audio.py tests/test_aubooks_generate_audio.py
git diff --check
```
Результат: 82/82 permission/audio/status/tasks tests passed; 7/7 релевантных generate tests passed; compile и whitespace checks passed. Покрыты guest redirects, отсутствие вызова download/queue до auth, normal user без role bits, hidden audio book 404 до `audio.db`, null guest status URLs, sanitized audio errors, safe/external/protocol-relative/POST-only `next`, registration enabled/disabled, guest polling transitions и сохранение standard-theme roles.
Общий `python3 -m unittest discover -s tests -v` дошёл до известного `test_aubooks_tts_transport.test_timeout` и был прекращён общим timeout 120 секунд. До timeout новые проверки проходили; остались 12 ранее известных stale assertions: пять ищут старую template-разметку состояний, семь ожидают заменённый HTTP dispatcher старый subprocess transport. TTS pipeline для их устранения не менялся.
## Browser verify
После restart только `calibre-web-dev.service` на `127.0.0.1:8084` выполнена guest-проверка GET/redirect flows. Book 10 отображает «Скачать книгу» и «Скачать аудиокнигу», поскольку его текущий audio status `ready`; book 1 со status `not_available` отображает «Скачать книгу» и «Озвучить». Ссылки ведут на login с canonical book URL. Direct ebook/audio requests возвращают 302 на login. Guest status для book 10 возвращает `download_url: null` и `generate_url: null`. Login показывает ссылку регистрации, сохраняет внутренний `/book/10`, а внешний target заменяет на `/`. Guest POST generate без cookies вернул 400 на CSRF до route logic и не создал job.
Browser login обычного пользователя не выполнялся: выделенные test credentials отсутствуют, а создавать пользователя или менять DEV DB ради проверки не стали. Authenticated ebook/TTS/audio paths проверены production-function tests с `role_download=False` и `role_tts=False`; реальный TTS POST и длинная генерация не запускались.
## Изменённые файлы
- `cps/aubooks_permissions.py`
- `cps/redirect.py`
- `cps/tasks_status.py`
- `cps/web.py`
- `cps/themes/aubooks/templates/detail.html`
- `cps/themes/aubooks/templates/login.html`
- `tests/test_aubooks_user_permissions.py`
- `tests/test_aubooks_audio.py`
- `tests/test_aubooks_generate_audio.py`
- `docs/works/2026-09-10-user-download-tts-permissions.md`
## Риски и ограничения
Role bits сохранены для compatibility и standard theme, поэтому новая registered-user policy действует только при активной теме AU-Books. Book 10 уже имеет ready audio, поэтому на нём корректно показывается download audiobook вместо generate action; guest generate UX дополнительно проверен на book 1. Полная authenticated browser-сессия не проверена по указанной выше причине. Существующие unrelated modified/untracked files не изменялись и не должны войти в commit.
## Git
Работа выполнена в `/home/feninf/calibre-web`, branch `aubooks`. Commit должен быть создан после финальной проверки с сообщением `fix: align audiobook permissions with registered users`. Push не выполнялся.
## Итог
AU-Books использует целевую registered-user модель для ebook download, TTS generate и ready audio download. Guest видит действия, но не может обойти authentication через прямые routes или polling. Canonical book filters и редактирование внутренних ошибок сохранены, standard theme и независимые роли не ослаблены.
