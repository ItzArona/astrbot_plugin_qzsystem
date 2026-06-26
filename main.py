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

"""AstrBot 插件：轻舟云(qzsystem)主控管理。

类型：命令（@filter.command / command_group），不暴露为 LLM 工具。
覆盖 qzsystem 全部 41 个接口，按 /server /snapshot /backup /firewall /nat /test /qz 分组。
"""

# ruff: noqa: E402
from __future__ import annotations

import os
import sys
from typing import Any

# 确保插件目录在 sys.path 上，使 ``qz_plugin`` 子包可被绝对导入。
# 无论 AstrBot 以“顶层模块 main”还是“包. main”方式加载本插件均生效。
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from qz_plugin.backend import build_client
from qz_plugin.config import PluginConfig
from qz_plugin.render import emit
from qz_plugin.store import bind_user, resolve_hostid, unbind_user

# 命令业务实现
from qz_plugin.server import (
    server_bios,
    server_cpu_history,
    server_create,
    server_delete,
    server_images,
    server_info,
    server_ip_add,
    server_ip_del,
    server_iso_list,
    server_iso_mount,
    server_iso_unmount,
    server_monitor,
    server_net_history,
    server_panel,
    server_power,
    server_reinstall,
    server_renew,
    server_reset_os_pwd,
    server_reset_panel_pwd,
    server_screenshot,
    server_synctime,
    server_upgrade,
    server_vnc,
)
from qz_plugin.snapshot import (
    snapshot_create,
    snapshot_del,
    snapshot_list,
    snapshot_restore,
)
from qz_plugin.backup import backup_create, backup_del, backup_list, backup_restore
from qz_plugin.firewall import firewall_add, firewall_del, firewall_list
from qz_plugin.nat import (
    nat_domain_add,
    nat_domain_del,
    nat_domain_list,
    nat_port_add,
    nat_port_del,
    nat_port_find,
    nat_port_list,
)
from qz_plugin.test_cmd import test_ping

HELP_TEXT = """轻舟云主机管理插件 · 命令帮助

绑定实例：/qz bind <别名|hostid>   /qz unbind   /qz whoami
查询类(全员)：
  /server info|monitor|screenshot|cpu-history|net-history|images|iso-list [别名]
  /snapshot list [别名]   /backup list [别名]
  /firewall list [别名] [dir=in|out] [method=accept|drop] [proto=TCP|UDP|ICMP|ANY] [page=N]
  /nat port list [别名]   /nat port find <关键词> [别名]   /nat domain list [别名]
管理员·写操作：
  /server power <on|off|cut|reboot> [别名]
  /server synctime <on|off> [别名]   /server bios <disk|cd> [别名]
  /server iso mount <名称> [别名]   /server iso unmount [别名]
  /server upgrade [别名] cpu=.. memory=.. sys_disk=.. data_disk=.. net_out=.. net_in=.. flow_limit=..
  /server renew <30d|12m|1y|YYYY-MM-DD> [别名]
  /server reset-os-pwd <新密码> [别名]   /server reset-panel-pwd <新密码> [别名]
  /server reinstall <镜像> <新密码> [别名]
  /server delete [别名] confirm
  /server create   (多轮向导，建议私聊)
  /server ip add <数量> [别名]   /server ip del <ip> [别名]
  /snapshot create [别名]   /snapshot del <id> [别名]   /snapshot restore <id> [别名] confirm
  /backup create [别名]   /backup del <id> [别名]   /backup restore <id> [别名] confirm
  /firewall add <in|out> <accept|drop> <TCP|UDP|ICMP|ANY> <端口|ANY> <IP|ANY> [priority=N] [remark=..] [alias=..]
  /firewall del <id> [alias=..]
  /nat port add <dport> [sport=..] [name=..] [alias=..]   /nat port del <id> [alias=..]
  /nat domain add <域名> [alias=..]   /nat domain del <id> [alias=..]
管理员·凭证类(群聊脱敏+私聊全文)：
  /server vnc [别名]   /server panel [别名]
联调：/test ping [别名]   (管理员)

说明：[别名] 可为别名或 hostid 数字；未带则使用 /qz bind 绑定的默认实例。
含凭证命令请在私聊执行；高危操作末尾需带 confirm。
后端：WebUI 配置“后端类型”选 v1(标准 qzsystem) 或 whmcs(qzweb/至简Stack)；whmcs 后端不支持截图/历史监控/时间同步/BIOS/IP增删/ISO/NAT域名/面板密码重置。"""


class QzsystemPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.cfg = PluginConfig(config or {})
        self.client = build_client(self.cfg)
        if not self.client.configured:
            cred = "apikey" if self.cfg.backend == "whmcs" else "signature/apiuser"
            logger.warning(
                f"[qzsystem] 凭证未配置（后端={self.cfg.backend}），"
                f"请在 WebUI 插件配置里填写 base_url/{cred}。"
            )

    async def terminate(self) -> None:
        """插件卸载/停用时关闭 HTTP 会话。"""
        await self.client.close()

    # ---------- /qz 元命令 ----------
    @filter.command_group("qz", alias={"轻舟", "qzsystem"})
    def qz_group(self) -> None:
        """轻舟云管理元命令"""
        pass

    @qz_group.command("help", alias={"帮助"})
    async def qz_help(self, event: AstrMessageEvent) -> Any:
        """查看命令帮助"""
        yield event.plain_result(HELP_TEXT)

    @qz_group.command("bind", alias={"绑定"})
    async def qz_bind(self, event: AstrMessageEvent, target: str = "") -> Any:
        """绑定当前用户的默认云主机：/qz bind <别名|hostid>"""
        yield event.plain_result(await bind_user(self, event, target))

    @qz_group.command("unbind", alias={"解绑"})
    async def qz_unbind(self, event: AstrMessageEvent) -> Any:
        """解除当前用户的默认实例绑定"""
        yield event.plain_result(await unbind_user(self, event))

    @qz_group.command("whoami", alias={"当前"})
    async def qz_whoami(self, event: AstrMessageEvent) -> Any:
        """查看当前绑定的默认实例"""
        try:
            hostid, label = await resolve_hostid(self, event, "")
        except ValueError as exc:
            yield event.plain_result(str(exc))
            return
        yield event.plain_result(f"当前默认实例：{label} (hostid={hostid})")

    # ---------- /server ----------
    @filter.command_group("server", alias={"云主机", "host"})
    def server_group(self) -> None:
        """云主机实例管理"""
        pass

    @server_group.command("info", alias={"信息", "详情"})
    async def server_info_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """云主机详细信息"""
        text = await server_info(self, event, alias)
        if text:
            yield await emit(self, event, text, title="云主机信息")

    @server_group.command("monitor", alias={"监控"})
    async def server_monitor_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """实时监控(CPU/内存/带宽/流量)"""
        text = await server_monitor(self, event, alias)
        if text:
            yield await emit(self, event, text, title="实时监控")

    @server_group.command("screenshot", alias={"截图", "屏幕"})
    async def server_screenshot_h(
        self, event: AstrMessageEvent, alias: str = ""
    ) -> Any:
        """运行屏幕截图"""
        text = await server_screenshot(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @server_group.command("cpu-history", alias={"cpu历史"})
    async def server_cpu_history_h(
        self, event: AstrMessageEvent, alias: str = ""
    ) -> Any:
        """近三天 CPU 历史摘要"""
        text = await server_cpu_history(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @server_group.command("net-history", alias={"网络历史"})
    async def server_net_history_h(
        self, event: AstrMessageEvent, alias: str = ""
    ) -> Any:
        """近三天网络历史摘要"""
        text = await server_net_history(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @server_group.command("images", alias={"镜像", "系统镜像"})
    async def server_images_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """可用系统镜像列表"""
        text = await server_images(self, event, alias)
        if text:
            yield await emit(self, event, text, title="可用镜像")

    @server_group.command("iso-list", alias={"iso列表"})
    async def server_iso_list_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """iso 文件列表"""
        text = await server_iso_list(self, event, alias)
        if text:
            yield await emit(self, event, text, title="ISO 文件")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("vnc", alias={"远程桌面"})
    async def server_vnc_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """获取 VNC 远程地址(含凭证，群聊脱敏+私聊全文)"""
        text = await server_vnc(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("panel", alias={"控制台"})
    async def server_panel_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """获取独立控制台登录链接(含面板密码，群聊脱敏+私聊全文)"""
        text = await server_panel(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("power", alias={"电源"})
    async def server_power_h(
        self, event: AstrMessageEvent, action: str, alias: str = ""
    ) -> Any:
        """电源操作：on/off/cut/reboot"""
        text = await server_power(self, event, action, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("synctime", alias={"时间同步"})
    async def server_synctime_h(
        self, event: AstrMessageEvent, mode: str, alias: str = ""
    ) -> Any:
        """同步宿主机时间：on/off"""
        text = await server_synctime(self, event, mode, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("bios", alias={"引导"})
    async def server_bios_h(
        self, event: AstrMessageEvent, mode: str, alias: str = ""
    ) -> Any:
        """设置 BIOS 引导顺序：disk/cd"""
        text = await server_bios(self, event, mode, alias)
        if text:
            yield await emit(self, event, text)

    @server_group.group("iso")
    def server_iso_group(self) -> None:
        """iso 挂载管理"""
        pass

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_iso_group.command("mount", alias={"挂载"})
    async def server_iso_mount_h(
        self, event: AstrMessageEvent, name: str, alias: str = ""
    ) -> Any:
        """挂载 iso：/server iso mount <名称> [别名]"""
        text = await server_iso_mount(self, event, name, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_iso_group.command("unmount", alias={"卸载"})
    async def server_iso_unmount_h(
        self, event: AstrMessageEvent, alias: str = ""
    ) -> Any:
        """卸载 iso"""
        text = await server_iso_unmount(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("reset-os-pwd", alias={"重置系统密码"})
    async def server_reset_os_pwd_h(
        self, event: AstrMessageEvent, password: str, alias: str = ""
    ) -> Any:
        """重置系统密码(建议私聊执行)"""
        text = await server_reset_os_pwd(self, event, password, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("reset-panel-pwd", alias={"重置面板密码"})
    async def server_reset_panel_pwd_h(
        self, event: AstrMessageEvent, password: str, alias: str = ""
    ) -> Any:
        """重置面板密码(建议私聊执行)"""
        text = await server_reset_panel_pwd(self, event, password, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("reinstall", alias={"重装系统"})
    async def server_reinstall_h(
        self, event: AstrMessageEvent, template: str, password: str, alias: str = ""
    ) -> Any:
        """重装系统(高危，建议私聊执行)"""
        text = await server_reinstall(self, event, template, password, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("upgrade", alias={"升降配"})
    async def server_upgrade_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """升降配：/server upgrade [别名] cpu=.. memory=.. sys_disk=.. ..."""
        text = await server_upgrade(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("renew", alias={"续费"})
    async def server_renew_h(
        self, event: AstrMessageEvent, duration: str, alias: str = ""
    ) -> Any:
        """续费：/server renew <30d|12m|1y|日期> [别名]"""
        text = await server_renew(self, event, duration, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("delete", alias={"删除"})
    async def server_delete_h(
        self, event: AstrMessageEvent, alias: str = "", confirm: str = ""
    ) -> Any:
        """删除云主机(高危，末尾需带 confirm)"""
        text = await server_delete(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_group.command("create", alias={"创建", "开通"})
    async def server_create_h(self, event: AstrMessageEvent) -> Any:
        """创建云主机(多轮向导，建议私聊执行)"""
        yield event.plain_result("🛠 开始创建云主机向导（回复“取消”随时退出）。")
        await server_create(self, event)

    @server_group.group("ip")
    def server_ip_group(self) -> None:
        """IP 管理"""
        pass

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_ip_group.command("add", alias={"新增ip"})
    async def server_ip_add_h(
        self, event: AstrMessageEvent, num: str, alias: str = ""
    ) -> Any:
        """新增附加 IP：/server ip add <数量> [别名]"""
        text = await server_ip_add(self, event, num, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @server_ip_group.command("del", alias={"删除ip"})
    async def server_ip_del_h(
        self, event: AstrMessageEvent, ip: str, alias: str = ""
    ) -> Any:
        """删除附加 IP：/server ip del <ip> [别名]"""
        text = await server_ip_del(self, event, ip, alias)
        if text:
            yield await emit(self, event, text)

    # ---------- /snapshot ----------
    @filter.command_group("snapshot", alias={"快照"})
    def snapshot_group(self) -> None:
        """快照管理"""
        pass

    @snapshot_group.command("list", alias={"列表"})
    async def snapshot_list_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """快照列表"""
        text = await snapshot_list(self, event, alias)
        if text:
            yield await emit(self, event, text, title="快照列表")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @snapshot_group.command("create", alias={"创建"})
    async def snapshot_create_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """创建快照"""
        text = await snapshot_create(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @snapshot_group.command("del", alias={"删除"})
    async def snapshot_del_h(
        self, event: AstrMessageEvent, id: str, alias: str = ""
    ) -> Any:
        """删除快照：/snapshot del <id> [别名]"""
        text = await snapshot_del(self, event, id, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @snapshot_group.command("restore", alias={"恢复"})
    async def snapshot_restore_h(
        self, event: AstrMessageEvent, id: str, alias: str = "", confirm: str = ""
    ) -> Any:
        """恢复快照(高危，末尾需带 confirm)"""
        text = await snapshot_restore(self, event, id, alias)
        if text:
            yield await emit(self, event, text)

    # ---------- /backup ----------
    @filter.command_group("backup", alias={"备份"})
    def backup_group(self) -> None:
        """备份管理"""
        pass

    @backup_group.command("list", alias={"列表"})
    async def backup_list_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """备份列表"""
        text = await backup_list(self, event, alias)
        if text:
            yield await emit(self, event, text, title="备份列表")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @backup_group.command("create", alias={"创建"})
    async def backup_create_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """创建备份"""
        text = await backup_create(self, event, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @backup_group.command("del", alias={"删除"})
    async def backup_del_h(
        self, event: AstrMessageEvent, id: str, alias: str = ""
    ) -> Any:
        """删除备份：/backup del <id> [别名]"""
        text = await backup_del(self, event, id, alias)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @backup_group.command("restore", alias={"恢复"})
    async def backup_restore_h(
        self, event: AstrMessageEvent, id: str, alias: str = "", confirm: str = ""
    ) -> Any:
        """恢复备份(高危，末尾需带 confirm)"""
        text = await backup_restore(self, event, id, alias)
        if text:
            yield await emit(self, event, text)

    # ---------- /firewall ----------
    @filter.command_group("firewall", alias={"防火墙"})
    def firewall_group(self) -> None:
        """防火墙策略管理"""
        pass

    @firewall_group.command("list", alias={"列表"})
    async def firewall_list_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """防火墙策略列表"""
        text = await firewall_list(self, event, alias)
        if text:
            yield await emit(self, event, text, title="防火墙策略")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @firewall_group.command("add", alias={"添加"})
    async def firewall_add_h(
        self,
        event: AstrMessageEvent,
        direction: str,
        method: str,
        protocol: str,
        port: str,
        ip: str,
    ) -> Any:
        """添加策略：/firewall add <in|out> <accept|drop> <TCP|UDP|ICMP|ANY> <端口|ANY> <IP|ANY>"""
        text = await firewall_add(self, event, direction, method, protocol, port, ip)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @firewall_group.command("del", alias={"删除"})
    async def firewall_del_h(
        self, event: AstrMessageEvent, id: str, alias: str = ""
    ) -> Any:
        """删除策略：/firewall del <id> [alias=..]"""
        text = await firewall_del(self, event, id)
        if text:
            yield await emit(self, event, text)

    # ---------- /nat ----------
    @filter.command_group("nat", alias={"挂机宝"})
    def nat_group(self) -> None:
        """NAT 挂机宝端口与域名管理"""
        pass

    @nat_group.group("port")
    def nat_port_group(self) -> None:
        """NAT 端口映射"""
        pass

    @nat_port_group.command("list", alias={"列表"})
    async def nat_port_list_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """NAT 端口映射列表"""
        text = await nat_port_list(self, event, alias)
        if text:
            yield await emit(self, event, text, title="NAT 端口映射")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @nat_port_group.command("add", alias={"添加"})
    async def nat_port_add_h(self, event: AstrMessageEvent, dport: str) -> Any:
        """添加端口映射：/nat port add <dport> [sport=..] [name=..] [alias=..]"""
        text = await nat_port_add(self, event, dport)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @nat_port_group.command("del", alias={"删除"})
    async def nat_port_del_h(
        self, event: AstrMessageEvent, id: str, alias: str = ""
    ) -> Any:
        """删除端口映射：/nat port del <id> [alias=..]"""
        text = await nat_port_del(self, event, id)
        if text:
            yield await emit(self, event, text)

    @nat_port_group.command("find", alias={"查询"})
    async def nat_port_find_h(
        self, event: AstrMessageEvent, keywords: str, alias: str = ""
    ) -> Any:
        """查询可用端口：/nat port find <关键词> [别名]"""
        text = await nat_port_find(self, event, keywords, alias)
        if text:
            yield await emit(self, event, text)

    @nat_group.group("domain")
    def nat_domain_group(self) -> None:
        """NAT 域名管理"""
        pass

    @nat_domain_group.command("list", alias={"列表"})
    async def nat_domain_list_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """NAT 域名列表"""
        text = await nat_domain_list(self, event, alias)
        if text:
            yield await emit(self, event, text, title="NAT 域名")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @nat_domain_group.command("add", alias={"添加"})
    async def nat_domain_add_h(self, event: AstrMessageEvent, domain: str) -> Any:
        """添加域名：/nat domain add <域名> [alias=..]"""
        text = await nat_domain_add(self, event, domain)
        if text:
            yield await emit(self, event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @nat_domain_group.command("del", alias={"删除"})
    async def nat_domain_del_h(
        self, event: AstrMessageEvent, id: str, alias: str = ""
    ) -> Any:
        """删除域名：/nat domain del <id> [alias=..]"""
        text = await nat_domain_del(self, event, id)
        if text:
            yield await emit(self, event, text)

    # ---------- /test ----------
    @filter.command_group("test", alias={"测试"})
    def test_group(self) -> None:
        """联调与健康检查"""
        pass

    @filter.permission_type(filter.PermissionType.ADMIN)
    @test_group.command("ping", alias={"连通"})
    async def test_ping_h(self, event: AstrMessageEvent, alias: str = "") -> Any:
        """调用 test 接口验证连通性"""
        text = await test_ping(self, event, alias)
        if text:
            yield await emit(self, event, text)
