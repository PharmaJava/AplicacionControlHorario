; ---------------------------------------------------------------------------
;  Control Horario · instalador de Windows (Inno Setup)
;
;  Produce un único .exe que instala el programa completo: no hace falta que
;  el equipo de destino tenga Python ni nada más.
;
;  Se instala para el usuario actual (sin pedir permisos de administrador) y
;  los datos van a %APPDATA%\ControlHorario, aparte del programa, para que
;  actualizar o desinstalar no toque nunca los registros de jornada.
; ---------------------------------------------------------------------------

#ifndef MiVersion
  #define MiVersion "2026.1.0"
#endif
#ifndef MiOrigen
  #define MiOrigen "..\dist\ControlHorario"
#endif
#ifndef MiSalida
  #define MiSalida "..\dist"
#endif

#define MiNombre       "Control Horario"
#define MiEditor       "PharmaJava"
#define MiEjecutable   "ControlHorario.exe"

[Setup]
; El AppId identifica el programa entre versiones: no cambiarlo nunca, o
; Windows tratará una actualización como un programa distinto.
AppId={{8F3A1C42-7B9E-4D58-A6C1-2E5F9B0D7A34}
AppName={#MiNombre}
AppVersion={#MiVersion}
AppVerName={#MiNombre} {#MiVersion}
AppPublisher={#MiEditor}
DefaultDirName={autopf}\ControlHorario
DefaultGroupName={#MiNombre}
DisableProgramGroupPage=yes
DisableDirPage=auto
; "lowest" evita el aviso de administrador: se instala en la carpeta del
; usuario, que es donde puede escribir sin permisos especiales.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#MiSalida}
OutputBaseFilename=ControlHorario-Instalador-{#MiVersion}
SetupIconFile=..\recursos\icono.ico
UninstallDisplayIcon={app}\{#MiEjecutable}
UninstallDisplayName={#MiNombre}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
spanish.CrearAccesoEscritorio=Crear un acceso directo en el &Escritorio
spanish.ArranqueAutomatico=Abrir Control Horario al &encender el equipo
spanish.GrupoTerminal=Terminal de fichaje
spanish.DescripcionTerminal=Marca esta opción si este ordenador es donde ficha la plantilla.
spanish.AbrirPrograma=Abrir {#MiNombre}
spanish.DatosConservados=Los registros de jornada NO se borran al desinstalar.

[Tasks]
Name: "escritorio"; Description: "{cm:CrearAccesoEscritorio}"; \
    GroupDescription: "{cm:AdditionalIcons}"
Name: "arranque"; Description: "{cm:ArranqueAutomatico}"; \
    GroupDescription: "{cm:GrupoTerminal}"; Flags: unchecked

[Files]
; La carpeta que genera PyInstaller, con el .exe y todas sus dependencias.
Source: "{#MiOrigen}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\NORMATIVA.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\README.md";         DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MiNombre}";  Filename: "{app}\{#MiEjecutable}"
Name: "{autodesktop}\{#MiNombre}";   Filename: "{app}\{#MiEjecutable}"; \
    Tasks: escritorio
Name: "{userstartup}\{#MiNombre}";   Filename: "{app}\{#MiEjecutable}"; \
    Tasks: arranque

[Run]
Filename: "{app}\{#MiEjecutable}"; Description: "{cm:AbrirPrograma}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Sólo se borra lo que instalamos. La carpeta de datos de %APPDATA% queda
; intacta a propósito: el art. 34.9 del Estatuto de los Trabajadores obliga
; a conservar los registros cuatro años.
Type: filesandordirs; Name: "{app}\_internal"

[Code]
{ Avisa al desinstalar de que los datos se conservan y dónde están. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CarpetaDatos: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    CarpetaDatos := ExpandConstant('{userappdata}\ControlHorario');
    if DirExists(CarpetaDatos) then
      MsgBox(
        'Control Horario se ha desinstalado.' + #13#10#13#10 +
        'Los registros de jornada, la clave de cifrado y las copias de ' +
        'seguridad se conservan en:' + #13#10#13#10 +
        CarpetaDatos + #13#10#13#10 +
        'La ley obliga a guardarlos cuatro años, por eso no se borran. ' +
        'Si de verdad quieres eliminarlos, borra esa carpeta a mano.',
        mbInformation, MB_OK);
  end;
end;
