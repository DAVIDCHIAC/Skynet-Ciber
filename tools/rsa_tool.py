#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rsa_tool.py -- Descifrador RSA pedagogico del analista "OJODEDIOS".

Implementa el algoritmo completo sobre enteros (sin bibliotecas de
criptografia):
  1) Lee p, q y e de los ficheros del nodo.
  2) Calcula d = e^-1 mod phi(N) con el EUCLIDES EXTENDIDO.
  3) Recupera el mensaje con exponenciacion MODULAR RAPIDA: m = C^d mod n.

Uso:
    python3 rsa_tool.py [llave_privada.txt] [nucleo.conf] [nucleo.conf.enc]
"""

import sys


def eeuclides(a, b):
    """Euclides extendido: x,y con a*x + b*y = mcd(a,b)."""
    if b == 0:
        return a, 1, 0
    g, x1, y1 = eeuclides(b, a % b)
    return g, y1, x1 - (a // b) * y1


def inversa_mod(a, m):
    """a^-1 mod m (exige mcd(a,m)==1)."""
    g, x, _ = eeuclides(a, m)
    if g != 1:
        raise ValueError('sin inversa: mcd != 1')
    return x % m


def exp_mod(base, exp, m):
    """Exponenciacion modular binaria (rapida)."""
    r = 1 % m
    base = base % m
    while exp > 0:
        if exp & 1:
            r = (r * base) % m
        base = (base * base) % m
        exp >>= 1
    return r


def leer_clave(path):
    datos = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if '=' in linea and not linea.startswith('#'):
                    k, v = linea.split('=', 1)
                    datos[k.strip()] = v.strip()
    except OSError as e:
        sys.stderr.write('[!] no puedo leer %s: %s\n' % (path, e))
        sys.exit(1)
    return datos


def main(argv):
    if len(argv) < 4:
        sys.stderr.write('uso: python3 rsa_tool.py llave_privada.txt nucleo.conf nucleo.conf.enc\n')
        return 1
    priv = leer_clave(argv[1])
    pub = leer_clave(argv[2])
    cif = leer_clave(argv[3])
    p, q = int(priv['p']), int(priv['q'])
    e = int(pub.get('e', priv.get('e', 65537)))
    n = int(pub['n'])
    c = int(cif['C'])

    phi = (p - 1) * (q - 1)
    d = inversa_mod(e, phi)
    m = exp_mod(c, d, n)

    sys.stderr.write('[i] n=%d\n[i] phi=%d\n[i] d=%d\n' % (n, phi, d))
    msj = m.to_bytes((m.bit_length() + 7) // 8, 'big')
    try:
        sys.stdout.write(msj.decode('ascii') + '\n')
    except UnicodeDecodeError:
        sys.stdout.buffer.write(msj + b'\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))