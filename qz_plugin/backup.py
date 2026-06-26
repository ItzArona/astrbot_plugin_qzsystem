# astrbot_plugin_qzsystem - 轻舟云(qzsystem)主控管理 AstrBot 插件
# Copyright (C) 2026  astrbot_server_manegent
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""/backup 备份四件套：list / create / del / restore。结构与快照一致。"""

from __future__ import annotations

from typing import Any

from astrbot.api.event import AstrMessageEvent

from . import endpoints as E
from .helpers import host_header, safe_call
from .snapshot import _format_snap_list
from .store import has_confirm, resolve_hostid


async def backup_list(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.BACKUP_LIST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    lines = _format_snap_list(data)
    if not lines:
        return f"{host_header(label, hostid)} 暂无备份。"
    return f"{host_header(label, hostid)} 备份列表\n\n" + "\n".join(lines)


async def backup_create(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    _, err = await safe_call(
        plugin, plugin.client.post(E.CREATE_BACKUP, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 创建失败：{err}"
    return f"{host_header(label, hostid)} 已发起创建备份请求（异步创建中）。"


async def backup_del(
    plugin: Any, event: AstrMessageEvent, id: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not id:
        return "请提供备份 id：/backup del <id>"
    _, err = await safe_call(
        plugin, plugin.client.post(E.REMOVE_BACKUP, {"hostid": hostid, "id": id})
    )
    if err:
        return f"{host_header(label, hostid)} 删除失败：{err}"
    return f"{host_header(label, hostid)} 已删除备份 #{id}。"


async def backup_restore(
    plugin: Any, event: AstrMessageEvent, id: str, alias: str = ""
) -> str:
    # 用户输入 /backup restore <id> confirm 时，confirm 会被位置参数解析进 alias，需清回
    if (alias or "").strip() in ("confirm", "确认"):
        alias = ""
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not id:
        return "请提供备份 id：/backup restore <id>"
    if plugin.cfg.require_confirm and not has_confirm(event.message_str):
        return f"{host_header(label, hostid)} ⚠️ 恢复备份会回滚整机数据。确认请发送：/backup restore {id} confirm"
    _, err = await safe_call(
        plugin, plugin.client.post(E.RESTORE_BACKUP, {"hostid": hostid, "id": id})
    )
    if err:
        return f"{host_header(label, hostid)} 恢复失败：{err}"
    return f"{host_header(label, hostid)} 已发起恢复备份 #{id} 请求。"


__all__ = ["backup_list", "backup_create", "backup_del", "backup_restore"]
