# AGENTS.md

AstrBot **command-type** plugin managing qzsystem (轻舟云) cloud servers. Covers all 41 qzsystem endpoints. Repo root IS the plugin directory — clone into `AstrBot/data/plugins/astrbot_plugin_qzsystem`. Plugin name: `astrbot_plugin_qzsystem`; requires AstrBot `>=4.10.4` (uses `template_list` config type). Licensed AGPL-3.0; public at `ItzArona/astrbot_plugin_qzsystem`.

## Layout

- `main.py` — Star entry; registers `/qz /server /snapshot /backup /firewall /nat /test` command groups as thin handlers that delegate to `qz_plugin/*`.
- `qz_plugin/` — internal package (client, endpoints, config, store, redaction, render, helpers, + per-domain command modules). Imported via `sys.path.insert(0, _PLUGIN_DIR)` at top of `main.py` — keep that shim or absolute imports break when AstrBot loads the plugin.
- `_conf_schema.json` — plugin config schema (WebUI renders this).
- `metadata.yaml` — plugin metadata; `astrbot_version` field gates load.

## Development references (gitignored — do NOT commit)

- `.astrbot_plugin_coding_docs/` — AstrBot plugin docs (17 md) + **full AstrBot source clone at `.astrbot_plugin_coding_docs/AstrBot/`**. When unsure whether an AstrBot API usage is correct, read the real source (e.g. `astrbot/core/star/register/star_handler.py` for decorators, `astrbot/core/platform/astr_message_event.py` for event methods, `astrbot/core/utils/session_waiter.py` for the wizard). Prefer this over guessing.
- `.qzsystem_development_docs/` — 41 OpenAPI specs. Start at its `README.md`. `04_云主机信息_info.md` is the canonical instance field dictionary.
- Refresh: `python .astrbot_plugin_coding_docs/_download.py` / `python .qzsystem_development_docs/_download.py`.
- `Vibing.md` — personal notes, also gitignored.

## Verify / format before committing

```bash
python -m ruff format main.py qz_plugin\
python -m ruff check main.py qz_plugin\
python -m py_compile main.py qz_plugin\*.py
```

There is no test suite and `astrbot`/`aiohttp` are NOT pip-installed locally (AstrBot provides them at runtime). To verify logic, write a throwaway script that stubs `astrbot.api.*`, `astrbot.core.*`, and `aiohttp` via `sys.modules`, then `import` the module under test. Run it, then delete it — do not commit verify scripts.

## Hard-won gotchas (each was a shipped bug)

**Decorator stacking** — never put `@filter.permission_type(...)` (or `@filter.event_message_type`/`platform_adapter_type`) above `@xxx.group(...)` or `@filter.command_group(...)`. `.group()`/`command_group()` return a `RegisteringCommandable` object (no `__name__`), and the permission decorator calls `get_handler_or_create(awaitable)` which reads `awaitable.__name__` → `AttributeError` at load. Stacking permission on `@xxx.command(...)` is safe (returns the original function). Verify in `.astrbot_plugin_coding_docs/AstrBot/astrbot/core/star/register/star_handler.py`.

**qzsystem endpoint paths** — the `.qzsystem_development_docs/README.md` index and the doc filenames are misleading; trust the OpenAPI `paths:` block in each spec. Already-corrected paths live in `qz_plugin/endpoints.py` (e.g. `osList` not `imageList`, `installOS` not `reinstall`, `mountISO` not `mountIso`, `addIP`/`removeIP` not `addIp`/`delIp`, `snapshot`/`backup` not `snapshotList`/`backupList`, `removeSnapshot`/`removeBackup`/`removeFirewall` not `del*`, `restoreBackupHost` not `restoreBackup`, NAT paths have NO `nat` prefix: `portList`/`addPort`/`removePort`/`findport`/`domainList`/`addDomain`/`removeDomain`, `vnc` not `getVnc`, `/api/v1/panel` is the only GET and needs no `signature`/`apiuser`). Header names in specs have trailing spaces (`signature ` / `apiuser   `) — `client.py` strips them.

**Config schema** — for object-valued list items (alias/hostid/remark), use `"type": "template_list"` (v4.10.4+), NOT `"type": "list"` + object `items`. `list` renders as a plain string list in WebUI, so users type bare strings → runtime `.get()` crashes. `invisible: true` **hides the field completely** in WebUI (users can't fill it) — use `obvious_hint: true` for sensitive-but-fillable fields like `signature`.

**Confirm guard for high-risk commands** — AstrBot's `CommandFilter` parses params by position. `/snapshot restore <id> confirm` assigns `id=<id>`, `alias="confirm"`, `confirm=""`. So `snapshot_restore`/`backup_restore`/`server_delete` must clear `alias` when it equals `"confirm"`/`"确认"` before calling `resolve_hostid` (otherwise "confirm" is treated as a missing alias and the user can never confirm). See `server.py:server_delete` for the canonical guard.

**Private message for credentials** — to send full-text credentials privately from a group-chat handler, construct a `MessageSession(platform_name=event.get_platform_id(), message_type=MessageType.FRIEND_MESSAGE, session_id=event.get_sender_id())` and `await plugin.context.send_message(session, chain)`. Do NOT string-edit `unified_msg_origin`'s last segment — the `message_type` segment stays `GroupMessage` and the platform tries to send to a nonexistent group. `qq_official` doesn't support `send_message` at all — `emit_sensitive` falls back to a "私聊执行该命令查看" notice.

**session_waiter in group chat** — default `SessionFilter` keys on `unified_msg_origin`, so everyone in a group shares one session and concurrent wizards clobber each other. `server_create` uses a custom `_UserSessionFilter` keyed by `f"{umo}:{sender_id}"` — copy this pattern for any new multi-turn wizard. Inside a waiter you MUST `await event.send(...)`; `yield` is forbidden.

**Screenshot temp files** — after decoding the `thumbnail` base64 to a temp PNG, call `event.track_temporary_local_file(path)` instead of `os.unlink` in a `finally`. Some platforms send asynchronously and may read the file after `await event.send` returns.

**Timeout capture** — `except TimeoutError` does not catch `asyncio.TimeoutError` on Python 3.10 (only 3.11+ aliases them). Use `except (TimeoutError, asyncio.TimeoutError)`.

## Conventions

- Async HTTP only (`aiohttp`); never `requests`.
- Persist via `self.put_kv_data`/`get_kv_data`/`delete_kv_data` (AstrBot KV store, plugin-scoped); large files under `data/plugin_data/<plugin_name>/`.
- `safe_text` passed to `emit_sensitive` must contain NO credentials by construction — do not rely on regex redaction.
- Chinese command aliases are registered via `alias={"中文"}` on each `@filter.command`/`command_group`.
