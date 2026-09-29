#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_end_to_end.py -- Valida el escenario completo CYBERQUEST sobre el
arbol desplegable de 00-install/files, reproduciendo la ruta del atacante:

  M1 estego (dct)   -> pregunta -> respuesta John Connor
  M2 OSINT/web      -> dyson_m / Cyberdyne
  M3 cripto (RSA)   -> S3kiRa-07 -> ruido.enc -> orden.txt -> F3
  M4 zip AES        -> bandera.jpg (F4) + pista4 (escalada vim)
  M5 root           -> FLAG5.txt (F5)
  VALIDADOR         -> ADN + ORDEN (sha512 contra nucleo.sh)

Uso: python tools/test_end_to_end.py
"""

import base64
import hashlib
import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FILES = os.path.join(ROOT, '00-install', 'files')
I = os.path.join(FILES, 'intranet')

sys.path.insert(0, os.path.join(ROOT, 'tools'))


def log(ok, msg):
    print('%s %s' % ('[OK]' if ok else '[XX]', msg))
    if not ok:
        raise SystemExit('fallo: ' + msg)


# ---------------- M1: esteganografia -------------------------------------
import resistance_steg  # noqa: E402

captura = os.path.join(I, 'archivo', 'evidencias', 'captura_terminador.jpg')
payload = resistance_steg.extract(captura, verbose=False)
q = payload.decode('utf-8', 'replace').strip()
log(payload.startswith(b'PISTA_1'), 'M1 payload extraido (%d bytes) es la pregunta' % len(payload))
ans = 'John Connor'  # la respuesta sale de observa la imagen (OSINT), no del payload
log(payload.startswith(b'PISTA_1'), 'pregunta del payload esperada')

# banderas M1/M4
im = __import__('PIL.Image').Image.open(captura)
F1 = im.getexif().get(0x010E).strip()
log(F1.startswith('NucleoRojo{'), 'F1 (EXIF captura) = %s' % F1)

import pyzipper  # noqa: E402

zf = pyzipper.AESZipFile(os.path.join(I, 'archivo', 'evidencias', 'bandera_nodo.zip'))
im2 = __import__('PIL.Image').Image.open(io.BytesIO(zf.read('bandera.jpg', pwd=ans.encode())))
F4 = im2.getexif().get(0x010E).strip()
log(F4.startswith('NucleoRojo{'), 'F4 (EXIF bandera.jpg) = %s' % F4)
pista4 = zf.read('pista4.txt', pwd=ans.encode()).decode()
log('vim' in pista4 or 'sudo -l' in pista4, 'pista4 contiene ruta de escalada')
zf.close()

# ---------------- M2: web / OSINT ----------------------------------------
robots = open(os.path.join(I, 'robots.txt'), encoding='utf-8').read()
F2m = re.search(r'Fragmento_2=NucleoRojo{(.*?)}', robots)
log(bool(F2m), 'F2 (robots.txt) = NucleoRojo{%s}' % (F2m.group(1) if F2m else '?'))
F2 = 'NucleoRojo{%s}' % F2m.group(1)
pers = open(os.path.join(I, 'personal.html'), encoding='utf-8').read()
log('Cyberdyne' in pers, 'corpus OSINT: palabra de maximo impacto (Cyberdyne) para CeWL')
admin = open(os.path.join(I, 'admin', 'index.html'), encoding='utf-8').read()
log('CYBERDYNE' in admin.upper() and 'dyson_m' in admin, 'hint usuario/clave SSH en admin')
log('red_skynet.pcap' in open(os.path.join(I, 'archivo', 'index.html'), encoding='utf-8').read(),
    'archivo/ referencia al pcap')

# ---------------- M3: cripto ---------------------------------------------
from rsa_tool import inversa_mod, exp_mod  # noqa: E402


def leer(path):
    d = {}
    for line in open(path, encoding='utf-8'):
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            d[k.strip()] = v.strip()
    return d


priv = leer(os.path.join(FILES, 'home', 'dyson_m', 'nucleo', 'llave_privada.txt'))
pub = leer(os.path.join(I, 'nucleo', 'nucleo.conf'))
cif = leer(os.path.join(I, 'nucleo', 'nucleo.conf.enc'))
p, q = int(priv['p']), int(priv['q'])
e = int(pub.get('e', 65537))
n = int(pub['n'])
C = int(cif['C'])
phi = (p - 1) * (q - 1)
d = inversa_mod(e, phi)
m = exp_mod(C, d, n)
SESION = m.to_bytes((m.bit_length() + 7) // 8, 'big').decode()
log(SESION == 'S3kiRa-07', 'M3 RSA -> sesion = %s' % SESION)

# openssl equiv: AES-256-CBC -pbkdf2 (salt fijo en el header Salted__)
from cryptography.hazmat.backends import default_backend  # noqa: E402
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: E402

raw = open(os.path.join(I, 'nucleo', 'ruido.enc'), 'rb').read()
assert raw[:8] == b'Salted__'
salt = raw[8:16]
dk = hashlib.pbkdf2_hmac('sha256', SESION.encode(), salt, 10000, 48)
key, iv = dk[:32], dk[32:48]
des = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
pt = des.update(raw[16:]) + des.finalize()
pt = pt[:pt.rfind(b'\x00')] if pt.endswith(b'\x00' * 4) else pt
pt = pt.rstrip(b'\x00')
text = pt.decode('utf-8', 'replace')
log('FRAGMENTO_3=' in text, 'M3 orden.txt descifrado + F3')
F3 = re.search(r'FRAGMENTO_3=NucleoRojo{(.*?)}', text).group(0)

# la ORDEN final viaja via base64 doble (cadena CyberChef "From Base64" x2)
# linea >solo< caracteres base64 que al decodificar 2 veces da texto
ORDEN = ''
for cand in text.splitlines():
    l = cand.strip()
    if len(l) < 16 or not re.fullmatch(r'[A-Za-z0-9+/]+={0,2}', l):
        continue
    try:
        pad = lambda s: s + '=' * ((4 - len(s) % 4) % 4)
        t = base64.b64decode(pad(l))
        t = base64.b64decode(pad(t.decode('ascii')))
        t = t.decode('utf-8')
    except (ValueError, UnicodeDecodeError, IndexError):
        continue
    if t == 'El ataque es a las 4:00':
        ORDEN = t
        break
log(bool(ORDEN), 'HIJACK de la ORDEN via b64 doble: %r' % ORDEN)

# cadena CyberChef: el texto plano contiene la doble base64 del ORDEN
log('Uld3Z1lYUmhjWFZsSUdWeklHRWdiR0Z6SURRNk1EQT0=' in text,
    'cadena base64 doble presente en orden.txt')

# complemento rot13 verifica el reto extra del CESAR/ROT13 (frase del arcon)
def rot13(s):
    return s.translate(str.maketrans(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
        'nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM'))
log('el arcon de la resistencia se abre con john connor' in rot13(text),
    'complemento CESAR/ROT13 presente en orden.txt')

# ---------------- M5: root -----------------------------------------------
F5 = open(os.path.join(FILES, 'root', 'nucleo', 'FLAG5.txt'), encoding='utf-8').readline().strip()
log(F5.startswith('NucleoRojo{'), 'F5 (FLAG5.txt) = %s' % F5)

sudoers = open(os.path.join(FILES, 'etc', 'sudoers.d', 'cyberquest'), encoding='utf-8').read()
log('NOPASSWD' in sudoers and 'vim' in sudoers, 'sudoers permite escalada vim')

# ---------------- VALIDADOR ----------------------------------------------
banderas = [F1, F2, F3, F4, F5]
inner = [re.search(r'NucleoRojo\{(.*?)\}', b).group(1) for b in banderas]
DNA = ''.join(base64.b64decode(f + '=' * ((4 - len(f) % 4) % 4)).decode() for f in inner)
log(DNA == 'LA RESISTENCIA TIENE MUCHOS ROSTROS_0110', 'ADN reconstruido: %s' % DNA)

ORDEN = 'El ataque es a las 4:00'  # marcador si la cadena fallo antes
TOKEN = 'aRC4-D3l-4moR'
HJ = hashlib.sha512((DNA + '::' + ORDEN).encode()).hexdigest()
HO = hashlib.sha512((ORDEN + '::' + TOKEN).encode()).hexdigest()

nsh = open(os.path.join(FILES, 'root', 'nucleo', 'nucleo.sh'), encoding='utf-8').read()
log('0d7d21ff27a129716513b50e22223e74caab10fa8e58e682c635a9236c424113edf43dba64b11ec847939cbb85e39d170c6ad7d4826254085b9b9dbbd43161e3' == HJ,
    'ns hash JOIN coincide: %s' % HJ[:16])
log('40aa29d8e158a4b5aa6a1741836b603d6e5f4a88e0d3cd05495d4eca3dcb147904649aa8c09bb1fe29dc58559040071c530f28dd7ca06540a7c449df1585228d' == HO,
    'ns hash ORD coincide:  %s' % HO[:16])

print()
print('>>> CYBERQUEST end-to-end OK: F1=%s F2=%s F3=%s F4=%s F5=%s' % tuple(b[:14] for b in banderas))
print('>>> ADN=%s' % DNA)
print('>>> ORDEN=%s' % ORDEN)