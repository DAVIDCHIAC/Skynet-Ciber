#!/bin/bash
# nucleo.sh :: validador final del nucleo "Luz y Sombras"
# Uso: sudo /root/nucleo/nucleo.sh
# Se alimenta de los 5 fragmentos NucleoRojo{...} hallados durante las misiones.

set -u

NUCLEO_EJECUTABLE="/root/nucleo/nucleo.sh"
EXPECTED_JOIN="0d7d21ff27a129716513b50e22223e74caab10fa8e58e682c635a9236c424113edf43dba64b11ec847939cbb85e39d170c6ad7d4826254085b9b9dbbd43161e3"
EXPECTED_ORD="40aa29d8e158a4b5aa6a1741836b603d6e5f4a88e0d3cd05495d4eca3dcb147904649aa8c09bb1fe29dc58559040071c530f28dd7ca06540a7c449df1585228d"
TOKEN="aRC4-D3l-4moR"

if [ "$(id -u)" != "0" ]; then
  echo "[-] esta utilidad requiere root. (sugerencia: sudo -l)"
  exit 1
fi

ayuda() {
  echo "=== NUCLEO ::: VALIDADOR ==="
  echo "Pega los 5 fragmentos con el formato NucleoRojo{...}, uno por linea:"
  echo "  1) F1 (EXIF de la captura)            2) F2 (robots.txt)"
  echo "  3) F3 (orden descifrada)              4) F4 (bandera.jpg en el ARCA)"
  echo "  5) F5 (FLAG5.txt)"
  echo "Despues indica la ORDEN NUCLEAR (la frase final del cifrado)."
}

declare -a FRAG=()
n=0
while [ $n -lt 5 ]; do
  printf '  Fragmento %d> ' $((n+1))
  read -r f
  f=$(echo "$f" | xargs)
  case "$f" in
    NucleoRojo\{*\})
      FRAG[$n]="${f#NucleoRojo\{}"
      FRAG[$n]="${FRAG[$n]%\}}"
      n=$((n+1)) ;;
    *) echo "[!] formato invalido, usa NucleoRojo{...}" ;;
  esac
done

printf '  ORDEN NUCLEAR> '
read -r ORDEN
ORDEN=$(echo "$ORDEN" | xargs)

DNA=""
for k in 0 1 2 3 4; do
  DNA="${DNA}$(echo -n "${FRAG[$k]}" | base64 -d 2>/dev/null)"
done

H_JOIN=$(printf '%s::%s' "$DNA" "$ORDEN" | sha512sum | awk '{print $1}')
H_ORD=$(printf '%s::%s' "$ORDEN" "$TOKEN" | sha512sum | awk '{print $1}')

echo
echo "-----------------------------------------------------------------"
echo " FRASE RECONSTRUIDA (ADN): $DNA"
echo " ORDEN INYECTADA        : $ORDEN"
echo "-----------------------------------------------------------------"

if [ "$H_JOIN" = "$EXPECTED_JOIN" ] && [ "$H_ORD" = "$EXPECTED_ORD" ]; then
  echo
  echo "   >>> NUCLEO VERIFICADO CON EXITO <<<"
  echo "   >>> LUZ PARA LA RESISTENCIA. ORDEN EJECUTADA: $ORDEN <<<"
  echo
  echo "   La Resistencia tiene muchos rostros_0110. Mision completada."
  echo
else
  echo
  echo "   [X] CHECKSUM NO COINCIDE: revisa el orden de los fragmentos"
  echo "       y/o la ORDEN NUCLEAR. La frase debe recuperarse entera."
  exit 1
fi