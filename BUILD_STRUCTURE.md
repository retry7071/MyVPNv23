## Структура проекта Intourist VPN

### Общее описание

Intourist VPN — современный VPN-клиент с веб-интерфейсом на PyQt6 + WebEngine. Сборка полностью автоматизирована через `build.ps1`.

### Структура каталогов

```
IntouristVPN/
│
├── build.ps1                          ← Скрипт сборки (PowerShell)
├── IntouristVPN_GUI.spec              ← PyInstaller конфиг (переименован)
├── installer.iss                      ← Inno Setup конфиг (обновлен)
│
├── myvpn_gui.py                       ← Главное приложение PyQt6
├── vpn_bridge_api.py                  ← API мост (WebChannel)
├── config_gen.py                      ← Генератор конфигов xray
├── myvpn_gui.manifest                 ← UAC манифест
│
├── intourist_vps_premium_ui/          ← Веб-интерфейс (новый!)
│   ├── index.html                     ← Главный интерфейс
│   ├── style.css                      ← Стили
│   ├── bridge.html                    ← WebChannel мост
│   └── images/
│       ├── space_source.png           ← Логотип (новый!)
│       ├── bolt.svg
│       ├── copy.svg
│       ├── faq.svg
│       ├── link.svg
│       ├── logo-rocket.svg
│       ├── power.svg
│       ├── telegram.svg
│       └── icon.ico
│
├── cmd/
│   └── myvpn/                         ← Go-приложение
│       └── main.go
│
├── internal/                          ← Go пакеты
│
├── bin/                               ← Бинарные зависимости
│   ├── helper.exe
│   ├── tun2socks.exe
│   ├── xray.exe
│   ├── helper.config.yaml
│   └── wintun.dll
│
├── geoip.dat                          ← Geo-данные xray
├── geosite.dat
├── config.json                        ← Дефолтная конфигурация
├── icon.ico                           ← Иконка приложения
│
├── dist/                              ← Выход PyInstaller
│   └── IntouristVPN_GUI/
│       └── intourist_vpn_gui.exe
│
├── installer_dist/                    ← Выход Inno Setup
│   └── IntouristVPN_Setup_2.2.0.exe
│
└── README.md
```

### Сборка проекта

#### Требования

- **PowerShell 5.0+** (встроен в Windows 10+)
- **Go 1.19+** (для компиляции `intourist_vpn.exe`)
- **Python 3.10+** с пакетами:
  ```bash
  pip install PyQt6 PyQt6-WebEngine requests pyinstaller
  ```
- **Inno Setup 6** (опционально, для создания установщика)

#### Шаги сборки

##### 1. Полная сборка (Go + Python + Installer)

```powershell
.\build.ps1
```

Или с указанием версии:

```powershell
.\build.ps1 -Version "2.3.0"
```

##### 2. Пропустить некоторые этапы

```powershell
# Только Python (без Go)
.\build.ps1 -SkipGo

# Только Go и Python (без Inno Setup)
.\build.ps1 -SkipInno

# Только PyInstaller (без Go и Inno)
.\build.ps1 -SkipGo -SkipInno
```

#### Результаты сборки

- **`intourist_vpn.exe`** — Go бинарь (VPN-движок)
- **`dist/IntouristVPN_GUI/intourist_vpn_gui.exe`** — Python приложение с PyQt6
- **`installer_dist/IntouristVPN_Setup_2.2.0.exe`** — Установщик

### Четыре этапа build.ps1

| Этап | Название | Выход | Пропуск |
|------|----------|--------|--------|
| 1 | Go Compilation | `intourist_vpn.exe` | `-SkipGo` |
| 2 | Dependencies Check | Проверка `bin/`, `wintun.dll` | — |
| 3 | PyInstaller | `dist/IntouristVPN_GUI/` | `-SkipPython` |
| 4 | Inno Setup | `installer_dist/IntouristVPN_Setup_*.exe` | `-SkipInno` |

### Переменные окружения (используются build.ps1)

```powershell
$env:INTOURIST_VERSION = "2.2.0"
$env:INTOURIST_BIN_DIR = "$Root\bin"
$env:INTOURIST_EXE = "$Root\intourist_vpn.exe"
$env:INTOURIST_ICON = "$Root\icon.ico"
```

Они автоматически устанавливаются в `build.ps1`, но можно переопределить перед запуском.

### Именование файлов (обновлено)

**Старое** → **Новое**

- `MyVPN_GUI.spec` → `IntouristVPN_GUI.spec`
- `MyVPN_GUI.exe` → `intourist_vpn_gui.exe`
- `MyVPN_Setup_*.exe` → `IntouristVPN_Setup_*.exe`
- `myvpn.exe` → `intourist_vpn.exe`
- Логотип: `logo-rocket.svg` → `space_source.png` 🚀

### Веб-интерфейс

**Директория:** `intourist_vps_premium_ui/`

**Технология:** HTML + CSS + JavaScript (встроен через QWebEngineView)

**Логотип:** `space_source.png` (ракета в космосе)

**Взаимодействие:** QWebChannel для Python ↔ JavaScript коммуникации

### Сборка установщика

1. Убедитесь, что установлен **Inno Setup 6**
2. Запустите: `.\build.ps1`
3. Установщик создается в: `installer_dist/IntouristVPN_Setup_2.2.0.exe`

После установки приложение будет в:
```
C:\Program Files\Intourist VPN\
  ├── intourist_vpn_gui.exe       ← главный exe
  ├── intourist_vpn.exe
  ├── IntouristVPN_GUI/           ← все файлы PyInstaller
  ├── intourist_vps_premium_ui/   ← веб-интерфейс
  ├── bin/
  └── ...
```

### Значки

- **Меню Пуск**: ✓ Создается автоматически
- **Рабочий стол**: ✓ Опционально (при установке)
- **Быстрый запуск**: ✓ Windows XP/Vista

### Дополнительные команды

```powershell
# Просмотр версии (во время сборки)
.\build.ps1 -Version "2.3.0"

# Только проверка зависимостей (без сборки)
# Изменить build.ps1, оставить только шаг 2

# Очистка кеша PyInstaller перед сборкой
Remove-Item dist -Recurse -Force
Remove-Item build_pyinstaller -Recurse -Force
```

### Поддерживаемые форматы VPN

- VLESS
- VMess  
- Trojan
- Shadowsocks

### Примечания

- ⚠️ **Требуется администратор** (UAC) — управление WinTUN
- ✅ **onedir режим** PyInstaller (не onefile) — критично для wintun.dll
- ✅ **x64 только** — wintun.dll 64-битная
- ✅ **Автоматическое удаление** старой версии при установке

---

**Версия документации:** 1.0  
**Дата обновления:** 2026-07-03  
**Проект:** Intourist VPN v2.2
