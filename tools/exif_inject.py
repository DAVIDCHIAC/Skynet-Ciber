#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exif_inject.py -- Inserta metadatos EXIF (APP1) en un JPEG sin re-codificar.

Necesario para las banderas F1/F4: reintroducir la imagen con PIL destruiria
los coeficientes cuantizados que transportan el payload DCT-LSB. Esta
herramienta opera a nivel de marcadores y preserva el flujo de entropia.

Uso (biblioteca):
    from exif_inject import inject_exif_bytes
    jab = inject_exif_bytes(jpeg, {'ImageDescription': 'NucleoRojo{...}'})
"""

import struct

# tipos EXIF
ASCII = 2


def _entry(tag, type_, count, value_bytes, base_offset):
    """Devuelve la entrada IFD de 12 bytes."""
    if type_ == ASCII:
        if count <= 4:
            # valor empotrado, alineado a la derecha
            field = value_bytes + b'\x00' * (4 - count)
            return (struct.pack('<HHI', tag, type_, count) + field)
        off = base_offset
        return (struct.pack('<HHI', tag, type_, count) +
                struct.pack('<I', off))


def build_exif_app1(meta):
    """Construye el segmento APP1 completo (FFE1 + Exif\\0\\0 + TIFF LE)."""
    # entrada estandar: ImageDescription y Software son ASCII
    tags = {
        'ImageDescription': 0x010E,
        'Software': 0x0131,
        'Make': 0x010F,
        'Model': 0x0110,
    }
    entries_meta = []
    for k in ('ImageDescription', 'Software', 'Make', 'Model'):
        if k in meta and meta[k]:
            entries_meta.append((tags[k], meta[k].encode('latin-1', 'replace') + b'\x00'))

    n = len(entries_meta)
    # offsets dentro del TIFF
    ifd_offset = 8
    entries_block = n * 12
    data_offset = ifd_offset + 2 + entries_block + 4
    tiff_len = data_offset + sum(len(v) for _, v in entries_meta)

    tiff = bytearray(b'II' + struct.pack('<H', 42) + struct.pack('<I', ifd_offset))
    tiff += struct.pack('<H', n)
    cursor = data_offset
    for tag, val in entries_meta:
        if len(val) <= 4:
            field = val + b'\x00' * (4 - len(val))
            tiff += struct.pack('<HHI', tag, ASCII, len(val)) + field
        else:
            tiff += struct.pack('<HHI', tag, ASCII, len(val)) + struct.pack('<I', cursor)
            cursor += len(val)
    tiff += struct.pack('<I', 0)  # next IFD
    for tag, val in entries_meta:
        if len(val) > 4:
            tiff += val
    assert len(tiff) == data_offset + sum(len(v) for _, v in entries_meta), \
        'longitud TIFF incorrecta'
    app1 = b'\xff\xe1' + struct.pack('>H', 2 + 6 + len(tiff)) + b'Exif\x00\x00' + bytes(tiff)
    return app1


def inject_exif_bytes(jpeg: bytes, meta: dict) -> bytes:
    """Inserta un segmento APP1 (EXIF) justo despues del SOI."""
    assert jpeg[:2] == b'\xff\xd8', 'no es JPEG'
    app1 = build_exif_app1(meta)
    return jpeg[:2] + app1 + jpeg[2:]


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        sys.stderr.write('uso: exif_inject.py IN.jpg OUT.jpg\n')
        sys.stderr.write('etiquetas por defecto: ImageDescription/Software\n')
        sys.exit(1)
    meta = {
        'ImageDescription': 'NucleoRojo{F1_PLACEHOLDER}',
        'Software': 'NucleoCore/1.0',
        'Make': 'Skynet Dynamics',
    }
    data = open(sys.argv[1], 'rb').read()
    out = inject_exif_bytes(data, meta)
    open(sys.argv[2], 'wb').write(out)
    print('[+] APP1 inyectado en %s (%d bytes)' % (sys.argv[2], len(out)))