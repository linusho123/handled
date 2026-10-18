"""Every Python test runs with the network refused: a socket may connect to loopback only.
HANDLED_REAL_NET=1, set by hand, lifts the guard (as in test/setup/no-network.ts)."""

import ipaddress
import os
import socket

import pytest


def _loopback(address) -> bool:
    if not isinstance(address, tuple):
        return True  # a Unix socket path
    host = address[0]
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # a DNS name: never resolved here


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    if os.environ.get("HANDLED_REAL_NET") == "1":
        return
    connect = socket.socket.connect

    def guarded(self, address):
        if not _loopback(address):
            raise OSError(f"a test tried to reach {address!r} over the network; the lanes never do")
        return connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
