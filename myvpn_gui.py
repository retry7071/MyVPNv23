from __future__ import annotations

import base64
import ctypes
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import winreg
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPalette, QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QSplitter,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

def _ensure_admin():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    if not is_admin:
        params = " ".join(f'"{a}"' for a in sys.argv)
        try:
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas",
                sys.executable,
                params,
                None, 1
            )
            if result > 32:
                sys.exit(0)
        except Exception:
            pass


def _resolve_base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


C_BG0    = "#181B1F"
C_BG1    = "#22262B"
C_BG2    = "#2A2F36"
C_ORANGE = "#FF864A"
C_BLUE   = "#2D8CFF"
C_GREEN  = "#17C964"
C_RED    = "#FF4A6A"
C_YELLOW = "#FFD26A"
C_TEXT   = "#E8EBF0"
C_MUTED  = "#7A8399"
RADIUS   = 12

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C_BG0};
    color: {C_TEXT};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}
QFrame#card {{
    background-color: {C_BG1};
    border-radius: {RADIUS}px;
    padding: 4px;
}}
QLineEdit {{
    background-color: {C_BG2};
    color: {C_TEXT};
    border: 1.5px solid {C_BG2};
    border-radius: {RADIUS}px;
    padding: 6px 12px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border-color: {C_ORANGE};
}}
QPushButton#connect {{
    background-color: {C_ORANGE};
    color: #fff;
    border: none;
    border-radius: {RADIUS}px;
    padding: 8px 24px;
    font-weight: bold;
    font-size: 15px;
    text-align: left;
}}
QPushButton#connect:hover {{ background-color: #ff9d6b; }}
QPushButton#connect:disabled {{ background-color: #5a3a26; color: #888; }}
QPushButton#disconnect {{
    background-color: {C_BG2};
    color: {C_TEXT};
    border: 1.5px solid #444a55;
    border-radius: {RADIUS}px;
    padding: 8px 24px;
    font-weight: bold;
    font-size: 15px;
    text-align: left;
}}
QPushButton#disconnect:hover {{ background-color: #353b44; }}
QPushButton#disconnect:disabled {{ background-color: {C_BG2}; color: #555; border-color: #333; }}
"""

LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAAYAAAAGACAYAAACkx7W/AAAQAElEQVR4Aey9B6AcR5W2/VR1mHSzcrYk27IcJOeIEw7YYGySCSYaMDmzLLAs4CWnJWNyDguYJYMxJtg4Z8tBVs7SlW4Ok6e7639rJJP+3W+/b9eBxbfVZ6q6usKpU1XvOXVq7sg[...]"

COUNTRY_FLAGS = {
    "ru": "RU", "us": "US", "de": "DE", "nl": "NL", "fi": "FI",
    "fr": "FR", "gb": "GB", "jp": "JP", "sg": "SG", "ua": "UA",
    "pl": "PL", "se": "SE", "tr": "TR", "ir": "IR",
}


def _country(host: str) -> str:
    for cc in COUNTRY_FLAGS:
        if cc in host.lower():
            return COUNTRY_FLAGS[cc]
    return ""


def parse_uri(uri: str) -> Optional[dict]:
    uri = uri.strip()
    try:
        if uri.startswith("vless://"):
            p = urllib.parse.urlparse(uri)
            qs = dict(urllib.parse.parse_qsl(p.query))
            name = urllib.parse.unquote(p.fragment) or p.hostname or "VLESS"
            return {
                "name": name, "host": p.hostname, "port": p.port or 443,
                "protocol": "VLESS", "transport": qs.get("type", "tcp"),
                "cred": p.username, "params": qs,
                "country": _country(p.hostname or ""),
                "kind": "sub",
            }
        if uri.startswith("trojan://"):
            p = urllib.parse.urlparse(uri)
            qs = dict(urllib.parse.parse_qsl(p.query))
            name = urllib.parse.unquote(p.fragment) or p.hostname or "Trojan"
            return {
                "name": name, "host": p.hostname, "port": p.port or 443,
                "protocol": "Trojan", "transport": qs.get("type", "tcp"),
                "cred": p.username, "params": qs,
                "country": _country(p.hostname or ""),
                "kind": "sub",
            }
        if uri.startswith("ss://"):
            p = urllib.parse.urlparse(uri)
            name = urllib.parse.unquote(p.fragment) or p.hostname or "SS"
            try:
                userinfo = base64.b64decode(p.username + "==").decode()
                method, password = userinfo.split(":", 1)
            except Exception:
                method, password = "aes-256-gcm", p.username or ""
            return {
                "name": name, "host": p.hostname, "port": p.port or 443,
                "protocol": "Shadowsocks", "transport": method,
                "cred": password, "params": {},
                "country": _country(p.hostname or ""),
                "kind": "sub",
            }
        if uri.startswith("vmess://"):
            data = base64.b64decode(uri[8:] + "==").decode()
            d = json.loads(data)
            name = d.get("ps") or d.get("add") or "VMess"
            return {
                "name": name, "host": d.get("add", ""), "port": int(d.get("port", 443)),
                "protocol": "VMess", "transport": d.get("net", "tcp"),
                "cred": d.get("id", ""), "params": d,
                "country": _country(d.get("add", "")),
                "kind": "sub",
            }
    except Exception:
        pass
    return None


def parse_subscription(raw: str) -> list[dict]:
    servers: list[dict] = []
    try:
        decoded = base64.b64decode(raw.strip() + "==").decode(errors="ignore")
        raw = decoded
    except Exception:
        pass
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        srv = parse_uri(line)
        if srv:
            servers.append(srv)
    return servers


class SubWorker(QThread):
    done   = pyqtSignal(list)
    error  = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            r = requests.get(self.url, timeout=15)
            r.raise_for_status()
            servers = parse_subscription(r.text)
            self.done.emit(servers)
        except Exception as exc:
            self.error.emit(str(exc))


class PingWorker(QThread):
    result = pyqtSignal(int, int)

    def __init__(self, row: int, host: str, port: int):
        super().__init__()
        self.row  = row
        self.host = host
        self.port = port

    def run(self):
        try:
            t0 = time.monotonic()
            with socket.create_connection((self.host, self.port), timeout=5):
                pass
            ms = int((time.monotonic() - t0) * 1000)
            self.result.emit(self.row, ms)
        except Exception:
            self.result.emit(self.row, -1)


class VpnWorker(QThread):
    log     = pyqtSignal(str)
    started_ok = pyqtSignal()
    stopped = pyqtSignal()

    READY_MARKERS = (
        "myvpn connected",
        "socks5 ready",
        "upstream connected",
        "tun2socks: started",
    )

    def __init__(self, cmd: list[str]):
        super().__init__()
        self.cmd   = cmd
        self._proc: Optional[subprocess.Popen] = None
        self._ready_emitted = False

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for line in self._proc.stdout:
                line = line.rstrip()
                self.log.emit(line)
                if not self._ready_emitted:
                    low = line.lower()
                    if any(m in low for m in self.READY_MARKERS):
                        self._ready_emitted = True
                        self.started_ok.emit()
            self._proc.wait()
        except Exception as exc:
            self.log.emit(f"[ERROR] {exc}")
        finally:
            self.stopped.emit()

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self._proc.pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5
                )
            except Exception as exc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass


COLS = ["Страна", "Сервер", "Протокол", "Транспорт", "Пинг"]

HELPER_SERVER = {
    "name":      "Обход белых списков",
    "host":      "local",
    "port":      0,
    "protocol":  "Helper",
    "transport": "WebSocket",
    "country":   "",
    "kind":      "helper",
    "params":    {},
}


class ServerModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._rows: list[dict] = [HELPER_SERVER]
        self._pings: dict[int, int] = {}
        self._best: int = -1

    def load(self, servers: list[dict]):
        self.beginResetModel()
        self._rows  = [HELPER_SERVER] + servers
        self._pings = {}
        self._best  = -1
        self.endResetModel()
        self._recalc_best()

    def set_ping(self, row: int, ms: int):
        real = row + 1
        self._pings[real] = ms
        self._recalc_best()
        self.dataChanged.emit(
            self.index(real, 0), self.index(real, len(COLS) - 1)
        )

    def _recalc_best(self):
        valid = {r: ms for r, ms in self._pings.items() if ms >= 0}
        if valid:
            self._best = min(valid, key=valid.get)

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(COLS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLS[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        srv  = self._rows[row]
        ping = self._pings.get(row)
        is_helper = srv.get("kind") == "helper"

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                if is_helper:
                    return "LOCAL"
                return srv.get("country", "")
            if col == 1:
                suffix = " *" if row == self._best else ""
                return f"{srv['name']}{suffix}"
            if col == 2:
                return srv.get("protocol", "")
            if col == 3:
                return srv.get("transport", "")
            if col == 4:
                if is_helper:
                    return "—"
                if ping is None:
                    return "..."
                if ping < 0:
                    return "недост."
                return f"{ping} ms"

        if role == Qt.ItemDataRole.ForegroundRole:
            if is_helper:
                return QColor(C_BLUE)
            if col == 4:
                if ping is None: return QColor(C_MUTED)
                if ping < 0:     return QColor(C_RED)
                if ping < 150:   return QColor(C_GREEN)
                if ping < 400:   return QColor(C_YELLOW)
                return QColor(C_RED)
            if col == 1 and row == self._best:
                return QColor(C_ORANGE)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 4):
                return int(Qt.AlignmentFlag.AlignCenter)

        if role == Qt.ItemDataRole.FontRole:
            if is_helper:
                f = QFont()
                f.setBold(True)
                return f

        return None

    def server(self, row: int) -> dict:
        return self._rows[row]


class LogConsole(QTextEdit):
    _COLORS = {
        "error": C_RED,
        "err":   C_RED,
        "warn":  C_YELLOW,
        "info":  C_GREEN,
        "ok":    C_GREEN,
    }

    LOG_LEVEL_FULL = 0
    LOG_LEVEL_NORMAL = 1
    LOG_LEVEL_IMPORTANT = 2

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self._log_level = self.LOG_LEVEL_FULL
        self._all_lines: list[tuple[str, str]] = []

    def set_log_level(self, level: int):
        self._log_level = level
        self._refresh_display()

    def _should_show(self, line: str) -> bool:
        lower = line.lower()
        
        if self._log_level == self.LOG_LEVEL_FULL:
            return True
        
        if self._log_level == self.LOG_LEVEL_NORMAL:
            if "[debug]" in lower:
                return False
            return True
        
        if self._log_level == self.LOG_LEVEL_IMPORTANT:
            if any(x in lower for x in ["[info]", "[warn]", "[error]", "[ok]"]):
                return True
            return False
        
        return True

    def append_line(self, line: str):
        lower = line.lower()
        color = C_TEXT
        for kw, clr in self._COLORS.items():
            if kw in lower:
                color = clr
                break
        
        self._all_lines.append((line, color))
        
        if self._should_show(line):
            self._add_to_display(line, color)

    def _add_to_display(self, line: str, color: str):
        escaped = (
            line.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        self.append(f'<span style="color:{color};">{escaped}</span>')
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refresh_display(self):
        self.clear()
        for line, color in self._all_lines:
            if self._should_show(line):
                self._add_to_display(line, color)


class MainWindow(QMainWindow):
    BASE    =   _resolve_base()
    EXE_DIR = _exe_dir()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Intourist VPN  v2.2")
        self.setMinimumSize(1024, 720)
        self.resize(1240, 800)

        self._vpn_worker: Optional[VpnWorker] = None
        self._sub_worker: Optional[SubWorker] = None
        self._ping_workers: list[PingWorker] = []
        self._connected = False
        self._conn_mode: Optional[str] = None
        self._original_dns: dict[str, list[str]] = {}
        self._dns_adapters: list[str] = []

        self._model = ServerModel()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Create web view
        self._web_view = QWebEngineView()
        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        # Load local HTML
        ui_path = self.BASE / "intourist_vps_premium_ui" / "index.html"
        if ui_path.exists():
            self._web_view.setUrl(QUrl.fromLocalFile(str(ui_path)))
        else:
            self._web_view.setHtml("<h1>UI файл не найден</h1>")
        
        root.addWidget(self._web_view)

        self._update_status(False)

    def _update_status(self, connected: bool):
        self._connected = connected
        # JavaScript injection to update status
        status_js = f"""
        document.querySelector('.status-card').classList.toggle('is-online', {str(connected).lower()});
        """
        self._web_view.page().runJavaScript(status_js)

    @staticmethod
    def _set_proxy(enable: bool):
        REG_INET = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        SOCKS    = "socks=127.0.0.1:1080"
        BYPASS   = "localhost;127.*;10.*;172.16.*;192.168.*;<local>"

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_INET,
                                0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, "ProxyEnable",   0, winreg.REG_DWORD, 1)
                    winreg.SetValueEx(key, "ProxyServer",   0, winreg.REG_SZ, SOCKS)
                    winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, BYPASS)
                else:
                    winreg.SetValueEx(key, "ProxyEnable",   0, winreg.REG_DWORD, 0)
        except Exception:
            pass

        try:
            INTERNET_OPTION_SETTINGS_CHANGED = 39
            INTERNET_OPTION_REFRESH          = 37
            wininet = ctypes.windll.wininet
            wininet.InternetSetOptionW(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
            wininet.InternetSetOptionW(None, INTERNET_OPTION_REFRESH, None, 0)
        except Exception:
            pass

        try:
            if enable:
                subprocess.run(
                    ["netsh", "winhttp", "set", "proxy",
                     "127.0.0.1:1080", BYPASS],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.run(
                    ["netsh", "winhttp", "reset", "proxy"],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
        except Exception:
            pass

        MainWindow._broadcast_proxy_change()

    @staticmethod
    def _broadcast_proxy_change():
        try:
            HWND_BROADCAST   = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_ulong()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                "Internet Settings",
                SMTO_ABORTIFHUNG, 5000,
                ctypes.byref(result),
            )
        except Exception:
            pass

    def _find_internet_adapter(self) -> Optional[str]:
        try:
            ps_script = (
                "Get-WmiObject Win32_NetworkAdapterConfiguration "
                "| Where-Object { $_.IPEnabled -and $_.DefaultIPGateway } "
                "| ForEach-Object { "
                "    $desc = $_.Description; "
                "    $adapter = Get-WmiObject Win32_NetworkAdapter "
                "               | Where-Object { $_.Description -eq $desc }; "
                "    if ($adapter) { $adapter.NetConnectionID } "
                "} "
                "| Select-Object -First 1"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            name = result.stdout.strip()
            if name:
                return name
        except Exception:
            pass

        try:
            route = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            iface_ip = None
            for line in route.stdout.split("\n"):
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    iface_ip = parts[3]
                    break

            if iface_ip:
                addrs = subprocess.run(
                    ["netsh", "interface", "ipv4", "show", "addresses"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                current_iface = None
                for line in addrs.stdout.split("\n"):
                    if 'Configuration for interface' in line:
                        current_iface = line.split('"')[1] if '"' in line else None
                    elif iface_ip in line and current_iface:
                        return current_iface
        except Exception:
            pass

        return None

    def _get_dns_info(self, adapter_name: str) -> dict:
        info = {"dhcp": False, "servers": []}
        try:
            result = subprocess.run(
                ["netsh", "interface", "ipv4", "show", "dnsservers", f"name={adapter_name}"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            out = result.stdout
            if "DHCP" in out or "dhcp" in out:
                info["dhcp"] = True
            for line in out.split("\n"):
                parts = line.strip().split()
                if parts and self._is_ip_address(parts[-1]):
                    info["servers"].append(parts[-1])
        except Exception:
            pass
        return info

    def _set_dns(self, enable: bool):
        try:
            if enable:
                adapter = self._find_internet_adapter()
                if not adapter:
                    return

                if adapter not in self._original_dns:
                    info = self._get_dns_info(adapter)
                    self._original_dns[adapter] = info
                    self._dns_adapters.append(adapter)

                subprocess.run(
                    ["netsh", "interface", "ipv4", "set", "dnsservers",
                     f"name={adapter}", "source=static", "address=1.1.1.1", "validate=no"],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                subprocess.run(
                    ["netsh", "interface", "ipv4", "add", "dnsservers",
                     f"name={adapter}", "address=8.8.8.8", "validate=no"],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

            else:
                for adapter in list(self._dns_adapters):
                    info = self._original_dns.get(adapter, {})
                    try:
                        if not info or info.get("dhcp"):
                            subprocess.run(
                                ["netsh", "interface", "ipv4", "set", "dnsservers",
                                 f"name={adapter}", "source=dhcp"],
                                capture_output=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW,
                            )
                        else:
                            servers = info.get("servers", [])
                            if servers:
                                subprocess.run(
                                    ["netsh", "interface", "ipv4", "set", "dnsservers",
                                     f"name={adapter}", "source=static",
                                     f"address={servers[0]}", "validate=no"],
                                    capture_output=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW,
                                )
                                for dns in servers[1:]:
                                    subprocess.run(
                                        ["netsh", "interface", "ipv4", "add", "dnsservers",
                                         f"name={adapter}", f"address={dns}", "validate=no"],
                                        capture_output=True, timeout=5,
                                        creationflags=subprocess.CREATE_NO_WINDOW,
                                    )
                            else:
                                subprocess.run(
                                    ["netsh", "interface", "ipv4", "set", "dnsservers",
                                     f"name={adapter}", "source=dhcp"],
                                    capture_output=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW,
                                )
                    except Exception:
                        pass

                self._dns_adapters.clear()
                self._original_dns.clear()

        except Exception:
            pass

    @staticmethod
    def _is_ip_address(s: str) -> bool:
        try:
            parts = s.split(".")
            return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)
        except (ValueError, AttributeError):
            return False

    def closeEvent(self, event):
        try:
            if self._vpn_worker and self._vpn_worker.isRunning():
                self._vpn_worker.stop()
        except Exception:
            pass
        finally:
            for w in self._ping_workers:
                try:
                    w.quit()
                except Exception:
                    pass
            event.accept()

    @staticmethod
    def _log_crash():
        import traceback
        try:
            log_path = Path(os.environ.get("TEMP", ".")) / "intourist_vpn_gui_crash.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass


def main():
    _ensure_admin()

    app = QApplication(sys.argv)
    app.setApplicationName("Intourist VPN")
    app.setStyleSheet(STYLESHEET)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(C_BG0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(C_BG1))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(C_BG2))
    palette.setColor(QPalette.ColorRole.Text, QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(C_ORANGE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000"))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
