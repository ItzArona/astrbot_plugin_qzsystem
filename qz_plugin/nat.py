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

"""/nat NAT 挂机宝端口与域名管理。"""

from __future__ import annotations

from typing import Any

from astrbot.api.event import AstrMessageEvent

from . import endpoints as E
from .helpers import host_header, parse_kwargs, safe_call
from .store import resolve_hostid


# ---- 端口 ----
def _format_port_list(data: Any) -> list[str]:
    arr = data if isinstance(data, list) else []
    lines = []
    for it in arr or []:
        sid = it.get("id")
        name = it.get("name", "")
        pt = it.get("port_type", "")
        sp = it.get("sport", "")
        dp = it.get("dport", "")
        api_url = it.get("api_url", "")
        sysflag = "系统" if str(it.get("sys")) == "2" else "自定义"
        lines.append(f"#{sid} {name} [{pt}] {api_url}:{sp} -> 内:{dp} ({sysflag})")
    if not lines:
        lines.append("暂无端口映射")
    return lines


async def nat_port_list(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.NAT_PORT_LIST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    return f"{host_header(label, hostid)} NAT 端口映射\n\n" + "\n".join(
        _format_port_list(data)
    )


async def nat_port_add(plugin: Any, event: AstrMessageEvent, dport: str) -> str:
    hostid, label = await resolve_hostid(plugin, event, "")
    if not dport:
        return "请提供内网端口：/nat port add <dport>，可选 sport=外网端口 name=名称 alias=别名"
    kw = parse_kwargs(event.message_str, {"sport", "name"})
    sport = kw.get("sport", "")
    name = kw.get("name", "")
    body: dict[str, Any] = {
        "hostid": hostid,
        "dport": dport,
        "sport": sport,
        "name": name,
    }
    _, err = await safe_call(plugin, plugin.client.post(E.NAT_ADD_PORT, body))
    if err:
        return f"{host_header(label, hostid)} 添加失败：{err}"
    extra = f" 外网端口 {sport}" if sport else "（外网端口自动分配）"
    return f"{host_header(label, hostid)} 已添加端口映射：内 {dport}{extra}"


async def nat_port_del(plugin: Any, event: AstrMessageEvent, id: str) -> str:
    hostid, label = await resolve_hostid(plugin, event, "")
    if not id:
        return "请提供端口 id：/nat port del <id>"
    _, err = await safe_call(
        plugin, plugin.client.post(E.NAT_REMOVE_PORT, {"hostid": hostid, "id": id})
    )
    if err:
        return f"{host_header(label, hostid)} 删除失败：{err}"
    return f"{host_header(label, hostid)} 已删除端口映射 #{id}。"


async def nat_port_find(
    plugin: Any, event: AstrMessageEvent, keywords: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not keywords:
        return "请提供查询关键词(数字)：/nat port find <关键词>"
    data, err = await safe_call(
        plugin,
        plugin.client.post_data(
            E.NAT_FIND_PORT, {"hostid": hostid, "keywords": keywords}
        ),
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    arr = data if isinstance(data, list) else []
    if not arr:
        return f"{host_header(label, hostid)} 没有匹配关键词 {keywords} 的可用端口。"
    return (
        f"{host_header(label, hostid)} 可用端口（关键词 {keywords}）：\n"
        + ", ".join(str(p) for p in arr[:50])
    )


# ---- 域名 ----
def _format_domain_list(data: Any) -> list[str]:
    arr = data if isinstance(data, list) else []
    lines = []
    for it in arr or []:
        sid = it.get("id")
        domain = it.get("domain", "")
        api_url = it.get("api_url", "")
        dip = it.get("dip", "")
        lines.append(f"#{sid} {domain}  (公:{api_url} 内:{dip})")
    if not lines:
        lines.append("暂无绑定域名")
    return lines


async def nat_domain_list(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.NAT_DOMAIN_LIST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    return f"{host_header(label, hostid)} NAT 域名列表\n\n" + "\n".join(
        _format_domain_list(data)
    )


async def nat_domain_add(plugin: Any, event: AstrMessageEvent, domain: str) -> str:
    hostid, label = await resolve_hostid(plugin, event, "")
    if not domain:
        return "请提供域名：/nat domain add <域名>"
    _, err = await safe_call(
        plugin,
        plugin.client.post(E.NAT_ADD_DOMAIN, {"hostid": hostid, "domain": domain}),
    )
    if err:
        return f"{host_header(label, hostid)} 添加失败：{err}"
    return f"{host_header(label, hostid)} 已添加域名：{domain}"


async def nat_domain_del(plugin: Any, event: AstrMessageEvent, id: str) -> str:
    hostid, label = await resolve_hostid(plugin, event, "")
    if not id:
        return "请提供域名 id：/nat domain del <id>"
    _, err = await safe_call(
        plugin, plugin.client.post(E.NAT_REMOVE_DOMAIN, {"hostid": hostid, "id": id})
    )
    if err:
        return f"{host_header(label, hostid)} 删除失败：{err}"
    return f"{host_header(label, hostid)} 已删除域名 #{id}。"


__all__ = [
    "nat_port_list",
    "nat_port_add",
    "nat_port_del",
    "nat_port_find",
    "nat_domain_list",
    "nat_domain_add",
    "nat_domain_del",
]
