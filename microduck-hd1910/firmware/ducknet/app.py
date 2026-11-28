#!/usr/bin/env python3
"""Microduck 蓝牙配网（Linux 桌面）。

通过 BLE 连上机器人，查看/修改 Wi-Fi 配置，并做改名、重启、看日志。

协议是上游 ``duck-ble`` / ``btd`` 的 GATT JSON-RPC：

    服务 6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019
    特征 6f5d2a11-3b47-4c8e-9a1f-2d7e8c4b6019
    读 = API 版本；写 = NDJSON 请求；订阅 = 回答

用法：

    ./app.py                 # 真机（需要 BlueZ 与 bleak）
    ./app.py --demo          # 进程内假机器人
    ./app.py --scan-time 12  # 扫描更久
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from dataclasses import replace
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import ttk
from typing import Any, Callable

import ble
import profiles
import protocol
import session as sessions

def _bleak_available() -> bool:
    """真机模式需要 bleak；--demo 与单元测试不需要。"""
    from importlib.util import find_spec

    return find_spec("bleak") is not None


BLEAK_AVAILABLE = _bleak_available()

APP_TITLE = "Microduck 蓝牙配网"
APP_VERSION = "1.0"
DEFAULT_SCAN_SECONDS = 8.0

BG = "#EEF1F5"
PANEL = "#FFFFFF"
PANEL2 = "#F7F9FB"
BORDER = "#D5DBE3"
DIVIDER = "#EDF1F5"
TEXT = "#1F2328"
MUTED = "#667085"
FAINT = "#98A2B3"
ACCENT = "#1F6FEB"
ACCENT_WEAK = "#E8F0FE"
ACCENT_LINE = "#B9D0F8"
OK = "#1A7F37"
OK_WEAK = "#E8F5EC"
WARN = "#9A6700"
WARN_WEAK = "#FFF8E5"
DANGER = "#CF222E"
DANGER_WEAK = "#FDECEE"

SECURITY_LABELS = {
    "open": "开放",
    "wep": "WEP（不支持）",
    "wpa_psk": "WPA2",
    "wpa3_sae": "WPA3",
    "enterprise": "企业（不支持）",
}

STATE_LABELS = {
    "connected": "已连接",
    "connecting": "正在连接",
    "disconnected": "未连接",
    "unavailable": "Wi-Fi 不可用",
}

REASON_LABELS = {
    "bad_key": "密码被拒绝，请重新输入",
    "not_found": "附近没有这个网络，靠近一点或检查 SSID",
    "timeout": "连接超时（DHCP 没完成），可以重试",
    "unsupported": "这个网络类型不在 API 支持范围内",
    "other": "NetworkManager 报错，详见日志",
}


class AsyncWorker:
    """后台线程里跑一个 asyncio 事件循环，界面只通过它提交协程。"""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="ducknet-async", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro) -> concurrent.futures.Future:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)


class ScrollableFrame(tk.Frame):
    """一个带竖向滚动条的容器；里面的内容用 ``.inner`` 放置。"""

    def __init__(self, parent: tk.Misc, bg: str) -> None:
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._window, width=e.width),
        )


class App:
    def __init__(self, root: tk.Tk, *, demo: bool, scan_seconds: float) -> None:
        self.root = root
        self.demo = demo
        self.scan_seconds = scan_seconds

        self.worker = AsyncWorker()
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._robots: list[ble.Found] = []
        self._networks: list[dict[str, Any]] = []
        self._link: ble.BleLink | None = None
        self._session: sessions.RobotSession | None = None
        self._agent: Any = None
        self._watch: concurrent.futures.Future | None = None
        self._closing = False
        self._rebooting = False
        self._last_status: dict[str, Any] = {}
        self._banner_action: Callable[[], None] | None = None
        self._console_url: str | None = None
        self._robot_key = ""
        # 密码与固定 IP：机器人不回读它们（NM 只回 "saved" 布尔），所以记在本地。
        self.profiles = profiles.Store()
        # 日志面板要到 _build_ui 才有，所以先存着。
        self._startup_notes = [self.profiles.last_error] if self.profiles.last_error else []

        self._init_fonts()
        self.root.title(APP_TITLE)
        self.root.geometry("1040x780")
        self.root.minsize(900, 660)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._init_styles()
        self._build_ui()
        for note in self._startup_notes:
            self._append_log(note)
        self._startup_notes = []
        self.root.after(50, self._drain)

        if demo:
            self._append_log("演示模式：连接的是进程内假机器人，不需要蓝牙")
            self._show_robots(self._demo_robots())
            self.scan_hint.configure(text="演示模式：1 台机器人")
        elif not BLEAK_AVAILABLE:
            self.show_banner(
                "未安装 bleak：运行 ./install.sh，或 pip install bleak。"
                "想先看界面可以用 ./app.py --demo。",
                "error",
            )
            self._append_log("未安装 bleak，真机模式不可用")
            self._set_tabs_enabled(False, "nobleak")
            self.sb_bt.configure(text="蓝牙：未安装 bleak")
        else:
            self.root.after(300, self.on_scan)

    # ── 基础样式 ────────────────────────────────────────────────────────────

    def _init_fonts(self) -> None:
        families = set(tkfont.families())
        sans = next(
            (
                name
                for name in (
                    "Noto Sans CJK SC",
                    "Source Han Sans SC",
                    "WenQuanYi Micro Hei",
                    "Ubuntu",
                    "DejaVu Sans",
                )
                if name in families
            ),
            "TkDefaultFont",
        )
        mono = next(
            (
                name
                for name in ("DejaVu Sans Mono", "Ubuntu Mono", "Noto Sans Mono")
                if name in families
            ),
            "TkFixedFont",
        )
        self.font_base = tkfont.Font(family=sans, size=10)
        self.font_small = tkfont.Font(family=sans, size=9)
        self.font_card = tkfont.Font(family=sans, size=10, weight="bold")
        self.font_title = tkfont.Font(family=sans, size=15, weight="bold")
        self.font_ssid = tkfont.Font(family=sans, size=20, weight="bold")
        self.font_ip = tkfont.Font(family=mono, size=15)
        self.font_mono = tkfont.Font(family=mono, size=9)
        self.font_mono_big = tkfont.Font(family=mono, size=10)
        # 控制台地址是可点的，所以它得看得出来是链接。
        self.font_link = tkfont.Font(family=mono, size=9, underline=True)

    def _init_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=self.font_base, background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("MutedPanel.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Faint.TLabel", background=BG, foreground=FAINT)
        style.configure(
            "TButton",
            padding=(10, 4),
            background="#FBFCFD",
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.map(
            "TButton",
            background=[("active", PANEL2), ("disabled", PANEL2)],
            foreground=[("disabled", FAINT)],
        )
        style.configure(
            "Primary.TButton",
            background=ACCENT,
            foreground="#FFFFFF",
            bordercolor=ACCENT,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#1A5FD0"), ("disabled", "#9CB8E6")],
            foreground=[("disabled", "#FFFFFF")],
        )
        style.configure(
            "Danger.TButton",
            background="#FFFFFF",
            foreground=DANGER,
            bordercolor="#E6B6BB",
            lightcolor="#E6B6BB",
            darkcolor="#E6B6BB",
        )
        style.map(
            "Danger.TButton",
            background=[("active", DANGER_WEAK)],
            foreground=[("disabled", FAINT)],
        )
        style.configure(
            "TEntry",
            fieldbackground="#FFFFFF",
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=4,
        )
        style.configure(
            "TCombobox",
            fieldbackground="#FFFFFF",
            background="#FFFFFF",
            bordercolor=BORDER,
            arrowcolor=TEXT,
            padding=3,
        )
        style.configure(
            "Small.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=TEXT,
            rowheight=24,
            font=self.font_small,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.map(
            "Small.Treeview",
            background=[("selected", ACCENT_WEAK)],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "Small.Treeview.Heading",
            background=PANEL2,
            foreground=MUTED,
            font=self.font_small,
            relief="flat",
            padding=(6, 4),
        )
        style.configure(
            "Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=TEXT,
            rowheight=26,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT_WEAK)],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "Treeview.Heading",
            background=PANEL2,
            foreground=MUTED,
            font=self.font_small,
            relief="flat",
            padding=(8, 5),
        )
        style.map("Treeview.Heading", background=[("active", PANEL2)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=BG,
            foreground=MUTED,
            padding=(14, 7),
            bordercolor=BORDER,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", PANEL), ("active", PANEL2)],
            foreground=[("selected", TEXT), ("disabled", FAINT)],
        )
        style.configure("TCheckbutton", background=BG, foreground=MUTED)
        style.configure("Panel.TCheckbutton", background=PANEL, foreground=MUTED)
        style.configure("TPanedwindow", background=BG)

    # ── 界面搭建 ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        self._build_header(outer)
        tk.Frame(outer, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew")

        body = tk.Frame(outer, bg=BG)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, minsize=308)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_main(body)
        self._build_statusbar(outer)

    def _build_header(self, outer: tk.Frame) -> None:
        header = tk.Frame(outer, bg=PANEL, height=60)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.columnconfigure(1, weight=1)

        titles = tk.Frame(header, bg=PANEL)
        titles.grid(row=0, column=0, sticky="w", padx=16, pady=5)
        tk.Label(
            titles, text=APP_TITLE, bg=PANEL, fg=TEXT, font=self.font_title
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="通过蓝牙配置机器人的网络与身份",
            bg=PANEL,
            fg=MUTED,
            font=self.font_small,
        ).pack(anchor="w")

        if self.demo:
            tk.Label(
                header,
                text="演示模式",
                bg=ACCENT_WEAK,
                fg=ACCENT,
                font=self.font_small,
                padx=8,
                pady=2,
                highlightthickness=1,
                highlightbackground=ACCENT_LINE,
            ).grid(row=0, column=2, padx=(0, 8))
        tk.Button(
            header,
            text="帮助",
            font=self.font_small,
            bg=PANEL,
            fg=MUTED,
            activebackground=PANEL,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._show_help,
        ).grid(row=0, column=3, padx=(0, 16))

    def _build_sidebar(self, body: tk.Frame) -> None:
        sidebar = tk.Frame(body, bg=BG)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(1, weight=1, minsize=180)

        self._build_robot_card(sidebar)
        self._build_connection_card(sidebar)
        self._build_tips_card(sidebar)

    def _card(self, parent: tk.Misc) -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        return card

    def _card_title(self, parent: tk.Frame, text: str) -> tk.Frame:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(9, 7))
        tk.Label(row, text=text, bg=PANEL, fg=TEXT, font=self.font_card).pack(side="left")
        return row

    def _build_robot_card(self, sidebar: tk.Frame) -> None:
        card = self._card(sidebar)
        card.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        title = self._card_title(card, "机器人")
        self.robot_count = tk.Label(
            title, text="0", bg=PANEL2, fg=MUTED, font=self.font_small, padx=7
        )
        self.robot_count.pack(side="left", padx=(6, 0))
        tk.Frame(title, bg=PANEL).pack(side="left", fill="x", expand=True)
        self.rescan_btn = tk.Button(
            title,
            text="重新扫描",
            bg=PANEL,
            fg=ACCENT,
            activebackground=PANEL,
            activeforeground=ACCENT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=self.font_small,
            command=self.on_scan,
        )
        self.rescan_btn.pack(side="right")

        list_frame = tk.Frame(card, bg=PANEL)
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.robots_tree = ttk.Treeview(
            list_frame,
            columns=("name", "ip", "rssi"),
            show="headings",
            height=2,
            selectmode="browse",
            style="Small.Treeview",
        )
        self.robots_tree.heading("name", text="名称")
        self.robots_tree.heading("ip", text="IPv4")
        self.robots_tree.heading("rssi", text="信号")
        self.robots_tree.column("name", width=80, anchor="w", stretch=True)
        self.robots_tree.column("ip", width=116, anchor="w", stretch=False)
        self.robots_tree.column("rssi", width=42, anchor="e", stretch=False)
        self.robots_tree.tag_configure("muted", foreground=FAINT)
        self.robots_tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.robots_tree.yview)
        scroll.pack(side="right", fill="y")
        self.robots_tree.configure(yscrollcommand=scroll.set)
        self.robots_tree.bind("<<TreeviewSelect>>", lambda _e: self._update_connect_button())

        footer = tk.Frame(card, bg=PANEL)
        footer.pack(fill="x", padx=12, pady=(0, 9))
        self.show_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            footer,
            text="显示全部蓝牙设备",
            variable=self.show_all,
            style="Panel.TCheckbutton",
            command=self.on_scan,
        ).pack(side="left")
        self.scan_hint = tk.Label(
            footer, text="", bg=PANEL, fg=FAINT, font=self.font_small
        )
        self.scan_hint.pack(side="right")

    def _build_connection_card(self, sidebar: tk.Frame) -> None:
        card = self._card(sidebar)
        card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self._card_title(card, "连接")

        body = tk.Frame(card, bg=PANEL)
        body.pack(fill="x", padx=12, pady=(0, 12))

        pin_row = tk.Frame(body, bg=PANEL)
        pin_row.pack(fill="x")
        tk.Label(pin_row, text="PIN", bg=PANEL, fg=MUTED, width=4, anchor="w").pack(side="left")
        self.pin_var = tk.StringVar(value=protocol.DEFAULT_PIN)
        self.pin_entry = ttk.Entry(pin_row, textvariable=self.pin_var, width=12)
        self.pin_entry.pack(side="left")
        self.pin_entry.bind("<Return>", lambda _e: self.on_connect())

        tk.Label(
            body,
            text="出厂 000000；改过用 robotctl system pin",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=262,
        ).pack(fill="x", pady=(4, 8))

        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(fill="x")
        self.connect_btn = ttk.Button(
            buttons, text="连接", style="Primary.TButton", command=self.on_connect
        )
        self.connect_btn.pack(side="left")
        self.disconnect_btn = ttk.Button(
            buttons, text="断开", command=self.on_disconnect, state="disabled"
        )
        self.disconnect_btn.pack(side="left", padx=(6, 0))

        self.conn_state = tk.Label(
            body, text="● 未连接", bg=PANEL, fg=MUTED, font=self.font_card, anchor="w"
        )
        self.conn_state.pack(fill="x", pady=(10, 2))
        self.conn_detail = tk.Label(
            body,
            text="选一台机器人，填 PIN，然后连接",
            bg=PANEL,
            fg=MUTED,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=262,
        )
        self.conn_detail.pack(fill="x")

    def _build_tips_card(self, sidebar: tk.Frame) -> None:
        card = self._card(sidebar)
        card.grid(row=3, column=0, sticky="ew")
        self._card_title(card, "提示")
        tk.Label(
            card,
            text=(
                "机器人不需要先联网：连上 BLE、通过 PIN 认证，就能扫描并加入 Wi-Fi。\n"
                "忘记网络只删除已保存的密码，不会立刻断开当前连接。"
            ),
            bg=PANEL,
            fg=MUTED,
            font=self.font_small,
            justify="left",
            anchor="nw",
            wraplength=262,
        ).pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_main(self, body: tk.Frame) -> None:
        main = tk.Frame(body, bg=BG)
        main.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self._build_banner(main)

        self.paned = ttk.Panedwindow(main, orient="vertical")
        self.paned.grid(row=2, column=0, sticky="nsew")
        main.rowconfigure(2, weight=1)

        self.notebook = ttk.Notebook(self.paned)
        self._build_status_tab()
        self._build_wifi_tab()
        self._build_robot_tab()
        self._build_diag_tab()
        self.paned.add(self.notebook, weight=4)
        self._build_overlay()

        self._build_log_pane()
        self.root.after(200, self._position_sash)
        self._set_tabs_enabled(False)

    def _build_overlay(self) -> None:
        """盖在页签内容上的“未连接”提示；连接成功后隐藏。"""
        self.overlay = tk.Frame(self.notebook, bg=BG)
        self.overlay_icon = tk.Label(
            self.overlay, text="◌", bg=BG, fg=FAINT, font=tkfont.Font(size=24)
        )
        self.overlay_icon.pack(pady=(70, 6))
        self.overlay_title = tk.Label(
            self.overlay, text="还没有连接机器人", bg=BG, fg=TEXT, font=self.font_card
        )
        self.overlay_title.pack()
        self.overlay_hint = tk.Label(
            self.overlay,
            text="扫描 → 选中机器人 → 输入 PIN，然后就能查看和修改 Wi-Fi",
            bg=BG,
            fg=MUTED,
            font=self.font_small,
            wraplength=460,
            justify="center",
        )
        self.overlay_hint.pack(pady=(3, 12))
        self.overlay_button = ttk.Button(
            self.overlay, text="扫描机器人", style="Primary.TButton", command=self.on_scan
        )
        self.overlay_button.pack()

    def _position_sash(self) -> None:
        try:
            height = self.paned.winfo_height()
            if height > 250:
                self.paned.sashpos(0, max(220, height - 170))
        except Exception:
            pass

    def _build_banner(self, main: tk.Frame) -> None:
        self.banner = tk.Frame(main, bg=DANGER_WEAK, highlightthickness=1, highlightbackground="#F0BCC1")
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.banner.grid_remove()
        self.banner.columnconfigure(1, weight=1)

        self.banner_icon = tk.Label(
            self.banner, text="!", bg=DANGER_WEAK, fg=DANGER, font=self.font_card
        )
        self.banner_icon.grid(row=0, column=0, padx=(12, 8), pady=8)
        self.banner_text = tk.Label(
            self.banner,
            text="",
            bg=DANGER_WEAK,
            fg="#8C1D26",
            font=self.font_base,
            anchor="w",
            justify="left",
            wraplength=620,
        )
        self.banner_text.grid(row=0, column=1, sticky="ew", pady=8)
        self.banner_button = tk.Button(
            self.banner,
            text="",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=self.font_small,
        )
        self.banner_button.grid(row=0, column=2, padx=(8, 4))
        self.banner_button.grid_remove()
        tk.Button(
            self.banner,
            text="×",
            bg=DANGER_WEAK,
            fg="#8C1D26",
            activebackground=DANGER_WEAK,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.hide_banner,
        ).grid(row=0, column=3, padx=(0, 8))

    def _build_status_tab(self) -> None:
        tab = ScrollableFrame(self.notebook, BG)
        self.notebook.add(tab, text="网络状态")
        root = tab.inner

        hero = tk.Frame(root, bg=BG)
        hero.pack(fill="x", pady=(0, 10))
        hero.columnconfigure(0, weight=1)
        hero.columnconfigure(1, minsize=232)
        hero.rowconfigure(0, weight=1)

        left = self._card(hero)
        left.grid(row=0, column=0, sticky="nsew")
        right = self._card(hero)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        inner = tk.Frame(left, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=14, pady=12)
        self.status_pill = tk.Label(
            inner,
            text="● 未连接",
            bg=PANEL2,
            fg=MUTED,
            font=self.font_small,
            padx=8,
            pady=2,
        )
        self.status_pill.pack(anchor="w")
        self.status_ssid = tk.Label(
            inner, text="未连接", bg=PANEL, fg=MUTED, font=self.font_ssid, anchor="w"
        )
        self.status_ssid.pack(anchor="w", pady=(8, 0))

        self.status_vars: dict[str, tk.StringVar] = {}
        for key in ("iface_mac", "ip4", "ip6"):
            self.status_vars[key] = tk.StringVar(value="—")

        tk.Label(
            inner,
            textvariable=self.status_vars["iface_mac"],
            bg=PANEL,
            fg=MUTED,
            font=self.font_mono,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            inner,
            textvariable=self.status_vars["ip4"],
            bg=PANEL,
            fg=TEXT,
            font=self.font_ip,
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            inner,
            textvariable=self.status_vars["ip6"],
            bg=PANEL,
            fg=MUTED,
            font=self.font_small,
            anchor="w",
        ).pack(anchor="w")
        self.status_source = tk.Label(
            inner, text="地址来源 —", bg=PANEL, fg=FAINT, font=self.font_small, anchor="w"
        )
        self.status_source.pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(inner, bg=PANEL)
        actions.pack(anchor="w", pady=(12, 0))
        self.status_btn = ttk.Button(
            actions, text="刷新状态", style="Primary.TButton", command=self.on_refresh_status
        )
        self.status_btn.pack(side="left")
        ttk.Button(actions, text="复制 IP", command=self._copy_ip).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(actions, text="在浏览器打开", command=self._open_console).pack(
            side="left", padx=(6, 0)
        )

        side = tk.Frame(right, bg=PANEL)
        side.pack(fill="both", expand=True, padx=14, pady=12)
        tk.Label(side, text="信号强度", bg=PANEL, fg=MUTED, font=self.font_small).pack(anchor="w")
        sig_row = tk.Frame(side, bg=PANEL)
        sig_row.pack(anchor="w", pady=(4, 0))
        self.signal_canvas = tk.Canvas(
            sig_row, width=44, height=26, bg=PANEL, highlightthickness=0
        )
        self.signal_canvas.pack(side="left")
        self.signal_label = tk.Label(
            sig_row, text="—", bg=PANEL, fg=TEXT, font=self.font_card
        )
        self.signal_label.pack(side="left", padx=(8, 0))

        tk.Label(
            side, text="控制台", bg=PANEL, fg=MUTED, font=self.font_small
        ).pack(anchor="w", pady=(12, 2))
        # 点一下就在浏览器里打开——这个地址的全部用处就是去看它，复制粘贴是多余的一步。
        self.console_label = tk.Label(
            side,
            text="—",
            bg=PANEL,
            fg=MUTED,
            font=self.font_mono,
            anchor="w",
            justify="left",
            wraplength=204,
            cursor="arrow",
        )
        self.console_label.pack(anchor="w")
        self.console_label.bind("<Button-1>", lambda _e: self._open_console())
        self.last_refresh = tk.Label(
            side,
            text="最后刷新 —",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
            anchor="w",
            wraplength=204,
        )
        self.last_refresh.pack(anchor="w", pady=(12, 0))

        self.raw_toggle = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            root,
            text="显示原始 net.status",
            variable=self.raw_toggle,
            command=self._toggle_raw,
        ).pack(anchor="w", pady=(0, 4))
        self.status_raw = tk.Text(
            root,
            height=8,
            bg="#0F172A",
            fg="#DBE4F0",
            insertbackground="#DBE4F0",
            relief="flat",
            bd=0,
            font=self.font_mono,
            padx=10,
            pady=8,
            wrap="none",
        )
        self.status_raw.pack(fill="both", expand=True)
        self.status_raw.configure(state="disabled")

    def _build_wifi_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="Wi-Fi")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        toolbar = tk.Frame(tab, bg=BG)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.wifi_scan_btn = ttk.Button(
            toolbar,
            text="扫描附近网络",
            style="Primary.TButton",
            command=self.on_scan_networks,
        )
        self.wifi_scan_btn.pack(side="left")
        self.wifi_connect_btn = ttk.Button(
            toolbar, text="连接所选", command=self.on_connect_network
        )
        self.wifi_connect_btn.pack(side="left", padx=(6, 0))
        self.wifi_forget_btn = ttk.Button(
            toolbar, text="忘记所选", command=self.on_forget_network
        )
        self.wifi_forget_btn.pack(side="left", padx=(6, 0))
        self.wifi_hint = tk.Label(
            toolbar, text="双击一行也可以连接", bg=BG, fg=MUTED, font=self.font_small
        )
        self.wifi_hint.pack(side="left", padx=10)

        stack = tk.Frame(tab, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        stack.grid(row=1, column=0, sticky="nsew")
        stack.columnconfigure(0, weight=1)
        stack.rowconfigure(0, weight=1)

        self.wifi_tree = ttk.Treeview(
            stack,
            columns=("ssid", "signal", "security", "saved"),
            show="headings",
            selectmode="browse",
            height=6,
        )
        for column, title, width, anchor in (
            ("ssid", "SSID", 260, "w"),
            ("signal", "信号", 70, "w"),
            ("security", "加密", 130, "w"),
            ("saved", "状态", 80, "w"),
        ):
            self.wifi_tree.heading(column, text=title)
            self.wifi_tree.column(column, width=width, anchor=anchor, stretch=column == "ssid")
        scroll = ttk.Scrollbar(stack, orient="vertical", command=self.wifi_tree.yview)
        self.wifi_tree.configure(yscrollcommand=scroll.set)
        self.wifi_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.wifi_tree.tag_configure("dim", foreground=FAINT)
        self.wifi_tree.bind("<Double-1>", lambda _e: self.on_connect_network())
        self.wifi_tree.bind("<<TreeviewSelect>>", lambda _e: self._load_static_editor())

        self.wifi_empty = tk.Frame(stack, bg=PANEL)
        self.wifi_empty.grid(row=0, column=0, sticky="nsew")
        tk.Label(
            self.wifi_empty, text="◌", bg=PANEL, fg=FAINT, font=tkfont.Font(size=24)
        ).pack(pady=(60, 6))
        tk.Label(
            self.wifi_empty,
            text="还没有扫描附近的网络",
            bg=PANEL,
            fg=TEXT,
            font=self.font_card,
        ).pack()
        tk.Label(
            self.wifi_empty,
            text="扫描通常需要几秒",
            bg=PANEL,
            fg=MUTED,
            font=self.font_small,
        ).pack(pady=(2, 10))
        ttk.Button(
            self.wifi_empty,
            text="扫描附近网络",
            style="Primary.TButton",
            command=self.on_scan_networks,
        ).pack()

        self._build_static_card(tab, row=2)

        manual = tk.Frame(tab, bg=BG)
        manual.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        tk.Label(
            manual,
            text="按 SSID 忘记",
            bg=BG,
            fg=MUTED,
            font=self.font_small,
        ).pack(side="left")
        self.manual_ssid = tk.StringVar()
        entry = ttk.Entry(manual, textvariable=self.manual_ssid, width=28)
        entry.pack(side="left", padx=(8, 6))
        entry.bind("<Return>", lambda _e: self.on_forget_typed())
        ttk.Button(manual, text="忘记", command=self.on_forget_typed).pack(side="left")
        tk.Label(
            manual,
            text="已保存但不在附近",
            bg=BG,
            fg=FAINT,
            font=self.font_small,
        ).pack(side="left", padx=10)

    def _build_static_card(self, parent: tk.Misc, *, row: int) -> None:
        """固定 IP：按「机器人 + SSID」记住，连接这个网络时随 net.connect 下发。

        记在本地而不是机器人上，是因为 ``net.connect`` 的 ``ipv4`` 只往里写、不回读：
        机器人只知道 ``saved`` 为真，问不出它是不是被钉住过地址。
        """
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=(8, 0))

        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(
            head, text="固定 IP", bg=PANEL, fg=TEXT, font=self.font_card, anchor="w"
        ).pack(side="left")
        self.static_hint = tk.Label(
            head,
            text="选中一个网络后可以给它钉固定地址",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
            anchor="w",
        )
        self.static_hint.pack(side="left", padx=(8, 0))
        self.static_clear_btn = ttk.Button(head, text="清除", command=self.on_clear_static)
        self.static_clear_btn.pack(side="right")
        self.static_save_btn = ttk.Button(
            head, text="保存", style="Primary.TButton", command=self.on_save_static
        )
        self.static_save_btn.pack(side="right", padx=(0, 6))

        self.static_enabled = tk.BooleanVar(value=False)
        self.static_address = tk.StringVar()
        self.static_mask = tk.StringVar(value="255.255.255.0")
        self.static_gateway = tk.StringVar()
        self.static_dns = tk.StringVar()
        self._static_ssid: str | None = None

        toggle = tk.Frame(card, bg=PANEL)
        toggle.pack(fill="x", padx=12, pady=(6, 0))
        ttk.Checkbutton(
            toggle,
            text="连接时使用固定地址",
            variable=self.static_enabled,
            command=self._sync_static_entries,
        ).pack(side="left")

        # 四个输入框单独一行：和复选框挤在一行时，DNS 会被裁掉。
        row_frame = tk.Frame(card, bg=PANEL)
        row_frame.pack(fill="x", padx=12, pady=(4, 10))

        self._static_entries: list[ttk.Entry] = []
        for label, var, width in (
            ("IP", self.static_address, 15),
            ("掩码", self.static_mask, 14),
            ("网关", self.static_gateway, 15),
            ("DNS", self.static_dns, 16),
        ):
            tk.Label(
                row_frame, text=label, bg=PANEL, fg=MUTED, font=self.font_small
            ).pack(side="left", padx=(0 if label == "IP" else 12, 4))
            entry = ttk.Entry(row_frame, textvariable=var, width=width)
            entry.pack(side="left")
            entry.bind("<Return>", lambda _e: self.on_save_static())
            self._static_entries.append(entry)

        self.static_detail = tk.Label(
            card,
            text="",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=640,
        )
        self.static_detail.pack(fill="x", padx=12, pady=(0, 10))

        self._sync_static_entries()

    def _sync_static_entries(self) -> None:
        state = "normal" if self.static_enabled.get() else "disabled"
        for entry in self._static_entries:
            entry.configure(state=state)

    def _load_static_editor(self) -> None:
        """选中网络后，把本地记住的固定 IP 填进编辑器。"""
        network = self._selected_network()
        self._static_ssid = str(network.get("ssid", "")) if network else None
        ssid = self._static_ssid
        saved = (
            self.profiles.static_ipv4(self._robot_key, ssid)
            if (ssid and self._robot_key)
            else None
        )
        self.static_enabled.set(saved is not None)
        self.static_address.set(str(saved.get("address", "")) if saved else "")
        self.static_mask.set(
            profiles.prefix_to_mask(int(saved["prefix"]))
            if saved
            else "255.255.255.0"
        )
        self.static_gateway.set(str(saved.get("gateway", "")) if saved else "")
        self.static_dns.set(
            " ".join(str(item) for item in (saved or {}).get("dns", []))
        )
        self._sync_static_entries()
        # 这一行很短：标题行右侧还有「保存 / 清除」，说明长了按钮就被挤出卡片。
        if saved:
            hint = f"「{ssid}」已固定 {saved.get('address')}/{saved.get('prefix')}"
        else:
            hint = f"「{ssid}」用 DHCP" if ssid else "选中一个网络后可以给它钉固定地址"
        self.static_hint.configure(text=hint, fg=OK if saved else FAINT)
        self.static_detail.configure(
            text=profiles.describe(saved)
            if saved
            else "掩码可以写 255.255.255.0 或 24；DNS 留空则用网络原来的。"
            "固定地址会写进机器人的 NetworkManager 配置，重启后仍然有效。"
        )

    def _static_target_ssid(self) -> str | None:
        """编辑器当前对应的 SSID。

        以列表当前选中行为准，选不中才回落到上次加载的那个：``<<TreeviewSelect>>`` 是
        排队派发的，选中一行之后立刻点保存时回调可能还没跑；反过来，用户换了行、事件还没
        派发时，也要按他刚点的那一行保存，而不是按上一次的。
        """
        network = self._selected_network()
        if network:
            return str(network.get("ssid", "")) or None
        return self._static_ssid

    def on_save_static(self) -> None:
        if not self._session:
            self.show_banner("先连上机器人，固定 IP 是写给这台机器人的。", "info")
            return
        ssid = self._static_target_ssid()
        if not ssid:
            self.show_banner("先在列表里选一个网络。", "info")
            return
        if not self.static_enabled.get():
            self.on_clear_static()
            return
        try:
            cfg = profiles.build_static(
                self.static_address.get(),
                self.static_mask.get(),
                self.static_gateway.get(),
                self.static_dns.get(),
            )
        except profiles.InvalidStaticIP as exc:
            self.show_banner(str(exc), "error")
            return

        self.profiles.set_static_ipv4(self._robot_key, ssid, cfg)
        self._static_ssid = ssid
        self._load_static_editor()
        self._append_log(f"固定 IP：{ssid} → {profiles.describe(cfg)}")
        self.show_banner(f"已记住 {ssid} 的固定地址 {cfg['address']}", "ok")

    def on_clear_static(self) -> None:
        ssid = self._static_target_ssid()
        if not ssid:
            self.show_banner("先在列表里选一个网络。", "info")
            return
        if self.profiles.static_ipv4(self._robot_key, ssid) is None:
            self._load_static_editor()
            self.show_banner(f"{ssid} 本来就没有固定地址。", "info")
            return
        self.profiles.set_static_ipv4(self._robot_key, ssid, None)
        self._static_ssid = ssid
        self._load_static_editor()
        self._append_log(f"固定 IP：{ssid} 改回 DHCP")
        self.show_banner(f"已让 {ssid} 改用 DHCP（下次连接生效）", "ok")

    def _build_robot_tab(self) -> None:
        tab = ScrollableFrame(self.notebook, BG)
        self.notebook.add(tab, text="机器人")
        root = tab.inner

        identity = self._card(root)
        identity.pack(fill="x", pady=(0, 8))
        self._card_title(identity, "身份")
        grid = tk.Frame(identity, bg=PANEL)
        grid.pack(fill="x", padx=12, pady=(0, 8))
        self.robot_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="—")
            for key in ("name", "serial", "uptime", "api", "address")
        }
        pairs = (
            ("名称", "name"),
            ("序列号", "serial"),
            ("运行时间", "uptime"),
            ("API 版本", "api"),
            ("蓝牙地址", "address"),
        )
        for index, (label, key) in enumerate(pairs):
            row, column = divmod(index, 2)
            tk.Label(
                grid, text=label, bg=PANEL, fg=MUTED, font=self.font_small, anchor="w"
            ).grid(row=row, column=column * 2, sticky="w", padx=(0, 8), pady=2)
            tk.Label(
                grid,
                textvariable=self.robot_vars[key],
                bg=PANEL,
                fg=TEXT,
                font=self.font_mono_big,
                anchor="w",
            ).grid(row=row, column=column * 2 + 1, sticky="w", padx=(0, 24), pady=2)

        rename = tk.Frame(identity, bg=PANEL)
        rename.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(rename, text="新名称", bg=PANEL, fg=MUTED, font=self.font_small).pack(
            side="left"
        )
        self.new_name = tk.StringVar()
        entry = ttk.Entry(rename, textvariable=self.new_name, width=24)
        entry.pack(side="left", padx=(8, 6))
        entry.bind("<Return>", lambda _e: self.on_rename())
        self.rename_btn = ttk.Button(
            rename, text="改名", style="Primary.TButton", command=self.on_rename
        )
        self.rename_btn.pack(side="left")
        tk.Label(
            rename,
            text="改名后广播名称立即更新",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
        ).pack(side="left", padx=8)

        logs = self._card(root)
        logs.pack(fill="x", pady=(0, 8))
        self._card_title(logs, "日志")
        body = tk.Frame(logs, bg=PANEL)
        body.pack(fill="x", padx=12, pady=(0, 10))
        controls = tk.Frame(body, bg=PANEL)
        controls.pack(fill="x", pady=(0, 8))
        self.log_unit = tk.StringVar(value="robotd")
        self.log_unit_box = ttk.Combobox(
            controls,
            textvariable=self.log_unit,
            values=list(protocol.LOG_UNITS),
            state="readonly",
            width=13,
        )
        self.log_unit_box.pack(side="left")
        tk.Label(
            controls, text="行数", bg=PANEL, fg=MUTED, font=self.font_small
        ).pack(side="left", padx=(8, 4))
        self.log_lines = tk.StringVar(value="40")
        ttk.Entry(controls, textvariable=self.log_lines, width=5).pack(side="left")
        self.logs_btn = ttk.Button(controls, text="读取日志", command=self.on_read_logs)
        self.logs_btn.pack(side="left", padx=(6, 0))
        tk.Label(
            controls,
            text="btd / bluetooth / NetworkManager 排障用",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
        ).pack(side="left", padx=8)

        self.device_log = tk.Text(
            body,
            height=3,
            bg="#0F172A",
            fg="#DBE4F0",
            insertbackground="#DBE4F0",
            relief="flat",
            bd=0,
            font=self.font_mono,
            padx=10,
            pady=6,
            wrap="none",
        )
        self.device_log.pack(fill="x")
        self.device_log.configure(state="disabled")
        self.logs_note = tk.Label(
            body,
            text="只显示最近 N 行；日志过长时机器人会截断并说明。",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
            anchor="w",
        )
        self.logs_note.pack(fill="x", pady=(4, 0))

        danger = tk.Frame(
            root, bg="#FFFDFD", highlightthickness=1, highlightbackground="#EFC9CD"
        )
        danger.pack(fill="x")
        inner = tk.Frame(danger, bg="#FFFDFD")
        inner.pack(fill="x", padx=12, pady=9)
        tk.Label(
            inner, text="⚠", bg="#FFFDFD", fg=DANGER, font=self.font_card
        ).pack(side="left")
        tk.Label(
            inner,
            text="重启会让机器人断开连接并让关节卸力。请先让机器人坐下或扶住它。",
            bg="#FFFDFD",
            fg=MUTED,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=380,
        ).pack(side="left", padx=10, fill="x", expand=True)
        self.reboot_btn = ttk.Button(
            inner,
            text="重启机器人…",
            style="Danger.TButton",
            command=self.on_reboot,
        )
        self.reboot_btn.pack(side="right")

    def _build_diag_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="诊断")
        tab.columnconfigure(1, weight=1)

        tk.Label(tab, text="方法", bg=BG, fg=MUTED, font=self.font_small).grid(
            row=0, column=0, sticky="w"
        )
        self.diag_method = tk.StringVar(value="net.status")
        ttk.Entry(tab, textvariable=self.diag_method, width=32).grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        tk.Label(
            tab,
            text="只能发 BLE 允许的方法；写操作请确认参数",
            bg=BG,
            fg=FAINT,
            font=self.font_small,
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(2, 6))

        chips = tk.Frame(tab, bg=BG)
        chips.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(0, 8))
        for method in ("net.status", "net.scan", "system.info", "system.logs", "robot.health"):
            tk.Button(
                chips,
                text=method,
                bg=PANEL,
                fg=MUTED,
                activebackground=ACCENT_WEAK,
                activeforeground=ACCENT,
                relief="solid",
                bd=1,
                font=self.font_small,
                padx=8,
                cursor="hand2",
                command=lambda m=method: self.diag_method.set(m),
            ).pack(side="left", padx=(0, 5))

        tk.Label(tab, text="参数", bg=BG, fg=MUTED, font=self.font_small).grid(
            row=3, column=0, sticky="nw"
        )
        self.diag_params = tk.Text(
            tab,
            height=4,
            width=48,
            bg="#FFFFFF",
            fg=TEXT,
            insertbackground=TEXT,
            relief="solid",
            bd=1,
            font=self.font_mono,
            padx=8,
            pady=6,
        )
        self.diag_params.insert("1.0", "{}")
        self.diag_params.grid(row=3, column=1, sticky="ew", padx=(8, 0))

        bar = tk.Frame(tab, bg=BG)
        bar.grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)
        self.diag_btn = ttk.Button(
            bar, text="发送", style="Primary.TButton", command=self.on_diag_send
        )
        self.diag_btn.pack(side="left")
        tk.Label(
            bar,
            text="net.scan / net.connect / system.logs 最长等 60 秒",
            bg=BG,
            fg=FAINT,
            font=self.font_small,
        ).pack(side="left", padx=10)

        tk.Label(tab, text="回答", bg=BG, fg=MUTED, font=self.font_small).grid(
            row=5, column=0, sticky="nw"
        )
        self.diag_output = tk.Text(
            tab,
            height=10,
            bg="#0F172A",
            fg="#DBE4F0",
            insertbackground="#DBE4F0",
            relief="flat",
            bd=0,
            font=self.font_mono,
            padx=10,
            pady=8,
            wrap="none",
        )
        self.diag_output.grid(row=5, column=1, sticky="nsew", padx=(8, 0))
        tab.rowconfigure(5, weight=1)

    def _build_log_pane(self) -> None:
        frame = tk.Frame(self.paned, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        self.paned.add(frame, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        title = tk.Frame(frame, bg=PANEL)
        title.grid(row=0, column=0, sticky="ew", padx=12, pady=(7, 4))
        tk.Label(title, text="日志", bg=PANEL, fg=TEXT, font=self.font_card).pack(side="left")
        tk.Label(
            title,
            text="密码与 PIN 自动隐藏",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
        ).pack(side="left", padx=8)
        tk.Button(
            title,
            text="清空",
            bg=PANEL,
            fg=ACCENT,
            activebackground=PANEL,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=self.font_small,
            command=self._clear_log,
        ).pack(side="right")
        self.auto_scroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            title,
            text="自动滚动",
            variable=self.auto_scroll,
            style="Panel.TCheckbutton",
        ).pack(side="right", padx=10)

        self.log_text = tk.Text(
            frame,
            height=8,
            bg="#FCFDFE",
            fg="#334155",
            relief="flat",
            bd=0,
            font=self.font_mono,
            padx=10,
            pady=6,
            wrap="word",
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=(1, 0), pady=(0, 1))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set, state="disabled")
        self.log_text.tag_configure("time", foreground=FAINT)
        self.log_text.tag_configure("out", foreground=ACCENT)
        self.log_text.tag_configure("err", foreground=DANGER)
        self.log_text.tag_configure("note", foreground=WARN)

    def _build_statusbar(self, outer: tk.Frame) -> None:
        tk.Frame(outer, bg=BORDER, height=1).grid(row=3, column=0, sticky="ew")
        bar = tk.Frame(outer, bg=PANEL, height=28)
        bar.grid(row=4, column=0, sticky="ew")
        bar.grid_propagate(False)
        self.sb_bt = tk.Label(bar, text="蓝牙：就绪", bg=PANEL, fg=MUTED, font=self.font_small)
        self.sb_bt.pack(side="left", padx=(14, 0))
        tk.Label(bar, text="·", bg=PANEL, fg=FAINT, font=self.font_small).pack(
            side="left", padx=6
        )
        self.sb_robots = tk.Label(
            bar, text="已找到 0 台机器人", bg=PANEL, fg=MUTED, font=self.font_small
        )
        self.sb_robots.pack(side="left")
        tk.Label(bar, text="·", bg=PANEL, fg=FAINT, font=self.font_small).pack(
            side="left", padx=6
        )
        self.sb_conn = tk.Label(
            bar, text="连接：未连接", bg=PANEL, fg=MUTED, font=self.font_small
        )
        self.sb_conn.pack(side="left")
        tk.Label(
            bar,
            text=f"ducknet {APP_VERSION} · 协议 v{protocol.API_VERSION}",
            bg=PANEL,
            fg=FAINT,
            font=self.font_small,
        ).pack(side="right", padx=14)

    # ── 线程桥 ──────────────────────────────────────────────────────────────

    def _post(self, fn: Callable[[], None]) -> None:
        self._ui_queue.put(fn)

    def _drain(self) -> None:
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:  # pragma: no cover - 界面回调不该把主循环带崩
                traceback.print_exc()
        if not self._closing:
            self.root.after(50, self._drain)

    def _guard(
        self,
        widgets: Any,
        coro,
        ok: Callable[[Any], None],
        fail: Callable[[BaseException], None] | None = None,
    ) -> concurrent.futures.Future:
        targets = widgets if isinstance(widgets, (list, tuple)) else [widgets]
        for widget in targets:
            widget.state(["disabled"])

        def done(future: concurrent.futures.Future) -> None:
            def finish() -> None:
                for widget in targets:
                    widget.state(["!disabled"])
                try:
                    result = future.result()
                except (asyncio.CancelledError, concurrent.futures.CancelledError):
                    return
                except BaseException as exc:  # 蓝牙/机器人异常都在这里落地
                    (fail or self._op_failed)(exc)
                else:
                    ok(result)

            self._post(finish)

        future = self.worker.submit(coro)
        future.add_done_callback(done)
        return future

    def _op_failed(self, exc: BaseException) -> None:
        self._append_log(f"! {exc}")
        if isinstance(exc, sessions.AuthError):
            self.show_banner(
                f"{exc}。出厂 PIN 是 000000；改过的话在机器人上运行 robotctl system pin。",
                "error",
            )
            self._reset_connection("error")
        elif isinstance(exc, sessions.LinkClosed):
            self.show_banner(str(exc), "error")
            self._reset_connection()
        elif isinstance(exc, (sessions.CallTimeout, TimeoutError)):
            self.show_banner(str(exc), "warn")
        elif isinstance(exc, ble.BleError):
            self.show_banner(str(exc), "error")
            if self._session is None:
                self._reset_connection("offline")
        else:
            self.show_banner(f"操作失败：{exc}", "error")

    def _log(self, message: str) -> None:
        self._post(lambda: self._append_log(message))

    def _append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        tag = ""
        if message.startswith("→"):
            tag = "out"
        elif message.startswith("!") or "错误" in message or "失败" in message:
            tag = "err"
        elif message.startswith("·"):
            tag = "note"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] ", ("time",))
        self.log_text.insert("end", f"{message}\n", (tag,) if tag else ())
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 2000:
            self.log_text.delete("1.0", "500.0")
        if self.auto_scroll.get():
            self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    # ── 横幅 ────────────────────────────────────────────────────────────────

    def show_banner(
        self,
        text: str,
        kind: str = "error",
        action_text: str = "",
        action: Callable[[], None] | None = None,
    ) -> None:
        palette = {
            "error": (DANGER_WEAK, "#8C1D26", "#F0BCC1", "!", DANGER),
            "warn": (WARN_WEAK, "#7A5200", "#EAD9A8", "⚠", WARN),
            "ok": (OK_WEAK, OK, "#C6E3CE", "●", OK),
            "info": (ACCENT_WEAK, ACCENT, ACCENT_LINE, "i", ACCENT),
        }
        bg, fg, border, icon, icon_fg = palette.get(kind, palette["error"])
        self.banner.configure(bg=bg, highlightbackground=border)
        self.banner_icon.configure(text=icon, bg=bg, fg=icon_fg)
        self.banner_text.configure(text=text, bg=bg, fg=fg)
        self.banner_button.configure(
            bg=bg, fg=fg, activebackground=bg, activeforeground=fg
        )
        for child in self.banner.winfo_children():
            if isinstance(child, tk.Button) and child["text"] == "×":
                child.configure(bg=bg, fg=fg, activebackground=bg)
        if action is not None and action_text:
            self._banner_action = action
            self.banner_button.configure(
                text=action_text, command=self._run_banner_action
            )
            self.banner_button.grid()
        else:
            self._banner_action = None
            self.banner_button.grid_remove()
        self.banner.grid()

    def _run_banner_action(self) -> None:
        if self._banner_action is not None:
            self._banner_action()

    def hide_banner(self) -> None:
        self.banner.grid_remove()
        self._banner_action = None

    # ── 连接状态 ────────────────────────────────────────────────────────────

    def _set_tabs_enabled(self, enabled: bool, reason: str = "") -> None:
        """连接前后切换页签与内容。

        页签本身常驻可用——把 ttk.Notebook 的 tab 设成 disabled 会把当前选中项一并
        取消，内容区就变成一块空白。未连接时改为在内容上盖一层提示，并禁用各页的
        操作按钮。
        """
        for button in (
            getattr(self, "status_btn", None),
            getattr(self, "wifi_scan_btn", None),
            getattr(self, "wifi_connect_btn", None),
            getattr(self, "wifi_forget_btn", None),
            getattr(self, "rename_btn", None),
            getattr(self, "logs_btn", None),
            getattr(self, "reboot_btn", None),
            getattr(self, "diag_btn", None),
        ):
            if button is not None:
                button.state(["!disabled"] if enabled else ["disabled"])

        if enabled:
            self.overlay.place_forget()
            self.notebook.select(0)
            return

        titles = {
            "idle": ("还没有连接机器人", "扫描 → 选中机器人 → 输入 PIN，然后就能查看和修改 Wi-Fi"),
            "disconnected": ("连接已断开", "点左侧「连接」重新连上"),
            "scanning": ("正在扫描…", "找到机器人后选中它，再点连接"),
            "connecting": ("正在连接机器人…", "读取版本 → 配对 → PIN 认证"),
            "error": ("认证失败", "改正 PIN 后点左侧「连接」重试"),
            "offline": ("蓝牙未开启", "开启蓝牙后点「重新扫描」"),
            "nobleak": (
                "未安装 bleak（真机模式需要）",
                "运行 ./install.sh，或 pip install bleak；也可以先用 ./app.py --demo 看界面",
            ),
        }
        title, hint = titles.get(reason, titles["idle"])
        self.overlay_title.configure(text=title)
        self.overlay_hint.configure(text=hint)
        self.overlay_button.configure(
            text="重新扫描" if reason in ("offline", "error", "disconnected") else "扫描机器人"
        )
        self.overlay_button.state(["disabled"] if reason == "nobleak" else ["!disabled"])
        self.overlay.place(in_=self.notebook, x=0, y=0, relwidth=1, relheight=1)
        self.overlay.lift()

    def _set_conn(self, kind: str, text: str, detail: str) -> None:
        colors = {
            "ok": OK,
            "warn": WARN,
            "off": MUTED,
        }
        self.conn_state.configure(text=f"● {text}", fg=colors.get(kind, MUTED))
        self.conn_detail.configure(text=detail)

    def _update_connect_button(self) -> None:
        if self._session is not None:
            self.connect_btn.state(["disabled"])
            return
        selection = self.robots_tree.selection()
        robot = self._robot_by_iid(selection[0]) if selection else None
        if robot is not None and robot.is_robot:
            self.connect_btn.state(["!disabled"])
        else:
            self.connect_btn.state(["disabled"])

    def _robot_by_iid(self, iid: str) -> ble.Found | None:
        try:
            return self._robots[int(iid)]
        except (ValueError, IndexError):
            return None

    def _selected_network(self) -> dict[str, Any] | None:
        selection = self.wifi_tree.selection()
        if not selection:
            return None
        try:
            return self._networks[int(selection[0])]
        except (ValueError, IndexError):
            return None

    # ── 扫描机器人 ──────────────────────────────────────────────────────────

    def _demo_robots(self) -> list[ble.Found]:
        adv = protocol.RobotAdvertisement(
            address="AA:BB:CC:DD:EE:FF",
            name="Microduck-DEMO",
            ipv4="192.168.1.42",
            has_address_field=True,
            extended=True,
            rssi=-55,
        )
        return [ble.Found(adv=adv, devices=[], is_robot=True)]

    def on_scan(self) -> None:
        if self.demo:
            self.scan_hint.configure(text="演示模式：1 台机器人")
            self._show_robots(self._demo_robots())
            return
        if not BLEAK_AVAILABLE:
            self.show_banner("未安装 bleak，无法扫描。见 ./install.sh。", "error")
            return

        self.scan_hint.configure(text="扫描中…")
        self.sb_robots.configure(text="扫描中…")
        self.rescan_btn.configure(state="disabled")
        if self._session is None:
            self._set_tabs_enabled(False, "scanning")
        include_all = bool(self.show_all.get())
        self._append_log("→ 扫描附近的机器人")

        def update(items: list[ble.Found]) -> None:
            self._post(lambda: self._show_robots(items))

        async def go() -> list[ble.Found]:
            return await ble.scan(
                self.scan_seconds, include_all=include_all, on_update=update
            )

        def ok(items: list[ble.Found]) -> None:
            self.rescan_btn.configure(state="normal")
            self._show_robots(items)
            robots = sum(1 for item in items if item.is_robot)
            if self._session is None:
                # 扫描结束后回到“选一台机器人”的提示，而不是停在“正在扫描”。
                self._set_tabs_enabled(False, "idle")
            self.scan_hint.configure(text=f"找到 {robots} 台机器人")
            self._append_log(f"· 找到 {robots} 台机器人")
            if robots == 0:
                self.show_banner(
                    "没有找到机器人。确认它在附近、蓝牙已开启，并且没有连在手机 App 上。",
                    "warn",
                )
            self._sync_statusbar()

        def fail(exc: BaseException) -> None:
            self.rescan_btn.configure(state="normal")
            self.scan_hint.configure(text="扫描失败")
            self.sb_bt.configure(text="蓝牙：不可用")
            self.sb_robots.configure(text="没有找到机器人")
            self._update_connect_button()
            if self._session is None:
                self._set_tabs_enabled(False, "offline")
            self._op_failed(exc)

        self._guard(self.connect_btn, go(), ok, fail)

    def _show_robots(self, items: list[ble.Found]) -> None:
        previous = None
        selection = self.robots_tree.selection()
        if selection:
            robot = self._robot_by_iid(selection[0])
            if robot is not None:
                previous = (robot.adv.name, robot.adv.address)

        self._robots = items
        self.robots_tree.delete(*self.robots_tree.get_children())
        for index, item in enumerate(items):
            adv = item.adv
            name = adv.label if item.is_robot else f"{adv.label}（非机器人）"
            self.robots_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(name, adv.ipv4 or "—", f"{adv.rssi}" if adv.rssi is not None else "—"),
                tags=() if item.is_robot else ("muted",),
            )
            if previous == (adv.name, adv.address):
                self.robots_tree.selection_set(str(index))
        self.robot_count.configure(text=str(sum(1 for i in items if i.is_robot)))
        self._update_connect_button()
        self._sync_statusbar()

    def _sync_statusbar(self) -> None:
        count = sum(1 for item in self._robots if item.is_robot)
        self.sb_robots.configure(text=f"已找到 {count} 台机器人")

    # ── 连接 / 断开 ─────────────────────────────────────────────────────────

    def on_connect(self) -> None:
        selection = self.robots_tree.selection()
        if not selection:
            self.show_banner("先选一台机器人。", "info")
            return
        found = self._robot_by_iid(selection[0])
        if found is None or not found.is_robot:
            self.show_banner("这一行不是机器人。", "info")
            return
        if not self.demo and not BLEAK_AVAILABLE:
            self.show_banner("未安装 bleak，无法连接。见 ./install.sh。", "error")
            return

        pin = self.pin_var.get().strip() or protocol.DEFAULT_PIN
        self.hide_banner()
        self._set_tabs_enabled(False, "connecting")
        self._set_conn("warn", "连接中…", f"{found.adv.label} · 读取版本并认证")
        self.sb_conn.configure(text="连接：连接中…")
        self.connect_btn.state(["disabled"])

        async def demo_connect():
            from fake import FakeRobot

            robot = FakeRobot(log=self._log)
            link = robot.link()
            sess = await sessions.RobotSession.open(link, pin, log=self._log)
            return link, sess, None, found.adv

        async def real_connect():
            from agent import BluezPairingAgent

            agent = BluezPairingAgent(log=self._log)
            await agent.start()
            try:
                # 连接 + 读版本 + 订阅 + 认证，失败会换广播/重试（0x3E 是间歇性的）。
                link, sess = await ble.open_session(found.adv, pin, log=self._log)
            except BaseException:
                await agent.stop()
                raise
            return link, sess, agent, found.adv

        def ok(result: tuple[Any, sessions.RobotSession, Any, Any]) -> None:
            link, sess, agent, adv = result
            self._link = link
            self._session = sess
            self._agent = agent
            self._set_tabs_enabled(True)
            self._set_conn("ok", f"已连接 · API v{sess.api_version}", f"{adv.label} · {adv.address}")
            self.connect_btn.state(["disabled"])
            self.disconnect_btn.state(["!disabled"])
            self.robot_vars["api"].set(f"v{sess.api_version}")
            self.robot_vars["address"].set(adv.address)
            # 固定 IP 按机器人分别记。serial 要等 system.info 回来，先用广播地址兜底。
            self._robot_key = adv.address
            self.sb_conn.configure(text="连接：已连接")
            self._append_log(f"已连接 {adv.label}（{adv.address}）")
            self.show_banner(f"已连接 {adv.label} · API v{sess.api_version}", "ok")
            self._watch_disconnect(sess)
            self.on_refresh_status()
            self.on_refresh_info()
            self.on_scan_networks()

        def fail(exc: BaseException) -> None:
            self._reset_connection()
            self._op_failed(exc)

        self._guard(
            self.connect_btn,
            demo_connect() if self.demo else real_connect(),
            ok,
            fail,
        )

    def _watch_disconnect(self, session: sessions.RobotSession) -> None:
        async def watch() -> sessions.RobotSession:
            await session.disconnect_event.wait()
            return session

        def done(future: concurrent.futures.Future) -> None:
            if future.cancelled():
                return

            def finish() -> None:
                if self._closing or self._session is not session:
                    return
                if self._rebooting:
                    self._rebooting = False
                    self.show_banner("机器人正在重启，稍后重新扫描并连接。", "warn")
                else:
                    self.show_banner("与机器人的连接已断开。", "error")
                self._append_log("与机器人的连接已断开")
                self._reset_connection()

            self._post(finish)

        self._watch = self.worker.submit(watch())
        self._watch.add_done_callback(done)

    def on_disconnect(self) -> None:
        if self._session is None:
            return
        self.disconnect_btn.state(["disabled"])

        async def go() -> None:
            if self._watch is not None:
                self._watch.cancel()
            session = self._session
            if session is not None:
                await session.close()
            if self._agent is not None:
                await self._agent.stop()

        def ok(_: None) -> None:
            self._append_log("已断开")
            self.hide_banner()
            self._reset_connection()

        self._guard(self.disconnect_btn, go(), ok)

    def _reset_connection(self, reason: str = "idle") -> None:
        self._session = None
        self._link = None
        self._agent = None
        self._watch = None
        self._last_status = {}
        self._set_tabs_enabled(False, reason)
        self._set_conn("off", "未连接", "选一台机器人，填 PIN，然后连接")
        self.sb_conn.configure(text="连接：未连接")
        self.disconnect_btn.state(["disabled"])
        self.connect_btn.state(["!disabled"])
        self._update_connect_button()
        self.status_pill.configure(text="● 未连接", bg=PANEL2, fg=MUTED)
        self.status_ssid.configure(text="未连接", fg=MUTED)
        for var in self.status_vars.values():
            var.set("—")
        self.signal_label.configure(text="—")
        self._draw_signal(None)
        self._set_console(None)
        self._robot_key = ""
        self.status_source.configure(text="地址来源 —", fg=FAINT)
        self.last_refresh.configure(text="最后刷新 —")
        self._set_text(self.status_raw, "")
        for var in self.robot_vars.values():
            var.set("—")
        self.wifi_tree.delete(*self.wifi_tree.get_children())
        self._networks = []
        self._show_wifi_empty(True)
        # 列表和机器人身份都清了，编辑器也就没有对象了。
        self._load_static_editor()

    # ── 网络状态 ────────────────────────────────────────────────────────────

    def on_refresh_status(self) -> None:
        if self._session is None:
            return
        session = self._session

        def ok(status: dict[str, Any]) -> None:
            self._last_status = status
            state = str(status.get("state", "unavailable"))
            connected = state == "connected"
            self.status_pill.configure(
                text="● " + STATE_LABELS.get(state, state),
                bg=OK_WEAK if connected else PANEL2,
                fg=OK if connected else MUTED,
            )
            ssid = status.get("ssid")
            self.status_ssid.configure(
                text=ssid or ("未接入网络" if connected is False else "—"),
                fg=TEXT,
            )
            mac = status.get("mac") or "—"
            iface = status.get("iface") or "—"
            self.status_vars["iface_mac"].set(f"{iface} · {mac}")
            ip4 = status.get("ip4") or "—"
            self.status_vars["ip4"].set(ip4)
            self.status_vars["ip6"].set(f"IPv6：{status.get('ip6') or '—'}")
            # 固定地址与 DHCP 在 net.status 里长得一样，只有本地记得住自己下发过什么。
            saved = self.profiles.static_ipv4(self._robot_key, str(ssid or ""))
            pinned = saved is not None and ip4 != "—"
            if pinned:
                # 短：这一行在左卡片里，写全（掩码、网关、DNS）会把卡片撑破。
                self.status_source.configure(
                    text=f"地址来源 固定 {saved.get('address')}/{saved.get('prefix')}", fg=OK
                )
            else:
                self.status_source.configure(text="地址来源 DHCP", fg=FAINT)
            signal = status.get("signal")
            self.signal_label.configure(text=f"{signal}%" if signal is not None else "—")
            self._draw_signal(signal if isinstance(signal, int) else None)
            self._set_console(None if ip4 == "—" else str(ip4))
            self.last_refresh.configure(text=f"最后刷新 {time.strftime('%H:%M:%S')}")
            self._set_text(
                self.status_raw, json.dumps(status, ensure_ascii=False, indent=2)
            )
            self._toggle_raw()

        self._guard(self.status_btn, session.net_status(), ok)

    def _toggle_raw(self) -> None:
        if self.raw_toggle.get():
            self.status_raw.pack(fill="both", expand=True)
        else:
            self.status_raw.pack_forget()

    def _draw_signal(self, percent: int | None) -> None:
        canvas = self.signal_canvas
        canvas.delete("all")
        heights = (6, 11, 17, 23)
        thresholds = (1, 35, 60, 80)
        for index, (height, threshold) in enumerate(zip(heights, thresholds)):
            active = percent is not None and percent >= threshold
            x0 = 2 + index * 10
            canvas.create_rectangle(
                x0,
                26 - height,
                x0 + 5,
                25,
                fill=OK if active else "#DDE3EA",
                outline="",
            )

    def _copy_ip(self) -> None:
        ip = self.status_vars["ip4"].get()
        if not ip or ip == "—":
            self.show_banner("当前没有 IPv4 地址。", "info")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(ip)
        self.show_banner(f"已复制 {ip}", "ok")

    def _open_console(self) -> None:
        if not self._console_url:
            self.show_banner("当前没有 IPv4 地址，机器人还没有控制台可开。", "info")
            return
        self._append_log(f"打开 {self._console_url}")
        try:
            webbrowser.open(self._console_url)
        except Exception as exc:  # 没有 xdg-open / 默认浏览器时别静默失败
            self.show_banner(f"没能打开浏览器：{exc}", "warn")

    def _set_console(self, ip4: str | None) -> None:
        """控制台地址是状态的一部分：地址变了，链接的可点性也跟着变。"""
        self._console_url = f"http://{ip4}:8001" if ip4 else None
        if self._console_url:
            self.console_label.configure(
                text=self._console_url, fg=ACCENT, font=self.font_link, cursor="hand2"
            )
        else:
            self.console_label.configure(text="—", fg=MUTED, font=self.font_mono, cursor="arrow")

    # ── 机器人身份 / 日志 / 重启 ────────────────────────────────────────────

    def on_refresh_info(self) -> None:
        if self._session is None:
            return
        session = self._session

        def ok(info: dict[str, Any]) -> None:
            self.robot_vars["name"].set(info.get("name") or "—")
            self.robot_vars["serial"].set(info.get("serial") or "—")
            self.robot_vars["uptime"].set(
                protocol.format_uptime(info.get("uptime_seconds"))
            )
            self.new_name.set(info.get("name") or "")
            # 序列号比 BLE 地址稳（机器人的广播地址有两个），有就用它当键。
            serial = str(info.get("serial") or "").strip()
            if serial and serial != self._robot_key:
                self._robot_key = serial
                self._load_static_editor()

        self._guard(self.status_btn, session.system_info(), ok)

    def on_rename(self) -> None:
        if self._session is None:
            return
        name = self.new_name.get().strip()
        if not name:
            self.show_banner("新名称不能为空。", "info")
            return
        session = self._session

        def ok(stored: str) -> None:
            self.robot_vars["name"].set(stored)
            self.new_name.set(stored)
            selection = self.robots_tree.selection()
            if selection:
                iid = selection[0]
                robot = self._robot_by_iid(iid)
                values = list(self.robots_tree.item(iid, "values"))
                values[0] = stored
                self.robots_tree.item(iid, values=values)
                if robot is not None:
                    self._robots[int(iid)] = replace(
                        robot, adv=replace(robot.adv, name=stored)
                    )
            version = self._session.api_version if self._session else 0
            address = self.robot_vars["address"].get()
            self._set_conn("ok", f"已连接 · API v{version}", f"{stored} · {address}")
            self.show_banner(f"名称已改为 {stored}（广播名称已更新）", "ok")
            self._append_log(f"名称已改为 {stored}")

        self._guard(self.rename_btn, session.set_name(name), ok)

    def on_read_logs(self) -> None:
        if self._session is None:
            return
        unit = self.log_unit.get().strip() or "robotd"
        try:
            lines = int(self.log_lines.get())
        except ValueError:
            self.show_banner("行数必须是整数。", "info")
            return
        lines = max(1, min(lines, 500))
        session = self._session
        self.logs_note.configure(text="读取中…")

        def ok(result: dict[str, Any]) -> None:
            unit_name = str(result.get("unit", unit))
            lines_out = result.get("lines") or []
            truncated = bool(result.get("truncated"))
            header = f"-- {unit_name} · 最近 {len(lines_out)} 行 --\n"
            self._set_text(self.device_log, header + "\n".join(lines_out))
            if truncated:
                self.logs_note.configure(
                    text=f"日志过长，机器人已截断；只显示最近 {len(lines_out)} 行。"
                )
            else:
                self.logs_note.configure(text=f"已读取 {len(lines_out)} 行。")

        def fail(exc: BaseException) -> None:
            self.logs_note.configure(text="读取失败")
            self._op_failed(exc)

        self._guard(
            self.logs_btn, session.logs(unit, lines=lines), ok, fail
        )

    def on_reboot(self) -> None:
        if self._session is None:
            return
        confirmed = self._confirm(
            "重启机器人？",
            "机器人会先回包，然后在约 3 秒后重启。当前连接会断开，关节会卸力——"
            "请先让机器人坐下或扶住它。",
            ok_text="重启",
            danger=True,
        )
        if not confirmed:
            return
        session = self._session
        self._rebooting = True

        def ok(seconds: int) -> None:
            self.show_banner(
                f"重启指令已接受，机器人将在约 {seconds} 秒后重启。连接会断开。",
                "warn",
            )
            self._append_log(f"机器人将在约 {seconds} 秒后重启")

        def fail(exc: BaseException) -> None:
            self._rebooting = False
            self._op_failed(exc)

        self._guard(self.reboot_btn, session.reboot(), ok, fail)

    # ── Wi-Fi ───────────────────────────────────────────────────────────────

    def _show_wifi_empty(self, empty: bool) -> None:
        if empty:
            self.wifi_empty.tkraise()
        else:
            self.wifi_tree.tkraise()

    def on_scan_networks(self) -> None:
        if self._session is None:
            return
        session = self._session
        self.wifi_hint.configure(text="扫描中…")
        self._append_log("→ net.scan")

        def ok(networks: list[dict[str, Any]]) -> None:
            previous = self._static_target_ssid() or ""
            self._networks = networks
            self.wifi_tree.delete(*self.wifi_tree.get_children())
            for index, network in enumerate(networks):
                security = str(network.get("security", ""))
                unsupported = security in ("wep", "enterprise")
                self.wifi_tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        network.get("ssid", ""),
                        f"{network.get('signal', '—')}%",
                        SECURITY_LABELS.get(security, security),
                        "已保存" if network.get("saved") else "",
                    ),
                    tags=("dim",) if unsupported else (),
                )
            self._show_wifi_empty(not networks)
            # 重扫会清空选中行；把原来那一行选回去，编辑器才还在说同一个网络。
            if previous:
                for index, network in enumerate(networks):
                    if network.get("ssid") == previous:
                        self.wifi_tree.selection_set(str(index))
                        break
            self._load_static_editor()
            self.wifi_hint.configure(
                text=f"扫描到 {len(networks)} 个网络 · {time.strftime('%H:%M:%S')}"
            )
            self._append_log(f"· 扫描到 {len(networks)} 个网络")

        def fail(exc: BaseException) -> None:
            self.wifi_hint.configure(text="扫描失败")
            self._op_failed(exc)

        self._guard(self.wifi_scan_btn, session.net_scan(), ok, fail)

    def on_connect_network(self) -> None:
        if self._session is None:
            return
        network = self._selected_network()
        if network is None:
            self.show_banner("先选一个网络。", "info")
            return
        ssid = str(network.get("ssid", ""))
        security = str(network.get("security", "open"))

        if security in ("wep", "enterprise"):
            self.show_banner(
                f"{ssid}：{SECURITY_LABELS.get(security, security)}。"
                "这个 API 不支持该加密方式；请换一个网络，或用网线/SSH 配置。",
                "error",
            )
            return

        if security == "open":
            self._start_network_connect(ssid, psk=None)
            return

        # 密码记得住，才不用每次都输：机器人只回 "saved" 不回答码，本地没存就只能问。
        psk = self.profiles.password(ssid)
        if psk is None:
            psk = self._ask_password(ssid)
            if psk is None:
                return
            if not psk:
                self.show_banner("这个网络需要密码。", "info")
                return
            self.profiles.set_password(ssid, psk)
        else:
            self._append_log(f"用记住的密码连接 {ssid}")
        self._start_network_connect(ssid, psk=psk)

    def _start_network_connect(
        self,
        ssid: str,
        psk: str | None,
        *,
        ipv4: dict[str, Any] | None = None,
        offer_retry: bool = True,
        skip_static: bool = False,
    ) -> None:
        if self._session is None:
            return
        session = self._session
        if ipv4 is None and not skip_static:
            ipv4 = self.profiles.static_ipv4(self._robot_key, ssid)

        hint = f"正在连接 {ssid}…"
        if ipv4:
            hint += f"（固定 {ipv4.get('address')}）"
        self.wifi_hint.configure(text=hint)
        self._append_log(
            f"连接 {ssid}…" + (f" 固定 IP {profiles.describe(ipv4)}" if ipv4 else "")
        )

        def ok(result: dict[str, Any]) -> None:
            if result.get("outcome") == "connected":
                if psk:
                    self.profiles.set_password(ssid, psk)
                ip = result.get("ip4") or "还没拿到 IP"
                self.wifi_hint.configure(text=f"已连接 {ssid}")
                self.show_banner(
                    f"已连接 {ssid} · {ip}",
                    "ok",
                    action_text="复制 IP",
                    action=lambda: self._copy_text(str(ip)),
                )
                self._append_log(f"已连接 {ssid}，IP {ip}")
                self.on_refresh_status()
                self.on_scan_networks()
                self._load_static_editor()
                return

            reason = str(result.get("reason", "other"))
            detail = str(result.get("detail") or "")
            hint = REASON_LABELS.get(reason, reason)
            self.wifi_hint.configure(text=hint)
            self.show_banner(f"{hint}。{detail}".strip(), "error")
            self._append_log(f"连接失败：{reason} {detail}")

            # 密码被拒才是"再问一次"的信号；网络不可见/超时再问密码只会让人以为是自己输错了。
            if reason == "bad_key" and offer_retry:
                self._retry_with_new_password(ssid, ipv4, detail)

        def fail(exc: BaseException) -> None:
            # 板上的 configd 比这个 App 旧时不认识 ipv4，整条请求会失败——退回 DHCP 连线，
            # 同时把话说清楚，别让人以为是自己密码输错了。
            if ipv4 and not skip_static and sessions.rejects_ipv4(exc):
                self._append_log("机器人上的 configd 不认识 ipv4 参数，退回 DHCP 连接")
                self.show_banner(
                    "机器人上的配置服务还不支持固定 IP，这次先按 DHCP 连上；"
                    "要钉地址需要先更新机器人侧的 configd（见文档 §2）。",
                    "warn",
                )
                self._start_network_connect(
                    ssid, psk, ipv4=None, offer_retry=offer_retry, skip_static=True
                )
                return
            self.wifi_hint.configure(text="连接失败")
            self._op_failed(exc)

        self._guard(self.wifi_connect_btn, session.net_connect(ssid, psk, ipv4), ok, fail)

    def _retry_with_new_password(
        self, ssid: str, ipv4: dict[str, Any] | None, detail: str
    ) -> None:
        """密码错了：忘掉记住的那个，问一次新的，然后再试一次（只再试一次）。"""
        self.profiles.drop_password(ssid)
        psk = self._ask_password(ssid, error="机器人拒绝了这个密码，请重新输入。")
        if psk is None or not psk:
            return
        self.profiles.set_password(ssid, psk)
        self._start_network_connect(ssid, psk, ipv4=ipv4, offer_retry=False)

    def _copy_text(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.show_banner(f"已复制 {text}", "ok")

    def _ask_password(self, ssid: str, *, error: str = "") -> str | None:
        dialog, body = self._dialog(f"连接 {ssid}")
        field = tk.Frame(body, bg=PANEL)
        field.pack(fill="x")
        tk.Label(field, text="密码", bg=PANEL, fg=MUTED, width=6, anchor="w").pack(
            side="left"
        )
        value = tk.StringVar()
        entry = ttk.Entry(field, textvariable=value, width=32, show="•")
        entry.pack(side="left")
        entry.focus_set()

        def toggle_show() -> None:
            entry.configure(show="" if entry.cget("show") else "•")

        tk.Button(
            field,
            text="显示",
            bg=PANEL,
            fg=MUTED,
            activebackground=PANEL,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=self.font_small,
            command=toggle_show,
        ).pack(side="left", padx=6)

        tk.Label(
            body,
            text=error
            or "连接成功后这个密码会记在本机，下次点连接就直接连，不再问。",
            bg=DANGER_WEAK if error else PANEL,
            fg=DANGER if error else FAINT,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=380,
            padx=8 if error else 0,
            pady=6 if error else 0,
        ).pack(fill="x", pady=(8, 0))

        result: dict[str, str | None] = {"value": None}

        def accept() -> None:
            result["value"] = value.get()
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="取消", command=cancel).pack(side="right")
        ttk.Button(buttons, text="连接", style="Primary.TButton", command=accept).pack(
            side="right", padx=(0, 6)
        )
        dialog.bind("<Return>", lambda _e: accept())
        dialog.bind("<Escape>", lambda _e: cancel())
        self.root.wait_window(dialog)
        return result["value"]

    def on_forget_network(self) -> None:
        network = self._selected_network()
        if network is None:
            self.show_banner("先选一个网络。", "info")
            return
        self._forget(str(network.get("ssid", "")))

    def on_forget_typed(self) -> None:
        ssid = self.manual_ssid.get().strip()
        if not ssid:
            self.show_banner("先输入 SSID。", "info")
            return
        self._forget(ssid)

    def _forget(self, ssid: str) -> None:
        if self._session is None:
            return
        if not self._confirm(
            "忘记网络",
            f"让机器人忘掉 {ssid} 的已保存密码？之后需要重新输入密码。",
            ok_text="忘记",
        ):
            return
        session = self._session

        def ok(removed: bool) -> None:
            # 本地那份跟着忘：留着它只会在下一次连接时被当成对的密码重发一遍。
            self.profiles.forget(ssid)
            self._load_static_editor()
            self._append_log(
                f"忘记 {ssid}：{'已删除' if removed else '没有已保存的配置'}"
            )
            if removed:
                self.show_banner(f"已忘记 {ssid}", "ok")
            else:
                self.show_banner(f"{ssid} 没有已保存的配置", "info")
            self.on_scan_networks()
            self.on_refresh_status()

        self._guard(self.wifi_forget_btn, session.net_forget(ssid), ok)

    # ── 诊断 ────────────────────────────────────────────────────────────────

    def on_diag_send(self) -> None:
        if self._session is None:
            return
        method = self.diag_method.get().strip()
        if not method:
            return
        raw = self.diag_params.get("1.0", "end").strip() or "{}"
        try:
            params = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.show_banner(f"参数不是 JSON：{exc}", "error")
            return
        if not isinstance(params, dict):
            self.show_banner("params 必须是一个 JSON 对象。", "error")
            return

        timeout = sessions.SLOW_TIMEOUT if method in ("net.scan", "net.connect", "system.logs") else sessions.DEFAULT_TIMEOUT
        session = self._session
        self._set_text(self.diag_output, "等待回答…")

        def ok(result: dict[str, Any]) -> None:
            self._set_text(self.diag_output, json.dumps(result, ensure_ascii=False, indent=2))

        def fail(exc: BaseException) -> None:
            self._set_text(self.diag_output, f"错误：{exc}")
            self._op_failed(exc)

        self._guard(self.diag_btn, session.call(method, params, timeout=timeout), ok, fail)

    # ── 对话框 ──────────────────────────────────────────────────────────────

    def _dialog(self, title: str) -> tuple[tk.Toplevel, tk.Frame]:
        dialog = tk.Toplevel(self.root, bg=PANEL)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        body = tk.Frame(dialog, bg=PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=(14, 16))
        tk.Label(
            body, text=title, bg=PANEL, fg=TEXT, font=self.font_card, anchor="w"
        ).pack(fill="x", pady=(0, 12))
        self.root.after(30, lambda: self._center(dialog))
        return dialog, body

    def _center(self, dialog: tk.Toplevel) -> None:
        if not dialog.winfo_exists():
            return
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _confirm(self, title: str, message: str, *, ok_text: str, danger: bool = False) -> bool:
        dialog, body = self._dialog(title)
        box = tk.Frame(
            body,
            bg=WARN_WEAK if not danger else DANGER_WEAK,
            highlightthickness=1,
            highlightbackground="#EAD9A8" if not danger else "#EFC9CD",
        )
        box.pack(fill="x")
        tk.Label(
            box,
            text=("⚠ " if danger else "! ") + message,
            bg=box["bg"],
            fg="#7A5200" if not danger else "#8C1D26",
            font=self.font_small,
            justify="left",
            anchor="w",
            wraplength=400,
        ).pack(fill="x", padx=10, pady=9)

        result = {"ok": False}

        def accept() -> None:
            result["ok"] = True
            dialog.destroy()

        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text=ok_text,
            style="Danger.TButton" if danger else "Primary.TButton",
            command=accept,
        ).pack(side="right", padx=(0, 6))
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        self.root.wait_window(dialog)
        return result["ok"]

    def _show_help(self) -> None:
        dialog, body = self._dialog("使用帮助")
        text = (
            "1. 点「重新扫描」，选中机器人。\n"
            "2. 输入 PIN（出厂 000000），点「连接」。\n"
            "3. 在「Wi-Fi」页扫描并连接网络——密码记一次，之后点连接直接连。\n"
            "4. 想让机器人固定用某个地址：在「固定 IP」卡片里填好保存，下次连接生效。\n"
            "5. 在「机器人」页可以改名、看日志、重启。\n\n"
            "命令行：\n"
            "  ./app.py            真机\n"
            "  ./app.py --demo     进程内假机器人\n"
            "  ./acceptance.py     只读验收\n\n"
            "排障：蓝牙未开启时执行\n"
            "  rfkill unblock bluetooth\n"
            "  bluetoothctl power on\n\n"
            "文档：README.md（用法）· ../docs/design/ble-provisioning-app.md（设计）"
        )
        tk.Label(
            body,
            text=text,
            bg=PANEL,
            fg=TEXT,
            font=self.font_small,
            justify="left",
            anchor="w",
        ).pack(fill="both", expand=True)
        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="关闭", command=dialog.destroy).pack(side="right")
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        self.root.wait_window(dialog)

    # ── 退出 ────────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self._closing = True
        try:
            future = self.worker.submit(self._shutdown())
            future.result(timeout=3.0)
        except Exception:
            pass
        self.worker.stop()
        self.root.destroy()

    async def _shutdown(self) -> None:
        if self._watch is not None:
            self._watch.cancel()
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
        if self._agent is not None:
            try:
                await self._agent.stop()
            except Exception:
                pass


def _single_instance() -> "object | None":
    """拿一把单实例锁；已经有一个在跑就返回 None。

    BLE 一次只服务一个中心，两个窗口同时开着只会互相把对方顶掉——用户看到的
    "上一条蓝牙操作还没结束" 多半就是这么来的。锁文件放在 XDG_RUNTIME_DIR（重启即清）。
    """
    import fcntl
    import os

    directory = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = os.path.join(directory, f"ducknet-{os.getuid()}.lock")
    handle = open(path, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ducknet",
        description="通过蓝牙连接 Microduck 机器人并修改它的网络配置。",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用进程内假机器人，不访问蓝牙（先熟悉界面用）",
    )
    parser.add_argument(
        "--scan-time",
        type=float,
        default=DEFAULT_SCAN_SECONDS,
        help=f"每次扫描的秒数（默认 {DEFAULT_SCAN_SECONDS:.0f}）",
    )
    args = parser.parse_args(argv)

    lock = _single_instance()
    if lock is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            APP_TITLE,
            "已经有一个「Microduck 蓝牙配网」在运行了。\n\n"
            "蓝牙一次只服务一个中心，两个窗口同时开着会互相把对方顶掉。\n"
            "请切到已经打开的那个窗口。",
        )
        root.destroy()
        return 1

    root = tk.Tk()
    App(root, demo=args.demo, scan_seconds=args.scan_time)
    root.mainloop()
    _ = lock  # 进程活着期间一直持有
    return 0


if __name__ == "__main__":
    sys.exit(main())
