"""
config_gen.py — Генератор Xray конфигов для MyVPN GUI
Исправлено: убрано allowInsecure, allowInsecureHostname, pinnedPeerCertSha256
"""

import json
from pathlib import Path


def make_xray_config(srv: dict) -> dict:
    """
    Генерирует конфиг Xray на основе сервера из подписки.
    
    Поддерживаемые типы:
      - VLESS (TCP, WS, gRPC)
      - Trojan (TCP, WS)
      - Shadowsocks (любой метод)
      - VMess (TCP, WS, mKCP)
    """
    protocol = srv.get("protocol", "").lower()
    transport = srv.get("transport", "tcp").lower()
    host = srv.get("host", "")
    port = srv.get("port", 443)
    cred = srv.get("cred", "")
    params = srv.get("params", {})

    config = {
        "log": {
            "loglevel": "info",
            "access": "",
            "error": ""
        },
        "inbounds": [
            {
                "port": 1080,
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": True,
                    "userLevel": 8
                },
                "tag": "socks-in"
            },
            {
                "port": 1081,
                "protocol": "http",
                "tag": "http-in"
            }
        ],
        "outbounds": [
            {
                "protocol": _get_outbound_protocol(protocol),
                "settings": _get_outbound_settings(protocol, srv),
                "streamSettings": _get_stream_settings(protocol, transport, params),
                "tag": "proxy"
            },
            {
                "protocol": "freedom",
                "tag": "direct"
            }
        ],
        "routing": {
            "domainStrategy": "IPOnDemand",
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["socks-in", "http-in"],
                    "outboundTag": "proxy"
                }
            ]
        }
    }

    return config


def _get_outbound_protocol(protocol: str) -> str:
    """Определить Xray-протокол по типу сервера."""
    proto_map = {
        "vless": "vless",
        "trojan": "trojan",
        "shadowsocks": "shadowsocks",
        "vmess": "vmess",
    }
    return proto_map.get(protocol.lower(), "vless")


def _get_outbound_settings(protocol: str, srv: dict) -> dict:
    """Генерирует settings для outbound."""
    protocol = protocol.lower()
    cred = srv.get("cred", "")
    host = srv.get("host", "")
    port = srv.get("port", 443)
    params = srv.get("params", {})

    if protocol == "vless":
        return {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [
                        {
                            "id": cred,
                            "encryptionMethod": "none",
                            "flow": params.get("flow", ""),
                            "alterId": 0,
                            "encryption":"none"
                        }
                    ]
                }
            ]
        }

    elif protocol == "trojan":
        return {
            "servers": [
                {
                    "address": host,
                    "port": port,
                    "password": cred,
                    "email": "user@trojan"
                }
            ]
        }

    elif protocol == "shadowsocks":
        # transport = метод шифрования (aes-256-gcm и т.д.)
        method = srv.get("transport", "aes-256-gcm")
        return {
            "servers": [
                {
                    "address": host,
                    "port": port,
                    "method": method,
                    "password": cred,
                    "email": "user@ss"
                }
            ]
        }

    elif protocol == "vmess":
        params = srv.get("params", {})
        return {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [
                        {
                            "id": cred,
                            "alterId": int(params.get("aid", 0)),
                            "security": params.get("scy", "auto")
                        }
                    ]
                }
            ]
        }

    return {}


def _get_stream_settings(protocol: str, transport: str, params: dict) -> dict:
    """Генерирует streamSettings (TLS, WS, и т.д.)."""
    protocol = protocol.lower()
    transport = transport.lower()

    # Базовые настройки TLS (без allowInsecure и другого опасного)
    tls_settings = {}
    sni = params.get("sni", "") or params.get("host", "")
    if sni:
        tls_settings["serverName"] = sni

    settings = {
        "network": transport,
        "security": "tls",
    }
    
    if tls_settings:
        settings["tlsSettings"] = tls_settings

    if transport == "ws" or transport == "websocket":
        settings["network"] = "ws"
        settings["wsSettings"] = {
            "path": params.get("path", "/"),
            "headers": {}
        }
        if "host" in params:
            settings["wsSettings"]["headers"]["Host"] = params["host"]

    elif transport == "grpc":
        settings["network"] = "grpc"
        settings["grpcSettings"] = {
            "serviceName": params.get("serviceName", "")
        }

    elif transport == "tcp":
        if protocol == "trojan":
            # Trojan часто использует "http" для маскировки
            settings["tcpSettings"] = {
                "header": {
                    "type": params.get("headerType", "http"),
                    "request": {
                        "version": "1.1",
                        "method": "GET",
                        "path": ["/"],
                        "headers": {
                            "Host": [params.get("host", "www.google.com")],
                            "User-Agent": ["Mozilla/5.0"]
                        }
                    }
                }
            }

    return settings


def write_config(config: dict, path: Path):
    """Записать конфиг JSON в файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
