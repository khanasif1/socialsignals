"""Generate SIGNAL's original, opaque 1024px iOS monogram without external assets."""
import math
import struct
import zlib
from pathlib import Path

size = 1024
background = (33, 38, 35)
foreground = (255, 115, 115)
accent = (242, 61, 69)
# An angular S: three horizontal strokes connected on opposite sides.
polygon = [
    (322, 267), (702, 267), (702, 366), (368, 366),
    (368, 462), (643, 462), (723, 542), (723, 679),
    (645, 757), (302, 757), (302, 658), (624, 658),
    (624, 561), (380, 561), (269, 487), (269, 346),
]
pixels = bytearray(background * (size * size))
for y in range(size):
    crossings = []
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 <= y < y2) or (y2 <= y < y1):
            crossings.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    crossings.sort()
    for start, end in zip(crossings[::2], crossings[1::2]):
        for x in range(math.ceil(start), math.ceil(end)):
            offset = (y * size + x) * 3
            pixels[offset:offset + 3] = bytes(foreground)
for y in range(220, 318):
    for x in range(746, 844):
        if (x - 795) ** 2 + (y - 269) ** 2 <= 48 ** 2:
            offset = (y * size + x) * 3
            pixels[offset:offset + 3] = bytes(accent)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


rows = b"".join(b"\0" + pixels[y * size * 3:(y + 1) * size * 3] for y in range(size))
png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
output = Path(__file__).resolve().parents[1] / "frontend" / "assets" / "icon.png"
output.write_bytes(png)
print("Generated original SIGNAL iOS icon.")
