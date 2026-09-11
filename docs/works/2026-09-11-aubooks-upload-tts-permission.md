# Отдельное право загрузки книг для озвучивания
## Цель
Добавить в AU-Books отдельное право на будущую загрузку пользовательских книг для TTS без реализации upload endpoint, storage или изменений audio pipeline.
## Что было изучено
- Bitmask ролей `User.role`, `ALL_ROLES` и `ADMIN_USER_ROLES`.
- Создание и редактирование пользователей, настройки default roles и bulk edit.
- AU-Books permission helpers и наследование admin templates между темами.
- Существующий общий Calibre-Web upload flow.
## Новый permission bit
Добавлен `ROLE_AUBOOKS_UPLOAD_TTS = 1 << 10`, числовое значение `1024`. Bits `0-9` уже заняты; конфликтов нет. Новый bit исключён из `ADMIN_USER_ROLES`, поэтому bootstrap-маска администратора остаётся `991`, а право администратора обеспечивается явным override в policy helper.
## Permission helpers
- `UserBase.role_aubooks_upload_tts()` проверяет только bit `1024` и не содержит theme logic.
- `can_upload_for_tts(user)` разрешает capability только аутентифицированному пользователю при активной теме AU-Books и наличии admin role либо нового bit.
- Для standard theme capability не предоставляется и нигде не используется.
## Почему не ROLE_UPLOAD
`ROLE_UPLOAD` открывает общий Calibre-Web upload flow, который добавляет книги в совместно используемую библиотеку и не поддерживает private ownership. Новое право отделяет будущий ограниченный TTS upload от общей загрузки и редактирования библиотеки.
## Admin UI
- Checkbox «Загрузка книг для озвучивания» добавлен в создание и редактирование пользователя.
- Existing `ROLE_GENERATE_TTS` также выведен в форме, чтобы edit не снимал ранее сохранённый bit.
- Оба права добавлены в default-role и bulk-edit UI.
- Bulk edit теперь принимает только явно зарегистрированные значения `ALL_ROLES`, а не устаревший диапазон до `ROLE_VIEWER`.
## Сохранение hidden bits
`selected_roles()` сохраняет bits, неизвестные текущему `ALL_ROLES`, при редактировании пользователя и default roles. Известные checkbox bits по-прежнему устанавливаются и снимаются согласно форме. Это предотвращает потерю newer/fork-specific permissions при полном сохранении формы.
## Тесты
- Focused tests покрывают anonymous, role `0`, uploader bit, admin override без bit, non-AU theme и User helper.
- Проверены checkbox ON/OFF, сохранение неизвестного bit, сохранение `ROLE_GENERATE_TTS`, admin edit, неизменность `ADMIN_USER_ROLES`, individual/default/bulk UI и bulk validation.
- `.venv/bin/python -m pytest tests/test_aubooks_upload_permission.py tests/test_aubooks_user_permissions.py tests/test_aubooks_audio.py tests/test_aubooks_generate_audio.py` — 154 passed.
- Полный `.venv/bin/python -m pytest` — 441 passed, 8 unrelated failures в `tests/test_cmd_start_book_id.py`: тест использует текущий внешний `/home/feninf/bin/aubook.sh` по старому контракту без обязательного `owner` и извлекает неполный shell fragment. Файлы этого runtime и теста в задаче не изменялись.
- Python compile и `git diff --check` — без ошибок.
- После перезапуска только `calibre-web-dev.service` DEV вернул HTTP 200. Authenticated GET страниц create/edit/default/bulk подтвердил оба checkbox; новый checkbox у пользователя с `role=0` не отмечен.
- Роли реальных пользователей, session counters и SHA-256 app DB до и после live GET совпали.
## Ограничения
- Upload functionality не реализована.
- Upload route и storage не добавлялись.
- DB schema, `User` table, реальные users и audio pipeline не изменялись.
- Возможность назначить permission через UI не запускает загрузку, пока отдельный endpoint не будет реализован будущей задачей.
- Вне scope остаётся обновление устаревшего integration test `tests/test_cmd_start_book_id.py` под уже изменённый внешний runtime.
## Git
Изменения подготовлены отдельным commit `feat: add audiobook upload permission`. Push и deploy не выполнялись.
