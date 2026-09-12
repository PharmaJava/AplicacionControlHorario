<#
.SYNOPSIS
    Genera el instalador .exe de Control Horario. Ejecutar en Windows.

.DESCRIPTION
    Produce dos ficheros en la carpeta 'dist':

      ControlHorario-Instalador-<version>.exe   instalador completo
      ControlHorarioPortable.exe                versión portátil, sin instalar

    Requisitos:
      · Python 3.10 o superior con tkinter
      · Inno Setup 6 (para el instalador). Si no está, se genera sólo la
        versión portátil. Se instala con:  winget install JRSoftware.InnoSetup

    Normalmente no hace falta ejecutar esto a mano: cada etiqueta 'v*' del
    repositorio dispara la compilación en GitHub Actions y publica el .exe.

.EXAMPLE
    .\construir\construir.ps1
    .\construir\construir.ps1 -SoloPortable
#>

[CmdletBinding()]
param(
    [switch]$SoloPortable,
    [switch]$SinPruebas
)

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
Push-Location $Raiz

function Paso($n, $texto) { Write-Host ""; Write-Host "[$n/5] $texto" -ForegroundColor Cyan }
function Bien($texto) { Write-Host "    $texto" -ForegroundColor Green }
function Nota($texto) { Write-Host "    $texto" -ForegroundColor Gray }

try {
    Write-Host ""
    Write-Host "  Construir Control Horario para Windows" -ForegroundColor Blue

    # ---------------------------------------------------------------------- #
    Paso 1 'Preparando el entorno de compilación...'

    $Entorno = Join-Path $Raiz '.venv-construir'
    if (-not (Test-Path (Join-Path $Entorno 'Scripts\python.exe'))) {
        $python = (Get-Command py -ErrorAction SilentlyContinue) `
            ? 'py' : 'python'
        & $python -m venv $Entorno
    }
    $Py = Join-Path $Entorno 'Scripts\python.exe'
    & $Py -m pip install --upgrade pip --quiet --disable-pip-version-check
    & $Py -m pip install --quiet --disable-pip-version-check `
        -r requirements.txt pyinstaller pytest
    if ($LASTEXITCODE -ne 0) { throw 'No se han podido instalar las dependencias.' }
    Bien 'Entorno listo.'

    $Version = (Select-String -Path 'controlhorario\version.py' `
                -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
    Nota "Versión: $Version"

    # ---------------------------------------------------------------------- #
    Paso 2 'Pasando las pruebas...'
    if ($SinPruebas) {
        Nota 'Omitidas por -SinPruebas.'
    } else {
        & $Py -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw 'Hay pruebas que fallan. No se compila un ejecutable roto.'
        }
        Bien 'Todas las pruebas pasan.'
    }

    # ---------------------------------------------------------------------- #
    Paso 3 'Empaquetando el programa...'

    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
    $env:CH_RAIZ = $Raiz

    $env:CH_MODO = 'carpeta'
    & $Py -m PyInstaller --noconfirm --clean construir\controlhorario.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller ha fallado (versión en carpeta).' }
    Bien 'Programa empaquetado.'

    $env:CH_MODO = 'portable'
    & $Py -m PyInstaller --noconfirm --clean construir\controlhorario.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller ha fallado (versión portátil).' }
    Bien 'Versión portátil generada.'

    # ---------------------------------------------------------------------- #
    Paso 4 'Comprobando que el ejecutable arranca...'

    $Exe = Join-Path $Raiz 'dist\ControlHorario\ControlHorario.exe'
    if (-not (Test-Path $Exe)) { throw "No se ha generado $Exe" }
    $proceso = Start-Process -FilePath $Exe -PassThru
    Start-Sleep -Seconds 8
    if ($proceso.HasExited) {
        throw ("El ejecutable se ha cerrado solo (código $($proceso.ExitCode)). " +
               "Mira %APPDATA%\ControlHorario\error_arranque.log")
    }
    Stop-Process -Id $proceso.Id -Force
    Bien 'El ejecutable arranca correctamente.'

    # ---------------------------------------------------------------------- #
    Paso 5 'Creando el instalador...'

    if ($SoloPortable) {
        Nota 'Omitido por -SoloPortable.'
    } else {
        $iscc = Get-Command iscc -ErrorAction SilentlyContinue
        if (-not $iscc) {
            foreach ($ruta in @(
                "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                "${env:ProgramFiles}\Inno Setup 6\ISCC.exe")) {
                if (Test-Path $ruta) { $iscc = $ruta; break }
            }
        } else { $iscc = $iscc.Source }

        if (-not $iscc) {
            Write-Host "    Inno Setup no está instalado." -ForegroundColor Yellow
            Nota 'Instálalo con: winget install JRSoftware.InnoSetup'
            Nota 'De momento tienes la versión portátil en dist\.'
        } else {
            & $iscc "/DMiVersion=$Version" 'construir\instalador.iss'
            if ($LASTEXITCODE -ne 0) { throw 'Inno Setup ha fallado.' }
            Bien 'Instalador creado.'
        }
    }

    # ---------------------------------------------------------------------- #
    Write-Host ""
    Write-Host "  Listo" -ForegroundColor Green
    Write-Host ""
    Get-ChildItem dist\*.exe -ErrorAction SilentlyContinue | ForEach-Object {
        $mb = [math]::Round($_.Length / 1MB, 1)
        Write-Host ("    {0,-45} {1,6} MB" -f $_.Name, $mb)
    }
    Write-Host ""
}
finally {
    Pop-Location
}
