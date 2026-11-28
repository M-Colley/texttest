"""
Raster image detection and pixel-level comparison utilities for FileComparison.
"""

import os
import struct
import zlib


def isImageFile(path):
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(12)
    except OSError:
        return False
    if len(header) < 6:
        return False
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith((b"GIF87a", b"GIF89a")):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return True
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return True
    if header[:2] == b"BM" and len(header) >= 6:
        try:
            declaredSize = struct.unpack("<I", header[2:6])[0]
            return declaredSize == os.path.getsize(path)
        except OSError:
            return False
    return False


def _paethPredictor(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decodePngStdlib(path):
    """Decode standard non-interlaced 8-bit grayscale/RGB/RGBA PNG files using stdlib zlib."""
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Not a PNG file")
    pos = 8
    width = height = bitDepth = colorType = interlace = None
    idatChunks = []
    while pos + 8 <= len(data):
        length, chunkType = struct.unpack(">I4s", data[pos:pos + 8])
        chunkData = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if chunkType == b"IHDR":
            width, height, bitDepth, colorType, _, _, interlace = struct.unpack(">IIBBBBB", chunkData[:13])
        elif chunkType == b"IDAT":
            idatChunks.append(chunkData)
        elif chunkType == b"IEND":
            break
    if not width or not height or bitDepth != 8 or interlace != 0:
        raise ValueError("Unsupported PNG encoding for stdlib fallback")
    channelMap = {0: 1, 2: 3, 4: 2, 6: 4}
    if colorType not in channelMap:
        raise ValueError("Unsupported PNG color type")
    channels = channelMap[colorType]
    bpp = channels
    stride = width * bpp
    raw = zlib.decompress(b"".join(idatChunks))
    expectedLen = height * (1 + stride)
    if len(raw) < expectedLen:
        raise ValueError("Truncated PNG image data")

    prevRow = bytearray(stride)
    rgba = []
    offset = 0
    for _ in range(height):
        filterType = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        if filterType == 1:  # Sub
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif filterType == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prevRow[i]) & 0xFF
        elif filterType == 3:  # Average
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prevRow[i]) >> 1)) & 0xFF
        elif filterType == 4:  # Paeth
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                up = prevRow[i]
                upLeft = prevRow[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paethPredictor(left, up, upLeft)) & 0xFF
        elif filterType != 0:
            raise ValueError("Unknown PNG filter")
        prevRow = row

        if colorType == 0:
            for g in row:
                rgba.append((float(g), float(g), float(g), 255.0))
        elif colorType == 4:
            for i in range(0, stride, 2):
                g = float(row[i])
                rgba.append((g, g, g, float(row[i + 1])))
        elif colorType == 2:
            for i in range(0, stride, 3):
                rgba.append((float(row[i]), float(row[i + 1]), float(row[i + 2]), 255.0))
        else:
            for i in range(0, stride, 4):
                rgba.append((float(row[i]), float(row[i + 1]), float(row[i + 2]), float(row[i + 3])))
    return width, height, rgba


def loadImagePixels(path):
    """Return (width, height, list_of_rgba_float_tuples_0_255) or None if undecodable."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            rgbaImg = img.convert("RGBA")
            w, h = rgbaImg.size
            pixels = [(float(r), float(g), float(b), float(a)) for r, g, b, a in rgbaImg.getdata()]
            return w, h, pixels
    except Exception:
        pass

    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        w = pixbuf.get_width()
        h = pixbuf.get_height()
        nChan = pixbuf.get_n_channels()
        rowstride = pixbuf.get_rowstride()
        buf = pixbuf.get_pixels()
        pixels = []
        for y in range(h):
            rowStart = y * rowstride
            for x in range(w):
                idx = rowStart + x * nChan
                r = float(buf[idx])
                g = float(buf[idx + 1]) if nChan > 1 else r
                b = float(buf[idx + 2]) if nChan > 2 else r
                a = float(buf[idx + 3]) if nChan > 3 else 255.0
                pixels.append((r, g, b, a))
        return w, h, pixels
    except Exception:
        pass

    try:
        return decodePngStdlib(path)
    except Exception:
        return None


def describeImageFile(path, prefix):
    sizeBytes = os.path.getsize(path) if os.path.isfile(path) else 0
    decoded = loadImagePixels(path)
    if decoded is not None:
        w, h, _ = decoded
        return f"{prefix} image file ({w}x{h} pixels, {sizeBytes} bytes).\n"
    return f"{prefix} image file ({sizeBytes} bytes).\n"


def _channelExceedsTolerance(v1, v2, absTol, relTol):
    diff = abs(v1 - v2)
    if diff == 0.0:
        return False
    allowed = absTol
    if relTol:
        denom = max(abs(v1), abs(v2))
        allowed = max(allowed, relTol * denom)
    return diff > allowed


def compareImages(stdFile, tmpFile, absTolerance=0.0, relTolerance=0.0):
    absTol = float(absTolerance or 0.0)
    relTol = float(relTolerance or 0.0)

    stdDecoded = loadImagePixels(stdFile)
    tmpDecoded = loadImagePixels(tmpFile)
    if stdDecoded is None or tmpDecoded is None:
        stdSize = os.path.getsize(stdFile)
        tmpSize = os.path.getsize(tmpFile)
        return False, f"Binary image files differ ({stdSize} and {tmpSize} bytes).\n"

    w1, h1, pixels1 = stdDecoded
    w2, h2, pixels2 = tmpDecoded
    if (w1, h1) != (w2, h2):
        return False, f"Image dimensions differ: {w1}x{h1} vs {w2}x{h2} pixels.\n"

    diffPixels = 0
    manhattanNorm = 0.0
    maxChannelDiff = 0.0
    for p1, p2 in zip(pixels1, pixels2):
        pixelDiffers = False
        for c1, c2 in zip(p1, p2):
            delta = abs(c1 - c2)
            manhattanNorm += delta
            if delta > maxChannelDiff:
                maxChannelDiff = delta
            if _channelExceedsTolerance(c1, c2, absTol, relTol):
                pixelDiffers = True
        if pixelDiffers:
            diffPixels += 1

    if diffPixels == 0:
        return True, ""

    totalPixels = max(1, w1 * h1)
    pct = 100.0 * diffPixels / totalPixels
    perPixel = manhattanNorm / totalPixels
    summary = (
        f"Images differ ({w1}x{h1} pixels):\n"
        f"  Differing pixels : {diffPixels} / {w1 * h1} ({pct:.2f}%)\n"
        f"  Max channel diff : {maxChannelDiff:.2f}\n"
        f"  Manhattan norm   : {manhattanNorm:.2f} ({perPixel:.4f} per pixel)\n"
    )
    return False, summary
