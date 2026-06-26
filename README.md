# 轻舟云主机管理 · AstrBot 插件

在 QQ / Telegram 等 IM 内通过**命令**管理轻舟云（qzsystem）主控的全部云主机能力：实例生命周期、电源、监控、密码、系统、ISO、BIOS、IP、快照、备份、防火墙、NAT 端口与域名、VNC、独立控制台。

> 命令类型插件，**不**暴露为 LLM 工具——只有显式发送命令才会触发，不会被大模型自动调用。

## 安装

将本仓库克隆到 AstrBot 的插件目录：

```bash
cd AstrBot/data/plugins
git clone <本仓库地址> astrbot_plugin_qzsystem
```

然后在 WebUI → 插件管理 → 重载插件。AstrBot 会自动安装 `requirements.txt` 里的 `aiohttp`。

## 配置

WebUI → 插件配置 → 「轻舟云主机管理」，填写：

| 配置项 | 说明 |
|---|---|
| `base_url` | 轻舟云主控 API 地址，如 `https://xxx.qzsystem.com`（不带末尾斜杠） |
| `signature` | 主控后台 → 第三方财务 key（隐藏存储） |
| `apiuser` | 财务中开通产品的用户名 |
| `hosts` | 别名表，把常用 hostid 起别名，如 `web1 → 3145` |
| `request_timeout` | 单次请求超时秒数，默认 30 |
| `text_to_image_threshold` | 文本超过该长度自动转图片，默认 150 |
| `redact_in_group` | 群聊对凭证脱敏并通过私聊发全文，默认开 |
| `require_confirm` | 高危操作末尾需带 `confirm`，默认开 |

## 快速上手

```
/qz bind web1        # 绑定当前用户的默认实例（别名或 hostid）
/qz whoami           # 查看当前绑定
/server info         # 查看详细信息（用绑定的实例）
/server monitor      # 实时监控
/server power reboot # 重启（需管理员）
/qz help             # 完整命令帮助
```

## 命令一览

权限：`R`=全员可读 · `W`=管理员写 · `W!`=管理员写+`confirm` 二次确认 · `W*`=管理员写(含凭证,群聊脱敏+私聊全文) · `R*`=管理员可读(含凭证)

### /qz 元命令

| 命令 | 权限 | 说明 |
|---|---|---|
| `/qz help` | R | 命令帮助 |
| `/qz bind <别名\|hostid>` | R | 绑定当前用户默认实例 |
| `/qz unbind` | R | 解除绑定 |
| `/qz whoami` | R | 查看当前绑定 |

### /server 实例管理（20 子命令）

| 命令 | 权限 | 对应接口 |
|---|---|---|
| `/server info [别名]` | R | info |
| `/server monitor [别名]` | R | monitor |
| `/server screenshot [别名]` | R | thumbnail（运行截图） |
| `/server cpu-history [别名]` | R | historyCpu |
| `/server net-history [别名]` | R | historyNetwork |
| `/server images [别名]` | R | osList |
| `/server iso-list [别名]` | R | isoList |
| `/server vnc [别名]` | R* | vnc |
| `/server panel [别名]` | R* | GET panel |
| `/server power <on\|off\|cut\|reboot> [别名]` | W | power |
| `/server synctime <on\|off> [别名]` | W | synctime |
| `/server bios <disk\|cd> [别名]` | W | bios |
| `/server iso mount <名称> [别名]` | W | mountISO |
| `/server iso unmount [别名]` | W | mountISO（空 iso_name） |
| `/server reset-os-pwd <新密码> [别名]` | W* | updateOSPassword |
| `/server reset-panel-pwd <新密码> [别名]` | W* | updatePanelPassword |
| `/server reinstall <镜像> <新密码> [别名]` | W* | installOS |
| `/server upgrade [别名] cpu=.. memory=.. sys_disk=.. data_disk=.. net_out=.. net_in=.. flow_limit=..` | W | updateHost |
| `/server renew <30d\|12m\|1y\|YYYY-MM-DD> [别名]` | W | renew |
| `/server delete [别名] confirm` | W! | removeHost |
| `/server create` | W | openHost（多轮向导） |
| `/server ip add <数量> [别名]` | W | addIP |
| `/server ip del <ip> [别名]` | W | removeIP |

### /snapshot 快照四件套

| 命令 | 权限 | 对应接口 |
|---|---|---|
| `/snapshot list [别名]` | R | snapshot |
| `/snapshot create [别名]` | W | createSnapshot |
| `/snapshot del <id> [别名]` | W | removeSnapshot |
| `/snapshot restore <id> [别名] confirm` | W! | restoreSnapshot |

### /backup 备份四件套

| 命令 | 权限 | 对应接口 |
|---|---|---|
| `/backup list [别名]` | R | backup |
| `/backup create [别名]` | W | createBackup |
| `/backup del <id> [别名]` | W | removeBackup |
| `/backup restore <id> [别名] confirm` | W! | restoreBackupHost |

### /firewall 防火墙三件套

| 命令 | 权限 | 对应接口 |
|---|---|---|
| `/firewall list [别名] [dir=in\|out] [method=accept\|drop] [proto=TCP\|UDP\|ICMP\|ANY] [page=N]` | R | firewallList |
| `/firewall add <in\|out> <accept\|drop> <TCP\|UDP\|ICMP\|ANY> <端口\|ANY> <IP\|ANY> [priority=N] [remark=..] [alias=..]` | W | addFirewall |
| `/firewall del <id> [alias=..]` | W | removeFirewall |

### /nat NAT 挂机宝端口与域名

| 命令 | 权限 | 对应接口 |
|---|---|---|
| `/nat port list [别名]` | R | portList |
| `/nat port add <dport> [sport=..] [name=..] [alias=..]` | W | addPort |
| `/nat port del <id> [alias=..]` | W | removePort |
| `/nat port find <关键词> [别名]` | R | findport |
| `/nat domain list [别名]` | R | domainList |
| `/nat domain add <域名> [alias=..]` | W | addDomain |
| `/nat domain del <id> [alias=..]` | W | removeDomain |

### /test 联调

| 命令 | 权限 | 对应接口 |
|---|---|---|
| `/test ping [别名]` | R* | test |

## hostid 寻址优先级

1. 命令里的 `[别名]` 位置参数，或 `alias=xxx` key=value
2. `/qz bind` 绑定的当前用户默认实例
3. 报错，提示先 `/qz bind`

## 安全说明

- **写操作**全部用 `@filter.permission_type(ADMIN)` 限制为 AstrBot 全局管理员（`admins_id`）。
- **含凭证命令**（`vnc`/`panel`/`reset-os-pwd`/`reset-panel-pwd`/`reinstall`）在群聊里脱敏显示，并通过私聊发送全文；建议直接在私聊执行。
- **高危操作**（`delete`/`snapshot restore`/`backup restore`）末尾必须带 `confirm` 才真正执行。
- `create` 创建向导建议在私聊执行，避免密码出现在群聊历史。

## 输出形式

短文本直接发送；超过 `text_to_image_threshold`（默认 150 字）自动用 HTML 模板渲染成图片，防止刷屏。Playwright 不可用时自动回退纯文本。运行截图（base64）解码后以图片消息发送。

## 接口路径纠错说明

本插件以各 OpenAPI 文档内的真实路径为准，不信任 README/文件名后缀。已纠正的路径：

| 文档名暗示 | 真实路径 |
|---|---|
| imageList | `/api/v1/osList` |
| reinstall | `/api/v1/installOS` |
| mountIso | `/api/v1/mountISO` |
| addIp / delIp | `/api/v1/addIP` / `/api/v1/removeIP` |
| snapshotList / delSnapshot | `/api/v1/snapshot` / `/api/v1/removeSnapshot` |
| backupList / delBackup / restoreBackup | `/api/v1/backup` / `/api/v1/removeBackup` / `/api/v1/restoreBackupHost` |
| delFirewall | `/api/v1/removeFirewall` |
| natPortList / natAddPort / natDelPort / natQueryPort | `/api/v1/portList` / `/api/v1/addPort` / `/api/v1/removePort` / `/api/v1/findport` |
| natDomainList / natAddDomain / natDelDomain | `/api/v1/domainList` / `/api/v1/addDomain` / `/api/v1/removeDomain` |
| getVnc | `/api/v1/vnc` |
| panel | `GET /api/v1/panel`（唯一 GET，不需 signature/apiuser） |

## 开发

- 内部包 `qz_plugin/`：`client.py`（aiohttp 客户端）/ `endpoints.py`（路径与枚举）/ `config.py` / `store.py` / `permissions.py` / `redaction.py` / `render.py` / `helpers.py` / `server.py` / `snapshot.py` / `backup.py` / `firewall.py` / `nat.py` / `test_cmd.py`。
- `main.py` 注册全部命令组，薄 handler 委托到 `qz_plugin/*` 的纯 async 函数。
- 提交前用 `ruff format` 与 `ruff check` 格式化。

## 许可

本项目基于 **GNU Affero General Public License v3.0**（AGPL-3.0-or-later）授权，详见 [LICENSE](LICENSE)。

任何对本插件的修改并通过网络提供服务的行为，必须向用户提供获取修改后源代码的途径（AGPL §13）。
