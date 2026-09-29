#!/usr/bin/env python3
"""
dctsteg.py — Herramienta propia de esteganografía DCT-LSB (variante JSteg).

La Resistencia desarrolló este script para esconder/recuperar mensajes
dentro de imágenes JPEG sin alterar su aspecto. Funciona a nivel de los
coeficientes cuantizados de la transformada de coseno discreta (DCT):

  1) Se codifica la imagen como JPEG baseline (4:4:4, calidad ~92).
  2) Por cada bloque 8x8 se obtienen sus coeficientes AC cuantizados.
  3) Se modifica el bit menos significativo (LSB) únicamente de los
     coeficientes AC cuyo valor NO es 0 ni +-1 (los deltas de color de
     baja amplitud; alterarlos cambiaria visiblesmente la imagen).
  4) El receptor recorre los mismos coeficientes y reconstruye el payload.

Uso (constructor / Red Team):
    python3 dctsteg.py -e -i imagen.jpg -f mensaje.txt -o imagen_stego.jpg
    python3 dctsteg.py -x -i imagen_stego.jpg -o mensaje_recuperado.txt
"""

import sys
import struct
import argparse
from array import array

import numpy as np

# ---------------------------------------------------------------------------
# Tablas JPEG estándar de cuantización (Anexo K del estándar)
# ---------------------------------------------------------------------------
LUMA_Q = np.array([
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
], dtype=np.float64).reshape(8, 8)

CHROMA_Q = np.array([
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
], dtype=np.float64).reshape(8, 8)

ZIGZAG = np.array([
    0, 1, 8, 16, 9, 2, 3, 10,
    17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63,
], dtype=np.int32)

# ---------------------------------------------------------------------------
# Tablas Huffman estándar JPEG (Anexo K.1): máx. 16 bits, siempre completas.
# ---------------------------------------------------------------------------
DC_LUMA_LEN = [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
DC_LUMA_SYM = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

DC_CHROMA_LEN = [0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
DC_CHROMA_SYM = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


def _full_ac_symbols():
    """Conjunto completo de 162 símbolos AC del estándar JPEG.

    El estándar (Anexo K.1) define la longitud de código de los 162
    símbolos posibles del flujo AC. Ordenamos EOB(0x00) y ZRL(0xF0)
    primero para darles las longitudes mas cortas (son los mas frecuentes).
    """
    syms = [0x00, 0xF0]
    for run in range(16):
        for cat in range(1, 11):
            s = (run << 4) | cat
            if s not in syms:
                syms.append(s)
    assert len(syms) == 162
    return syms


# Distribución de longitudes estándar (Anexo K.1): 162 códigos, máx 16 bits.
AC_LUMA_LEN = [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 125]
AC_CHROMA_LEN = [0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 119]

AC_LUMA_SYM = _full_ac_symbols()
AC_CHROMA_SYM = _full_ac_symbols()


def canonical_codes(lengths, symbols):
    """Construye (símbolo -> (código, longitud)) desde el formato DHT."""
    lookup = {}
    code = 0
    idx = 0
    for i in range(16):
        code <<= 1
        for _ in range(lengths[i]):
            if idx >= len(symbols):
                break
            lookup[symbols[idx]] = (code, i + 1)
            code += 1
            idx += 1
    return lookup


DC_LUMA_TBL = canonical_codes(DC_LUMA_LEN, DC_LUMA_SYM)
DC_CHROMA_TBL = canonical_codes(DC_CHROMA_LEN, DC_CHROMA_SYM)
AC_LUMA_TBL = canonical_codes(AC_LUMA_LEN, AC_LUMA_SYM)
AC_CHROMA_TBL = canonical_codes(AC_CHROMA_LEN, AC_CHROMA_SYM)


def build_qt(quality=92):
    """Construye tablas de cuantización para una 'calidad' dada."""
    if quality <= 0:
        quality = 1
    if quality > 100:
        quality = 100
    if quality < 50:
        s = 5000 // quality
    else:
        s = 200 - quality * 2
    luma = np.clip((LUMA_Q * s + 50) // 100, 1, 255).astype(np.uint8)
    chroma = np.clip((CHROMA_Q * s + 50) // 100, 1, 255).astype(np.uint8)
    return luma, chroma


# ---------------------------------------------------------------------------
# DCT / IDCT  (normalización acorde al estándar JPEG: C(0)=1/sqrt(2))
# ---------------------------------------------------------------------------
def _dct_basis():
    """Matrices de base de la DCT-II 8x8 precalculadas (para velocidad)."""
    C = np.zeros((8, 8), dtype=np.float64)
    for k in range(8):
        for n in range(8):
            c = 1.0 / np.sqrt(2) if k == 0 else 1.0
            C[k, n] = c * np.cos((2 * n + 1) * k * np.pi / 16)
    return 0.5 * C


_DCT_C = _dct_basis()


def fdct8(block):
    """DCT-2D de un bloque 8x8 (float): D = C * X * C^T."""
    return _DCT_C @ block @ _DCT_C.T


def idct8(coef):
    """IDCT-2D: X = C^T * D * C."""
    return _DCT_C.T @ coef @ _DCT_C


# ---------------------------------------------------------------------------
# Codificación / decodificación Huffman (canónica) construida dinámicamente
# ---------------------------------------------------------------------------
def huffman_from_freq(freq):
    """Construye código Huffman canónico a partir de frecuencias de símbolos."""
    import heapq
    heap = []
    for sym, f in freq.items():
        if f > 0:
            heapq.heappush(heap, (f, sym, None, None))
    if not heap:
        return {}
    while len(heap) > 1:
        a = heapq.heappop(heap)
        b = heapq.heappop(heap)
        heapq.heappush(heap, (a[0] + b[0], -1, a, b))
    root = heap[0]

    codes = {}

    def walk(node, bits, length):
        if node[2] is None and node[3] is None and node[1] != -1:
            codes[node[1]] = (bits, length)
            return
        if node[2] is not None:
            walk(node[2], (bits << 1) | 0, length + 1)
        if node[3] is not None:
            walk(node[3], (bits << 1) | 1, length + 1)

    walk(root, 0, 0)

    # Reasignar códigos canónicos (para que DHT cumpla la regla de prefijos)
    by_len = {}
    for sym, (_b, l) in codes.items():
        by_len.setdefault(l, []).append(sym)
    next_code = 0
    canonical = {}
    for length in sorted(by_len):
        for sym in sorted(by_len[length]):
            canonical[sym] = (next_code, length)
            next_code += 1
        next_code <<= 1
    return canonical


def build_huff_tables(hist_dc, hist_ac):
    """Construye tablas DC y AC. Devuelve dicts sym->(code,length)."""
    dc_tbl = huffman_from_freq(hist_dc)
    ac_tbl = huffman_from_freq(hist_ac)
    return dc_tbl, ac_tbl


def emit_bits(bits_out, code, length):
    """Agrega 'length' bits (MSB primero) al buffer de bits."""
    for i in range(length - 1, -1, -1):
        bits_out.append((code >> i) & 1)


def bits_to_bytes(bits_out):
    """Convierte el flujo de bits a bytes con relleno de bits (bit-stuffing)."""
    out = bytearray()
    acc = 0
    nbits = 0
    for b in bits_out:
        acc = (acc << 1) | b
        nbits += 1
        if nbits == 8:
            out.append(acc)
            if acc == 0xFF:
                out.append(0x00)  # byte stuffing
            acc = 0
            nbits = 0
    if nbits:
        acc <<= (8 - nbits)
        out.append(acc)
        if acc == 0xFF:
            out.append(0x00)
    return bytes(out)


class BitReader:
    def __init__(self, data, pos):
        self.data = data
        self.pos = pos
        self.bitbuf = 0
        self.bitcnt = 0

    def next_byte(self):
        if self.pos >= len(self.data):
            raise EOFError('fin de datos JPEG')
        b = self.data[self.pos]
        self.pos += 1
        if b == 0xFF:
            # 0xFF puede ir seguido de 0x00 (stuffing) o de marcador
            if self.pos < len(self.data):
                nb = self.data[self.pos]
                if nb == 0x00:
                    self.pos += 1
                    return 0xFF
                if 0xD0 <= nb <= 0xD7:
                    self.pos += 1  # restart marker
                    return self.next_byte()
                if nb == 0xFF:
                    self.pos += 1
                    return self.next_byte()
                raise EOFError('marcador inesperado en flujo de datos')
        return b

    def read_bit(self):
        if self.bitcnt == 0:
            b = self.next_byte()
            self.bitbuf = b
            self.bitcnt = 8
        self.bitcnt -= 1
        return (self.bitbuf >> self.bitcnt) & 1

    def read_bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.read_bit()
        return v

    def skip_to_byte(self):
        self.bitcnt = 0


def build_decode_table(codes_bylen, symbols_byval):
    """No usada: mantenida como referencia. Ver decode_tables()."""
    return None


# ---------------------------------------------------------------------------
# Emisión del archivo JPEG
# ---------------------------------------------------------------------------
def write_jpeg_4_4_4(path, ycc, luma_q, chroma_q, payload_bytes=None,
                     quality=92):
    """Codifica Y,Cb,Cr (4:4:4) a JPEG baseline insertando payload si se da."""
    Y, Cb, Cr = ycc
    h, w = Y.shape
    assert h % 8 == 0 and w % 8 == 0

    luma_q, chroma_q = build_qt(quality)

    # --- cuantización + zigzag de Y, Cb, Cr ---
    blocks = []
    ncells_h = w // 8
    ncells_v = h // 8
    for yy in range(ncells_v):
        for xx in range(ncells_h):
            y_b = Y[yy * 8:(yy + 1) * 8, xx * 8:(xx + 1) * 8] - 128.0
            cb_b = Cb[yy * 8:(yy + 1) * 8, xx * 8:(xx + 1) * 8] - 128.0
            cr_b = Cr[yy * 8:(yy + 1) * 8, xx * 8:(xx + 1) * 8] - 128.0
            qy = np.rint(fdct8(y_b) / luma_q).astype(np.int32)
            qcb = np.rint(fdct8(cb_b) / chroma_q).astype(np.int32)
            qcr = np.rint(fdct8(cr_b) / chroma_q).astype(np.int32)
            blocks.append((qy, qcb, qcr))

    # --- inserción del payload (DCT-LSB / JSteg) ---
    if payload_bytes is not None:
        bitstream = []
        for byte_val in struct.pack('<I', len(payload_bytes)) + payload_bytes:
            for i in range(7, -1, -1):
                bitstream.append((byte_val >> i) & 1)
        idx = 0
        for qy, qcb, qcr in blocks:
            if idx >= len(bitstream):
                break
            for q in (qy, qcb, qcr):
                if idx >= len(bitstream):
                    break
                for z in range(1, 64):  # solo AC (sin DC)
                    if idx >= len(bitstream):
                        break
                    u, v = divmod(int(ZIGZAG[z]), 8)
                    val = int(q[u, v])
                    if val == 0 or val == 1 or val == -1:
                        continue
                    bit = bitstream[idx]
                    newval = val
                    if (val & 1) != bit:
                        newval = val ^ 1
                    if newval == 0 or newval == 1 or newval == -1:
                        # el LSB toggled cae en la zona inelegible (p.ej. -2 ^ 1 == -1).
                        # escribimos el valor marcador (asi la extraccion lo salta) pero
                        # NO consumimos bit: el siguiente coeficiente elegible lo lleva.
                        q[u, v] = newval
                        continue
                    q[u, v] = newval
                    idx += 1
        if idx < len(bitstream):
            raise RuntimeError(
                'capacidad de ocultamiento insuficiente: faltan %d bits'
                % (len(bitstream) - idx))

    # --- dos pasadas: 1) secuencia de símbolos exacta, 2) codificación ---
    # DPCM en DC y RLE en AC (formato estándar JPEG).
    def dc_deltas(blocks_comp):
        deltas = []
        prev = 0
        for q in blocks_comp:
            cur = int(q[0, 0])
            deltas.append(cur - prev)
            prev = cur
        return deltas

    def ac_symbols(q):
        out = []
        run = 0
        for z in range(1, 64):
            u, v = divmod(int(ZIGZAG[z]), 8)
            coef = int(q[u, v])
            if coef == 0:
                run += 1
                continue
            while run >= 16:
                out.append(0xF0)  # ZRL
                run -= 16
            out.append((run << 4) | abs(coef).bit_length())
            run = 0
        if run > 0:
            out.append(0x00)  # EOB
        return out

    y_blocks = [b[0] for b in blocks]
    cb_blocks = [b[1] for b in blocks]
    cr_blocks = [b[2] for b in blocks]

    # --- serialización ---
    out = bytearray()
    out += b'\xff\xd8'  # SOI
    # APP0 JFIF
    out += b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00' + b'\x01\x01' + \
           b'\x00' + struct.pack('>HH', 1, 1) + b'\x00\x00'
    # DQT (2 tablas)
    dqt = b'\xff\xdb'
    tbl = bytearray([0x00]) + luma_q.tobytes() + bytearray([0x01]) + chroma_q.tobytes()
    dqt += struct.pack('>H', 2 + len(tbl)) + bytes(tbl)
    out += dqt
    # SOF0
    sof = bytearray(b'\xff\xc0')
    sof += struct.pack('>H', 17)
    sof += bytes([8])
    sof += struct.pack('>HH', h, w)
    sof += bytes([3, 1, 0x11, 0x00, 2, 0x11, 0x01, 3, 0x11, 0x01])
    out += sof
    # DHT (tablas estándar: DC0/AC0 luma, DC1/AC1 croma)
    def dht_segment(cls_id, lengths, syms):
        seg = bytearray()
        seg.append(cls_id)
        for i in range(16):
            seg.append(lengths[i])
        for s in syms:
            seg.append(s)
        return seg

    dht = bytearray(b'\xff\xc4')
    body = (dht_segment(0x00, DC_LUMA_LEN, DC_LUMA_SYM) +
            dht_segment(0x10, AC_LUMA_LEN, AC_LUMA_SYM) +
            dht_segment(0x01, DC_CHROMA_LEN, DC_CHROMA_SYM) +
            dht_segment(0x11, AC_CHROMA_LEN, AC_CHROMA_SYM))
    dht += struct.pack('>H', 2 + len(body)) + body
    out += dht
    # SOS
    sos = bytearray(b'\xff\xda')
    sos += struct.pack('>H', 12)
    sos += bytes([3, 1, 0x00, 2, 0x11, 3, 0x11])
    sos += bytes([0x00, 0x3F, 0x00])
    out += sos
    # Entropía
    bits = []

    def enc_dc(diff, tbl):
        cat = abs(diff).bit_length()
        code, length = tbl[cat]
        emit_bits(bits, code, length)
        if cat > 0:
            if diff < 0:
                emit_bits(bits, (1 << cat) - 1 + diff, cat)
            else:
                emit_bits(bits, diff, cat)

    def enc_ac_z(run, cat, tbl):
        while run > 15:
            code, length = tbl[0xF0]
            emit_bits(bits, code, length)
            run -= 16
        sym = (run << 4) | cat
        code, length = tbl[sym]
        emit_bits(bits, code, length)

    def emit_block(q, prev_dc, dc_tbl, ac_tbl):
        d = int(q[0, 0]) - int(prev_dc[0])
        enc_dc(d, dc_tbl)
        prev_dc[0] = int(q[0, 0])
        run = 0
        for z in range(1, 64):
            u, v = divmod(int(ZIGZAG[z]), 8)
            coef = int(q[u, v])
            if coef == 0:
                run += 1
                continue
            enc_ac_z(run, abs(coef).bit_length(), ac_tbl)
            catc = abs(coef).bit_length()
            if coef < 0:
                emit_bits(bits, (1 << catc) - 1 + coef, catc)
            else:
                emit_bits(bits, coef, catc)
            run = 0
        if run > 0:
            enc_ac_z(0, 0, ac_tbl)  # EOB

    prev_y = [0]
    prev_cb = [0]
    prev_cr = [0]
    for qy, qcb, qcr in blocks:
        emit_block(qy, prev_y, DC_LUMA_TBL, AC_LUMA_TBL)
        emit_block(qcb, prev_cb, DC_CHROMA_TBL, AC_CHROMA_TBL)
        emit_block(qcr, prev_cr, DC_CHROMA_TBL, AC_CHROMA_TBL)

    out += bits_to_bytes(bits)
    out += b'\xff\xd9'  # EOI
    with open(path, 'wb') as f:
        f.write(out)
    return len(payload_bytes) if payload_bytes is not None else 0


# ---------------------------------------------------------------------------
# Lectura de un JPEG baseline y extracción del payload
# ---------------------------------------------------------------------------
def read_jpeg(path):
    """Devuelve (cuant, huff, scan_data, comps, dims) para baseline 4:4:4."""
    data = open(path, 'rb').read()
    pos = 2
    qt = {}          # id -> 8x8 array
    huff = {}        # (cls,id) -> {'lengths':..,'syms':..}
    comps = []
    dims = None
    scan = None
    while True:
        if data[pos] != 0xFF:
            # dentro de datos de escaneo
            break
        marker = data[pos + 1]
        seglen = struct.unpack('>H', data[pos + 2:pos + 4])[0]
        if marker == 0xDB:  # DQT
            body = data[pos + 4:pos + 2 + seglen]
            qp = 0
            while qp < len(body):
                pq_tq = body[qp]
                qp += 1
                if pq_tq >> 4 == 0:
                    table = np.full(64, 0, dtype=np.uint8)
                    table[:] = np.frombuffer(body[qp:qp + 64], dtype=np.uint8)
                    qp += 64
                else:
                    raise ValueError('DQT 16-bit no soportado')
                qt[pq_tq & 0x0F] = table.reshape(8, 8)
        elif marker == 0xC0:  # SOF0
            body = data[pos + 4:pos + 2 + seglen]
            prec = body[0]
            h, w = struct.unpack('>HH', body[1:5])
            ncomp = body[5]
            comps = []
            for i in range(ncomp):
                cid, hv, tq = body[6 + i * 3], body[7 + i * 3], body[8 + i * 3]
                comps.append((cid, hv >> 4, hv & 0x0F, tq))
            dims = (h, w)
        elif marker == 0xC4:  # DHT
            body = data[pos + 4:pos + 2 + seglen]
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
                huff[(cls, tid)] = {'lengths': lengths, 'syms': syms}
        elif marker == 0xDA:  # SOS
            body = data[pos + 4:pos + 2 + seglen]
            ns = body[0]
            scan_comps = []
            for i in range(ns):
                cid, t = body[1 + i * 2], body[2 + i * 2]
                scan_comps.append((cid, t >> 4, t & 0x0F))
            ss, se, a = body[1 + ns * 2], body[2 + ns * 2], body[3 + ns * 2]
            scan = {'comps': scan_comps, 'ss': ss, 'se': se, 'a': a,
                    'start': pos + 2 + seglen}
            break
        pos += 2 + seglen
    if scan is None:
        raise ValueError('no se encontró la sección SOS')
    return qt, huff, scan, comps, dims


def decode_tables(huff):
    """Convierte DHT en: dict (cls,id) -> (codebits,length,sym) navegable."""
    tables = {}
    for (cls, tid), t in huff.items():
        lengths = t['lengths']
        syms = t['syms']
        # construir mapa code->(len,sym) canónico
        code = 0
        table = {}
        sp = 0
        for i in range(16):
            ncodes = lengths[i] if i < len(lengths) else 0
            code <<= 1
            for _ in range(ncodes):
                if sp >= len(syms):
                    break
                sym = syms[sp]
                sp += 1
                table[(code, i + 1)] = sym
                code += 1
        # almacenar con mapa (valor, longitud) para decodificar bit a bit.
        # la longitud es parte de la clave: el acumulador de N bits solo puede
        # compararse contra los códigos canónicos de exactamente N bits.
        tables[(cls, tid)] = table
    return tables


def decode_huff_bit(reader, table):
    """Lee bits hasta hallar un código (valor, longitud) en la tabla."""
    code = 0
    for depth in range(1, 17):
        b = reader.read_bit()
        code = (code << 1) | b
        if (code, depth) in table:
            return table[(code, depth)]
    raise ValueError('símbolo Huffman no encontrado')


def extract_from_jpeg(path, verbose=False):
    """Extrae payload DCT-LSB de un JPEG baseline creado por esta herramienta."""
    qt, huff, scan, comps, dims = read_jpeg(path)
    tables = decode_tables(huff)
    data = open(path, 'rb').read()
    reader = BitReader(data, scan['start'])
    h, w = dims
    nblocks_x = w // 8
    nblocks_y = h // 8

    # tabla de cuantización por componente (luma=0, chroma=1)
    qt_ids = [c[3] for c in comps]  # tq por componente

    # identificar cuál tabla DC/AC usar por la info del scan (t por comp)
    scan_comp_t = {cid: t for cid, t, _ in scan['comps']}
    bits = []

    dc_prev = {}
    for _ in comps:
        dc_prev_set = {}

    def order_blocks():
        return [(y, x) for y in range(nblocks_y) for x in range(nblocks_x)]

    # procesar MCU por MCU: componentes en orden del scan
    for (y, x) in order_blocks():
        for cid, t, qid in scan['comps']:
            if cid not in dc_prev:
                dc_prev[cid] = 0

            dc_sym = decode_huff_bit(reader, tables[(0, qid)])
            if dc_sym == 0:
                delta = 0
            else:
                delta = reader.read_bits(dc_sym)
                if delta < (1 << (dc_sym - 1)):
                    delta -= (1 << dc_sym) - 1
            coef_dc = dc_prev[cid] + delta
            dc_prev[cid] = coef_dc

            coeffs = np.zeros(64, dtype=np.int32)
            coeffs[0] = coef_dc
            z = 1
            while z <= 63:
                sym = decode_huff_bit(reader, tables[(1, qid)])
                if sym == 0x00:  # EOB
                    break
                if sym == 0xF0:  # ZRL
                    z += 16
                    continue
                run = sym >> 4
                size = sym & 0x0F
                z += run
                if z > 63:
                    break
                val = reader.read_bits(size)
                if val < (1 << (size - 1)):
                    val -= (1 << size) - 1
                if z <= 63:
                    coeffs[z] = val
                z += 1
            # extraer bits de los AC elegibles
            for z in range(1, 64):
                val = int(coeffs[z])
                if val == 0 or val == 1 or val == -1:
                    continue
                bits.append(val & 1)

    # reconstruir payload desde los bits
    bitlen = (len(bits) // 8) * 8
    nbytes = bitlen // 8
    raw = bytearray(nbytes)
    for i in range(nbytes):
        b = 0
        for j in range(8):
            b = (b << 1) | (bits[i * 8 + j] if i * 8 + j < len(bits) else 0)
        raw[i] = b
    if len(raw) < 4:
        raise ValueError('sin payload')
    plen = struct.unpack('<I', bytes(raw[:4]))[0]
    # seguridad: el payload no debe exceder el resto
    payload = bytes(raw[4:4 + plen]) if plen <= len(raw) - 4 else b''
    if verbose:
        print('[i] bits disponibles:', len(bits))
        print('[i] longitud del payload:', plen)
    return payload


# ---------------------------------------------------------------------------
# Conversión RGB -> YCbCr y viceversa (rango de color JPEG)
# ---------------------------------------------------------------------------
def rgb_to_ycc(rgb):
    r = rgb[:, :, 0].astype(np.float64)
    g = rgb[:, :, 1].astype(np.float64)
    b = rgb[:, :, 2].astype(np.float64)
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return y, cb, cr


def ycc_to_rgb(y, cb, cr):
    y = y.astype(np.float64)
    cb = cb.astype(np.float64)
    cr = cr.astype(np.float64)
    r = y + 1.402 * (cr - 128)
    g = y - 0.344136 * (cb - 128) - 0.714136 * (cr - 128)
    b = y + 1.772 * (cb - 128)
    out = np.stack([r, g, b], axis=-1)
    return np.clip(out, 0, 255).astype(np.uint8)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Esteganografía DCT-LSB (JSteg)')
    ap.add_argument('-e', '--embed', action='store_true', help='ocultar archivo')
    ap.add_argument('-x', '--extract', action='store_true', help='recuperar archivo')
    ap.add_argument('-i', '--input', required=True, help='imagen JPEG de entrada')
    ap.add_argument('-f', '--file', help='archivo a ocultar (embed)')
    ap.add_argument('-o', '--output', required=True, help='archivo de salida')
    ap.add_argument('-q', '--quality', type=int, default=92)
    args = ap.parse_args(argv)

    from PIL import Image
    im = Image.open(args.input).convert('RGB')
    w, h = im.size
    # recortar a múltiplo de 8
    nw, nh = (w // 8) * 8, (h // 8) * 8
    if nw != w or nh != h:
        im = im.crop((0, 0, nw, nh))
    rgb = np.array(im, dtype=np.uint8)
    y, cb, cr = rgb_to_ycc(rgb)

    if args.embed:
        payload = open(args.file, 'rb').read()
        n = write_jpeg_4_4_4(args.output, (y, cb, cr), None, None, payload,
                             args.quality)
        print('[+] Ocultados %d bytes en %s' % (n, args.output))
    elif args.extract:
        payload = extract_from_jpeg(args.input, verbose=True)
        with open(args.output, 'wb') as f:
            f.write(payload)
        print('[+] Mensaje recuperado (%d bytes) -> %s' % (len(payload), args.output))
        try:
            txt = payload.decode('utf-8')
            print('    Contenido:')
            print('    ' + txt.replace('\n', '\n    '))
        except UnicodeDecodeError:
            pass
    else:
        ap.error('indique -e o -x')


if __name__ == '__main__':
    main()