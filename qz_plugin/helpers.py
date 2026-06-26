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

"""命令层共享小工具：统一 API 调用错误处理、表头、参数解析。"""

from __future__ import annotations

import re
from typing import Any

from .client import QzsystemError

_KV_RE = re.compile(r"(?:^|\s)(\w+)=([^\s]+)")


def parse_kwargs(message_str: str, keys: set[str] | None = None) -> dict[str, str]:
    """从消息文本提取 ``key=value`` 对。可选 keys 白名单过滤。"""
    out: dict[str, str] = {}
    for m in _KV_RE.finditer(message_str or ""):
        k, v = m.group(1), m.group(2)
        if keys is None or k in keys:
            out[k] = v
    return out


def host_header(label: str, hostid: str) -> str:
    if label and label != hostid:
        return f"[{label} #{hostid}]"
    return f"[#{hostid}]"


async def safe_call(plugin: Any, coro: Any) -> tuple[Any, str | None]:
    """执行 API 协程，捕获 QzsystemError，返回 (data, error_text)。"""
    try:
        data = await coro
        return data, None
    except QzsystemError as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001
        return None, f"调用异常: {exc}"
