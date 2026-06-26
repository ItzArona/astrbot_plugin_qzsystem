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

"""/server 命令组业务实现：实例生命周期、电源、监控、密码、系统、iso、bios、ip、创建向导。

每个函数为 ``async def(plugin, event, ...) -> str | None``：
- 返回字符串：由 main.py 的 handler 通过 ``emit`` 渲染后 yield。
- 返回 None：函数内已用 ``await event.send(...)`` 自行发送（多消息/图片/敏感场景）。
"""

from __future__ import annotations

import base64
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.utils.session_waiter import SessionController, session_waiter

from . import endpoints as E
from .helpers import host_header, parse_kwargs, safe_call
from .permissions import is_group_chat
from .redaction import redact_secrets, send_private_message
from .render import fmt_kv
from .store import has_confirm, resolve_hostid

_CREATE_STEPS = [
    ("nodes_id", "① 请输入物理节点 id (nodes_id)："),
    ("os_name", "② 请输入操作系统名 (如 ubuntu24.04 / centos7.9)："),
    ("cpu", "③ 请输入 CPU 核心数："),
    ("memory", "④ 请输入内存大小 (MB，如 2048)："),
    ("sys_disk_size", "⑤ 请输入系统盘大小 (GB，如 40)："),
    ("net_out", "⑥ 请输入上行带宽 (Mbps，如 10)："),
    ("sys_pwd", "⑦ 请输入系统密码 (建议私聊执行本向导)："),
    ("expire_time", "⑧ 请输入到期时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)："),
]


def _parse_renew_date(text: str) -> str:
    """支持 ``30d``/``12m``/``1y`` 或原始日期。返回 nextduedate 字符串。"""
    t = (text or "").strip()
    if not t:
        return ""
    if t[-1] in "dmy":
        try:
            n = int(t[:-1])
        except ValueError:
            return t
        now = datetime.now()
        if t[-1] == "d":
            dt = now + timedelta(days=n)
        elif t[-1] == "m":
            dt = now + timedelta(days=n * 30)
        else:
            dt = now + timedelta(days=n * 365)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return t


def _info_rows(info: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("实例ID", info.get("id")),
        ("标识", info.get("host_name")),
        ("状态", info.get("state_name")),
        ("公网IP", info.get("ip")),
        ("内网IP", info.get("local_ip")),
        ("地区", info.get("area_name")),
        ("系统", info.get("os_name")),
        ("系统用户", info.get("os_username")),
        ("CPU(核)", info.get("cpu")),
        ("内存(MB)", info.get("memory")),
        ("硬盘(GB)", info.get("hard_disks")),
        ("上行带宽", info.get("bandwidth_out")),
        ("下行带宽", info.get("bandwidth_in")),
        ("流量(G)", info.get("traffic")),
        ("购买日", info.get("buy_time")),
        ("到期日", info.get("end_time")),
        ("远程地址", info.get("remote_addr")),
        ("远程端口", info.get("remote_port")),
        ("快照数", info.get("snapshot_num")),
        ("备份数", info.get("backup_num")),
        ("NAT挂机宝", "是" if str(info.get("is_nat")) == "1" else "否"),
        ("引导顺序", info.get("bios")),
        ("同步宿主时间", "是" if str(info.get("sync_time")) == "1" else "否"),
        ("附加IP数", len(info.get("attachip") or [])),
    ]


async def server_info(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.INFO, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    info = data or {}
    # 凭证字段：群聊脱敏
    show = info
    if is_group_chat(event) and plugin.cfg.redact_in_group:
        show = dict(info)
        for k in ("os_password", "panel_password"):
            if show.get(k):
                show[k] = "****"
    rows = _info_rows(show)
    rows.append(("系统密码", show.get("os_password") or "(空)"))
    rows.append(("面板密码", show.get("panel_password") or "(空)"))
    return f"{host_header(label, hostid)} 云主机信息\n\n{fmt_kv(rows)}"


async def server_monitor(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.MONITOR, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 监控失败：{err}"
    d = data or {}
    rows = [
        ("CPU使用率(%)", d.get("cpu")),
        ("内存使用率(%)", d.get("memory")),
        ("上行带宽(Mbps/s)", d.get("bwOut")),
        ("下行带宽(Mbps/s)", d.get("bwIn")),
        ("上行流量(MB)", d.get("trafficOut")),
        ("下行流量(MB)", d.get("trafficIn")),
    ]
    return f"{host_header(label, hostid)} 实时监控\n\n{fmt_kv(rows)}"


async def server_screenshot(
    plugin: Any, event: AstrMessageEvent, alias: str = ""
) -> str | None:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.THUMBNAIL, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 截图失败：{err}"
    b64 = (data or {}).get("images", "")
    if not b64:
        return f"{host_header(label, hostid)} 暂无运行截图（可能已关机或不支持）。"
    try:
        raw = base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        return f"{host_header(label, hostid)} 截图解码失败：{exc}"
    fd, path = tempfile.mkstemp(prefix="qz_thumb_", suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    await event.send(
        event.chain_result(
            [
                Comp.Plain(f"{host_header(label, hostid)} 运行截图："),
                Comp.Image.fromFileSystem(path),
            ]
        )
    )
    return None


def _history_summary(data: Any, key_hint: str) -> str:
    """历史数据为嵌套数组，降采样为峰值/均值/末值摘要。"""
    try:
        flat: list[float] = []

        def walk(x: Any) -> None:
            if isinstance(x, (list, tuple)):
                for i in x:
                    walk(i)
            elif isinstance(x, (int, float)):
                flat.append(float(x))

        walk(data)
    except Exception:  # noqa: BLE001
        return f"{key_hint}：数据解析失败"
    if not flat:
        return f"{key_hint}：暂无数据"
    peak = max(flat)
    avg = sum(flat) / len(flat)
    last = flat[-1]
    return f"{key_hint} 近三天：峰值 {peak:.2f} / 均值 {avg:.2f} / 末值 {last:.2f}（共 {len(flat)} 个采样点）"


async def server_cpu_history(
    plugin: Any, event: AstrMessageEvent, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.HISTORY_CPU, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    return f"{host_header(label, hostid)} {_history_summary(data, 'CPU使用率(%)')}"


async def server_net_history(
    plugin: Any, event: AstrMessageEvent, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.HISTORY_NETWORK, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    return f"{host_header(label, hostid)} {_history_summary(data, '网络带宽(Mbps/s)')}"


async def server_images(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.OS_LIST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    if not data:
        return f"{host_header(label, hostid)} 暂无可用镜像。"
    if isinstance(data, list):
        items = [str(x) for x in data]
    elif isinstance(data, dict):
        items = [f"{k}: {v}" for k, v in data.items()]
    else:
        items = [str(data)]
    return f"{host_header(label, hostid)} 可用镜像列表\n\n" + "\n".join(items)


async def server_iso_list(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.ISO_LIST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 查询失败：{err}"
    if not data:
        return f"{host_header(label, hostid)} 暂无 iso 文件。"
    if isinstance(data, dict):
        items = [f"{k}: {v}" for k, v in data.items()]
    else:
        items = [str(data)]
    return f"{host_header(label, hostid)} iso 文件列表\n\n" + "\n".join(items)


async def _emit_sensitive(plugin: Any, event: AstrMessageEvent, full_text: str) -> None:
    """群聊：脱敏发群里 + 私聊发全文；私聊：直接发全文。返回 None。"""
    if is_group_chat(event) and plugin.cfg.redact_in_group:
        await event.send(event.plain_result(redact_secrets(full_text)))
        ok = await send_private_message(plugin, event, full_text)
        if not ok:
            await event.send(
                event.plain_result("⚠️ 完整内容含凭证，请私聊执行该命令查看。")
            )
        return
    await event.send(event.plain_result(full_text))


async def server_vnc(
    plugin: Any, event: AstrMessageEvent, alias: str = ""
) -> str | None:
    hostid, label = await resolve_hostid(plugin, event, alias)
    data, err = await safe_call(
        plugin, plugin.client.post_data(E.VNC, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 获取VNC失败：{err}"
    url = (data or {}).get("url", "")
    full = f"{host_header(label, hostid)} VNC 远程地址：{url}\n（地址含一次性凭证，请勿转发，及时使用）"
    await _emit_sensitive(plugin, event, full)
    return None


async def server_panel(
    plugin: Any, event: AstrMessageEvent, alias: str = ""
) -> str | None:
    hostid, label = await resolve_hostid(plugin, event, alias)
    # panel 需要 host_name 与 panel_password：先 info 取
    info, err = await safe_call(
        plugin, plugin.client.post_data(E.INFO, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 获取信息失败：{err}"
    host_name = (info or {}).get("host_name", "")
    panel_pwd = (info or {}).get("panel_password", "")
    if not host_name or not panel_pwd:
        return f"{host_header(label, hostid)} 缺少 host_name 或 panel_password，无法生成控制台链接。"
    url = plugin.client.build_panel_url(host_name, panel_pwd)
    full = f"{host_header(label, hostid)} 独立控制台链接：\n{url}\n（链接含面板密码明文，请勿在群内转发）"
    await _emit_sensitive(plugin, event, full)
    return None


async def server_iso_mount(
    plugin: Any, event: AstrMessageEvent, name: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    body = {"hostid": hostid, "iso_name": name}
    _, err = await safe_call(plugin, plugin.client.post(E.MOUNT_ISO, body))
    if err:
        return f"{host_header(label, hostid)} 挂载失败：{err}"
    return f"{host_header(label, hostid)} 已挂载 iso：{name}"


async def server_iso_unmount(
    plugin: Any, event: AstrMessageEvent, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    body = {"hostid": hostid, "iso_name": ""}
    _, err = await safe_call(plugin, plugin.client.post(E.MOUNT_ISO, body))
    if err:
        return f"{host_header(label, hostid)} 卸载失败：{err}"
    return f"{host_header(label, hostid)} 已卸载 iso。"


async def server_bios(
    plugin: Any, event: AstrMessageEvent, mode: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    bios = E.BIOS_MAP.get((mode or "").lower())
    if bios is None:
        return f"引导顺序参数无效：{mode}，应为 disk(硬盘) 或 cd(光驱)。"
    _, err = await safe_call(
        plugin, plugin.client.post(E.SET_BIOS, {"hostid": hostid, "bios": bios})
    )
    if err:
        return f"{host_header(label, hostid)} 设置失败：{err}"
    return f"{host_header(label, hostid)} 已设置引导顺序：{bios}（{'硬盘' if bios == E.BIOS_DISK else 'DVD'}）"


async def server_power(
    plugin: Any, event: AstrMessageEvent, action: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    state = E.POWER_MAP.get((action or "").lower())
    if state is None:
        return f"电源动作无效：{action}，应为 on/off/cut/reboot。"
    _, err = await safe_call(
        plugin, plugin.client.post(E.POWER, {"hostid": hostid, "state": state})
    )
    if err:
        return f"{host_header(label, hostid)} 电源操作失败：{err}"
    name = {
        E.POWER_ON: "开机",
        E.POWER_SOFT_OFF: "软关机",
        E.POWER_CUT: "断开电源",
        E.POWER_REBOOT: "重启",
    }[state]
    return f"{host_header(label, hostid)} 已执行电源操作：{name}"


async def server_synctime(
    plugin: Any, event: AstrMessageEvent, mode: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    st = E.SYNCTIME_MAP.get((mode or "").lower())
    if st is None:
        return f"参数无效：{mode}，应为 on(开启同步) 或 off(关闭同步)。"
    _, err = await safe_call(
        plugin, plugin.client.post(E.SYNCTIME, {"hostid": hostid, "sync_time": st})
    )
    if err:
        return f"{host_header(label, hostid)} 设置失败：{err}"
    return f"{host_header(label, hostid)} 已{'开启' if st == E.SYNCTIME_ON else '关闭'}宿主机时间同步。"


async def server_reset_os_pwd(
    plugin: Any, event: AstrMessageEvent, password: str, alias: str = ""
) -> str | None:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not password:
        return "请提供新密码：/server reset-os-pwd <新密码>（建议私聊执行）。"
    _, err = await safe_call(
        plugin,
        plugin.client.post(
            E.UPDATE_OS_PASSWORD, {"hostid": hostid, "password": password}
        ),
    )
    if err:
        return f"{host_header(label, hostid)} 重置失败：{err}"
    full = f"{host_header(label, hostid)} 系统密码已重置为：{password}"
    await _emit_sensitive(plugin, event, full)
    return None


async def server_reset_panel_pwd(
    plugin: Any, event: AstrMessageEvent, password: str, alias: str = ""
) -> str | None:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not password:
        return "请提供新面板密码：/server reset-panel-pwd <新密码>（建议私聊执行）。"
    _, err = await safe_call(
        plugin,
        plugin.client.post(
            E.UPDATE_PANEL_PASSWORD, {"hostid": hostid, "panel_password": password}
        ),
    )
    if err:
        return f"{host_header(label, hostid)} 重置失败：{err}"
    full = f"{host_header(label, hostid)} 面板密码已重置为：{password}"
    await _emit_sensitive(plugin, event, full)
    return None


async def server_reinstall(
    plugin: Any, event: AstrMessageEvent, template: str, password: str, alias: str = ""
) -> str | None:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not template or not password:
        return "用法：/server reinstall <镜像名> <新密码>（建议私聊执行）。"
    body = {"hostid": hostid, "template": template, "password": password}
    _, err = await safe_call(plugin, plugin.client.post(E.INSTALL_OS, body))
    if err:
        return f"{host_header(label, hostid)} 重装失败：{err}"
    full = f"{host_header(label, hostid)} 已发起重装系统请求\n镜像：{template}\n新密码：{password}\n⚠️ 重装会清空系统盘，耗时较长。"
    await _emit_sensitive(plugin, event, full)
    return None


async def server_upgrade(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    kw = parse_kwargs(
        event.message_str,
        {
            "cpu",
            "memory",
            "sys_disk",
            "data_disk",
            "net_out",
            "net_in",
            "flow_limit",
            "snapshot",
            "backups",
        },
    )
    body: dict[str, Any] = {"hostid": hostid}
    field_map = {
        "cpu": "cpu",
        "memory": "memory",
        "sys_disk": "sys_disk_size",
        "data_disk": "data_disk_size",
        "net_out": "net_out",
        "net_in": "net_in",
        "flow_limit": "flow_limit",
        "snapshot": "snapshot",
        "backups": "backups",
    }
    for k, apik in field_map.items():
        if k in kw and kw[k]:
            body[apik] = kw[k]
    if len(body) == 1:
        return "请至少指定一项要升级的参数，如：/server upgrade alias=web1 cpu=2 memory=4096 sys_disk=60"
    _, err = await safe_call(plugin, plugin.client.post(E.UPDATE_HOST, body))
    if err:
        return f"{host_header(label, hostid)} 升级失败：{err}"
    changed = ", ".join(f"{k}={v}" for k, v in body.items() if k != "hostid")
    return f"{host_header(label, hostid)} 已提交升降配：{changed}"


async def server_renew(
    plugin: Any, event: AstrMessageEvent, duration: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    nd = _parse_renew_date(duration)
    if not nd:
        return "请提供续费时长，如 30d / 12m / 1y，或日期 2025-12-07。"
    _, err = await safe_call(
        plugin, plugin.client.post(E.RENEW, {"hostid": hostid, "nextduedate": nd})
    )
    if err:
        return f"{host_header(label, hostid)} 续费失败：{err}"
    return f"{host_header(label, hostid)} 已续费，新的到期时间：{nd}"


async def server_delete(plugin: Any, event: AstrMessageEvent, alias: str = "") -> str:
    if (alias or "").strip() in ("confirm", "确认"):
        alias = ""
    hostid, label = await resolve_hostid(plugin, event, alias)
    if plugin.cfg.require_confirm and not has_confirm(event.message_str):
        return f"{host_header(label, hostid)} ⚠️ 删除不可逆。确认请发送：/server delete {label if label != hostid else ''} confirm".strip()
    _, err = await safe_call(
        plugin, plugin.client.post(E.REMOVE_HOST, {"hostid": hostid})
    )
    if err:
        return f"{host_header(label, hostid)} 删除失败：{err}"
    return f"{host_header(label, hostid)} 已删除云主机。"


async def server_ip_add(
    plugin: Any, event: AstrMessageEvent, num: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not num or not num.isdigit() or int(num) <= 0:
        return "请提供新增 IP 数量(>0)：/server ip add <数量>"
    _, err = await safe_call(
        plugin, plugin.client.post(E.ADD_IP, {"hostid": hostid, "ip_num": num})
    )
    if err:
        return f"{host_header(label, hostid)} 新增IP失败：{err}"
    return f"{host_header(label, hostid)} 已申请新增 {num} 个附加 IP。"


async def server_ip_del(
    plugin: Any, event: AstrMessageEvent, ip: str, alias: str = ""
) -> str:
    hostid, label = await resolve_hostid(plugin, event, alias)
    if not ip:
        return "请提供要删除的 IP（多 IP 用英文逗号分隔）：/server ip del <ip>"
    _, err = await safe_call(
        plugin, plugin.client.post(E.REMOVE_IP, {"hostid": hostid, "ip": ip})
    )
    if err:
        return f"{host_header(label, hostid)} 删除IP失败：{err}"
    return f"{host_header(label, hostid)} 已删除 IP：{ip}"


def _format_create_summary(data: dict[str, Any]) -> str:
    if not data:
        return "创建请求已提交，未返回实例详情。"
    rows = [
        ("实例ID", data.get("id")),
        ("标识", data.get("host_name")),
        ("公网IP", data.get("ip")),
        ("内网IP", data.get("local_ip")),
        ("状态", data.get("state_name")),
        ("系统", data.get("os_name")),
        ("系统密码", data.get("os_password")),
        ("面板密码", data.get("panel_password")),
        ("远程地址", data.get("remote_addr")),
        ("远程端口", data.get("remote_port")),
    ]
    return "✅ 云主机创建成功\n\n" + fmt_kv(rows)


async def server_create(plugin: Any, event: AstrMessageEvent) -> str | None:
    """创建云主机向导（多轮会话）。已在 main.py 用 ADMIN 装饰器限制。"""
    await event.send(event.plain_result(_CREATE_STEPS[0][1]))
    state: dict[str, Any] = {"i": 0, "data": {}, "confirm_pending": False}

    @session_waiter(timeout=180, record_history_chains=False)
    async def wizard(controller: SessionController, ev: AstrMessageEvent) -> None:
        text = (ev.message_str or "").strip()
        if text in ("取消", "退出", "exit", "quit", "cancel"):
            await ev.send(ev.plain_result("已取消创建向导。"))
            controller.stop()
            return
        if state["confirm_pending"]:
            if text in ("确认", "确定", "yes", "y", "ok", "继续"):
                body = dict(state["data"])
                data, err = await safe_call(
                    plugin, plugin.client.post(E.OPEN_HOST, body)
                )
                if err:
                    await ev.send(
                        ev.plain_result(f"❌ 创建失败：{err}\n提交参数：{body}")
                    )
                else:
                    await ev.send(ev.plain_result(_format_create_summary(data or {})))
            else:
                await ev.send(ev.plain_result("已取消创建。"))
            controller.stop()
            return
        key, _ = _CREATE_STEPS[state["i"]]
        state["data"][key] = text
        state["i"] += 1
        if state["i"] < len(_CREATE_STEPS):
            await ev.send(ev.plain_result(_CREATE_STEPS[state["i"]][1]))
            controller.keep(timeout=180, reset_timeout=True)
            return
        state["confirm_pending"] = True
        summary = fmt_kv([(k, v) for k, v in state["data"].items()])
        await ev.send(
            ev.plain_result(
                f"请确认创建参数：\n\n{summary}\n\n回复“确认”提交创建，或“取消”退出。"
            )
        )
        controller.keep(timeout=60, reset_timeout=True)

    try:
        await wizard(event)
    except TimeoutError:
        await event.send(event.plain_result("⌛ 创建向导超时已退出。"))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"server_create wizard error: {exc}")
        await event.send(event.plain_result(f"向导出错：{exc}"))
    finally:
        event.stop_event()
    return None


__all__ = [
    "server_info",
    "server_monitor",
    "server_screenshot",
    "server_cpu_history",
    "server_net_history",
    "server_images",
    "server_iso_list",
    "server_vnc",
    "server_panel",
    "server_iso_mount",
    "server_iso_unmount",
    "server_bios",
    "server_power",
    "server_synctime",
    "server_reset_os_pwd",
    "server_reset_panel_pwd",
    "server_reinstall",
    "server_upgrade",
    "server_renew",
    "server_delete",
    "server_create",
    "server_ip_add",
    "server_ip_del",
]
