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

"""qzweb(至简Stack) ``/api/whmcs/*`` 后端适配器。

对外暴露与 :class:`qz_plugin.client.QzsystemClient` 完全相同的接口
(``post`` / ``post_data`` / ``build_panel_url`` / ``configured`` /
``missing_credentials`` / ``close`` / ``terminate``)，内部把命令层按 v1
语义发出的 ``/api/v1/*`` 路径 + JSON body 翻译为 qzweb 的
``/api/whmcs/<action>`` + 表单 + ``apikey`` 头 + ``code==1`` 约定，
并把响应归一化回 v1 字段形状，使上层命令模块无须感知后端差异。

qzweb 的 whmcs 接口能力子集小于标准 qzsystem 主控：未覆盖的操作（运行截图、
历史监控、时间同步、BIOS、IP 增删、ISO 挂载、NAT 域名、面板密码重置等）
会抛 :class:`QzsystemError`，由命令层友好提示。

参考实现：``.temp_development_problem/魔方对接轻舟插件/qzvps/qzvps.php``（财务
插件，已验证可对接 qzweb）与 ``qzweb(主控)/app/api/controller/Whmcs.php``。
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any
from urllib.parse import quote

import aiohttp

from .client import QzsystemError
from . import endpoints as E

# whmcs HostVps.state → 中文状态名（与 v1 info 的 state_name 对齐，尽力而为）
_STATE_NAME = {0: "已关机", 1: "创建中", 2: "运行中", 3: "已停止", 4: "已暂停"}


def _unsupported(path: str, hint: str = "") -> QzsystemError:
    msg = f"当前后端 qzweb(whmcs) 不支持该操作（{path}）。"
    if hint:
        msg += hint
    msg += "如需使用，请在 WebUI 插件配置把“后端类型”改为 v1 并对接标准 qzsystem 主控。"
    return QzsystemError(msg)


class WhmcsClient:
    """qzweb ``/api/whmcs/*`` 后端，接口与 :class:`QzsystemClient` 一致。"""

    def __init__(self, base_url: str, apikey: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.apikey = (apikey or "").strip()
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self._handlers: dict[str, Any] = {
            E.INFO: self._info,
            E.OPEN_HOST: self._open_host,
            E.UPDATE_HOST: self._update_host,
            E.REMOVE_HOST: self._remove_host,
            E.RENEW: self._renew,
            E.POWER: self._power,
            E.MONITOR: self._monitor,
            E.THUMBNAIL: self._uns(E.THUMBNAIL, "（qzweb 无运行截图接口）"),
            E.HISTORY_NETWORK: self._uns(E.HISTORY_NETWORK, "（qzweb 无历史网络监控）"),
            E.HISTORY_CPU: self._uns(E.HISTORY_CPU, "（qzweb 无历史 CPU 监控）"),
            E.SYNCTIME: self._uns(E.SYNCTIME, "（qzweb 无时间同步接口）"),
            E.UPDATE_OS_PASSWORD: self._reset_os_pwd,
            E.UPDATE_PANEL_PASSWORD: self._uns(
                E.UPDATE_PANEL_PASSWORD, "（qzweb 无面板密码重置接口）"
            ),
            E.OS_LIST: self._images,
            E.INSTALL_OS: self._reinstall,
            E.ISO_LIST: self._iso_list,
            E.MOUNT_ISO: self._uns(E.MOUNT_ISO, "（qzweb 无 ISO 挂载接口）"),
            E.SET_BIOS: self._uns(E.SET_BIOS, "（qzweb 无 BIOS 引导接口）"),
            E.ADD_IP: self._uns(E.ADD_IP, "（qzweb 无 IP 新增接口）"),
            E.REMOVE_IP: self._uns(E.REMOVE_IP, "（qzweb 无 IP 删除接口）"),
            E.SNAPSHOT_LIST: self._snap_list,
            E.CREATE_SNAPSHOT: self._snap_create,
            E.REMOVE_SNAPSHOT: self._snap_del,
            E.RESTORE_SNAPSHOT: self._snap_restore,
            E.BACKUP_LIST: self._backup_list,
            E.CREATE_BACKUP: self._backup_create,
            E.REMOVE_BACKUP: self._backup_del,
            E.RESTORE_BACKUP: self._backup_restore,
            E.FIREWALL_LIST: self._fw_list,
            E.ADD_FIREWALL: self._fw_add,
            E.REMOVE_FIREWALL: self._fw_del,
            E.NAT_PORT_LIST: self._port_list,
            E.NAT_ADD_PORT: self._port_add,
            E.NAT_REMOVE_PORT: self._port_del,
            E.NAT_FIND_PORT: self._uns(E.NAT_FIND_PORT, "（qzweb 无独立端口查询接口）"),
            E.NAT_DOMAIN_LIST: self._uns(
                E.NAT_DOMAIN_LIST, "（qzweb 无 NAT 域名接口）"
            ),
            E.NAT_ADD_DOMAIN: self._uns(E.NAT_ADD_DOMAIN, "（qzweb 无 NAT 域名接口）"),
            E.NAT_REMOVE_DOMAIN: self._uns(
                E.NAT_REMOVE_DOMAIN, "（qzweb 无 NAT 域名接口）"
            ),
            E.VNC: self._vnc,
            E.TEST: self._test,
        }

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.apikey)

    def missing_credentials(self) -> list[str]:
        missing: list[str] = []
        if not self.base_url:
            missing.append("base_url（qzweb 主控基础地址）")
        if not self.apikey:
            missing.append("apikey（qzweb 后台 apikey，对应财务插件 accesshash）")
        return missing

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.apikey}

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def terminate(self) -> None:
        await self.close()

    # ---- 底层 whmcs 调用 ----
    async def _whmcs(self, action: str, params: dict[str, Any] | None = None) -> Any:
        """POST 表单到 ``/api/whmcs/<action>``，``code != 1`` 抛错，返回 ``data``。

        Args:
            action: whmcs 控制器方法名（如 ``hostinfo``）。
            params: 表单字段；值会被 ``str()`` 化。

        Returns:
            whmcs 响应的 ``data`` 字段。

        Raises:
            QzsystemError: 网络异常、响应非 JSON 或 ``code != 1``。
        """
        url = self.base_url + "/api/whmcs/" + action
        form = {k: ("" if v is None else str(v)) for k, v in (params or {}).items()}
        session = await self._ensure_session()
        try:
            async with session.post(url, data=form, headers=self._headers()) as resp:
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
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise QzsystemError(f"请求超时: {exc}") from exc

        if not isinstance(payload, dict):
            raise QzsystemError(f"响应不是对象: {str(payload)[:200]}", payload=payload)
        code = payload.get("code")
        if code != 1:
            msg = payload.get("msg") or payload.get("message") or "未知错误"
            raise QzsystemError(str(msg), code=code, payload=payload)
        return payload.get("data")

    # ---- 对外接口 ----
    async def post(
        self, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """按 v1 路径分发到 whmcs，返回 v1 形状的 ``{msg, code, time, data}``。"""
        if not self.configured:
            raise QzsystemError(
                "qzweb(whmcs) 凭证未配置，请在 WebUI 插件配置里补填以下项："
                + "、".join(self.missing_credentials())
            )
        handler = self._handlers.get(path)
        if handler is None:
            raise _unsupported(path)
        data = await handler(body or {})
        return {"msg": "success", "code": 200, "time": int(time.time()), "data": data}

    async def post_data(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return (await self.post(path, body)).get("data")

    def build_panel_url(self, host_name: str, panel_password: str) -> str:
        """qzweb 控制台登录跳转：``/api/whmcs/panel?host_name=&panel_password=``。"""
        return (
            self.base_url
            + f"/api/whmcs/panel?host_name={quote(host_name)}&panel_password={quote(panel_password)}"
        )

    # ---- 不支持的操作 ----
    def _uns(self, path: str, hint: str = "") -> Any:
        """构造一个抛 ``QzsystemError`` 的异步 handler，供分发表使用。"""

        async def _h(_body: dict[str, Any]) -> Any:
            raise _unsupported(path, hint)

        return _h

    # ---- 实例生命周期 ----
    async def _info(self, body: dict[str, Any]) -> dict[str, Any]:
        d = await self._whmcs("hostinfo", {"host_id": body.get("hostid")})
        return self._norm_info(d if isinstance(d, dict) else {})

    async def _remove_host(self, body: dict[str, Any]) -> Any:
        return await self._whmcs("delete", {"host_id": body.get("hostid")})

    async def _renew(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "renew",
            {"host_id": body.get("hostid"), "nextduedate": body.get("nextduedate")},
        )

    async def _power(self, body: dict[str, Any]) -> Any:
        state = body.get("state")
        action_map = {
            str(E.POWER_ON): "start",
            str(E.POWER_SOFT_OFF): "shutdown",
            str(E.POWER_REBOOT): "reboot",
        }
        action = action_map.get(str(state))
        if action is None:
            raise _unsupported(
                E.POWER, "（qzweb whmcs 仅支持 开机/软关机/重启，不支持断开电源）"
            )
        return await self._whmcs(action, {"host_id": body.get("hostid")})

    async def _open_host(self, body: dict[str, Any]) -> dict[str, Any]:
        # 把 v1 openHost 向导收集的字段映射到 qzweb create_host 表单
        sys_pwd = body.get("sys_pwd", "")
        params: dict[str, Any] = {
            "nodes_id": body.get("nodes_id", ""),
            "line_id": body.get("line_id", ""),
            "os": body.get("os_name", ""),
            "cpu": body.get("cpu", ""),
            "memory": body.get("memory", ""),
            "hard_disks": body.get("sys_disk_size") or body.get("data_disk_size", ""),
            "bandwidth": body.get("net_out", ""),
            "sys_pwd": sys_pwd,
            "vnc_pwd": sys_pwd,
            "expire_time": body.get("expire_time", ""),
            "ipnum": body.get("ip_num", 0),
            "host_name": body.get("host_name", ""),
        }
        if body.get("snapshot"):
            params["snapshot"] = body.get("snapshot")
        if body.get("backups"):
            params["backups"] = body.get("backups")
        if body.get("port_num"):
            params["port_num"] = body.get("port_num")
        if body.get("domain_num"):
            params["domain_num"] = body.get("domain_num")
        d = await self._whmcs("create_host", params)
        return self._norm_create(d if isinstance(d, dict) else {})

    async def _update_host(self, body: dict[str, Any]) -> Any:
        raise _unsupported(
            E.UPDATE_HOST,
            "（qzweb whmcs 升级按套餐 product_id 进行，与本插件按规格升级语义不兼容）",
        )

    # ---- 监控 ----
    async def _monitor(self, body: dict[str, Any]) -> dict[str, Any]:
        d = await self._whmcs("monitor", {"host_id": body.get("hostid")})
        return self._norm_monitor(d if isinstance(d, dict) else {})

    # ---- 密码与系统 ----
    async def _reset_os_pwd(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "reset_password",
            {"host_id": body.get("hostid"), "password": body.get("password")},
        )

    async def _reinstall(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "reset_os",
            {
                "host_id": body.get("hostid"),
                "template_id": body.get("template"),
                "password": body.get("password"),
            },
        )

    async def _images(self, body: dict[str, Any]) -> Any:
        return await self._whmcs("mirror_image", {})

    async def _iso_list(self, body: dict[str, Any]) -> Any:
        return await self._whmcs("cdrom", {"host_id": body.get("hostid", 0)})

    # ---- 快照 ----
    async def _snap_list(self, body: dict[str, Any]) -> dict[str, Any]:
        d = await self._whmcs("snapshot_list", {"host_id": body.get("hostid")})
        return self._norm_list(d)

    async def _snap_create(self, body: dict[str, Any]) -> Any:
        return await self._whmcs("snapshot_add", {"host_id": body.get("hostid")})

    async def _snap_del(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "snapshot_del", {"host_id": body.get("hostid"), "id": body.get("id")}
        )

    async def _snap_restore(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "snapshot_restore", {"host_id": body.get("hostid"), "id": body.get("id")}
        )

    # ---- 备份 ----
    async def _backup_list(self, body: dict[str, Any]) -> dict[str, Any]:
        d = await self._whmcs("backups_list", {"host_id": body.get("hostid")})
        return self._norm_list(d)

    async def _backup_create(self, body: dict[str, Any]) -> Any:
        return await self._whmcs("backups_add", {"host_id": body.get("hostid")})

    async def _backup_del(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "backups_del", {"host_id": body.get("hostid"), "id": body.get("id")}
        )

    async def _backup_restore(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "backups_restore", {"host_id": body.get("hostid"), "id": body.get("id")}
        )

    # ---- 防火墙 ----
    async def _fw_list(self, body: dict[str, Any]) -> dict[str, Any]:
        d = await self._whmcs("security_acl_list", {"host_id": body.get("hostid")})
        arr: list[Any] = []
        if isinstance(d, list):
            arr = d
        elif isinstance(d, dict):
            arr = [d]
        return {"data": arr, "extend": {"count": len(arr)}}

    async def _fw_add(self, body: dict[str, Any]) -> Any:
        # Whmcs.php security_acl_add 把 $post 原样传给 Ecs::add_firewall_host，
        # 后者读 $param['hostid']（非 host_id），故此处保持 hostid 不改名。
        params = {k: v for k, v in body.items() if v is not None}
        return await self._whmcs("security_acl_add", params)

    async def _fw_del(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "security_acl_del",
            {"host_id": body.get("hostid"), "id": body.get("id")},
        )

    # ---- NAT 端口 ----
    async def _port_list(self, body: dict[str, Any]) -> Any:
        return await self._whmcs("nat_acl_list", {"host_id": body.get("hostid")})

    async def _port_add(self, body: dict[str, Any]) -> Any:
        return await self._whmcs(
            "add_port_host",
            {
                "host_id": body.get("hostid"),
                "dport": body.get("dport", ""),
                "sport": body.get("sport", ""),
                "name": body.get("name", ""),
            },
        )

    async def _port_del(self, body: dict[str, Any]) -> Any:
        # Whmcs.php remove_port_host 把 $param 原样传给 Ecs::remove_forward_port，
        # 后者读 $param['hostid']（非 host_id），故此处用 hostid。
        return await self._whmcs(
            "remove_port_host",
            {"hostid": body.get("hostid"), "id": body.get("id")},
        )

    # ---- VNC / 测试 ----
    async def _vnc(self, body: dict[str, Any]) -> dict[str, str]:
        # qzweb vnc_view 是 302 跳转，直接本地拼出目标 URL，避免一次无意义的 HTTP 往返
        host_id = str(body.get("hostid") or "")
        token = hashlib.md5((host_id + self.apikey).encode("utf-8")).hexdigest()
        url = f"{self.base_url}/control/ecs/vnc?hostid={host_id}&token={token}"
        return {"url": url}

    async def _test(self, body: dict[str, Any]) -> list[dict[str, str]]:
        # whmcs 无 v1 test 接口；用 product 做鉴权+连通性探活，返回一条诊断信息
        d = await self._whmcs("product", {})
        n = len(d) if isinstance(d, (list, dict)) else 0
        return [
            {
                "host_name": "qzweb(至简Stack)",
                "domain": f"后端连通正常，产品 {n} 个",
                "api_url": self.base_url,
                "dip": "",
            }
        ]

    # ---- 响应归一化（whmcs → v1 字段形状）----
    @staticmethod
    def _norm_info(d: dict[str, Any]) -> dict[str, Any]:
        info = dict(d)
        state = d.get("state")
        info.setdefault(
            "state_name",
            d.get("state_name")
            or _STATE_NAME.get(state, str(state) if state is not None else ""),
        )
        if d.get("bandwidth") is not None:
            info.setdefault("bandwidth_out", d.get("bandwidth"))
        rip = d.get("remote_ip") or ""
        if rip and ":" in rip:
            addr, _, port = rip.rpartition(":")
            info.setdefault("remote_addr", addr)
            info.setdefault("remote_port", port)
        elif rip:
            info.setdefault("remote_addr", rip)
        net = d.get("network") or {}
        eth1 = net.get("eth1")
        if isinstance(eth1, list):
            info.setdefault("attachip", eth1)
        return info

    @staticmethod
    def _norm_create(d: dict[str, Any]) -> dict[str, Any]:
        out = dict(d)
        out.setdefault("id", d.get("host_id") or d.get("id"))
        state = d.get("state")
        out.setdefault(
            "state_name",
            d.get("state_name")
            or _STATE_NAME.get(state, str(state) if state is not None else ""),
        )
        return out

    @staticmethod
    def _norm_monitor(d: dict[str, Any]) -> dict[str, Any]:
        # qzweb Kvm monitorHost 返回 {CpuStats, MemoryStats, NetworkStats: [[time,up,down],...]}
        # 其中 up/down 为 Mbps；取最末一行作为瞬时上下行带宽。流量本接口不提供。
        net = d.get("NetworkStats")
        bw_out = bw_in = ""
        if isinstance(net, list) and net:
            last = net[-1]
            if isinstance(last, (list, tuple)) and len(last) >= 3:
                bw_out = last[1]
                bw_in = last[2]
        return {
            "cpu": d.get("CpuStats", d.get("cpu", "")),
            "memory": d.get("MemoryStats", d.get("memory", "")),
            "bwOut": d.get("bwOut") or bw_out,
            "bwIn": d.get("bwIn") or bw_in,
            "trafficOut": d.get("trafficOut", ""),
            "trafficIn": d.get("trafficIn", ""),
        }

    @staticmethod
    def _norm_list(d: Any) -> dict[str, Any]:
        """快照/备份列表归一：whmcs 返回 ``[{id,virtuals_id,name,created_at}]``。"""
        arr = d if isinstance(d, list) else []
        out = []
        for it in arr:
            if not isinstance(it, dict):
                continue
            out.append(
                {
                    "id": it.get("id"),
                    "name": it.get("name", ""),
                    "host_id": it.get("virtuals_id"),
                    "state": it.get("state", 2),
                    "create_time": it.get("created_at") or it.get("create_time", ""),
                    "update_time": it.get("update_time", ""),
                }
            )
        return {"data": out, "extend": {"count": len(out)}}


__all__ = ["WhmcsClient"]
