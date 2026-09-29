# CYBERQUEST :: Entrega del Organizador (clave de corrección)

> Material protegido. Solo el jurado. NO distribuir a los concursantes.

## Respuestas oficiales

| Flag | Valor |
|---|---|
| F1 | `NucleoRojo{TEEgUkVTSVNU}` |
| F2 | `NucleoRojo{RU5DSUEgVEk}` |
| F3 | `NucleoRojo{RU5FIE1VQ0hP}` |
| F4 | `NucleoRojo{UyBST1NUUk9T}` |
| F5 | `NucleoRojo{XzAxMTA}` |

- **ADN (concat.)**: `LA RESISTENCIA TIENE MUCHOS ROSTROS_0110`
- **ORDEN**: `El ataque es a las 4:00`
- **Proceso demo**: `sudo /root/nucleo/nucleo.sh` en la víctima → 5 flags +
  ORDEN → *NUCLEO VERIFICADO CON EXITO*.

## Cadena M3 (solución oficial)

1. `python3 tools/rsa_tool.py llave_privada.txt nucleo.conf nucleo.conf.enc`
   → `S3kiRa-07`
2. `openssl enc -d -aes-256-cbc -pbkdf2 -k 'S3kiRa-07' -in ruido.enc`
   → orden.txt (FRAGMENTO_3, doble base64 `Uld3...`, CESAR).
3. `From Base64` ×2 → `El ataque es a las 4:00`.

## Comandos de verificación rápida (en el host organizador)

```bash
python tools/test_end_to_end.py            # valida la cadena completa
python tools/build_artifacts.py            # regenera M3 (si se modifica algo)
```

## Checklist de despliegue

- [ ] Ubuntu Server limpio (sin interfaz gráfica).
- [ ] `sudo bash 00-install/install_cyberquest.sh`.
- [ ] Comprobar: web en :80, ssh dyson_m/Cyberdyne, `sudo -l` muestra vim.
- [ ] Confirmar `AllowUsers dyson_m` bloquea a los señuelos.
- [ ] Ejecutar `nucleo.sh` con las 5 flags → éxito.
- [ ] Quitar `00-install/` y `tools/` del alcance de los concursantes.

## Máquina virtual entregada (OVA)

Artefacto: **`Skynet-CYBERQUEST-Nodo07.ova`** (raíz del repo, ~594 MB).

- Imagen: Ubuntu Server 24.04.5 LTS (cloud image), autoinstalada y provista por
  `make_cidata.py` + `install_cyberquest.sh`. Servicios ya desplegados y probados.
- **Red**: host-only, estática `10.10.10.7/24` (gw `10.10.10.1`).
  El netplan persistente es `/etc/netplan/99-cyberquest.yaml`. Se necesita un
  host-only 10.10.10.x en el equipo donde se importe.
- **SSH**: `dyson_m` / `Cyberdyne` (único usuario permitido, `AllowUsers`).
- **Web**: `http://10.10.10.7/` (servicio `skynet-web`, usuario www-data con
  `CAP_NET_BIND_SERVICE`, puerto 80). Accesos del escenario en `/srv/intranet`.
- **Núcleo**: `/root/nucleo/` -> `nucleo.sh` (validador) + `FLAG5.txt`.
  Validación: `sudo /root/nucleo/nucleo.sh`.
- VM: 1 vCPU (la EFI de VirtualBox 7.2 falla con #GP si >1 vCPU en hosts con
  Hyper-V), 2048 MB RAM, firmware EFI, NIC host-only. Ajustar RAM/CPU al gusto
  del organizador si el anfitrión no tiene Hyper-V.
- cloud-init desactivado y usuario `ubuntu` eliminado; el arranque es directo.

Para **re-provisionar desde cero** (opcional): regenerar `tools/make_cidata.py`,
montar el ISO como CD y arrancar (provisión automática + `poweroff`).