#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resistance_steg.py -- Extractor de datos ocultos en JPEG (DCT-LSB / JSteg).

Herramienta "forense" del atacante en la mision M4 del escenario Skynet.
Analiza los coeficientes AC cuantizados de un JPEG baseline 4:4:4 de la
maquina victima y recupera el mensaje incrustado en el bit menos
significativo (LSB) de cada coeficiente utilizable.

Uso:
    python3 resistance_steg.py captura_terminador.jpg > pista.txt

Requiere unicamente la libreria estandar de Python 3 (sin numpy ni PIL):
se construye sobre el propio codificador/decodificador del escenario.
"""

import struct
import sys

# ---------------------------------------------------------------------------
# Lector de bits (flujo de entropia JPEG, relleno 0xFF 0x00)
# ---------------------------------------------------------------------------
class BitReader:
    def __init__(self, data, start):
        self.data = data
        self.pos = start
        self.bitbuf = 0
        self.bitcnt = 0

    def read_bit(self):
        if self.bitcnt == 0:
            b = self._next_byte()
            self.bitbuf = b
            self.bitcnt = 8
        self.bitcnt -= 1
        return (self.bitbuf >> self.bitcnt) & 1

    def read_bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.read_bit()
        return v

    def _next_byte(self):
        while True:
            b = self.data[self.pos]
            self.pos += 1
            if b == 0xFF:
                nb = self.data[self.pos]
                if nb == 0x00:      # relleno: 0xFF -> 0xFF 0x00
                    self.pos += 1
                    return 0xFF
                if 0xD0 <= nb <= 0xD7 or nb == 0xFF:  # flujos de reinicio
                    self.pos += 1
                    continue
                raise EOFError('marcador no esperado en flujo de datos')
            return b


# ---------------------------------------------------------------------------
# Parseo del JPEG (baseline): DQT, SOF0, DHT, SOS
# ---------------------------------------------------------------------------
def read_jpeg(path):
    data = open(path, 'rb').read()
    pos = 2
    huff = {}
    comps = []
    dims = None
    scan = None
    while True:
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        seglen = struct.unpack('>H', data[pos + 2:pos + 4])[0]
        body = data[pos + 4:pos + 2 + seglen]
        if marker == 0xC0:          # SOF0
            h, w = struct.unpack('>HH', body[1:5])
            ncomp = body[5]
            dims = (h, w)
            comps = []
            for i in range(ncomp):
                cid, hv, tq = body[6 + i * 3], body[7 + i * 3], body[8 + i * 3]
                comps.append((cid, hv >> 4, hv & 0x0F, tq))
        elif marker == 0xC4:        # DHT
            p = 0
            while p < len(body):
                tc_th = body[p]
                p += 1
                cls = tc_th >> 4
                tid = tc_th & 0x0F
                lengths = list(body[p:p + 16])
                p += 16
                nsym = sum(lengths)
                syms = list(body[p:p + nsym])
                p += nsym
                huff[(cls, tid)] = (lengths, syms)
        elif marker == 0xDA:        # SOS
            ns = body[0]
            scan_comps = []
            for i in range(ns):
                cid, t = body[1 + i * 2], body[2 + i * 2]
                scan_comps.append((cid, t >> 4, t & 0x0F))
            scan = {'comps': scan_comps, 'start': pos + 2 + seglen}
        pos += 2 + seglen
    return huff, scan, dims


# ---------------------------------------------------------------------------
# Tablas Huffman canonicas y decodificacion bit a bit
# ---------------------------------------------------------------------------
def decode_tables(huff):
    tables = {}
    for (cls, tid), (lengths, syms) in huff.items():
        code = 0
        table = {}
        sp = 0
        for i in range(16):
            code <<= 1
            ncodes = lengths[i] if i < len(lengths) else 0
            for _ in range(ncodes):
                table[(code, i + 1)] = syms[sp]
                code += 1
                sp += 1
        tables[(cls, tid)] = table
    return tables


def decode_huff_bit(reader, table):
    code = 0
    for depth in range(1, 17):
        b = reader.read_bit()
        code = (code << 1) | b
        if (code, depth) in table:
            return table[(code, depth)]
    raise ValueError('simbolo Huffman no encontrado')


# ---------------------------------------------------------------------------
# Extraccion DCT-LSB
# ---------------------------------------------------------------------------
def extract(path, verbose=False):
    huff, scan, dims = read_jpeg(path)
    tables = decode_tables(huff)
    data = open(path, 'rb').read()
    reader = BitReader(data, scan['start'])
    h, w = dims
    nbx, nby = w // 8, h // 8

    bits = []
    dc_prev = {}
    for _y in range(nby):
        for _x in range(nbx):
            for cid, dc_id, ac_id in scan['comps']:
                if cid not in dc_prev:
                    dc_prev[cid] = 0
                dc_sym = decode_huff_bit(reader, tables[(0, dc_id)])
                if dc_sym:
                    delta = reader.read_bits(dc_sym)
                    if delta < (1 << (dc_sym - 1)):
                        delta -= (1 << dc_sym) - 1
                else:
                    delta = 0
                dc_prev[cid] += delta

                coeffs = [0] * 64
                coeffs[0] = dc_prev[cid]
                z = 1
                while z <= 63:
                    sym = decode_huff_bit(reader, tables[(1, ac_id)])
                    if sym == 0x00:      # EOB
                        break
                    if sym == 0xF0:      # ZRL
                        z += 16
                        continue
                    run = sym >> 4
                    size = sym & 0x0F
                    z += run
                    if z > 63:
                        break
                    if size:
                        val = reader.read_bits(size)
                        if val < (1 << (size - 1)):
                            val -= (1 << size) - 1
                        coeffs[z] = val
                    z += 1

                for z in range(1, 64):
                    val = coeffs[z]
                    if val == 0 or val == 1 or val == -1:
                        continue
                    bits.append(val & 1)

    nbytes = len(bits) // 8
    raw = bytearray(nbytes)
    for i in range(nbytes):
        b = 0
        for j in range(8):
            b = (b << 1) | bits[i * 8 + j]
        raw[i] = b
    if len(raw) < 4:
        raise ValueError('sin payload')
    plen = struct.unpack('<I', bytes(raw[:4]))[0]
    payload = bytes(raw[4:4 + plen]) if plen <= len(raw) - 4 else b''
    if verbose:
        sys.stderr.write('[i] bits disponibles: %d\n' % len(bits))
        sys.stderr.write('[i] longitud del payload: %d\n' % plen)
    return payload


def main():
    if len(sys.argv) < 2:
        sys.stderr.write('Uso: python3 resistance_steg.py <imagen.jpg>\n')
        return 1
    payload = extract(sys.argv[1], verbose=True)
    try:
        print(payload.decode('utf-8'))
    except UnicodeDecodeError:
        sys.stdout.buffer.write(payload)
    return 0


if __name__ == '__main__':
    sys.exit(main())