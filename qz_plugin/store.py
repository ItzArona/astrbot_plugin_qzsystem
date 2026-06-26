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

"""hostid 寻址与每用户绑定存储。

解析优先级：
1. 命令里显式传的别名/hostid（含 ``alias=`` key=value 形式）
2. 当前用户 KV 绑定 ``binding:<sender_id>``
3. 报错提示 ``/qz bind``
"""

from __future__ import annotations

import re
from typing import Any

from astrbot.api.event import AstrMessageEvent

from .config import PluginConfig

_ALIAS_KV_RE = re.compile(r"(?:^|\s)alias=(\S+)")


def extract_alias_kv(message_str: str) -> str | None:
    """从消息文本里提取 ``alias=xxx`` key=value，返回别名/hostid 字符串。"""
    m = _ALIAS_KV_RE.search(message_str or "")
    return m.group(1) if m else None


def has_confirm(message_str: str) -> bool:
    return " confirm" in f" {message_str or ''} "


def _kv_key(sender_id: str) -> str:
    return f"binding:{sender_id}"


async def bind_user(
    plugin: "StarLike", event: AstrMessageEvent, alias_or_hostid: str
) -> str:
    """为当前用户绑定默认实例别名/hostid。返回友好提示。"""
    cfg: PluginConfig = plugin.cfg
    value = (alias_or_hostid or "").strip()
    if not value:
        return "请提供别名或 hostid，例如：/qz bind web1 或 /qz bind 3145"
    hostid = cfg.alias_to_hostid(value)
    if hostid is None:
        return (
            f"未找到别名 “{value}”。请要么直接传 hostid 数字（如 /qz bind 3145），"
            f"要么先在 WebUI 插件配置的“云主机别名表”里添加一条：别名={value}，hostid=<实例id>。"
        )
    await plugin.put_kv_data(_kv_key(event.get_sender_id()), hostid)
    label = cfg.hostid_to_alias(hostid)
    return f"已绑定默认实例：{label} (hostid={hostid})"


async def unbind_user(plugin: "StarLike", event: AstrMessageEvent) -> str:
    key = _kv_key(event.get_sender_id())
    cur = await plugin.get_kv_data(key, None)
    if cur is None:
        return "当前没有绑定实例。"
    await plugin.delete_kv_data(key)
    return "已解除绑定。"


async def resolve_hostid(
    plugin: "StarLike",
    event: AstrMessageEvent,
    alias_param: str | None,
) -> tuple[str, str]:
    """返回 (hostid, display_label)。无法解析时抛 ValueError。"""
    cfg: PluginConfig = plugin.cfg
    # 1. key=value alias=
    kv = extract_alias_kv(event.message_str)
    candidate = kv or (alias_param or "").strip()
    if candidate:
        hostid = cfg.alias_to_hostid(candidate)
        if hostid is None:
            raise ValueError(
                f"未找到别名 “{candidate}”。请检查插件配置 hosts，或直接传 hostid 数字。"
            )
        return hostid, cfg.hostid_to_alias(hostid)
    # 2. 用户绑定
    bound = await plugin.get_kv_data(_kv_key(event.get_sender_id()), None)
    if bound:
        return str(bound), cfg.hostid_to_alias(str(bound))
    # 3. 报错
    raise ValueError(
        "未指定云主机。请在命令里带别名/hostid，或先 /qz bind <别名> 绑定默认实例。"
    )


class StarLike:
    """结构化协议提示，仅为类型提示用。"""

    cfg: PluginConfig
    put_kv_data: Any
    get_kv_data: Any
    delete_kv_data: Any
