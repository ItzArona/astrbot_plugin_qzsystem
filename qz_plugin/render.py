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

"""输出渲染：短文本直接发，长文本转 HTML 图片；Playwright 不可用时回退纯文本。"""

from __future__ import annotations

from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

_CARD_TMPL = """
<div style="font-family: -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background:#f5f6f8; padding:24px; width:fit-content; max-width:760px;">
  <div style="background:#fff; border-radius:12px; padding:20px 24px;
              box-shadow:0 1px 3px rgba(0,0,0,.08); border:1px solid #eceef2;">
    {% if title %}
    <div style="font-size:20px; font-weight:600; color:#1f2937; margin-bottom:12px;
                border-bottom:1px solid #eef0f3; padding-bottom:8px;">{{ title }}</div>
    {% endif %}
    <pre style="margin:0; font-family:'Cascadia Code','Consolas','Menlo',monospace;
                font-size:14px; line-height:1.65; color:#374151;
                white-space:pre-wrap; word-break:break-word;">{{ content }}</pre>
  </div>
</div>
"""


async def _try_image(plugin: Any, title: str, text: str) -> str | None:
    """尝试 html_render，失败返回 None。"""
    try:
        url = await plugin.html_render(_CARD_TMPL, {"title": title, "content": text})
        if url:
            return url
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"html_render 失败，回退纯文本: {exc}")
    return None


async def emit(plugin: Any, event: AstrMessageEvent, text: str, title: str = "") -> Any:
    """根据文本长度自动选择 plain_result 或 image_result，返回可 yield 的结果对象。"""
    text = text or ""
    threshold = plugin.cfg.text_to_image_threshold
    if len(text) <= threshold:
        return event.plain_result(text)
    url = await _try_image(plugin, title, text)
    if url:
        return event.image_result(url)
    return event.plain_result(text)


async def emit_image(
    plugin: Any, event: AstrMessageEvent, text: str, title: str = ""
) -> Any:
    """尽量以图片形式输出（用于截图/监控等场景），失败回退纯文本。"""
    text = text or ""
    url = await _try_image(plugin, title, text)
    if url:
        return event.image_result(url)
    return event.plain_result(text)


def fmt_kv(rows: list[tuple[str, Any]]) -> str:
    """把 (key, value) 列表格式化为 ``key: value`` 多行文本。"""
    lines = []
    for k, v in rows:
        if v is None or v == "":
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines)
