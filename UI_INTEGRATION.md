## Интеграция нового интерфейса Intourist VPS

### Что было изменено

1. **Заменен интерфейс** с PyQt6 таблицы на современный веб-интерфейс из папки `intourist_vps_premium_ui`
2. **Добавлен логотип** `space_source.png` в место логотипа rocket.svg
3. **Реализован WebChannel мост** между Python и JavaScript для управления VPN
4. **Все функции сохранены**: подключение, отключение, DNS, прокси

### Новые файлы

- **`vpn_bridge_api.py`** - API для взаимодействия между UI и VPN
- **`intourist_vps_premium_ui/bridge.html`** - JavaScript мост для WebChannel
- **`intourist_vps_premium_ui/images/space_source.png`** - новый логотип

### Как работает

```
Пользователь кликает в веб-UI
    ↓
JavaScript отправляет команду через WebChannel
    ↓
Python обработчик (VPNBridgeAPI) получает сигнал
    ↓
Запускается VPN процесс (xray или helper)
    ↓
Python обновляет UI в реальном времени через WebChannel
```

### Требования

```
PyQt6>=6.0
PyQt6-WebEngine>=6.0
requests>=2.28.0
```

### Установка

```bash
pip install PyQt6 PyQt6-WebEngine requests
```

### Запуск

```bash
python myvpn_gui.py
```

**Требуется администратор (UAC будет запрошен автоматически)**

### Функции

✅ Быстрый выбор серверов по странам  
✅ Отображение пинга в реальном времени  
✅ Логирование всех событий  
✅ Отслеживание времени подключения  
✅ Управление DNS и системным прокси  
✅ Поддержка VLESS, VMess, Trojan, Shadowsocks  
✅ Режим "Обход белых списков" (helper mode)

### Структура папок

```
MyVPNv23/
├── myvpn_gui.py              # Основное приложение
├── vpn_bridge_api.py         # API мост
├── config_gen.py             # Генератор конфигов
├── intourist_vps_premium_ui/
│   ├── index.html            # Главный интерфейс
│   ├── style.css             # Стили
│   ├── bridge.html           # WebChannel мост
│   └── images/
│       ├── space_source.png  # Новый логотип 🚀
│       └── *.svg             # Иконки
```

### Техническая архитектура

**QWebEngineView** загружает локальный HTML → **JavaScript** обрабатывает события → **QWebChannel** передает команды в Python → **VPNBridgeAPI** выполняет действия → **Signals/Slots** обновляют UI в реальном времени

---

**Версия**: 2.2  
**Логотип**: space_source.png  
**UI Framework**: Intourist VPS Premium  
**Последнее обновление**: 2026-07-03
