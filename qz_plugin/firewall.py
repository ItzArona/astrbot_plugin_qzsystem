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

"""/firewall 防火墙三件套：list / add / del。"""

from __future__ import annotations

from typing import Any

from astrbot.api.event import AstrMessageEvent

from . import endpoints as E
from .helpers import host_header, parse_kwargs, safe_call
from .store import resolve_hostid


def _format_fw_list(data: Any) -> list[str]:
    if isinstance(data, dict):
        arr = data.get("data") or []
        count = (data.get("extend") or {}).get("count")
    elif isinstance(data, list):
        arr, count = data, len(data)
    else:
        arr, count = [], 0
    lines = []
    for it in arr or []:
        sid = it.get("id")
        name = it.get("name", "")
        d = it.get("direction_name") or it.get("direction", "")
        m = it.get("method_name") or it.get("method", "")
        proto = it.get("protocol", "")
        port = it.get("port", "")
        ip = it.get("ip", "")
        pri = it.get("priority", "")
        lines.append(f"#{sid} [{d}/{m}] {proto} 端口:{port} IP:{ip} 权重:{pri}  {name}")
    if count is not None:
        lines.append(f"共 {count} 条策略")
    return lines


async def firewall_list(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    kw = parse_kwargs(event.message_str, {"page", "dir", "method", "proto"})
    body: dict[str, Any] = {"hostid": hostid}
    if "page" in kw:
        body["page"] = kw["page"]
    if "dir" in kw:
        body["direction"] = E.FIREWALL_DIR_MAP.get(kw["dir"].lower(), kw["dir"])
    if "method" in kw:
        body["method"] = E.FIREWALL_METHOD_MAP.get(kw["method"].lower(), kw["method"])
    if "proto" in kw:
        body["protocol"] = kw["proto"].upper()
    data, err = await safe_call(plugin, plugin.client.post_data(E.FIREWALL_LIST, body))
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    lines = _format_fw_list(data)
    if not lines:
        return f"{host_header(label, hostid)} 暂无防火墙策略。"
    return f"{host_header(label, hostid)} 防火墙策略\n\n" + "\n".join(lines)


async def firewall_add(
    plugin: Any,
    event: AstrMessageEvent,
    direction: str,
    method: str,
    protocol: str,
    port: str,
    ip: str,
) -> str:
    hostid, label = await resolve_hostid(plugin, event, "")
    d = E.FIREWALL_DIR_MAP.get((direction or "").lower())
    m = E.FIREWALL_METHOD_MAP.get((method or "").lower())
    proto = (protocol or "").upper()
    if d is None or m is None or proto not in E.FIREWALL_PROTOCOLS:
        return (
            "参数无效。用法：/firewall add <in|out> <accept|drop> <TCP|UDP|ICMP|ANY> <端口|ANY> <IP|ANY>\n"
            "可选：priority=10 remark=备注 alias=web1"
        )
    kw = parse_kwargs(event.message_str, {"priority", "remark"})
    body: dict[str, Any] = {
        "hostid": hostid,
        "direction": d,
        "method": m,
        "protocol": proto,
        "port": port,
        "ip": ip,
        "remark": kw.get("remark", ""),
    }
    if "priority" in kw and kw["priority"].isdigit():
        body["priority"] = int(kw["priority"])
    else:
        body["priority"] = 100
    _, err = await safe_call(plugin, plugin.client.post(E.ADD_FIREWALL, body))
    if err:
        return f"{host_header(label, hostid)} 添加失败：{err}"
    return (
        f"{host_header(label, hostid)} 已添加策略 [{d}/{m}] {proto} 端口:{port} IP:{ip}"
    )


async def firewall_del(plugin: Any, event: AstrMessageEvent, id: str) -> str:
    hostid, label = await resolve_hostid(plugin, event, "")
    if not id:
        return "请提供策略 id：/firewall del <id>"
    _, err = await safe_call(
        plugin, plugin.client.post(E.REMOVE_FIREWALL, {"hostid": hostid, "id": id})
    )
    if err:
        return f"{host_header(label, hostid)} 删除失败：{err}"
    return f"{host_header(label, hostid)} 已删除策略 #{id}。"


__all__ = ["firewall_list", "firewall_add", "firewall_del"]
