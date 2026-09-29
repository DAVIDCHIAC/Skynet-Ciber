#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_cidata.py -- Genera el dispositivo NoCloud (cidata.iso) para la
autoinstalacion de la maquina victima en VirtualBox.

El ISO contiene:
  /meta-data          -- identidad del nodo
  /user-data          -- #cloud-config: hostname, admin user, netplan
                         estatico 10.10.10.7, executa install_cyberquest.sh
                         y apaga la maquina al terminar.
  /cyberquest/...     -- payload completo de 00-install (files/ + installer)

Uso: python tools/make_cidata.py [destino.iso]
"""

import os
import shutil
import sys
import tempfile

import pycdlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INSTALL_DIR = os.path.join(ROOT, '00-install')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.expanduser('~'), 'VirtualBox VMs', 'Skynet-Nodo07', 'cidata.iso')

META_DATA = """instance-id: cyberquest-nodo07-d
local-hostname: intranet.skynet.local
"""

USER_DATA = """#cloud-config
hostname: intranet.skynet.local
preserve_hostname: false
ssh_pwauth: true
disable_root: false
locale: es_ES.UTF-8
timezone: America/Guayaquil
network:
  version: 2
  ethernets:
    nodo0:
      match:
        name: "en*"
      dhcp4: false
      addresses:
        - 10.10.10.7/24
      routes:
        - to: default
          via: 10.10.10.1
      nameservers:
        addresses:
          - 10.10.10.1
          - 8.8.8.8
runcmd:
  - mkdir -p /opt/cyberquest /mnt/cidata
  - mount -t iso9660 /dev/sr0 /mnt/cidata 2>/dev/null || true
  - cp -a /mnt/cidata/cyberquest/* /opt/cyberquest/ 2>/dev/null || true
  - chmod +x /opt/cyberquest/install_cyberquest.sh
  - bash /opt/cyberquest/install_cyberquest.sh
  - poweroff
"""


def stage_payload(tmp):
    """Copia 00-install (files/ + install_cyberquest.sh) a /cyberquest del ISO."""
    dst = os.path.join(tmp, 'cyberquest')
    shutil.copytree(INSTALL_DIR, dst, ignore=shutil.ignore_patterns('build_sources'))
    return dst


def build_iso(tmp):
    """Bucle principal de escritura del ISO (vol. label cidata, Rock Ridge)."""
    payload = os.path.join(tmp, 'cyberquest')
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=4, joliet=3, rock_ridge='1.09', vol_ident='cidata')

    def add_file(local, iso_path, jpath):
        import posixpath
        iso.add_file(local, iso_path,
                     rr_name=posixpath.basename(jpath),
                     joliet_path=jpath)

    def add_dir(iso_path, jpath):
        import posixpath
        iso.add_directory(iso_path,
                          rr_name=posixpath.basename(jpath.rstrip('/')),
                          joliet_path=jpath)

    add_file(os.path.join(tmp, 'meta-data'), '/META-DATA.;1', '/meta-data')
    add_file(os.path.join(tmp, 'user-data'), '/USER-DATA.;1', '/user-data')
    add_dir('/CYBERQUEST', '/cyberquest')

    for root, dirs, files in os.walk(payload):
        rel = os.path.relpath(root, tmp).replace(os.sep, '/')
        if rel != 'cyberquest':
            add_dir('/' + rel.upper(), '/' + rel)
        for name in files:
            local = os.path.join(root, name)
            add_file(local, '/' + rel.upper() + '/' + name, '/' + rel + '/' + name)
    iso.write(OUT)
    iso.close()
    print('[*] ISO escrito en %s' % OUT)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'meta-data'), 'wb') as f:
            f.write(META_DATA.encode())
        with open(os.path.join(tmp, 'user-data'), 'wb') as f:
            f.write(USER_DATA.encode())
        stage_payload(tmp)
        build_iso(tmp)
    print('[*] tamano %d bytes' % os.path.getsize(OUT))