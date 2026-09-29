# ARQUITECTURA RED TEAM :: Skynet — Nodo 07

> Documento técnico de la infraestructura del escenario (organizadores y
> Blue Team).

## 1. Visión general

| Capa | Componente | Notas |
|---|---|---|
| Ataque | Kali Linux (2026.x) | estación del participante |
| Víctima | Ubuntu Server 22.04/24.04 (CLI) | `intranet.skynet.local` · 10.10.10.7 |
| Red | LAN aislada (VirtualBox/VMware, host-only) | sin salida a Internet garantizada |
| Web | `python3 -m http.server 80` → `/srv/intranet` | intranet Skynet |
| SSH | OpenSSH · `AllowUsers dyson_m` · banner | único acceso remoto `dyson_m` |
| Señuelos | 8 cuentas `/usr/sbin/nologin` | desvío táctico (pistas rojas) |

## 2. Catálogo de banderas

```
F1 → EXIF captura_terminador.jpg   NucleoRojo{TEEgUkVTSVNU}
F2 → robots.txt                    NucleoRojo{RU5DSUEgVEk}
F3 → orden.txt (ruta crypto)       NucleoRojo{RU5FIE1VQ0hP}
F4 → EXIF bandera.jpg (ZIP AES)    NucleoRojo{UyBST1NUUk9T}
F5 → FLAG5.txt (root)              NucleoRojo{XzAxMTA}
```

- **ADN**: `LA RESISTENCIA TIENE MUCHOS ROSTROS_0110`
- **ORDEN**: `El ataque es a las 4:00`
- El validador `/root/nucleo/nucleo.sh` exige los 5 fragmentos en orden +
  la ORDEN y comprueba dos SHA-512 (JOIN y ORD, token `aRC4-D3l-4moR`).

## 3. Firmas de los artefactos

| Artefacto | Algoritmo | Parámetros |
|---|---|---|
| `nucleo.conf` / `.enc` (`C`) | RSA 512 | e=65537 · mensaje `S3kiRa-07` |
| `ruido.enc` | AES-256-CBC OpenSSL | `-pbkdf2` SHA-256 · 10000 iter |
| `orden.txt` (plano) | doble Base64 + ROT13 | ORDEN oculta + FRAGMENTO_3 |
| `bandera_nodo.zip` | AES-256 (WZ_AES, pyzipper) | password `John Connor` |
| `red_skynet.pcap` | PCAP clásico, 10 tramas | GET de la imagen + HEAD; checksums OK |
| `captura_terminador.jpg` | JSteg/DCT-LSB (AC) | payload 267 B + EXIF APP1 (F1) |

## 4. Esteganografía DCT (detalle)

- Coeficientes AC cuantizados, paridad LSB = bit del mensaje; zonas
  {-1,0,1} no se tocan (evita artefactos). Tablas Huffman K.1 del JPEG
  estándar (EOB/ZRL + AC run/cat). CAPACIDAD ~222 Kb.
- Extractor del atacante: `tools/resistance_steg.py` (solo stdlib).
- Explicación técnica en `tools/dctsteg.py` (embed/extract, límite de
  zona elegible, byte-stuffing `0xFF 0x00` en extract).

## 5. Cadena criptográfica M3 (recorrido del atacante)

```
nucleo.conf + nucleo.conf.enc + llave_privada.txt
   ├─ rsa_tool (Euclides extendido)  ->  S3kiRa-07
   └─ openssl enc -d -aes-256-cbc -pbkdf2 -k 'S3kiRa-07' -in ruido.enc
        -> orden.txt  (FRAGMENTO_3 + doble base64 + ROT13)
        -> From Base64 x2 (CyberChef) -> 'El ataque es a las 4:00'
```

## 6. Superficie de ataque y mitigaciones sugeridas

| Hallazgo | Corrección |
|---|---|
| Llave RSA en home accesible | separar secrets; nunca en home |
| Comentarios HTML con credenciales | sanitizar el sitio; prohibir secretos |
| `NOPASSWD` en `vim`/`vi` | restringir a `sudoedit` o pasar a `visudo` con comandos fijos |
| Salt/AES predecible (dev) | parametrizar salt por fichero + rotación |
| palabras del sitio = diccionario | política de contraseñas + MFA + `fail2ban` |

## 7. Puntajes y badges (tournament)

- Puntos de la tabla `RedTeam_AfterAction.md` (§6) · máximo ~5000.
- **Badges**: `root_admin` (escalada), `arconero` (ZIP), `ruptor_de_ruido`
  (AES), `eclosion` (DCT), `destructor_de_nucleo` (validador completo).
- La ORDEN correcta confirma la **ROJO /** victoria final de dominio.