# AGENTS.md

Project: AstrBot plugin for managing qzsystem (轻舟云) cloud servers. Repo is a fresh scaffold — **no plugin source code exists yet**; first work is creating the plugin under AstrBot's `data/plugins/` layout.

## Development references (local, gitignored)

Two doc caches live in this repo as the primary dev references. **Read them before writing code** instead of fetching from the web.

- `.astrbot_plugin_coding_docs/` — AstrBot plugin development docs (17 files). Start at its `README.md`, then `00_从这里开始_plugin-new.md` and `01_最小实例_simple.md` for the plugin skeleton.
- `.qzsystem_development_docs/` — 轻舟云主控 API (41 OpenAPI specs). Start at its `README.md` for the categorized index. `04_云主机信息_info.md` has the canonical instance field dictionary.

Both are gitignored (see `.gitignore`) and refreshed by their own `_download.py`:
- `python .astrbot_plugin_coding_docs/_download.py`
- `python .qzsystem_development_docs/_download.py`

`Vibing.md` is personal notes, also gitignored.

## Gitignore policy — do not commit

`.gitignore` excludes `.qzsystem_development_docs/`, `.astrbot_plugin_coding_docs/`, and `Vibing.md`. Do not `git add` these. Only real project source should be tracked. If you generate files into those doc dirs, leave them untracked.

## Conventions to follow (from cached docs, summarized)

AstrBot plugin (verify against `.astrbot_plugin_coding_docs/`):
- Plugin class extends `Star`; handler signature is `async def fn(self, event: AstrMessageEvent)`; plugin entry file must be `main.py`.
- Use `aiohttp`/`httpx`, never `requests`. Persist data under AstrBot's `data/` dir, not the plugin's own dir (survives plugin updates).
- Format with `ruff` before committing.

qzsystem API (verify against `.qzsystem_development_docs/`):
- All endpoints are `POST /api/v1/*` with headers `signature` (主控后台第三方财务 key) and `apiuser` (财务用户名). Most bodies need `hostid`.
- Response shape `{msg, code, time, data?}`; `code == 200` means success.
- Note: some specs list header names with trailing spaces (`signature `, `apiuser   `) — strip them when implementing.
