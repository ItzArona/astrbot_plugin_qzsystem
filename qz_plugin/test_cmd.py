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

"""/test 联调与健康检查。"""

from __future__ import annotations

from typing import Any

from astrbot.api.event import AstrMessageEvent

from . import endpoints as E
from .helpers import host_header, safe_call
from .store import resolve_hostid


async def test_ping(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.TEST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 测试失败：{err}"
    arr = data if isinstance(data, list) else []
    lines = []
    for it in arr or []:
        lines.append(
            f"{it.get('host_name', '')}  {it.get('domain', '')}  (公:{it.get('api_url', '')} 内:{it.get('dip', '')})"
        )
    return f"{host_header(label, hostid)} test 接口返回 {len(arr)} 条：\n" + (
        "\n".join(lines) if lines else "(空)"
    )


__all__ = ["test_ping"]
