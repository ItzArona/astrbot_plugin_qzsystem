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

"""插件配置的类型化访问包装。"""

from __future__ import annotations

from typing import Any


class PluginConfig:
    def __init__(self, config: dict[str, Any]) -> None:
        self._c = config

    @property
    def base_url(self) -> str:
        return str(self._c.get("base_url", "") or "").strip()

    @property
    def backend(self) -> str:
        """后端类型：``v1``（标准 qzsystem 主控 /api/v1/*）或 ``whmcs``（qzweb/至简Stack /api/whmcs/*）。

        未配置时根据已填凭证推断：填了 apikey 视为 whmcs，填了 signature 视为 v1，
        以兼容旧配置。
        """
        v = str(self._c.get("backend", "") or "").strip().lower()
        if v in ("v1", "whmcs"):
            return v
        if self.apikey and not self.signature:
            return "whmcs"
        return "v1"

    @property
    def signature(self) -> str:
        return str(self._c.get("signature", "") or "").strip()

    @property
    def apiuser(self) -> str:
        return str(self._c.get("apiuser", "") or "").strip()

    @property
    def apikey(self) -> str:
        """qzweb(whmcs) 后端的 apikey（主控后台配置的 apikey，对应财务插件 accesshash）。"""
        return str(self._c.get("apikey", "") or "").strip()

    @property
    def hosts(self) -> list[dict[str, str]]:
        """别名表，过滤掉非 dict 条目与 template_list 的 __template_key 元字段。"""
        out: list[dict[str, str]] = []
        for item in self._c.get("hosts", []) or []:
            if not isinstance(item, dict):
                continue
            entry = {
                "alias": str(item.get("alias", "") or "").strip(),
                "hostid": str(item.get("hostid", "") or "").strip(),
                "remark": str(item.get("remark", "") or ""),
            }
            if entry["alias"] and entry["hostid"]:
                out.append(entry)
        return out

    @property
    def request_timeout(self) -> int:
        try:
            return int(self._c.get("request_timeout", 30))
        except (TypeError, ValueError):
            return 30

    @property
    def text_to_image_threshold(self) -> int:
        try:
            return int(self._c.get("text_to_image_threshold", 150))
        except (TypeError, ValueError):
            return 150

    @property
    def redact_in_group(self) -> bool:
        return bool(self._c.get("redact_in_group", True))

    @property
    def require_confirm(self) -> bool:
        return bool(self._c.get("require_confirm", True))

    def alias_to_hostid(self, alias: str) -> str | None:
        """别名 -> hostid；找不到返回 None。纯数字直接当 hostid 返回。"""
        alias = (alias or "").strip()
        if not alias:
            return None
        if alias.isdigit():
            return alias
        for item in self.hosts:
            if item["alias"] == alias:
                return item["hostid"]
        return None

    def hostid_to_alias(self, hostid: str) -> str:
        hostid = str(hostid)
        for item in self.hosts:
            if item["hostid"] == hostid:
                return item["alias"]
        return hostid
