# IntouristVPN_GUI.spec  —  PyInstaller 6.x
# ВАЖНО: onedir режим (НЕ onefile) — единственно правильный для wintun.dll
#
# Запуск:  pyinstaller IntouristVPN_GUI.spec
#
# Переменные окружения:
#   INTOURIST_VERSION  — версия (по умолчанию "2.2.0")
#   INTOURIST_BIN_DIR  — путь к bin\  (по умолчанию "./bin")
#   INTOURIST_EXE      — путь к intourist_vpn.exe (по умолчанию "./intourist_vpn.exe")
#   INTOURIST_ICON     — путь к .ico (по умолчанию "./icon.ico")

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

version   = os.environ.get("INTOURIST_VERSION", "2.2.0")
bin_dir   = Path(os.environ.get("INTOURIST_BIN_DIR",  str(ROOT / "bin")))
vpn_exe   = Path(os.environ.get("INTOURIST_EXE",      str(ROOT / "intourist_vpn.exe")))
icon_path = Path(os.environ.get("INTOURIST_ICON",     str(ROOT / "icon.ico")))
cfg_gen   = ROOT / "config_gen.py"
vpn_bridge = ROOT / "vpn_bridge_api.py"
manifest  = ROOT / "myvpn_gui.manifest"

# ── Данные, встраиваемые в onedir ──────────────────────────────────────────
# ПРИМЕЧАНИЕ: при onedir все файлы лежат рядом с intourist_vpn_gui.exe в dist/IntouristVPN_GUI/
# Поэтому wintun.dll, xray.exe, geoip.dat и пр. будут рядом — это и нужно.
datas    = []
binaries = []

# Копируем всю папку bin\ рядом с exe
if bin_dir.exists():
    datas.append((str(bin_dir), "bin"))

# intourist_vpn.exe (Go-бинарь) кладём рядом с GUI-exe
if vpn_exe.exists():
    datas.append((str(vpn_exe), "."))

# config_gen.py нужен для генерации xray-конфигов
if cfg_gen.exists():
    datas.append((str(cfg_gen), "."))

# vpn_bridge_api.py для WebChannel коммуникации
if vpn_bridge.exists():
    datas.append((str(vpn_bridge), "."))

# intourist_vps_premium_ui — веб-интерфейс
ui_dir = ROOT / "intourist_vps_premium_ui"
if ui_dir.exists():
    datas.append((str(ui_dir), "intourist_vps_premium_ui"))

# wintun.dll ОБЯЗАТЕЛЬНО должна лежать рядом с intourist_vpn_gui.exe (и intourist_vpn.exe).
# При onedir это автоматически выполняется, т.к. всё в одной папке.
wintun_dll = ROOT / "wintun.dll"
if wintun_dll.exists():
    # binaries[] — PyInstaller сам скопирует DLL рядом с exe
    binaries.append((str(wintun_dll), "."))
else:
    # Проверяем также в bin\
    wintun_in_bin = bin_dir / "wintun.dll"
    if wintun_in_bin.exists():
        binaries.append((str(wintun_in_bin), "."))

# geo-файлы для xray
for geo in ("geoip.dat", "geosite.dat"):
    p = ROOT / geo
    if p.exists():
        datas.append((str(p), "."))

# Дефолтный config.json
config_json = ROOT / "config.json"
if config_json.exists():
    datas.append((str(config_json), "."))

# ── Analysis ───────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "myvpn_gui.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebChannel",
        "requests",
        "winreg",
        "ctypes",
        "config_gen",
        "vpn_bridge_api",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# ── ONEDIR exe (НЕ onefile!) ───────────────────────────────────────────────
# При onefile: wintun.dll распаковывается во TEMP → не найдена при CreateAdapter
# При onedir:  wintun.dll лежит рядом с exe → LoadLibrary находит её
exe = EXE(
    pyz,
    a.scripts,
    [],                # <-- пусто при onedir
    exclude_binaries=True,  # <-- True при onedir
    name="intourist_vpn_gui",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=["wintun.dll", "intourist_vpn.exe", "helper.exe", "tun2socks.exe", "xray.exe"],
    console=False,
    manifest=str(manifest) if manifest.exists() else None,
    icon=str(icon_path) if icon_path.exists() else None,
    uac_admin=True,
)

# ── COLLECT — собирает все файлы в dist\IntouristVPN_GUI\ ──────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["wintun.dll", "intourist_vpn.exe", "helper.exe", "tun2socks.exe", "xray.exe"],
    name="IntouristVPN_GUI",
)
