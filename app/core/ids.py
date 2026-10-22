"""UUIDv7 (RFC 9562): sortowalne w czasie, niezgadywalne identyfikatory."""

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    ts_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")  # 80 bitów losowych
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # wersja
    value |= ((rand >> 68) & 0xFFF) << 64  # rand_a (12 bitów)
    value |= 0b10 << 62  # wariant RFC
    value |= rand & ((1 << 62) - 1)  # rand_b (62 bity)
    return uuid.UUID(int=value)
