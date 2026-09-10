# Исправление публикации на OpenDrive (WebDAV)

## Цель
Исправить ошибку, из-за которой шаг `publish` в TTS-конвейере падал с HTTP 404 при попытке получить ссылки на файл на OpenDrive.

## Что было изучено
1. Анализ двух тестовых заданий (jobs) показал:
   - Job 1 (175916): PUBLISH=1 отсутствовал — тест был запущен без флага `publish` (не баг).
   - Job 2 (180145): PUBLISH=1 присутствовал, но `aubook-publish-opendrive.py` получал 404 от API OpenDrive.
2. `rclone ls` показал, что rclone создал **директорию** вместо файла: `Тест Автор - Тестовая книга...m4b/test_avtor_..._ozvuchki.m4b`. WebDAV-бэкенд rclone интерпретировал последний компонент пути как директорию.
3. Причина: `rclone copy` с WebDAV-бэкендом создаёт коллекцию (директорию) при загрузке файла по несуществующему пути.

## Какие файлы изменены
- `~/bin/aubook-remote.sh` — шаг publish
- `~/aubooks/audio_index_ops.py` — новые команды

## Что именно изменено

### aubook-remote.sh
1. **`rclone mkdir` перед `rclone copyto`** — предсоздание родительской директории на WebDAV.
2. **`rclone copy` → `rclone copyto --no-traverse`** — `copyto` явно указывает, что назначение — файл, а не директория. Флаг `--no-traverse` предотвращает обход дерева назначения.
3. **Два имени файла**: `audio_filename` (кириллическое, для отображения пользователям) и `od_filename` (ASCII-slug, для WebDAV-пути).

### audio_index_ops.py
1. **`make-opendrive-filename`** — новая функция, генерирующая ASCII-slug из кириллического автора/заголовка. Транслитерация: `Тест Автор` → `test-avtor`.
2. **`reset-for-retry`** — новая CLI-команда для сброса статуса `failed` → `queued`.

## Тесты
- Полный E2E-тест: `aubook-remote.sh start-book-id 999999 1 publish`
- TTS (edge-tts, ru-RU-SvetlanaNeural): 3 главы, 548 символов, M4B 184793 байт, 39 сек
- Загрузка на OpenDrive: файл создан как файл (не директория)
- Получение ссылок: LINK_DOWNLOAD и LINK_STREAM получены успешно
- audio.db: статус `ready`, все поля заполнены
- Тестовые артефакты удалены

## Известные ограничения
- Имя файла на OpenDrive теперь ASCII-slug (`test-avtor-testovaya-kniga-dlya-publikatsii.m4b`), а не кириллическое. Это компромисс для надёжности WebDAV-загрузки.
- Флаг `--no-traverse` может замедлить загрузку очень больших файлов, но для аудиокниг это неактуально.

## Commit hash
Локальные изменения, коммит не создан.
