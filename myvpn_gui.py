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
from PyQt6.QtWebChannel import QWebChannel

from vpn_bridge_api import VPNBridgeAPI

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
"""

LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAAYAAAAGACAYAAACkx7W/AAAQAElEQVR4Aey9B6AcR5W2/VR1mHSzcrYk27IcJOeIEw7YYGySCSYaMDmzLLAs4CWnJWNyDguYJYMxJtg4Z8tBVs7SlW4Ok6e7639rJJP+3W+/b9eBxbfVZ6q6usKpU1XvOXVq7sg[...]"

COUNTRY_FLAGS = {
    "ru": "🇷🇺", "us": "🇺🇸", "de": "🇩🇪", "nl": "🇳🇱", "fi": "🇫🇮",
    "fr": "🇫🇷", "gb": "🇬🇧", "jp": "🇯🇵", "sg": "🇸🇬", "ua": "🇺🇦",
    "pl": "🇵🇱", "se": "🇸🇪", "tr": "🇹🇷", "ir": "🇮🇷", "bg": "🇧🇬",
}


def _country(host: str) -> str:
    for cc in COUNTRY_FLAGS:
        if cc in host.lower():
            return cc.upper()
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
                "location": p.hostname or "",
                "ping": None,
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
                "location": p.hostname or "",
                "ping": None,
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
                "location": p.hostname or "",
                "ping": None,
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
                "location": d.get("add", ""),
                "ping": None,
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
        self._servers: list[dict] = []
        self._current_server: Optional[dict] = None
        self._connection_time = 0

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
        
        # Setup WebChannel
        self._channel = QWebChannel()
        self._bridge_api = VPNBridgeAPI()
        
        # Connect signals
        self._bridge_api.connectionRequested.connect(self._on_connect_requested)
        self._bridge_api.disconnectionRequested.connect(self._on_disconnect_requested)
        self._bridge_api.serversRefreshRequested.connect(self._on_refresh_requested)
        self._bridge_api.statusChanged.connect(self._on_status_changed)
        
        self._channel.registerObject("vpnApi", self._bridge_api)
        self._web_view.page().setWebChannel(self._channel)
        
        # Load local HTML
        ui_path = self.BASE / "intourist_vps_premium_ui" / "index.html"
        if ui_path.exists():
            self._web_view.setUrl(QUrl.fromLocalFile(str(ui_path)))
        else:
            self._web_view.setHtml("<h1>UI файл не найден</h1>")
        
        root.addWidget(self._web_view)

        # Timer for connection time
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_connection_time)

        self._update_status(False)

    def _on_connect_requested(self, server: dict):
        """Handle connection request from web UI"""
        self._current_server = server
        self._connect_to_server(server)

    def _on_disconnect_requested(self):
        """Handle disconnection request from web UI"""
        self._disconnect()

    def _on_refresh_requested(self):
        """Handle server refresh request from web UI"""
        # This would reload servers from subscription
        pass

    def _on_status_changed(self, connected: bool):
        """Handle status change"""
        self._connected = connected

    def _connect_to_server(self, server: dict):
        """Connect to a specific server"""
        if self._connected or (self._vpn_worker and self._vpn_worker.isRunning()):
            return

        self._bridge_api.appendLog(f"[INFO] Подключение к {server.get('name')}...")
        
        try:
            from config_gen import make_xray_config, write_config
            cfg      = make_xray_config(server)
            cfg_path = self.EXE_DIR / "config.json"
            write_config(cfg, cfg_path)
            self._bridge_api.appendLog(f"[INFO] Конфиг записан: {cfg_path}")
        except ImportError:
            self._bridge_api.appendLog("[WARN] config_gen не найден — fallback на helper.")
            self._do_connect_helper()
            return
        except Exception as exc:
            self._bridge_api.appendLog(f"[ERROR] config_gen: {exc}")
            return

        xray = self.EXE_DIR / "bin" / "xray.exe"
        if not xray.exists():
            xray = self.EXE_DIR / "xray.exe"
        if not xray.exists():
            self._bridge_api.appendLog(f"[WARN] xray.exe не найден, fallback на helper.")
            self._do_connect_helper()
            return

        self._conn_mode = "sub"
        self._connection_time = 0
        self._timer.start(1000)
        self._launch_vpn([str(xray), "run", "-c", str(cfg_path)])

    def _do_connect_helper(self):
        """Connect using helper mode"""
        myvpn = self.EXE_DIR / "myvpn.exe"
        if not myvpn.exists():
            myvpn = self.BASE / "myvpn.exe"
        if not myvpn.exists():
            self._bridge_api.appendLog(f"[ERROR] myvpn.exe не найден")
            return
        
        self._conn_mode = "helper"
        self._connection_time = 0
        self._timer.start(1000)
        self._launch_vpn([str(myvpn), "--base-dir", str(self.BASE)])

    def _launch_vpn(self, cmd: list[str]):
        """Launch VPN process"""
        if self._connected or (self._vpn_worker and self._vpn_worker.isRunning()):
            return

        self._vpn_worker = VpnWorker(cmd)
        self._vpn_worker.log.connect(self._bridge_api.appendLog)
        self._vpn_worker.started_ok.connect(self._on_vpn_ready)
        self._vpn_worker.stopped.connect(self._on_vpn_stopped)
        self._vpn_worker.start()

        self._bridge_api.appendLog(f"[INFO] Запуск: {' '.join(cmd)}")

    def _on_vpn_ready(self):
        """Called when VPN is ready"""
        self._update_status(True)
        if self._conn_mode == "sub":
            self._set_proxy(True)
            self._bridge_api.appendLog("[INFO] Intourist VPN готов. Прокси включён.")
        else:
            self._set_proxy(False)
            self._bridge_api.appendLog("[INFO] Intourist VPN готов (helper, полный туннель).")
        
        self._set_dns(True)

    def _on_vpn_stopped(self):
        """Called when VPN process stops"""
        self._update_status(False)
        self._set_proxy(False)
        self._set_dns(False)
        self._conn_mode = None
        self._bridge_api.appendLog("[INFO] VPN-процесс завершён.")
        self._timer.stop()

    def _disconnect(self):
        """Disconnect from VPN"""
        if self._vpn_worker and self._vpn_worker.isRunning():
            self._bridge_api.appendLog("[INFO] Остановка VPN-процесса...")
            self._vpn_worker.stop()
            if not self._vpn_worker.wait(5000):
                self._bridge_api.appendLog("[WARN] VPN-процесс не завершился в срок.")
        
        self._set_proxy(False)
        self._set_dns(False)
        
        self._conn_mode = None
        self._update_status(False)
        self._bridge_api.appendLog("[INFO] Отключено.")
        self._timer.stop()

    def _update_status(self, connected: bool):
        """Update connection status in UI"""
        self._connected = connected
        self._bridge_api.setStatus(connected)
        
        # Update UI via JavaScript
        status_text = "подключено" if connected else "отключено"
        status_color = "#17C964" if connected else "#FF4A6A"
        
        js_code = f"""
        var statusCard = document.querySelector('.status-card');
        if (statusCard) {{
            statusCard.classList.toggle('is-online', {str(connected).lower()});
            var strong = statusCard.querySelector('strong');
            if (strong) strong.textContent = '{status_text}';
        }}
        var connectBtn = document.querySelector('.connect');
        var disconnectBtn = document.querySelector('.disconnect');
        if (connectBtn) connectBtn.disabled = {str(connected).lower()};
        if (disconnectBtn) disconnectBtn.disabled = {str(not connected).lower()};
        """
        self._web_view.page().runJavaScript(js_code)

    def _update_connection_time(self):
        """Update connection time display"""
        self._connection_time += 1
        hours = self._connection_time // 3600
        minutes = (self._connection_time % 3600) // 60
        seconds = self._connection_time % 60
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        metrics = {
            "time": time_str,
            "downloaded": "0 MB",
            "uploaded": "0 MB",
            "dns": "1.1.1.1"
        }
        self._bridge_api.setMetrics(metrics)

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
                    ["netsh", "winhttp", "set", "proxy", "127.0.0.1:1080", BYPASS],
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
            self._disconnect()
        except Exception:
            pass
        finally:
            for w in self._ping_workers:
                try:
                    w.quit()
                except Exception:
                    pass
            self._timer.stop()
            event.accept()


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
