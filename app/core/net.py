"""Minimalizacja danych: zamiast pełnego IP przechowujemy prefiks sieci."""

import ipaddress

from fastapi import Request


def ip_prefix(request: Request) -> str:
    host = request.client.host if request.client else ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "unknown"
    prefix = 24 if ip.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:255] if ua else None
