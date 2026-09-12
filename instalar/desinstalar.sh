#!/usr/bin/env bash
# Desinstala Control Horario. Los datos se conservan salvo --borrar-datos:
# el art. 34.9 ET obliga a guardar los registros cuatro años.
set -euo pipefail

DESTINO="${HOME}/.local/share/controlhorario-app"
BIN="${HOME}/.local/bin/controlhorario"
BORRAR_DATOS=0
[ "${1:-}" = "--borrar-datos" ] && BORRAR_DATOS=1

if [ "$(uname -s)" = "Darwin" ]; then
    DATOS="${HOME}/Library/Application Support/ControlHorario"
else
    DATOS="${XDG_DATA_HOME:-$HOME/.local/share}/controlhorario"
fi

echo
echo "  Desinstalar Control Horario"
echo

rm -f "$BIN" && echo "    Lanzador eliminado."
rm -rf "${HOME}/Applications/Control Horario.app"
rm -f "${HOME}/.local/share/applications/controlhorario.desktop"
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/controlhorario.desktop"
AGENTE_MAC="${HOME}/Library/LaunchAgents/com.pharmajava.controlhorario.plist"
if [ -f "$AGENTE_MAC" ]; then
    launchctl unload "$AGENTE_MAC" 2>/dev/null || true
    rm -f "$AGENTE_MAC"
fi
rm -f "${HOME}/.local/share/icons/hicolor/256x256/apps/controlhorario.png"
for escritorio in "${HOME}/Escritorio" "${HOME}/Desktop"; do
    rm -f "${escritorio}/controlhorario.desktop"
done
echo "    Accesos directos y arranque automático eliminados."

rm -rf "$DESTINO" && echo "    Programa eliminado."

if [ "$BORRAR_DATOS" = "1" ]; then
    echo
    echo "    ATENCION: vas a borrar los registros de jornada."
    echo "    El art. 34.9 ET obliga a conservarlos cuatro años."
    read -r -p "    Escribe BORRAR para confirmar: " respuesta
    if [ "$respuesta" = "BORRAR" ]; then
        rm -rf "$DATOS"
        echo "    Datos eliminados."
    else
        echo "    Cancelado: los datos se conservan."
    fi
else
    echo
    echo "    Los datos siguen en: $DATOS"
    echo "    (registros de jornada, clave de cifrado y copias)"
fi
echo
echo "  Desinstalación terminada."
echo
