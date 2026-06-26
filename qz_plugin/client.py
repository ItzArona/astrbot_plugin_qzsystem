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

"""qzsystem 主控 API 异步客户端。

统一封装：
- ``aiohttp.ClientSession`` 长连接会话（在插件 ``terminate`` 时关闭）。
- Header ``signature`` / ``apiuser``（文档中部分带尾随空格，此处发送时一律 strip）。
- 通用响应外壳 ``{msg, code, time, data?}`` 解析；``code != 200`` 抛 :class:`QzsystemError`。
- 唯一 GET 接口 ``/api/v1/panel`` 不需要鉴权 header，单独提供 :meth:`build_panel_url`。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import aiohttp


class QzsystemError(Exception):
    """qzsystem API 返回 code != 200 或网络/解析异常。"""

    def __init__(
        self, message: str, code: int | None = None, payload: Any = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload


class QzsystemClient:
    def __init__(
        self,
        base_url: str,
        signature: str,
        apiuser: str,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.signature = (signature or "").strip()
        self.apiuser = (apiuser or "").strip()
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.signature and self.apiuser)

    def missing_credentials(self) -> list[str]:
        """返回缺失的凭证字段名列表；全填好返回空列表。"""
        missing: list[str] = []
        if not self.base_url:
            missing.append("base_url（轻舟云主控 API 基础地址）")
        if not self.signature:
            missing.append("signature（主控后台第三方财务 key）")
        if not self.apiuser:
            missing.append("apiuser（财务用户名）")
        return missing

    def _headers(self) -> dict[str, str]:
        # 文档中 header 名有时带尾随空格，发送时统一 strip
        return {
            "signature": self.signature,
            "apiuser": self.apiuser,
            "Content-Type": "application/json",
        }

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def post(
        self, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST JSON，返回解析后的响应字典。code != 200 抛 QzsystemError。"""
        if not self.configured:
            missing = self.missing_credentials()
            raise QzsystemError(
                "qzsystem 凭证未配置，请在 WebUI 插件配置里补填以下项："
                + "、".join(missing)
            )
        url = self.base_url + path
        session = await self._ensure_session()
        try:
            async with session.post(
                url, json=body or {}, headers=self._headers()
            ) as resp:
                text = await resp.text()
                try:
                    payload = await resp.json(content_type=None)
                except Exception:
                    raise QzsystemError(
                        f"HTTP {resp.status} 响应非 JSON: {text[:200]}",
                        code=resp.status,
                    )
        except aiohttp.ClientError as exc:
            raise QzsystemError(f"网络请求失败: {exc}") from exc
        except TimeoutError as exc:
            raise QzsystemError(f"请求超时: {exc}") from exc

        if not isinstance(payload, dict):
            raise QzsystemError(f"响应不是对象: {str(payload)[:200]}", payload=payload)
        code = payload.get("code")
        if code != 200:
            msg = payload.get("msg") or "未知错误"
            raise QzsystemError(str(msg), code=code, payload=payload)
        return payload

    async def post_data(self, path: str, body: dict[str, Any] | None = None) -> Any:
        """POST 并返回 ``data`` 字段（可能为 dict / list / None）。"""
        return (await self.post(path, body)).get("data")

    def build_panel_url(self, host_name: str, panel_password: str) -> str:
        """唯一 GET 接口 ``/api/v1/panel``，参数走 query，不需 signature/apiuser。"""
        return (
            self.base_url
            + f"/api/v1/panel?host_name={quote(host_name)}&panel_password={quote(panel_password)}"
        )

    async def terminate(self) -> None:
        await self.close()
