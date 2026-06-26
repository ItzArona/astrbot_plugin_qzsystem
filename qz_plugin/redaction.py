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

from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType

from .permissions import is_group_chat

_MASK = "****"


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

    用发送者 id 构造一个 FRIEND_MESSAGE 类型的 MessageSession，
    交由 ``context.send_message`` 找到对应平台适配器私聊发送。
    若平台不支持私聊（如 qq_official）会静默失败，由调用方回退提示用户私聊重发。
    """
    sender_id = event.get_sender_id()
    platform_id = event.get_platform_id()
    if not sender_id or not platform_id:
        return False
    private_session = MessageSession(
        platform_name=platform_id,
        message_type=MessageType.FRIEND_MESSAGE,
        session_id=str(sender_id),
    )
    try:
        chain = MessageChain().message(text)
        await plugin.context.send_message(private_session, chain)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"send_private_message 失用回退: {exc}")
        return False


class StarLike:
    context: Any
