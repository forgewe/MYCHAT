#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MyChat Android (Kivy) — 与电脑版局域网协议兼容（发现 + 文字聊天）
在同一 Wi‑Fi 下可与 Windows MyChat 互发消息。
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from collections import defaultdict
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput

APP_NAME = "MyChat"
APP_VERSION = "20260924.A1"
DEFAULT_UDP_PORT = 2425
UDP_PORT_CANDIDATES = [2425, 2426, 2427, 2428, 34567, 34568]
BROADCAST_ADDR = "255.255.255.255"

KV = """
<LoginScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(24)
        spacing: dp(12)
        Label:
            text: "MyChat 手机版"
            font_size: "22sp"
            size_hint_y: None
            height: dp(40)
        Label:
            text: "与电脑版同一 Wi‑Fi 即可互聊"
            font_size: "13sp"
            color: 0.5, 0.5, 0.5, 1
            size_hint_y: None
            height: dp(28)
        TextInput:
            id: name_in
            hint_text: "昵称"
            multiline: False
            size_hint_y: None
            height: dp(44)
        TextInput:
            id: group_in
            text: "默认"
            hint_text: "班级/分组"
            multiline: False
            size_hint_y: None
            height: dp(44)
        Button:
            text: "进入"
            size_hint_y: None
            height: dp(48)
            background_color: 0.03, 0.76, 0.38, 1
            on_press: root.do_login()

<MainScreen>:
    BoxLayout:
        orientation: "vertical"
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            padding: dp(8)
            spacing: dp(6)
            Label:
                id: title
                text: "MyChat"
                text_size: self.size
                halign: "left"
                valign: "middle"
            Button:
                text: "刷新"
                size_hint_x: None
                width: dp(72)
                on_press: root.do_refresh()
        BoxLayout:
            # left users / right chat
            BoxLayout:
                orientation: "vertical"
                size_hint_x: 0.38
                Label:
                    text: "在线"
                    size_hint_y: None
                    height: dp(28)
                RecycleView:
                    id: user_rv
                    viewclass: "UserBtn"
                    data: root.user_data
                    RecycleBoxLayout:
                        default_size: None, dp(40)
                        default_size_hint: 1, None
                        size_hint_y: None
                        height: self.minimum_height
                        orientation: "vertical"
            BoxLayout:
                orientation: "vertical"
                size_hint_x: 0.62
                Label:
                    id: chat_title
                    text: "选择联系人"
                    size_hint_y: None
                    height: dp(28)
                    color: 0.2, 0.2, 0.2, 1
                ScrollView:
                    Label:
                        id: chat_log
                        text: ""
                        size_hint_y: None
                        height: self.texture_size[1]
                        text_size: self.width, None
                        padding: dp(8), dp(8)
                        halign: "left"
                        valign: "top"
                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(6)
                    padding: dp(4)
                    TextInput:
                        id: msg_in
                        hint_text: "输入消息"
                        multiline: False
                    Button:
                        text: "发送"
                        size_hint_x: None
                        width: dp(72)
                        background_color: 0.03, 0.76, 0.38, 1
                        on_press: root.do_send()

<UserBtn@Button>:
    size_hint_y: None
    height: dp(40)
    font_size: "13sp"
    on_release: app.root.get_screen("main").select_user(self.text, self.ip)
"""


class UserBtn(Button):
    ip = StringProperty("")


class NetCore:
    def __init__(self, username: str, group: str, on_event):
        self.username = username
        self.group = group
        self.hostname = socket.gethostname()
        self.role = "student"
        self.on_event = on_event
        self.running = False
        self.udp_sock = None
        self.udp_port = DEFAULT_UDP_PORT
        self.tcp_port = 2426
        self.video_port = 2433
        self.local_ip = self._get_local_ip()
        self.users = {}  # ip -> dict
        self.chat_history = defaultdict(list)

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except Exception:
            pass
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

    def start(self):
        self.running = True
        last = None
        for port in UDP_PORT_CANDIDATES:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                except Exception:
                    pass
                sock.bind(("", port))
                sock.settimeout(0.5)
                self.udp_sock = sock
                self.udp_port = port
                break
            except Exception as e:
                last = e
                try:
                    sock.close()
                except Exception:
                    pass
        if not self.udp_sock:
            raise RuntimeError(f"无法绑定 UDP: {last}")
        threading.Thread(target=self._udp_loop, daemon=True).start()
        self.discover()
        threading.Thread(target=self._heartbeat, daemon=True).start()

    def stop(self):
        self.running = False
        try:
            self._broadcast({"type": "OFFLINE", "username": self.username})
        except Exception:
            pass
        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass

    def _broadcast(self, data: dict):
        data = dict(data)
        data["udp_port"] = self.udp_port
        data["tcp_port"] = self.tcp_port
        data["video_port"] = self.video_port
        data["ip"] = self.local_ip
        msg = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ports = set(UDP_PORT_CANDIDATES) | {self.udp_port}
        for baddr in (BROADCAST_ADDR,):
            for port in ports:
                try:
                    self.udp_sock.sendto(msg, (baddr, port))
                except Exception:
                    pass

    def _send_udp(self, data: dict, target_ip: str, target_port=None):
        data = dict(data)
        data.setdefault("udp_port", self.udp_port)
        data.setdefault("tcp_port", self.tcp_port)
        data.setdefault("ip", self.local_ip)
        msg = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ports = []
        if target_port:
            ports.append(int(target_port))
        ports.extend(UDP_PORT_CANDIDATES)
        seen = set()
        for p in ports:
            if p in seen:
                continue
            seen.add(p)
            try:
                self.udp_sock.sendto(msg, (target_ip, p))
            except Exception:
                pass

    def discover(self):
        self._broadcast({
            "type": "ONLINE",
            "username": self.username,
            "hostname": self.hostname,
            "group": self.group,
            "role": self.role,
        })
        self._broadcast({
            "type": "WHO",
            "username": self.username,
            "hostname": self.hostname,
            "group": self.group,
            "role": self.role,
        })

    def _heartbeat(self):
        while self.running:
            try:
                self._broadcast({
                    "type": "ONLINE",
                    "username": self.username,
                    "hostname": self.hostname,
                    "group": self.group,
                    "role": self.role,
                })
            except Exception:
                pass
            time.sleep(8)

    def _udp_loop(self):
        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(65535)
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    time.sleep(0.1)
                continue
            ip = addr[0]
            if ip == self.local_ip:
                continue
            try:
                msg = json.loads(data.decode("utf-8"))
            except Exception:
                continue
            self._handle(msg, ip)

    def _handle(self, msg: dict, ip: str):
        mtype = msg.get("type")
        if mtype in ("ONLINE", "WHO"):
            uname = msg.get("username") or "未知"
            self.users[ip] = {
                "username": uname,
                "group": msg.get("group", ""),
                "udp_port": msg.get("udp_port", DEFAULT_UDP_PORT),
                "role": msg.get("role", "student"),
            }
            if mtype == "WHO":
                self._send_udp({
                    "type": "ONLINE",
                    "username": self.username,
                    "hostname": self.hostname,
                    "group": self.group,
                    "role": self.role,
                }, ip, target_port=msg.get("udp_port"))
            self.on_event("users")
        elif mtype == "OFFLINE":
            self.users.pop(ip, None)
            self.on_event("users")
        elif mtype == "TEXT":
            to = msg.get("to")
            if to and to != self.local_ip:
                return
            sender = msg.get("username", "未知")
            content = msg.get("content", "")
            ts = datetime.now().strftime("%H:%M:%S")
            self.chat_history[ip].append((ts, sender, content))
            self.on_event("text", ip=ip, sender=sender, content=content, ts=ts)

    def send_text(self, target_ip: str, content: str):
        content = (content or "").strip()
        if not content:
            return
        payload = {
            "type": "TEXT",
            "username": self.username,
            "content": content,
            "to": target_ip,
        }
        peer = self.users.get(target_ip, {})
        peer_udp = peer.get("udp_port")
        self._send_udp(payload, target_ip, target_port=peer_udp)
        self._broadcast(payload)
        ts = datetime.now().strftime("%H:%M:%S")
        self.chat_history[target_ip].append((ts, "我", content))
        self.on_event("text_self", ip=target_ip, content=content, ts=ts)


class LoginScreen(Screen):
    def do_login(self):
        name = self.ids.name_in.text.strip() or "手机用户"
        group = self.ids.group_in.text.strip() or "默认"
        app = App.get_running_app()
        app.start_net(name, group)
        app.root.current = "main"


class MainScreen(Screen):
    user_data = ListProperty([])

    def on_enter(self, *args):
        app = App.get_running_app()
        self.ids.title.text = f"{app.net.username} · {app.net.local_ip}"
        self.refresh_users()

    def do_refresh(self):
        App.get_running_app().net.discover()
        self.refresh_users()

    def refresh_users(self):
        app = App.get_running_app()
        data = []
        for ip, u in sorted(app.net.users.items(), key=lambda x: x[1]["username"]):
            data.append({
                "text": f"{u['username']}\n{ip}",
                "ip": ip,
            })
        if not data:
            data = [{"text": "(暂无用户)\n点刷新", "ip": ""}]
        self.user_data = data

    def select_user(self, text, ip):
        if not ip:
            return
        app = App.get_running_app()
        app.current_ip = ip
        u = app.net.users.get(ip, {})
        self.ids.chat_title.text = f"{u.get('username', ip)}"
        lines = []
        for ts, sender, content in app.net.chat_history.get(ip, []):
            lines.append(f"{ts} {sender}\n{content}\n")
        self.ids.chat_log.text = "\n".join(lines) if lines else "开始聊天吧"

    def do_send(self):
        app = App.get_running_app()
        ip = app.current_ip
        if not ip:
            return
        msg = self.ids.msg_in.text
        app.net.send_text(ip, msg)
        self.ids.msg_in.text = ""
        self.select_user("", ip)

    def append_msg(self, ip, sender, content, ts):
        app = App.get_running_app()
        if app.current_ip == ip:
            self.ids.chat_log.text += f"\n{ts} {sender}\n{content}\n"


class MyChatApp(App):
    def build(self):
        self.net = None
        self.current_ip = None
        Builder.load_string(KV)
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(MainScreen(name="main"))
        return sm

    def start_net(self, username, group):
        def on_event(kind, **kw):
            Clock.schedule_once(lambda dt: self._ui_event(kind, **kw), 0)

        self.net = NetCore(username, group, on_event)
        try:
            self.net.start()
        except Exception as e:
            popup = Popup(
                title="网络错误",
                content=Label(text=str(e)),
                size_hint=(0.8, 0.4),
            )
            popup.open()

    def _ui_event(self, kind, **kw):
        main = self.root.get_screen("main")
        if kind == "users":
            main.refresh_users()
        elif kind == "text":
            main.append_msg(kw["ip"], kw["sender"], kw["content"], kw["ts"])
            main.refresh_users()
        elif kind == "text_self":
            main.select_user("", kw["ip"])

    def on_stop(self):
        if self.net:
            self.net.stop()


if __name__ == "__main__":
    MyChatApp().run()
