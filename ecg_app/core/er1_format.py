"""Lepu/Viatom ER1 raw recording format (R files) and decoded PCM."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np

HEADER_LEN = 10
TRAILER_LEN = 20
TRAILER_MAGIC = b"\x38\x04\x5a\xa5"
SAMPLE_RATE = 250
# UNVERIFIED: typical Lepu ER1 scale; confirm against the vendor waveform.
MV_PER_LSB = 0.002467


class ER1FormatError(ValueError):
    pass


@dataclass(frozen=True)
class ER1Header:
    version: int
    start: Optional[datetime]
    reserved: bytes


@dataclass(frozen=True)
class ER1Trailer:
    duration: int  # seconds * 2 (vendor convention)
    checksum: int  # CRC-16/CCITT-FALSE of header+body, stored as u32
    reserved: bytes
    magic: bytes

    @property
    def duration_seconds(self) -> float:
        return self.duration / 2


def crc16_ccitt_false(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def parse_header(raw: bytes) -> ER1Header:
    if len(raw) < HEADER_LEN:
        raise ER1FormatError("file shorter than ER1 header")
    y, mo, d, h, mi, s = struct.unpack("<HBBBBB", raw[1:8])
    try:
        start = datetime(y, mo, d, h, mi, s)
    except ValueError:
        start = None
    return ER1Header(raw[0], start, bytes(raw[8:10]))


def parse_trailer(raw: bytes) -> ER1Trailer:
    if len(raw) < HEADER_LEN + TRAILER_LEN:
        raise ER1FormatError("file shorter than header + trailer")
    t = bytes(raw[-TRAILER_LEN:])
    if t[-4:] != TRAILER_MAGIC:
        raise ER1FormatError("bad ER1 trailer magic: " + t[-4:].hex())
    duration, checksum = struct.unpack("<II", t[:8])
    return ER1Trailer(duration, checksum, t[8:16], t[16:])


def verify_checksum(raw: bytes) -> bool:
    return crc16_ccitt_false(bytes(raw[:-TRAILER_LEN])) == parse_trailer(raw).checksum


def decode(raw: bytes) -> np.ndarray:
    """Decode an R file to int16 samples (250 Hz, single lead). Validates trailer."""
    parse_trailer(raw)
    body = raw[HEADER_LEN:-TRAILER_LEN]
    out = np.empty(len(body), dtype=np.int16)
    n = 0
    acc = 0
    i = 0
    L = len(body)
    while i < L:
        b = body[i]
        i += 1
        if b == 0x80:
            if i + 2 > L:
                raise ER1FormatError("truncated absolute sample")
            v = body[i] | (body[i + 1] << 8)
            i += 2
            acc = v - 65536 if v >= 32768 else v
        elif b == 0x7F or b == 0x81:
            if i >= L:
                raise ER1FormatError("truncated escape")
            step = 127 + body[i]
            i += 1
            acc += step if b == 0x7F else -step
        else:
            acc += b - 256 if b >= 128 else b
        acc = ((acc + 32768) & 0xFFFF) - 32768
        out[n] = acc
        n += 1
    return out[:n].copy()


def decode_to_bytes(raw: bytes) -> bytes:
    return decode(raw).astype("<i2").tobytes()


def load_pcm(path) -> np.ndarray:
    return np.fromfile(path, dtype="<i2")


def to_mv(samples: np.ndarray) -> np.ndarray:
    return samples.astype(np.float64) * MV_PER_LSB
