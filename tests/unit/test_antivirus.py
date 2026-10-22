"""Klient clamd (INSTREAM) na prawdziwym gnieździe TCP z serwerem udającym clamd."""

import socket
import struct
import threading

import pytest

from app.core import antivirus
from app.core.config import get_settings

# Standardowy plik testowy EICAR składany w czasie działania — dosłowny ciąg w źródle bywa
# blokowany przez antywirus stacji roboczej (Windows Defender).
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$" + b"EICAR-STANDARD-ANTIVIRUS-TEST-" + b"FILE!$H+H*"


def fake_clamd(reply_for):
    """Serwer na jedno połączenie: odbiera INSTREAM, składa dane, odpowiada wg funkcji."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    received: dict[str, bytes] = {}

    def serve():
        conn, _ = srv.accept()
        with conn:
            buf = b""
            while not buf.startswith(b"zINSTREAM\0") or len(buf) < 10:
                buf += conn.recv(4096)
            buf = buf[len(b"zINSTREAM\0") :]
            data = b""
            while True:
                while len(buf) < 4:
                    buf += conn.recv(4096)
                (size,) = struct.unpack(">I", buf[:4])
                buf = buf[4:]
                if size == 0:
                    break
                while len(buf) < size:
                    buf += conn.recv(65536)
                data, buf = data + buf[:size], buf[size:]
            received["data"] = data
            conn.sendall(reply_for(data).encode() + b"\0")
        srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1], received


@pytest.fixture
def clamd_at(monkeypatch):
    def configure(port):
        monkeypatch.setattr(get_settings(), "clamav_host", "127.0.0.1")
        monkeypatch.setattr(get_settings(), "clamav_port", port)
        monkeypatch.setattr(get_settings(), "clamav_timeout_seconds", 5)

    return configure


def test_clean_file_streamed_in_chunks(clamd_at):
    port, received = fake_clamd(lambda data: "stream: OK")
    clamd_at(port)
    data = bytes(range(256)) * 1000  # 256 kB → kilka porcji po 64 kB
    assert antivirus.scan(data) == antivirus.ScanResult(clean=True)
    assert received["data"] == data


def test_infected_file_reports_signature(clamd_at):
    port, _ = fake_clamd(
        lambda data: "stream: Win.Test.EICAR_HDB-1 FOUND" if b"EICAR" in data else "stream: OK"
    )
    clamd_at(port)
    assert antivirus.scan(EICAR) == antivirus.ScanResult(
        clean=False, signature="Win.Test.EICAR_HDB-1"
    )


def test_scanner_error_and_no_scanner_are_unavailable(clamd_at):
    port, _ = fake_clamd(lambda data: "INSTREAM size limit exceeded. ERROR")
    clamd_at(port)
    with pytest.raises(antivirus.ScannerUnavailable):
        antivirus.scan(b"x" * 10)

    # Nikt nie słucha na porcie: odmowa połączenia.
    free = socket.socket()
    free.bind(("127.0.0.1", 0))
    closed_port = free.getsockname()[1]
    free.close()
    clamd_at(closed_port)
    with pytest.raises(antivirus.ScannerUnavailable):
        antivirus.scan(b"x")


def test_parse_reply_variants():
    assert antivirus.parse_reply("stream: OK").clean is True
    assert antivirus.parse_reply("OK").clean is True
    assert antivirus.parse_reply("stream: Eicar-Signature FOUND").signature == "Eicar-Signature"
    with pytest.raises(antivirus.ScannerUnavailable):
        antivirus.parse_reply("")
