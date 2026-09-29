#!/bin/bash
# ============================================================
#  CYBERQUEST -- instalador del escenario "Skynet :: Nodo 07"
#  Maquina VICTIMA (Ubuntu Server, sin interfaz grafica)
#
#  Uso:      sudo bash install_cyberquest.sh
#  Tested:   Ubuntu Server 22.04/24.04 LTS
# ============================================================
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$INSTALL_DIR/files"
WEBROOT="/srv/intranet"
ZHOST="intranet.skynet.local"

# ---- pre-requisitos -----------------------------------------------------
if [ "$(id -u)" != "0" ]; then
  echo "[!] ejecutar como root (sudo)." >&2
  exit 1
fi

echo "[*] CYBERQUEST :: instalando nodo victima"
hostnamectl set-hostname "$ZHOST" || true

# ---- usuarios -----------------------------------------------------------
declare -A DECOYS
DECOYS[sarah_c]="investigacion civil"
DECOYS[kyle_r]="linea temporal 1"
DECOYS[john_c]="resistencia -- no desplegado"
DECOYS[derek_r]="operaciones especiales"
DECOYS[catherine_w]="prensa del nodo"
DECOYS[ross_h]="contabilidad"
DECOYS[james_c]="sistemas legacy"
DECOYS[trent_a]="becario ciberseguridad"

for u in "${!DECOYS[@]}"; do
  id "$u" >/dev/null 2>&1 || useradd -m -s /usr/sbin/nologin "$u"
done

if ! id dyson_m >/dev/null 2>&1; then
  useradd -m -s /bin/bash dyson_m
  echo "dyson_m:Cyberdyne" | chpasswd
else
  echo "dyson_m:Cyberdyne" | chpasswd
fi
usermod -aG sudo dyson_m

# eliminar señuelos de debajo del arbol webserver (nunca deben existir sueltos)
rm -rf "$WEBROOT"/archivo/evidencias/bandera_nodo

# ---- arbol de ficheros --------------------------------------------------
mkdir -p "$WEBROOT" /etc/ssh/sshd_config.d /root/nucleo /etc/netplan
cp -a "$TREE"/. /
mkdir -p "$WEBROOT"
cp -a "$TREE"/intranet/. "$WEBROOT"/
chmod 600 /etc/netplan/99-cyberquest.yaml 2>/dev/null || true
if command -v netplan >/dev/null 2>&1; then
  netplan generate >/dev/null 2>&1 || true
  netplan apply >/dev/null 2>&1 || true
fi

# --- cuentas de red (shadows) y passwords --------------------------------
for u in "${!DECOYS[@]}"; do
  chsh -s /usr/sbin/nologin "$u" 2>/dev/null || true
  # cada señuelo guarda un rastro falso (pista roja)
  mkdir -p "/home/$u/Documentos"
  printf 'simulacion de nodo %s :: datos cifrados, sin acceso por SSH\n' "${DECOYS[$u]}" > "/home/$u/Documentos/leeme.txt"
  chown -R "$u:$u" "/home/$u"
done

chown -R dyson_m:dyson_m /home/dyson_m
chown -R dyson_m:dyson_m /srv /var/www 2>/dev/null || true
chown -R root:root /root/nucleo
chmod 700 /root/nucleo
chmod +x /root/nucleo/nucleo.sh
chown root:root /etc/motd /etc/ssh/banner_cyberquest.txt
chown -R root:root /etc/ssh/sshd_config.d /etc/sudoers.d 2>/dev/null || true
chmod 440 /etc/sudoers.d/cyberquest

# ---- validar sudoers antes de instalarlo -------------------------------
if ! visudo -cf /etc/sudoers.d/cyberquest >/dev/null 2>&1; then
  echo "[!] sudoers invalido" >&2
  exit 1
fi
chmod 440 /etc/sudoers.d/cyberquest

# ---- sshd ---------------------------------------------------------------
if [ -d /etc/ssh/sshd_config.d ]; then
  if ! grep -q '^Include /etc/ssh/sshd_config.d/\*\.conf' /etc/ssh/sshd_config; then
    sed -i '1i Include /etc/ssh/sshd_config.d/*.conf' /etc/ssh/sshd_config
  fi
  systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
fi

# ---- webserver intranet (python3) ----------------------------------------
PORT=80
if command -v python3 >/dev/null 2>&1; then
  systemctl stop apache2 nginx 2>/dev/null || true
  cat > /etc/systemd/system/skynet-web.service <<'UNIT'
[Unit]
Description=Skynet intranet nodo 07
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m http.server 80 --bind 0.0.0.0 --directory /srv/intranet
Restart=always
User=www-data
Group=www-data
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now skynet-web.service
else
  echo "[!] python3 no encontrado; levanta el webserver manual en $WEBROOT"
fi

# ---- firewall ------------------------------------------------------------
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp >/dev/null 2>&1 || true
  ufw allow 80/tcp >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
fi

telemetry() {
  echo
  echo "  [OK] CYBERQUEST desplegado en el nodo:"
  echo "       WEB   http://$ZHOST/  (servida desde $WEBROOT)"
  echo "       SSH   dyson_m@$ZHOST  (password: Cyberdyne)"
  echo "       MOTD  $(hostname)"
}
telemetry