<#
.SYNOPSIS
    Instala Control Horario en este equipo y crea los accesos directos.

.DESCRIPTION
    Instalación de usuario, sin permisos de administrador:

      1. Busca Python 3.10 o superior (y ofrece instalarlo si no está).
      2. Copia el programa a  %LOCALAPPDATA%\Programs\ControlHorario
      3. Crea un entorno virtual propio e instala las dependencias, para no
         tocar el Python del sistema ni chocar con otros programas.
      4. Crea el acceso directo en el Escritorio y en el menú Inicio.
      5. Registra la aplicación en «Agregar o quitar programas».

    Los datos (base de datos, clave de cifrado y copias) NO se guardan aquí,
    sino en %APPDATA%\ControlHorario, de modo que reinstalar o actualizar el
    programa nunca borra los registros de jornada.
#>

[CmdletBinding()]
param(
    [switch]$SinAccesoDirecto,
    [switch]$ArranqueAutomatico,
    [switch]$SinArranqueAutomatico,
    [switch]$Silencioso
)

$ErrorActionPreference = 'Stop'
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$NombreApp   = 'Control Horario'
$IdApp       = 'ControlHorario'
$Origen      = Split-Path -Parent $PSScriptRoot
$Destino     = Join-Path $env:LOCALAPPDATA "Programs\$IdApp"
$CarpetaDatos = Join-Path $env:APPDATA $IdApp
$MinPython   = [version]'3.10'

function Escribir($texto, $color = 'Gray') { Write-Host $texto -ForegroundColor $color }
function Paso($n, $texto) { Write-Host ""; Write-Host "[$n/6] $texto" -ForegroundColor Cyan }

Write-Host ""
Write-Host "  ┌────────────────────────────────────────────┐" -ForegroundColor Blue
Write-Host "  │   Control Horario · Registro de jornada    │" -ForegroundColor Blue
Write-Host "  │   Instalación en este equipo               │" -ForegroundColor Blue
Write-Host "  └────────────────────────────────────────────┘" -ForegroundColor Blue

# --------------------------------------------------------------------------- #
# 1. Python
# --------------------------------------------------------------------------- #
Paso 1 'Buscando Python...'

function Buscar-Python {
    $candidatos = @()
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($v in @('-3.13', '-3.12', '-3.11', '-3.10', '-3')) {
            try {
                $ruta = & py $v -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $ruta) { $candidatos += $ruta.Trim() }
            } catch { }
        }
    }
    foreach ($nombre in @('python', 'python3')) {
        $cmd = Get-Command $nombre -ErrorAction SilentlyContinue
        if ($cmd) { $candidatos += $cmd.Source }
    }
    foreach ($ruta in ($candidatos | Select-Object -Unique)) {
        # El "python" de la Microsoft Store es un lanzador falso de 0 bytes.
        if (-not (Test-Path $ruta) -or (Get-Item $ruta).Length -eq 0) { continue }
        try {
            $v = & $ruta -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$v -ge $MinPython) {
                $tk = & $ruta -c "import tkinter" 2>&1
                if ($LASTEXITCODE -ne 0) {
                    Escribir "    Python $v encontrado pero sin tkinter; se descarta." 'DarkYellow'
                    continue
                }
                return @{ Ruta = $ruta; Version = $v }
            }
        } catch { }
    }
    return $null
}

$python = Buscar-Python

if (-not $python) {
    Escribir "    No se ha encontrado Python $MinPython o superior con soporte gráfico." 'Yellow'
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    $instalar = $false
    if ($winget) {
        if ($Silencioso) {
            $instalar = $true
        } else {
            Write-Host ""
            $r = Read-Host '    ¿Quieres que lo instale ahora con winget? (S/N)'
            $instalar = $r -match '^[SsYy]'
        }
    }
    if ($instalar) {
        Escribir '    Instalando Python 3.12 (puede tardar unos minutos)...' 'Gray'
        winget install --id Python.Python.3.12 --scope user --silent `
               --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
                    [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $python = Buscar-Python
    }
    if (-not $python) {
        Write-Host ""
        Escribir '  No se puede continuar sin Python.' 'Red'
        Escribir '  Descárgalo de https://www.python.org/downloads/' 'Red'
        Escribir '  IMPORTANTE: marca «Add python.exe to PATH» y deja activada' 'Red'
        Escribir '  la opción «tcl/tk and IDLE» durante la instalación.' 'Red'
        Write-Host ""
        if (-not $Silencioso) { Read-Host 'Pulsa Intro para salir' }
        exit 1
    }
}
Escribir "    Python $($python.Version) en $($python.Ruta)" 'Green'

# --------------------------------------------------------------------------- #
# 2. Copiar el programa
# --------------------------------------------------------------------------- #
Paso 2 "Copiando el programa a $Destino ..."

if (Test-Path $Destino) {
    # Actualización: se borra sólo el código, nunca la carpeta de datos.
    foreach ($resto in @('controlhorario', 'recursos')) {
        $ruta = Join-Path $Destino $resto
        if (Test-Path $ruta) { Remove-Item $ruta -Recurse -Force }
    }
}
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

Copy-Item (Join-Path $Origen 'controlhorario') $Destino -Recurse -Force
Copy-Item (Join-Path $Origen 'recursos') $Destino -Recurse -Force
foreach ($fichero in @('requirements.txt', 'README.md', 'LICENSE')) {
    $ruta = Join-Path $Origen $fichero
    if (Test-Path $ruta) { Copy-Item $ruta $Destino -Force }
}
Copy-Item (Join-Path $PSScriptRoot 'desinstalar.ps1') $Destino -Force
Copy-Item (Join-Path $PSScriptRoot 'desinstalar.bat') $Destino -Force
Escribir '    Archivos copiados.' 'Green'

# --------------------------------------------------------------------------- #
# 3. Entorno virtual y dependencias
# --------------------------------------------------------------------------- #
Paso 3 'Preparando el entorno y las dependencias...'

$Entorno   = Join-Path $Destino 'entorno'
$PythonW   = Join-Path $Entorno 'Scripts\pythonw.exe'
$PythonExe = Join-Path $Entorno 'Scripts\python.exe'

if (-not (Test-Path $PythonExe)) {
    & $python.Ruta -m venv $Entorno
    if ($LASTEXITCODE -ne 0) { throw 'No se ha podido crear el entorno virtual.' }
}

& $PythonExe -m pip install --upgrade pip --quiet --disable-pip-version-check
& $PythonExe -m pip install --quiet --disable-pip-version-check `
    -r (Join-Path $Destino 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    throw 'No se han podido instalar las dependencias. ¿Hay conexión a Internet?'
}

# La comprobación se hace desde la carpeta de instalación: el paquete
# 'controlhorario' se importa desde ahí, no está en site-packages.
Push-Location $Destino
try {
    & $PythonExe -c "import controlhorario, cryptography, openpyxl, tkinter" 2>&1 | Out-Null
    $comprobacion = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($comprobacion -ne 0) {
    throw 'La instalación ha terminado pero el programa no se puede importar. Revisa los mensajes anteriores.'
}
Escribir '    Dependencias instaladas y comprobadas.' 'Green'

# --------------------------------------------------------------------------- #
# 4. Lanzador
# --------------------------------------------------------------------------- #
Paso 4 'Creando el lanzador...'

$Lanzador = Join-Path $Destino 'ControlHorario.cmd'
@"
@echo off
rem Lanzador de Control Horario. No lo muevas de sitio.
cd /d "%~dp0"
start "" "%~dp0entorno\Scripts\pythonw.exe" -m controlhorario %*
"@ | Set-Content -Path $Lanzador -Encoding ASCII

$Icono = Join-Path $Destino 'recursos\icono.ico'
Escribir '    Lanzador creado.' 'Green'

# --------------------------------------------------------------------------- #
# 5. Accesos directos
# --------------------------------------------------------------------------- #
Paso 5 'Creando los accesos directos...'

function Nuevo-AccesoDirecto($ruta, $descripcion) {
    $shell = New-Object -ComObject WScript.Shell
    $enlace = $shell.CreateShortcut($ruta)
    $enlace.TargetPath       = $PythonW
    $enlace.Arguments        = '-m controlhorario'
    $enlace.WorkingDirectory = $Destino
    $enlace.IconLocation     = "$Icono,0"
    $enlace.Description      = $descripcion
    $enlace.WindowStyle      = 1
    $enlace.Save()
}

if (-not $SinAccesoDirecto) {
    $escritorio = [Environment]::GetFolderPath('Desktop')
    Nuevo-AccesoDirecto (Join-Path $escritorio "$NombreApp.lnk") `
        'Registro de jornada laboral'
    Escribir "    Acceso directo en el Escritorio." 'Green'

    $inicio = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
    Nuevo-AccesoDirecto (Join-Path $inicio "$NombreApp.lnk") `
        'Registro de jornada laboral'
    Escribir "    Acceso directo en el menú Inicio." 'Green'
}

# Arranque automático al iniciar sesión. Se usa la carpeta Inicio del usuario:
# no requiere administrador y se quita con sólo borrar el acceso directo.
$CarpetaInicio = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
$EnlaceInicio  = Join-Path $CarpetaInicio "$NombreApp.lnk"

$quiereArranque = $false
if ($ArranqueAutomatico) {
    $quiereArranque = $true
} elseif (-not $SinArranqueAutomatico -and -not $Silencioso) {
    Write-Host ""
    Escribir '    Si este equipo es el terminal donde ficha la plantilla,' 'Gray'
    Escribir '    conviene que el programa se abra solo al encender.' 'Gray'
    $r = Read-Host '    ¿Abrir Control Horario al iniciar Windows? (S/N)'
    $quiereArranque = $r -match '^[SsYy]'
}

if ($quiereArranque) {
    Nuevo-AccesoDirecto $EnlaceInicio 'Registro de jornada laboral (inicio automático)'
    Escribir '    Se abrirá automáticamente al iniciar sesión.' 'Green'
} elseif (Test-Path $EnlaceInicio) {
    Remove-Item $EnlaceInicio -Force
    Escribir '    Arranque automático desactivado.' 'Gray'
}

# --------------------------------------------------------------------------- #
# 6. Registro de desinstalación
# --------------------------------------------------------------------------- #
Paso 6 'Registrando la aplicación...'

$clave = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$IdApp"
New-Item -Path $clave -Force | Out-Null
$version = (Select-String -Path (Join-Path $Destino 'controlhorario\version.py') `
            -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$propiedades = @{
    DisplayName     = $NombreApp
    DisplayVersion  = $version
    Publisher       = 'PharmaJava'
    InstallLocation = $Destino
    DisplayIcon     = $Icono
    UninstallString = "powershell -ExecutionPolicy Bypass -File `"$Destino\desinstalar.ps1`""
    NoModify        = 1
    NoRepair        = 1
}
foreach ($k in $propiedades.Keys) {
    New-ItemProperty -Path $clave -Name $k -Value $propiedades[$k] -Force | Out-Null
}
Escribir '    Registrada en «Agregar o quitar programas».' 'Green'

# --------------------------------------------------------------------------- #
Write-Host ""
Write-Host "  ✔ Instalación terminada" -ForegroundColor Green
Write-Host ""
Escribir "    Programa : $Destino"
Escribir "    Datos    : $CarpetaDatos"
Escribir "    Versión  : $version"
Write-Host ""
Escribir '    Abre «Control Horario» desde el Escritorio.' 'White'
if ($quiereArranque) {
    Escribir '    A partir del próximo encendido se abrirá solo.' 'Gray'
}
Escribir '    La primera vez te pedirá los datos de la empresa y una' 'Gray'
Escribir '    contraseña de administración, y te ofrecerá importar el' 'Gray'
Escribir '    histórico de la versión anterior si lo encuentra.' 'Gray'
Write-Host ""

if (-not $Silencioso) {
    $r = Read-Host '  ¿Abrir el programa ahora? (S/N)'
    if ($r -match '^[SsYy]') { Start-Process -FilePath $PythonW -ArgumentList '-m', 'controlhorario' -WorkingDirectory $Destino }
}
