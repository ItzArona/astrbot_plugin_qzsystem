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

"""凭证脱敏与主动私聊发送。"""

from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain

from .permissions import is_group_chat

# 匹配 http(s)://... 或 base64 图片数据等长串里的密码 query 参数
_PWD_QUERY_RE = re.compile(r"(password|panel_password)=([^&\s]+)", re.IGNORECASE)
# 纯密码行/字段
_PWD_FIELD_RE = re.compile(
    r"(?im)^\s*(系统密码|面板密码|os_password|panel_password)\s*[:：]\s*(.+)$"
)
# VNC url 里的 token 参数
_TOKEN_QUERY_RE = re.compile(r"(token|password)=([^&\s]+)", re.IGNORECASE)

_MASK = "****"


def redact_secrets(text: str) -> str:
    """对文本里的密码/凭证做掩码，用于群聊输出。"""
    if not text:
        return text
    text = _PWD_QUERY_RE.sub(lambda m: f"{m.group(1)}={_MASK}", text)
    text = _TOKEN_QUERY_RE.sub(lambda m: f"{m.group(1)}={_MASK}", text)
    text = _PWD_FIELD_RE.sub(lambda m: f"{m.group(1)}: {_MASK}", text)
    return text


def redact_info_dict(info: dict[str, Any]) -> dict[str, Any]:
    """对 info 接口返回的字典里的敏感字段做掩码，返回新字典。"""
    redacted = dict(info or {})
    for k in ("os_password", "panel_password"):
        if k in redacted and redacted[k]:
            redacted[k] = _MASK
    return redacted


async def emit_sensitive(
    plugin: "StarLike",
    event: AstrMessageEvent,
    safe_text: str,
    full_text: str,
) -> None:
    """发送含凭证的命令结果。

    - 群聊 + redact_in_group 开启：群里发 ``safe_text``（不含凭证），私聊发 ``full_text``；
      私聊失败则在群里提示用户私聊重发。
    - 私聊 或 群聊但未开启脱敏：直接发 ``full_text``。

    ``safe_text`` 由调用方负责保证不含任何凭证，本函数不再依赖正则脱敏，
    避免因输出格式与正则不匹配导致凭证泄露。
    """
    if is_group_chat(event) and plugin.cfg.redact_in_group:
        await event.send(event.plain_result(safe_text))
        ok = await send_private_message(plugin, event, full_text)
        if not ok:
            await event.send(
                event.plain_result("⚠️ 完整内容含凭证，请私聊执行该命令查看。")
            )
        return
    await event.send(event.plain_result(full_text))


async def send_private_message(
    plugin: "StarLike", event: AstrMessageEvent, text: str
) -> bool:
    """尽力把全文私聊发给当前触发者；失败返回 False。

    通过解析 ``unified_msg_origin`` 并把末段会话 id 替换为发送者 id，构造私聊 UMO。
    仅对常见平台格式有效；不支持的格式静默失败，由调用方回退提示用户私聊重发。
    """
    umo = getattr(event, "unified_msg_origin", "") or ""
    if not umo:
        return False
    parts = umo.split(":")
    if len(parts) < 3:
        return False
    # 末段是会话 id（群 id 或私聊对方 id）；用发送者 id 替换构造私聊会话
    sender_id = event.get_sender_id()
    if not sender_id:
        return False
    parts[-1] = str(sender_id)
    private_umo = ":".join(parts)
    try:
        chain = MessageChain().message(text)
        await plugin.context.send_message(private_umo, chain)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"send_private_message 失用回退: {exc}")
        return False


class StarLike:
    context: Any
