"""
Web UI Bridge for VPN Control
This module provides JavaScript bridge to control VPN from web interface
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import json


class VPNBridgeAPI(QObject):
    """Bridge between web UI and VPN backend"""
    
    # Signals
    connectionRequested = pyqtSignal(dict)
    disconnectionRequested = pyqtSignal()
    serversRefreshRequested = pyqtSignal()
    logMessage = pyqtSignal(str)
    statusChanged = pyqtSignal(bool)
    metricsUpdated = pyqtSignal(dict)
    serversUpdated = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.connected = False
        self.current_server = None

    @pyqtSlot(str)
    def connect(self, server_json: str):
        """Connect to a VPN server"""
        try:
            server = json.loads(server_json)
            self.current_server = server
            self.connectionRequested.emit(server)
            self.logMessage.emit(f"[INFO] Подключение к {server.get('name', 'серверу')}...")
        except json.JSONDecodeError:
            self.logMessage.emit("[ERROR] Ошибка парсинга параметров сервера")

    @pyqtSlot()
    def disconnect(self):
        """Disconnect from VPN"""
        self.disconnectionRequested.emit()
        self.logMessage.emit("[INFO] Отключение от VPN...")

    @pyqtSlot()
    def refreshServers(self):
        """Refresh server list"""
        self.serversRefreshRequested.emit()
        self.logMessage.emit("[INFO] Обновление списка серверов...")

    def setStatus(self, connected: bool):
        """Update connection status in UI"""
        self.connected = connected
        self.statusChanged.emit(connected)

    def setMetrics(self, metrics: dict):
        """Update connection metrics in UI"""
        self.metricsUpdated.emit(metrics)

    def setServers(self, servers: list):
        """Update server list in UI"""
        self.serversUpdated.emit(servers)

    def appendLog(self, message: str):
        """Append message to log in UI"""
        self.logMessage.emit(message)
