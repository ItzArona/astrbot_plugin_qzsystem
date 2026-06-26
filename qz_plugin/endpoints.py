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

"""qzsystem 主控 API 真实端点路径与请求参数构造。

路径以各 OpenAPI 文档内的 ``paths`` 段为准；README/文件名后缀存在误导，已在此纠正。
所有路径为相对路径，由 ``QzsystemClient`` 拼接 ``base_url`` 后调用。
"""

from __future__ import annotations

# --- 端点路径（POST 除非另注） ---
INFO = "/api/v1/info"
OPEN_HOST = "/api/v1/openHost"
UPDATE_HOST = "/api/v1/updateHost"
REMOVE_HOST = "/api/v1/removeHost"
RENEW = "/api/v1/renew"
POWER = "/api/v1/power"
MONITOR = "/api/v1/monitor"
THUMBNAIL = "/api/v1/thumbnail"
HISTORY_NETWORK = "/api/v1/historyNetwork"
HISTORY_CPU = "/api/v1/historyCpu"
SYNCTIME = "/api/v1/synctime"
UPDATE_OS_PASSWORD = "/api/v1/updateOSPassword"
UPDATE_PANEL_PASSWORD = "/api/v1/updatePanelPassword"
OS_LIST = "/api/v1/osList"  # 文件名 imageList，真实路径 osList
INSTALL_OS = "/api/v1/installOS"  # 文件名 reinstall，真实路径 installOS
ISO_LIST = "/api/v1/isoList"
MOUNT_ISO = "/api/v1/mountISO"  # 大小写敏感
SET_BIOS = "/api/v1/bios"
ADD_IP = "/api/v1/addIP"  # 大小写敏感
REMOVE_IP = "/api/v1/removeIP"  # 非 delIp
SNAPSHOT_LIST = "/api/v1/snapshot"  # 非 snapshotList
CREATE_SNAPSHOT = "/api/v1/createSnapshot"
REMOVE_SNAPSHOT = "/api/v1/removeSnapshot"  # 非 delSnapshot
RESTORE_SNAPSHOT = "/api/v1/restoreSnapshot"
BACKUP_LIST = "/api/v1/backup"  # 非 backupList
CREATE_BACKUP = "/api/v1/createBackup"
REMOVE_BACKUP = "/api/v1/removeBackup"  # 非 delBackup
RESTORE_BACKUP = "/api/v1/restoreBackupHost"  # 多了 Host 后缀
FIREWALL_LIST = "/api/v1/firewallList"
ADD_FIREWALL = "/api/v1/addFirewall"
REMOVE_FIREWALL = "/api/v1/removeFirewall"  # 非 delFirewall
NAT_PORT_LIST = "/api/v1/portList"  # 无 nat 前缀
NAT_ADD_PORT = "/api/v1/addPort"
NAT_REMOVE_PORT = "/api/v1/removePort"  # 非 natDelPort
NAT_FIND_PORT = "/api/v1/findport"  # 非 natQueryPort
NAT_DOMAIN_LIST = "/api/v1/domainList"
NAT_ADD_DOMAIN = "/api/v1/addDomain"
NAT_REMOVE_DOMAIN = "/api/v1/removeDomain"  # 非 natDelDomain
VNC = "/api/v1/vnc"  # 非 getVnc
PANEL = "/api/v1/panel"  # 唯一 GET 接口，无需 signature/apiuser
TEST = "/api/v1/test"

# --- 电源动作枚举 (power.state) ---
POWER_ON = 2  # 开机
POWER_SOFT_OFF = 3  # 软关机
POWER_CUT = 4  # 断开电源(硬关机)
POWER_REBOOT = 5  # 重启

POWER_MAP = {
    "on": POWER_ON,
    "start": POWER_ON,
    "开机": POWER_ON,
    "off": POWER_SOFT_OFF,
    "stop": POWER_SOFT_OFF,
    "软关机": POWER_SOFT_OFF,
    "shutdown": POWER_SOFT_OFF,
    "cut": POWER_CUT,
    "断开": POWER_CUT,
    "硬关机": POWER_CUT,
    "reboot": POWER_REBOOT,
    "restart": POWER_REBOOT,
    "重启": POWER_REBOOT,
}

# --- 时间同步 (synctime.sync_time) ---
SYNCTIME_ON = "1"
SYNCTIME_OFF = "2"
SYNCTIME_MAP = {
    "on": SYNCTIME_ON,
    "开": SYNCTIME_ON,
    "off": SYNCTIME_OFF,
    "关": SYNCTIME_OFF,
}

# --- BIOS 引导顺序 (bios.bios) ---
BIOS_DISK = "IDE"  # 硬盘引导
BIOS_CD = "CD"  # DVD 引导
BIOS_MAP = {
    "disk": BIOS_DISK,
    "硬盘": BIOS_DISK,
    "hd": BIOS_DISK,
    "cd": BIOS_CD,
    "dvd": BIOS_CD,
    "光驱": BIOS_CD,
}

# --- 防火墙方向/动作/协议 ---
FIREWALL_DIR_MAP = {"in": "in", "入": "in", "out": "out", "出": "out"}
FIREWALL_METHOD_MAP = {
    "accept": "accept",
    "接受": "accept",
    "允许": "accept",
    "drop": "drop",
    "拒绝": "drop",
}
FIREWALL_PROTOCOLS = ("TCP", "UDP", "ICMP", "ANY")
