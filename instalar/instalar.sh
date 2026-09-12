#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Control Horario · instalación en Linux y macOS
#
#  Instalación de usuario, sin sudo:
#    · programa   →  ~/.local/share/controlhorario-app
#    · lanzador   →  ~/.local/bin/controlhorario
#    · icono      →  menú de aplicaciones (Linux) o ~/Applications (macOS)
#    · datos      →  ~/.local/share/controlhorario  (Linux)
#                    ~/Library/Application Support/ControlHorario  (macOS)
#
#  Los datos van aparte del programa: reinstalar nunca borra los registros.
# ---------------------------------------------------------------------------
set -euo pipefail

ORIGEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESTINO="${HOME}/.local/share/controlhorario-app"
BIN="${HOME}/.local/bin"
MIN_PYTHON="3.10"

azul()  { printf '\033[1;34m%s\033[0m\n' "$*"; }
verde() { printf '\033[0;32m%s\033[0m\n' "$*"; }
gris()  { printf '\033[0;90m%s\033[0m\n' "$*"; }
rojo()  { printf '\033[0;31m%s\033[0m\n' "$*"; }
paso()  { echo; azul "[$1/6] $2"; }

echo
azul "  ┌────────────────────────────────────────────┐"
azul "  │   Control Horario · Registro de jornada    │"
azul "  │   Instalación en este equipo               │"
azul "  └────────────────────────────────────────────┘"

# --------------------------------------------------------------------------- #
paso 1 "Buscando Python..."

PYTHON=""
for candidato in python3.13 python3.12 python3.11 python3.10 python3; do
    ruta="$(command -v "$candidato" 2>/dev/null || true)"
    [ -n "$ruta" ] || continue
    if ! "$ruta" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
        continue
    fi
    if ! "$ruta" -c "import tkinter" 2>/dev/null; then
        gris "    $candidato no tiene tkinter; se descarta."
        continue
    fi
    PYTHON="$ruta"
    break
done

if [ -z "$PYTHON" ]; then
    rojo "  No se ha encontrado Python ${MIN_PYTHON}+ con soporte gráfico (tkinter)."
    echo
    gris "  Instálalo con:"
    gris "    Debian/Ubuntu : sudo apt install python3 python3-venv python3-tk"
    gris "    Fedora        : sudo dnf install python3 python3-tkinter"
    gris "    Arch          : sudo pacman -S python tk"
    gris "    macOS         : brew install python-tk"
    echo
    exit 1
fi
verde "    $($PYTHON --version) en $PYTHON"

# --------------------------------------------------------------------------- #
paso 2 "Copiando el programa a $DESTINO ..."

rm -rf "${DESTINO}/controlhorario" "${DESTINO}/recursos"
mkdir -p "$DESTINO"
cp -r "${ORIGEN}/controlhorario" "$DESTINO/"
cp -r "${ORIGEN}/recursos" "$DESTINO/"
cp "${ORIGEN}/requirements.txt" "$DESTINO/"
[ -f "${ORIGEN}/README.md" ] && cp "${ORIGEN}/README.md" "$DESTINO/"
cp "${ORIGEN}/instalar/desinstalar.sh" "$DESTINO/"
chmod +x "${DESTINO}/desinstalar.sh"
verde "    Archivos copiados."

# --------------------------------------------------------------------------- #
paso 3 "Preparando el entorno y las dependencias..."

ENTORNO="${DESTINO}/entorno"
if [ ! -x "${ENTORNO}/bin/python" ]; then
    "$PYTHON" -m venv "$ENTORNO"
fi
"${ENTORNO}/bin/python" -m pip install --upgrade pip --quiet --disable-pip-version-check
"${ENTORNO}/bin/python" -m pip install --quiet --disable-pip-version-check \
    -r "${DESTINO}/requirements.txt"
verde "    Dependencias instaladas."

# --------------------------------------------------------------------------- #
paso 4 "Creando el lanzador..."

mkdir -p "$BIN"
cat > "${BIN}/controlhorario" << LANZADOR
#!/usr/bin/env bash
# Lanzador de Control Horario (generado por el instalador).
cd "${DESTINO}"
exec "${ENTORNO}/bin/python" -m controlhorario "\$@"
LANZADOR
chmod +x "${BIN}/controlhorario"
verde "    Lanzador en ${BIN}/controlhorario"

case ":${PATH}:" in
    *":${BIN}:"*) ;;
    *) gris "    Aviso: ${BIN} no está en el PATH. Añádelo a tu ~/.bashrc:"
       gris "           export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# --------------------------------------------------------------------------- #
paso 5 "Creando el acceso directo..."

if [ "$(uname -s)" = "Darwin" ]; then
    APP="${HOME}/Applications/Control Horario.app"
    mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"
    cat > "${APP}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>               <string>Control Horario</string>
    <key>CFBundleDisplayName</key>        <string>Control Horario</string>
    <key>CFBundleIdentifier</key>         <string>com.pharmajava.controlhorario</string>
    <key>CFBundleExecutable</key>         <string>ControlHorario</string>
    <key>CFBundleIconFile</key>           <string>icono</string>
    <key>CFBundlePackageType</key>        <string>APPL</string>
    <key>NSHighResolutionCapable</key>    <true/>
</dict>
</plist>
PLIST
    cat > "${APP}/Contents/MacOS/ControlHorario" << ARRANQUE
#!/usr/bin/env bash
cd "${DESTINO}"
exec "${ENTORNO}/bin/python" -m controlhorario
ARRANQUE
    chmod +x "${APP}/Contents/MacOS/ControlHorario"
    if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
        JUEGO="$(mktemp -d)/icono.iconset"; mkdir -p "$JUEGO"
        for t in 16 32 64 128 256 512; do
            sips -z $t $t "${DESTINO}/recursos/icono.png" \
                 --out "${JUEGO}/icon_${t}x${t}.png" >/dev/null 2>&1 || true
        done
        iconutil -c icns "$JUEGO" -o "${APP}/Contents/Resources/icono.icns" 2>/dev/null || true
    fi
    verde "    Aplicación creada en ${APP}"
    gris  "    Aparece en el Launchpad y en la carpeta Aplicaciones."
else
    ICONOS="${HOME}/.local/share/icons/hicolor/256x256/apps"
    mkdir -p "$ICONOS"
    cp "${DESTINO}/recursos/icono_256.png" "${ICONOS}/controlhorario.png"

    APLICACIONES="${HOME}/.local/share/applications"
    mkdir -p "$APLICACIONES"
    cat > "${APLICACIONES}/controlhorario.desktop" << ACCESO
[Desktop Entry]
Type=Application
Version=1.0
Name=Control Horario
GenericName=Registro de jornada
Comment=Registro de jornada laboral conforme al art. 34.9 del Estatuto de los Trabajadores
Exec=${BIN}/controlhorario
Icon=controlhorario
Terminal=false
Categories=Office;ProjectManagement;
Keywords=fichar;jornada;horario;trabajo;registro;
StartupNotify=true
StartupWMClass=controlhorario
ACCESO
    chmod +x "${APLICACIONES}/controlhorario.desktop"

    # Acceso también en el escritorio, si existe
    for escritorio in "${HOME}/Escritorio" "${HOME}/Desktop"; do
        if [ -d "$escritorio" ]; then
            cp "${APLICACIONES}/controlhorario.desktop" "${escritorio}/"
            chmod +x "${escritorio}/controlhorario.desktop"
            gtk-launch --version >/dev/null 2>&1 && \
                gio set "${escritorio}/controlhorario.desktop" \
                    metadata::trusted true 2>/dev/null || true
            verde "    Acceso directo en ${escritorio}"
        fi
    done

    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database "$APLICACIONES" 2>/dev/null || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
    verde "    Entrada creada en el menú de aplicaciones."
fi

# --------------------------------------------------------------------------- #
paso 6 "Arranque automático..."

if [ "$(uname -s)" = "Darwin" ]; then
    AUTO="${HOME}/Library/LaunchAgents/com.pharmajava.controlhorario.plist"
else
    AUTO="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/controlhorario.desktop"
fi

QUIERE_ARRANQUE=0
if [ "${CONTROLHORARIO_ARRANQUE:-}" = "1" ]; then
    QUIERE_ARRANQUE=1
elif [ "${CONTROLHORARIO_ARRANQUE:-}" = "0" ]; then
    QUIERE_ARRANQUE=0
elif [ -t 0 ]; then
    gris "    Si este equipo es el terminal donde ficha la plantilla,"
    gris "    conviene que el programa se abra solo al iniciar sesión."
    printf '    ¿Abrir Control Horario al iniciar sesión? (s/N) '
    read -r respuesta
    case "$respuesta" in [SsYy]*) QUIERE_ARRANQUE=1 ;; esac
fi

if [ "$QUIERE_ARRANQUE" = "1" ]; then
    mkdir -p "$(dirname "$AUTO")"
    if [ "$(uname -s)" = "Darwin" ]; then
        cat > "$AUTO" << AGENTE
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pharmajava.controlhorario</string>
    <key>ProgramArguments</key>
    <array>
        <string>${ENTORNO}/bin/python</string>
        <string>-m</string>
        <string>controlhorario</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${DESTINO}</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
AGENTE
        launchctl load "$AUTO" 2>/dev/null || true
    else
        cat > "$AUTO" << ARRANQUE
[Desktop Entry]
Type=Application
Version=1.0
Name=Control Horario
Comment=Registro de jornada laboral
Exec=${BIN}/controlhorario
Path=${DESTINO}
Icon=controlhorario
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
ARRANQUE
        chmod +x "$AUTO"
    fi
    verde "    Se abrirá automáticamente al iniciar sesión."
    gris  "    Para quitarlo: Ajustes → Arranque, o borra $AUTO"
else
    rm -f "$AUTO"
    gris "    Sin arranque automático (se puede activar en Ajustes → Arranque)."
fi

VERSION="$(grep -oP '__version__\s*=\s*"\K[^"]+' "${DESTINO}/controlhorario/version.py")"
echo
verde "  ✔ Instalación terminada"
echo
gris "    Programa : ${DESTINO}"
gris "    Versión  : ${VERSION}"
gris "    Orden    : controlhorario"
echo
echo "    Ábrelo desde el menú de aplicaciones o escribiendo 'controlhorario'."
gris "    La primera vez te pedirá los datos de la empresa y una contraseña"
gris "    de administración, y te ofrecerá importar el histórico anterior."
echo
