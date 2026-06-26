# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

`astrbot_plugin_qzsystem` —— AstrBot 插件，在 QQ / Telegram 等 IM 内通过**命令**管理轻舟云（qzsystem）主控的全部云主机能力（实例生命周期、电源、监控、密码、ISO、BIOS、IP、快照、备份、防火墙、NAT、VNC、控制台）。覆盖 qzsystem 全部 41 个接口。

**命令类型插件，不暴露为 LLM 工具**——只有显式发送命令才会触发，大模型不会自动调用。

## 开发命令

- **格式化 / lint（提交前必做）**：`ruff format` 然后 `ruff check`。
- **没有自动化测试套件**。`.pytest_cache` 出现在 `.gitignore` 里但仓库无 `tests/`。唯一的“测试”是运行期联调命令 `/test ping`（调用 qzsystem `test` 接口验证连通性，仅管理员）。
- **运行方式**：这是 AstrBot 插件，不能独立运行。克隆到 `AstrBot/data/plugins/`，在 WebUI → 插件管理 → 重载插件。依赖 `aiohttp`（由 AstrBot 按 `requirements.txt` 自动装）。
- 要求 `astrbot_version >= 4.10.4`（见 `metadata.yaml`）。

## 本地开发参考文档（已 gitignore，不入库）

两份缓存是主要开发依据，**写代码前先读它们，别去抓网页**：

- `.astrbot_plugin_coding_docs/` —— AstrBot 插件开发文档。从其 `README.md` 起步，再看 `00_从这里开始` / `01_最小实例`。注意：这里面还嵌了一份完整的 AstrBot 源码树（`AstrBot/astrbot/...`），可用于对照框架真实行为（如 `session_waiter`、`MessageSession`、KV API 的实际签名）。
- `.qzsystem_development_docs/` —— 轻舟云主控 41 个 OpenAPI 规范。从其 `README.md` 起步；`04_云主机信息_info.md` 是实例字段字典。
- 二者各由自己的 `_download.py` 刷新：`python .qzsystem_development_docs/_download.py`。
- **不要 `git add`** 这两个目录或 `Vibing.md`（个人笔记）。

> 注意：`AGENTS.md` 称“尚无插件源码”，已**过时**——完整插件早已实现。其中的 API/约定小结仍然有效，但“fresh scaffold”叙述请忽略。

## 架构

分层非常清晰，改代码前理解这套分工能避免破坏约定：

```
main.py                 仅做命令注册 + 薄 handler，委托给 qz_plugin/* 的纯函数
qz_plugin/
  client.py             QzsystemClient：aiohttp 会话、鉴权 header、响应外壳解析
  endpoints.py          真实端点路径常量 + 枚举映射表（POWER_MAP / BIOS_MAP / ...）
  config.py             PluginConfig：AstrBotConfig dict 的类型化包装 + 别名↔hostid
  store.py              hostid 寻址 + 每用户绑定（KV）+ has_confirm
  permissions.py        is_group_chat / sender_label
  redaction.py          凭证脱敏 + 主动私聊发送（emit_sensitive）
  render.py             emit：长文本自动转图片；fmt_kv 格式化
  helpers.py            parse_kwargs / host_header / safe_call
  server.py snapshot.py backup.py firewall.py nat.py test_cmd.py   各命令组业务实现
```

### 命令实现的核心契约

每个业务函数签名为 `async def fn(plugin, event, ...) -> str | None`：

- **返回 `str`**：由 `main.py` 的 handler 用 `emit(self, event, text, title=...)` 渲染后 `yield`。
- **返回 `None`**：函数内部已用 `await event.send(...)` 自行发送（用于多消息、图片、含凭证三类场景）。handler 里写成 `if text: yield await emit(...)`，`None` 时不再 yield。

`main.py` 的 handler 应保持极薄——只做装饰器、参数声明、调用业务函数、渲染。业务逻辑一律放进 `qz_plugin/*`。

### 必须遵守的横切约定

1. **API 错误处理走 `safe_call`**：业务函数用 `data, err = await safe_call(plugin, plugin.client.post_data(...))`，绝不让 `QzsystemError` 冒泡到 handler。`err` 非空就返回友好错误串。

2. **hostid 寻址统一走 `resolve_hostid(plugin, event, alias)`**，返回 `(hostid, label)`。优先级：命令里的位置参数 `alias` 或 `alias=xxx` key=value → 当前用户 `/qz bind` 绑定（KV 键 `binding:<sender_id>`）→ 抛 `ValueError`。输出前缀统一用 `host_header(label, hostid)`。

3. **权限**：写操作必须加 `@filter.permission_type(filter.PermissionType.ADMIN)`，且该装饰器要放在 `@xxx_group.command(...)` **上方**（见 `main.py` 现有写法）。

4. **凭证安全（vnc / panel / reset-os-pwd / reset-panel-pwd / reinstall / create / info）**：调用方自己构造 `safe_text`（保证零凭证）和 `full_text` 两份，交给 `emit_sensitive(plugin, event, safe, full)`。群聊+脱敏开启时群里发 safe、私聊发 full；私聊失败则提示用户私聊重发。**不依赖正则脱敏**——safe_text 由调用方负责彻底不含凭证。`info` 命令额外用 `redact_info_dict` 掩码 `os_password`/`panel_password`。

5. **高危操作二次确认（delete / snapshot restore / backup restore）**：当 `plugin.cfg.require_confirm` 为真时，用 `has_confirm(event.message_str)` 检查命令末尾是否带 `confirm`，否则只返回确认提示、不执行。

6. **key=value 参数**用 `parse_kwargs(event.message_str, {白名单})` 解析（如 `cpu=2 memory=4096`、`priority=10 remark=..`）。位置参数有限时（如 firewall/nat 的 add/del），`alias` 只能用 `alias=` kv 形式传，handler 不再声明 `alias` 位置参数。

7. **多轮向导**（`server_create`）用 `astrbot.core.utils.session_waiter.session_waiter`，配 `_UserSessionFilter`（按 `unified_msg_origin:sender_id` 隔离会话，防群聊串扰），结束时 `event.stop_event()`。

8. **输出渲染**：短文本（≤ `text_to_image_threshold`，默认 150）走 `plain_result`；超长用 `plugin.html_render` 渲成图片，Playwright 不可用时回退纯文本。截图等 base64 图片解码后用 `event.chain_result([...Image.fromFileSystem])` 发送，临时文件用 `event.track_temporary_local_file(path)` 交由事件生命周期清理。

### qzsystem API 约定（client.py）

- 除 `panel` 外全部是 `POST /api/v1/*`，响应外壳 `{msg, code, time, data?}`，`code == 200` 才算成功，否则 `client` 抛 `QzsystemError`。
- 鉴权 header `signature`（主控后台第三方财务 key）/ `apiuser`（财务用户名）。**OpenAPI 文档里 header 名常带尾随空格**，`client` 发送时统一 strip。
- `panel` 是**唯一的 GET 接口**，不需鉴权 header，用 `client.build_panel_url(host_name, panel_password)` 拼 query。
- 凭证缺失时 `client.post` 会抛带缺失项清单的 `QzsystemError`；`client.configured` / `missing_credentials()` 可预检。
- 会话长连接复用，插件 `terminate()` 时关闭。

### 端点路径以 OpenAPI `paths` 为准，不信文件名

`endpoints.py` 已把所有路径纠正到真实值并逐条注释。**新增/修改接口时务必核对 `.qzsystem_development_docs/` 里对应 spec 的 `paths` 段**，不要按文件名后缀想当然。已知陷阱举例：`imageList`→`osList`、`reinstall`→`installOS`、`mountIso`→`mountISO`（大小写敏感）、`delSnapshot`→`removeSnapshot`、`restoreBackup`→`restoreBackupHost`、`getVnc`→`vnc`、NAT 系列无 `nat` 前缀（`portList`/`addPort`/`findport`/...）。

## 其它

- **持久化用 AstrBot KV API**（`plugin.put_kv_data` / `get_kv_data` / `delete_kv_data`），数据存 AstrBot 的 `data/` 目录（随插件更新存活），不要写到插件自己的目录。
- HTTP 用 `aiohttp`，不用 `requests`。
- 所有源码文件头部带 AGPL-3.0 许可声明；新建 `.py` 文件请沿用同样的头部。
- `main.py` 顶部把插件目录插入 `sys.path` 以便绝对导入 `qz_plugin` 子包——无论 AstrBot 以“顶层模块 main”还是“包.main”方式加载都生效，不要删除这段。
