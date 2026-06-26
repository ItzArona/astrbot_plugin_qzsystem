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

"""/snapshot 快照四件套：list / create / del / restore。"""

from __future__ import annotations

from typing import Any

from astrbot.api.event import AstrMessageEvent

from . import endpoints as E
from .helpers import host_header, safe_call
from .store import has_confirm, resolve_hostid

_STATE_NAME = {1: "创建中", 2: "已完成"}


def _format_snap_list(data: Any) -> list[str]:
    items = []
    if isinstance(data, dict):
        arr = data.get("data") or []
        count = (data.get("extend") or {}).get("count")
    elif isinstance(data, list):
        arr, count = data, len(data)
    else:
        arr, count = [], 0
    for it in arr or []:
        sid = it.get("id")
        name = it.get("name", "")
        st = _STATE_NAME.get(it.get("state"), it.get("state"))
        ctime = it.get("create_time", "")
        items.append(f"#{sid}  {name}  [{st}]  {ctime}")
    if count is not None:
        items.append(f"共 {count} 个快照")
    return items


async def snapshot_list(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.SNAPSHOT_LIST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    lines = _format_snap_list(data)
    if not lines:
        return f"{host_header(label, hostid)} 暂无快照。"
    return f"{host_header(label, hostid)} 快照列表\n\n" + "\n".join(lines)


async def snapshot_create(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    _, err = await safe_call(
        plugin, plugin.client.post(E.CREATE_SNAPSHOT, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 创建失败：{err}"
    return f"{host_header(label, hostid)} 已发起创建快照请求（异步创建中）。"


async def snapshot_del(
    plugin: Any, event: AstrMessageEvent, id: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not id:
        return "请提供快照 id：/snapshot del <id>"
    _, err = await safe_call(
        plugin, plugin.client.post(E.REMOVE_SNAPSHOT, {"hostid": hostid, "id": id})
    )
    if err:
        return f"{host_header(label, hostid)} 删除失败：{err}"
    return f"{host_header(label, hostid)} 已删除快照 #{id}。"


async def snapshot_restore(
    plugin: Any, event: AstrMessageEvent, id: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not id:
        return "请提供快照 id：/snapshot restore <id>"
    if plugin.cfg.require_confirm and not has_confirm(event.message_str):
        return f"{host_header(label, hostid)} ⚠️ 恢复快照会回滚系统盘。确认请发送：/snapshot restore {id} confirm"
    _, err = await safe_call(
        plugin, plugin.client.post(E.RESTORE_SNAPSHOT, {"hostid": hostid, "id": id})
    )
    if err:
        return f"{host_header(label, hostid)} 恢复失败：{err}"
    return f"{host_header(label, hostid)} 已发起恢复快照 #{id} 请求。"


__all__ = ["snapshot_list", "snapshot_create", "snapshot_del", "snapshot_restore"]
