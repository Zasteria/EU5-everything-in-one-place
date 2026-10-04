#!/usr/bin/env python3
"""Write the 512x512 .metadata/thumbnail.png the EU5 launcher requires.

Every mod the launcher lists carries one; a mod without it is silently skipped.
No image libraries are available here, so the PNG is assembled by hand: a dark
parchment-toned panel with a lighter band across the middle.
"""

import struct
import sys
import zlib

SIZE = 512
BACKGROUND = (26, 30, 38)
BAND = (198, 160, 92)


def chunk(tag, payload):
    body = tag + payload
    return (struct.pack(">I", len(payload)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def main(path):
    rows = bytearray()
    for y in range(SIZE):
        rows.append(0)  # filter type 0 (None)
        # Soft vertical fade, with a solid band through the middle third.
        fade = 1.0 - abs(y - SIZE / 2) / (SIZE / 2)
        in_band = SIZE * 0.44 < y < SIZE * 0.56
        for x in range(SIZE):
            if in_band:
                rows.extend(BAND)
            else:
                rows.extend(int(c + (BAND[i] - c) * 0.12 * fade)
                            for i, c in enumerate(BACKGROUND))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
           + chunk(b"IEND", b""))

    with open(path, "wb") as handle:
        handle.write(png)
    print("wrote %s (%d bytes)" % (path, len(png)))


if __name__ == "__main__":
    main(sys.argv[1])
