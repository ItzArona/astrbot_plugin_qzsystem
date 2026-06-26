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

"""后端客户端工厂。

独立成新模块（而非放在 ``client.py``）的原因：插件 ``main.py`` 顶部有
``sys.path.insert(0, _PLUGIN_DIR)`` 垫片，子包以**裸名** ``qz_plugin.client``
被导入；而 AstrBot 重载插件时只清理 ``sys.modules`` 里 ``data.plugins.<插件名>`` 前缀
的键，不会清理这些裸名子模块。于是新增到既有模块 ``client.py`` 的符号
（``build_client``）在热重载时命中旧缓存而 ``ImportError``。把工厂放到一个**新文件**
里——新文件首次重载时不在 ``sys.modules``，必从磁盘重新导入，从而绕开旧缓存。
"""

from __future__ import annotations

from typing import Any

from .client import QzsystemClient


def build_client(cfg: Any) -> QzsystemClient | Any:
    """按配置的 ``backend`` 选择并构造客户端。

    Args:
        cfg: :class:`qz_plugin.config.PluginConfig`。

    Returns:
        v1 后端返回 :class:`QzsystemClient`；whmcs 后端返回
        :class:`qz_plugin.whmcs_client.WhmcsClient`。两者接口一致。
    """
    if cfg.backend == "whmcs":
        from .whmcs_client import WhmcsClient

        return WhmcsClient(
            base_url=cfg.base_url,
            apikey=cfg.apikey,
            timeout=cfg.request_timeout,
        )
    return QzsystemClient(
        base_url=cfg.base_url,
        signature=cfg.signature,
        apiuser=cfg.apiuser,
        timeout=cfg.request_timeout,
    )


__all__ = ["build_client"]
