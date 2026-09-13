# Phase 2B Contract Reconciliation — Deploy Security Model

## Цель
Перевести production CD transport на forced-command protocol: dispatcher, stdin upload, root wrapper. Устранить произвольный SSH shell, SCP и прямой sudo.

## Что изучено
- `.github/workflows/deploy-production.yml` — workflow SSH/SCP invocation
- `deploy/vps2/deploy-calibre-web-release.sh` — root release helper (462 строки)
- `tests/test_calibre_web_deploy_helper.py` — 29 hermetic tests
- `docs/works/2026-09-13-calibre-web-production-cd.md` — Phase 2A contract

## Выводы

### 1. Прежняя модель (признана недостаточной)

Workflow использовал:
1. `ssh ... install -d -m 0700 /var/tmp/...` — произвольная SSH команда
2. `scp ... $BUNDLE_DIR/* target:$remote_stage/` — SCP
3. `ssh ... sudo /usr/local/sbin/...` — прямой sudo

**Проблемы**:
- `no-pty` НЕ запрещает non-interactive SSH commands
- Deploy user с `/bin/bash` и без forced command может выполнять произвольные SSH команды
- SCP несовместим с forced command моделью
- Sudoers wildcard/regex для dynamic SHA/path ненадёжно

### 2. Новая forced-command модель

**authorized_keys:**
```
restrict,command="/usr/local/sbin/aubooks-deploy-dispatcher" ssh-ed25519 AAAA... deploy@calibre-web
```

sshd автоматически предоставляет `SSH_ORIGINAL_COMMAND` при forced command. Никакого `export` не требуется.

**Два компонента:**
- `deploy/vps2/aubooks-deploy-dispatcher.sh` — forced-command dispatcher
- `deploy/vps2/aubooks-deploy-root.sh` — root wrapper

**Разрешённые команды:**
```
upload <40hex-sha>
deploy <40hex-sha>
```

Всё остальное — `exit 1`.

### 3. Upload Protocol

Workflow:
```
tar -C "$BUNDLE_DIR" -cf - $WHEEL SHA256SUMS artifact-manifest.json deploy-request.json \
| ssh ... "upload $COMMIT_SHA"
```

Dispatcher:
- Валидирует SHA (`^[0-9a-f]{40}$`)
- Формирует staging path САМ: `/var/tmp/aubooks-calibre-web-$SHA/deploy-bundle`
- Не принимает path от клиента
- Принимает tar через stdin
- `--wildcards` фильтр: ровно 4 ожидаемых файла
- Python validation:拒绝 symlinks, absolute paths, path traversal
- chown только от root (в tests — skip)

### 4. Deploy Protocol

Workflow:
```
ssh ... "deploy $COMMIT_SHA"
```

Dispatcher:
- Валидирует SHA
- Сам вычисляет bundle dir: `/var/tmp/aubooks-calibre-web-$SHA/deploy-bundle`
- Проверяет staging ownership
- Передаёт SHA через stdin: `printf '%s\n' "$sha" | sudo -n /usr/local/sbin/aubooks-deploy-root`
- Никаких command-line arguments

### 5. Root Wrapper

`deploy/vps2/aubooks-deploy-root.sh`:
- НЕ принимает никаких command-line arguments (`[[ "$#" -eq 0 ]]`)
- Читает ровно одну строку SHA из stdin (`read -r sha`)
- Reject trailing additional input
- Валидирует SHA строго: `^[0-9a-f]{40}$`
- Сам вычисляет bundle dir: `$STAGING_BASE/aubooks-calibre-web-$SHA/deploy-bundle`
- НЕ принимает произвольные paths
- `exec` в `deploy-calibre-web-release.sh`

### 6. Sudoers

```
aubooks-deploy ALL=(root) NOPASSWD: /usr/local/sbin/aubooks-deploy-root
```

БЕЗ аргументов. БЕЗ wildcard. БЕЗ dynamic matching.
Root wrapper принимает SHA через stdin и сам вычисляет paths.

### 7. Bundle Transport

**Workflow side:**
- Local: tar 4 files → stdin pipe → SSH forced command
- Нет SCP, нет `ssh install`, нет прямого sudo

**Dispatcher side:**
- Сохраняет stdin как временный archive file
- Полностью проверяет archive BEFORE extraction:
  - Ровно 4 members
  - Каждый: top-level basename only, regular file only
  - НЕ symlink, НЕ hardlink, НЕ directory, НЕ device/fifo
  - НЕ absolute path, НЕ "..", НЕ slash/path components
  - НЕ duplicate names
  - Size limits: archive ≤512MB, wheel ≤256MB, metadata ≤256KB
- После PASS: извлекает каждый approved member непосредственно
- chown от root
- file permission hardening
- При ошибке: staging cleanup, nonzero exit

**Helper side (без изменений):**
- Triple checksum verification
- Manifest/request cross-validation
- Release transaction with rollback

### 8. Security Properties

- Deploy user shell: `/bin/bash` (безопасно thanks forced command)
- Forced command перехватывает ВСЕ SSH commands для deploy key
- SCP: НЕВОЗМОЖЕН (forced command блокирует)
- Arbitrary SSH: НЕВОЗМОЖЕН
- Arbitrary sudo: НЕВОЗМОЖЕН (root wrapper derives all paths)
- Shell expansion: НЕВОЗМОЖЕН (no `eval`, no `bash -c`)
- Path traversal: ОТКЛОНЁН (Python validation)
- Symlinks: ОТКЛОНЁНЫ (Python validation)
- Absolute paths: ОТКЛОНЁНЫ (Python validation)

### 9. Production Helper

`deploy/vps2/deploy-calibre-web-release.sh` — БЕЗ ИЗМЕНЕНИЙ:
- SHA validation, manifest gate, checksum gate
- Legacy layout stop, rollback, health checks

### 10. Old Venv

`/opt/calibre-web/venv` — НЕ удалять. Emergency rollback path.

### 11. Master Workflow

`deploy-production.yml` также существует в master branch (commit `8f1fb8c7`).
После commit потребуется синхронизировать обновлённый workflow в master.

## Изменённые файлы

- `deploy/vps2/aubooks-deploy-dispatcher.sh` — НОВЫЙ forced-command dispatcher
- `deploy/vps2/aubooks-deploy-root.sh` — НОВЫЙ root wrapper
- `.github/workflows/deploy-production.yml` — upload/deploy protocol
- `tests/test_calibre_web_deploy_helper.py` — 51 hermetic tests (12 helper + 21 dispatcher + 9 root wrapper + 9 script checks)
- `docs/works/2026-09-13-phase-2b-contract-reconciliation.md` — этот doc

## Проверки
- Deploy helper tests: 12/12 pass
- Dispatcher upload tests: 21/21 pass
- Root wrapper tests: 9/9 pass
- Script structure tests: 9/9 pass
- Bash syntax: `bash -n` на всех scripts OK
- YAML parse: OK
- Security grep: no `scp`, no `ssh.*install`, no `ssh.*sudo` в workflow
- git diff --check: OK

## Commit
Changes staged but NOT pushed. Commit pending operator approval.
