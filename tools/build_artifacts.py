#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_artifacts.py -- Generador de artefactos del escenario (uso del fabricante).

Genera de forma DETERMINISTA los ficheros de las misiones M3/M4 (criptografia),
el zip cifrado y el pcap de red, dentro de 00-install/files/.

La semilla fija permite reproducir exactamente los mismos numeros RSA y el
mismo sha512 de validacion en cada ejecucion.
"""

import base64
import hashlib
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resistance_steg  # noqa: F401  (referencia: el extractor de M4 ya existe)

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: E402
from cryptography.hazmat.primitives import padding as sym_padding  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FILES = os.path.join(ROOT, '00-install', 'files')
BUILD_SRC = os.path.join(ROOT, '00-install', 'build_sources')

RAND = random.Random(0x5E3E7A5E57)

# ---------------------------------------------------------------------------
# Material literario (se genera una vez aqui; el resto del escenario lo usa)
# ---------------------------------------------------------------------------
ORDEN_FINAL = 'El ataque es a las 4:00'
PASSPHRASE_AES = 'S3kiRa-07'
PHRASE_B64 = 'LA RESISTENCIA TIENE MUCHOS ROSTROS_0110'

PISTA1_TEXT = (
    'PISTA_1 :: TRANSMISION INTERCEPTADA DEL ANALISTA "OJODEDIOS"\n'
    '\n'
    '{PROTOCOLO:0x07}\n'
    '\n'
    'PREGUNTA: \u00bfCual es el nombre de la persona que esta al lado del terminator?\n'
    '\n'
    '[SUB-PROTOCOLO] La respuesta abre el ARCA. Usala tal cual, respetando\n'
    'mayusculas y la posicion de la palabra.\n'
)

PISTA2_TEXT = (
    'PISTA_2 :: bitacora del analista "OJODEDIOS"\n'
    '\n'
    'Aprendimos que Skynet deja los primos junto al motor de claves:\n'
    '  - llave_privada.txt tiene p y q\n'
    '  - nucleo.conf publica e y n\n'
    '  - el cifrado RSA se resuelve con el Euclides extendido (algoritmo de\n'
    '    nuestra generacion) y la exponenciacion modular rapida.\n'
    '  - la frase resultante desbloquea el ruido (openssl enc -aes-256-cbc -d\n'
    '    -pbkdf2 -pass pass:<clave> -in ruido.enc -out orden.txt)\n'
    'El diccionario de la Resistance tambien ataca cerraduras de acceso remoto.\n'
)

PISTA3_TEXT = (
    'PISTA_3 :: inteligencia de campo\n'
    '\n'
    'El nucleo Skynet tiene MASCARA: se valida la concatenacion de los cinco\n'
    'fragmentos de bandera (en orden de mision) junto con la ORDEN exacta.\n'
    'Para la mision de la imagen: la pregunta se ha ocultado en los\n'
    'coeficientes del JPEG. La respuesta es una persona. Esa misma respuesta\n'
    'abre el ARCA (bandera_nodo.zip).\n'
)


def frase_nucleo():
    """Split de la frase en 5 fragmentos y sus bases64 (sin '=')."""
    frags = ['LA RESIST', 'ENCIA TI', 'ENE MUCHO', 'S ROSTROS', '_0110']
    assert ''.join(frags) == PHRASE_B64
    b64s = [base64.b64encode(f.encode('utf-8')).decode('ascii').rstrip('=') for f in frags]
    return frags, b64s


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def write(path, data, text=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data)
    return path


def wbin(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    return path


def facto(p, q):
    return (p - 1) * (q - 1)


def rsa_gen():
    """Genera primos ~64 bits, e=65537 y clave privada d (Euclides extendido)."""
    def is_prime(n):
        if n < 2:
            return False
        if n % 2 == 0:
            return n == 2
        d, s = n - 1, 0
        while d % 2 == 0:
            s += 1
            d //= 2
        for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            if a >= n:
                continue
            x = pow(a, d, n)
            if x == 1 or x == n - 1:
                continue
            ok = False
            for _ in range(s - 1):
                x = x * x % n
                if x == n - 1:
                    ok = True
                    break
            if not ok:
                return False
        return True

    def rnd_prime(bits):
        while True:
            n = RAND.getrandbits(bits) | (1 << (bits - 1)) | 1
            if is_prime(n):
                return n

    e = 65537
    while True:
        p = rnd_prime(64)
        q = rnd_prime(64)
        if p == q:
            continue
        n = p * q
        phi = facto(p, q)
        try:
            d = pow(e, -1, phi)
        except ValueError:
            continue
        return p, q, n, e, d


def rsa_encrypt(m_int, e, n):
    return pow(m_int, e, n)


# ---------------------------------------------------------------------------
# AES en formato OpenSSL (`enc -aes-256-cbc -pbkdf2 -pass pass:...`)
# ---------------------------------------------------------------------------
def openssl_aes256_cbc_encrypt(plaintext: bytes, password: bytes, salt: bytes):
    key_iv = hashlib.pbkdf2_hmac('sha256', password, salt, 10000, dklen=48)
    key, iv = key_iv[:32], key_iv[32:]
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    body = enc.update(padded) + enc.finalize()
    return b'Salted__' + salt + body


def openssl_aes256_cbc_decrypt(blob: bytes, password: bytes):
    assert blob[:8] == b'Salted__'
    salt = blob[8:16]
    key_iv = hashlib.pbkdf2_hmac('sha256', password, salt, 10000, dklen=48)
    key, iv = key_iv[:32], key_iv[32:]
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = dec.update(blob[16:]) + dec.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


# ---------------------------------------------------------------------------
# Caesar (ROT) para el reto extra de M3
# ---------------------------------------------------------------------------
def caesar(text, shift=13):
    out = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            out.append(chr((ord(ch) - ord('A') + shift) % 26 + ord('A')))
        elif 'a' <= ch <= 'z':
            out.append(chr((ord(ch) - ord('a') + shift) % 26 + ord('a')))
        else:
            out.append(ch)
    return ''.join(out)


# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------
def build_crypto():
    frags, b64s = frase_nucleo()

    # --- RSA ---------------------------------------------------------------
    p, q, n, e, d = rsa_gen()
    m = int.from_bytes(PASSPHRASE_AES.encode('ascii'), 'big')
    assert m < n
    c = rsa_encrypt(m, e, n)
    assert pow(c, d, n) == m

    write(os.path.join(FILES, 'intranet', 'nucleo', 'nucleo.conf'),
          'NUCLEO_CONFIG v1\n# parametros publicos del motor de claves\n'
          'e=%d\nn=%d\n' % (e, n))
    write(os.path.join(FILES, 'intranet', 'nucleo', 'nucleo.conf.enc'),
          '# cifrado RSA de la clave operativa (decimal)\nC=%d\n' % c)
    priv = (os.path.join(FILES, 'home', 'dyson_m', 'nucleo', 'llave_privada.txt'))
    write(priv, 'PRIVATE_KEY v1\n# material privado del nodo (ROBADO a Skynet)\n'
                'p=%d\nq=%d\ne=%d\n' % (p, q, e))

    # --- orden (contenido de ruido.enc) ------------------------------------
    b64_doble = base64.b64encode(base64.b64encode(ORDEN_FINAL.encode('utf-8'))).decode('ascii')
    orden = (
        'NUCLEO :: ORDEN DE EJECUCION v0x07\n'
        '=====================================\n'
        + PISTA3_TEXT +
        '\nORDEN (traduccion de la red):\n' + b64_doble + '\n'
        'Deberias leerlo dos veces para que el CyberChef devuelva la orden exacta.\n'
        '\n'
        'FRAGMENTO_3=NucleoRojo{%s}\n' % b64s[2] +
        '\nRETO_EXTRA (Cesar/ROT13 si te sobran puntos):\n'
        'CESAR::%s\n' % caesar('el arcon de la resistencia se abre con john connor') +
        '\n-- fin orden --\n'
    )
    salt = bytes.fromhex('0f4a2b0117c9d3e8')
    blob = openssl_aes256_cbc_encrypt(orden.encode('utf-8'),
                                      PASSPHRASE_AES.encode('utf-8'), salt)
    wbin(os.path.join(FILES, 'intranet', 'nucleo', 'ruido.enc'), blob)
    # copia descifrada para el corrector (el atacante la obtiene con openssl)
    assert openssl_aes256_cbc_decrypt(blob, PASSPHRASE_AES.encode('utf-8')).decode('utf-8') == orden
    write(os.path.join(FILES, 'intranet', 'nucleo', 'orden.txt'), orden, text=True)

    json = dict(p=p, q=q, n=n, e=e, d=d, c=c, b64s=b64s, frags=frags)
    write(os.path.join(BUILD_SRC, 'meta_artefactos.txt'),
          'p=%d\nq=%d\nn=%d\ne=%d\nd=%d\nc=%d\ne=%d\n' % (p, q, n, e, d, c, e) +
          ''.join('b%d=%s\n' % (i + 1, b) for i, b in enumerate(b64s)) +
          'orden=%s\n' % ORDEN_FINAL)
    return json


def build_zip():
    import pyzipper
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from exif_inject import inject_exif_bytes
    base = FILES
    src_img = os.path.join(BUILD_SRC, 'bandera_original.jpg')
    out = os.path.join(base, 'intranet', 'archivo', 'evidencias', 'bandera_nodo.zip')
    if not os.path.exists(src_img):
        raise SystemExit('falta la imagen bandera_original.jpg en build_sources/')
    b64s = frase_nucleo()[1]
    bandera_bytes = open(src_img, 'rb').read()
    # F4 via EXIF (no re-codificar)
    bandera_bytes = inject_exif_bytes(bandera_bytes, {
        'ImageDescription': 'NucleoRojo{%s}' % b64s[3],
        'Software': 'NucleoCore/1.0',
        'Make': 'Skynet Dynamics',
        'Model': 'Arco-Nodo',
    })
    pista4 = (
        'PISTA_4 :: dentro del ARCA\n'
        '\n'
        'La persona correcta te abrio el ARCA. El archivo que ves es una\n'
        'BANDERA: un fragmento nucleo mas.\n'
        'FRAGMENTO_4=NucleoRojo{%s}\n'
        '\n'
        'Para el ultimo paso recuerda el camino clasico de escalada:\n'
        '  sudo -l; si el visor de texto corre como root, genera una shell.\n'
        '  (vi/vim :!/bin/bash paga la deuda)\n'
    ) % b64s[3]
    if os.path.exists(out):
        os.remove(out)
    with pyzipper.AESZipFile(out, 'w', compression=pyzipper.ZIP_DEFLATED,
                             encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(b'John Connor')
        zf.writestr('bandera.jpg', bandera_bytes)
        zf.writestr('pista4.txt', pista4.encode('utf-8'))
    return out


def build_pcap():
    """Genera un pcap con la sesion HTTP de la intranet (GET de la imagen)."""
    import socket
    out = os.path.join(FILES, 'intranet', 'archivo', 'pcap', 'red_skynet.pcap')
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # trama Ethernet II + IPv4 + TCP
    def eth(frame_type, src_mac, dst_mac):
        src = bytes.fromhex(src_mac.replace(':', ''))
        dst = bytes.fromhex(dst_mac.replace(':', ''))
        return dst + src + struct.pack('>H', frame_type)

    def ipv4(src, dst, proto, payload):
        version_ihl = 0x45
        tos = 0
        total = 20 + len(payload)
        ident = 0x1234
        flags_frag = 0x4000
        ttl = 64
        s = socket.inet_aton(src)
        d = socket.inet_aton(dst)
        hdr = struct.pack('>BBHHHBBH4s4s', version_ihl, tos, total, ident,
                          flags_frag, ttl, proto, 0, s, d)
        chk = ip_checksum(hdr)
        hdr = hdr[:10] + struct.pack('>H', chk) + hdr[12:]
        return hdr + payload

    def ip_checksum(h):
        if len(h) % 2:
            h += b'\x00'
        s = 0
        for i in range(0, len(h), 2):
            s += (h[i] << 8) | h[i + 1]
        s = (s & 0xFFFF) + (s >> 16)
        s = (s & 0xFFFF) + (s >> 16)
        return (~s) & 0xFFFF

    def tcp(src_p, dst_p, seq, ack, flags, payload, ip_src, ip_dst):
        off = 5
        ns = 0
        win = 65535
        hdr = struct.pack('>HHIIBBHHH', src_p, dst_p, seq, ack, (off << 4) | ns,
                          flags, win, 0, 0)
        chk = tcp_checksum(ip_src, ip_dst, hdr + payload)
        hdr = hdr[:16] + struct.pack('>H', chk) + hdr[18:]
        return hdr + payload

    def tcp_checksum(src, dst, data):
        tcp_len = len(data)
        if len(data) % 2:
            data += b'\x00'
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) | data[i + 1]
        s += (socket.inet_aton(src)[0] << 8) | socket.inet_aton(src)[1]
        s += (socket.inet_aton(src)[2] << 8) | socket.inet_aton(src)[3]
        s += (socket.inet_aton(dst)[0] << 8) | socket.inet_aton(dst)[1]
        s += (socket.inet_aton(dst)[2] << 8) | socket.inet_aton(dst)[3]
        s += 6  # TCP
        s += tcp_len
        s = (s & 0xFFFF) + (s >> 16)
        s = (s & 0xFFFF) + (s >> 16)
        return (~s) & 0xFFFF

    def pcap_recycle():
        pass

    global src_ip, dst_ip
    src_ip = '10.10.10.25'   # analista interno (victima == intranet)
    dst_ip = '10.10.10.7'    # servidor intranet

    req = (b'GET /archivo/evidencias/captura_terminador.jpg HTTP/1.1\r\n'
           b'Host: intranet.skynet.local\r\n'
           b'User-Agent: Mozilla/5.0\r\n'
           b'Connection: close\r\n\r\n')

    # Secuencia de paquetes: 3-WHS + request + ACK + response(headers) + FIN
    packets = []
    mac_c = '00:0c:29:ab:01:25'
    mac_s = '00:0c:29:cd:11:07'

    def seg(frm, srcp, dstp, seq, ack, flags, payload):
        if frm == 'c':
            ip_src, ip_dst = src_ip, dst_ip
        else:
            ip_src, ip_dst = dst_ip, src_ip
        part = tcp(srcp, dstp, seq, ack, flags, payload, ip_src, ip_dst)
        if frm == 'c':
            return (eth(0x0800, mac_c, mac_s) + ipv4(src_ip, dst_ip, 6, part))
        return (eth(0x0800, mac_s, mac_c) + ipv4(dst_ip, src_ip, 6, part))

    # 3-way handshake
    packets.append(seg('c', 45123, 80, 1000, 0, 0x02, b''))          # SYN
    packets.append(seg('s', 80, 45123, 4000, 1001, 0x12, b''))       # SYN+ACK
    packets.append(seg('c', 45123, 80, 1001, 4001, 0x10, b''))       # ACK
    # GET
    packets.append(seg('c', 45123, 80, 1001, 4001, 0x18, req))
    packets.append(seg('s', 80, 45123, 4001, 1001 + len(req), 0x10, b''))
    # respuesta HTTP (headers)
    resp_body = (b'HTTP/1.1 200 OK\r\nCache-Control: private\r\n'
                 b'Content-Type: image/jpeg\r\nX-Skynet-Nodo: 7\r\n\r\n')
    packets.append(seg('s', 80, 45123, 4001, 1001 + len(req), 0x18, resp_body))
    packets.append(seg('c', 45123, 80, 1001 + len(req), 4001 + len(resp_body), 0x10, b''))
    # cierre
    packets.append(seg('c', 45123, 80, 1001 + len(req), 4001 + len(resp_body), 0x11, b''))
    packets.append(seg('s', 80, 45123, 4001 + len(resp_body), 1002 + len(req), 0x11, b''))
    packets.append(seg('c', 45123, 80, 1002 + len(req), 4002 + len(resp_body), 0x10, b''))

    with open(out, 'wb') as f:
        f.write(struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        ts = 1651182800.0
        for i, fr in enumerate(packets):
            ts_sec = int(ts)
            tsu = int((ts - ts_sec) * 1000000)
            f.write(struct.pack('<IIII', ts_sec, tsu, len(fr), len(fr)))
            f.write(fr)
            ts += 0.0001 * (i + 1)
    return out


# ---------------------------------------------------------------------------
def main():
    print('[*] generando criptografia M3 ...')
    meta = build_crypto()
    print('[+] RSA n=%d (d=%d)' % (meta['n'], meta['d']))
    print('[*] generando zip cifrado (bandera_nodo.zip) ...')
    build_zip()
    print('[*] generando pcap de la intranet ...')
    build_pcap()
    print('[*] hecho.')


if __name__ == '__main__':
    main()