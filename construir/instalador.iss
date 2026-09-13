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

{ ---------------------------------------------------------------------------
  Limpieza de la versión de 2024

  Aquella versión era un fichero control.py suelto, sin instalador: Windows no
  la tiene registrada y este instalador no puede desinstalarla. Lo único que la
  hace visible son los accesos directos que se crearan a mano, así que se
  buscan y se ofrece quitarlos para no acabar con dos programas en el menú.

  Nunca se toca la base de datos: los registros de 2024 hay que conservarlos
  cuatro años (art. 34.9 ET).
  --------------------------------------------------------------------------- }

function ApuntaAlProgramaViejo(const RutaEnlace: String): Boolean;
var
  Shell, Enlace: Variant;
  Destino: String;
begin
  Result := False;
  try
    Shell := CreateOleObject('WScript.Shell');
    Enlace := Shell.CreateShortcut(RutaEnlace);
    Destino := Lowercase(Enlace.TargetPath + ' ' + Enlace.Arguments);
    Result := Pos('control.py', Destino) > 0;
  except
    { Un acceso directo ilegible simplemente no cuenta. }
    Result := False;
  end;
end;

procedure BuscarAccesosViejos(const Carpeta: String; Lista: TStringList);
var
  Encontrado: TFindRec;
  Ruta: String;
begin
  if not DirExists(Carpeta) then
    Exit;
  if FindFirst(AddBackslash(Carpeta) + '*.lnk', Encontrado) then
  begin
    try
      repeat
        Ruta := AddBackslash(Carpeta) + Encontrado.Name;
        if ApuntaAlProgramaViejo(Ruta) then
          Lista.Add(Ruta);
      until not FindNext(Encontrado);
    finally
      FindClose(Encontrado);
    end;
  end;
end;

procedure RetirarVersionAntigua;
var
  Lista: TStringList;
  Detalle: String;
  i: Integer;
begin
  Lista := TStringList.Create;
  try
    try
      BuscarAccesosViejos(ExpandConstant('{userdesktop}'), Lista);
      BuscarAccesosViejos(ExpandConstant('{commondesktop}'), Lista);
      BuscarAccesosViejos(ExpandConstant('{userprograms}'), Lista);
      BuscarAccesosViejos(ExpandConstant('{commonprograms}'), Lista);
      BuscarAccesosViejos(ExpandConstant('{userstartup}'), Lista);
    except
      Exit;
    end;

    if Lista.Count = 0 then
      Exit;

    Detalle := '';
    for i := 0 to Lista.Count - 1 do
      Detalle := Detalle + '    ' + ExtractFileName(Lista[i]) + #13#10;

    if MsgBox(
      'Se han encontrado accesos directos a la versión anterior del programa:'
      + #13#10#13#10 + Detalle + #13#10 +
      '¿Quieres quitarlos para que sólo quede el programa nuevo?' + #13#10#13#10 +
      'Se borran únicamente los accesos directos. Ni el programa antiguo ni ' +
      'los registros de jornada se tocan.',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      for i := 0 to Lista.Count - 1 do
        DeleteFile(Lista[i]);
    end;
  finally
    Lista.Free;
  end;
end;

procedure AvisarDelHistorico;
var
  BaseAntigua: String;
begin
  BaseAntigua := ExpandConstant('{userappdata}\ControlHorario\time_tracker.db');
  if not FileExists(BaseAntigua) then
    Exit;

  MsgBox(
    'Se ha encontrado la base de datos de la versión anterior.' + #13#10#13#10 +
    'Al abrir el programa te ofrecerá importarla: acepta, y tus registros ' +
    'desde 2024 estarán todos dentro.' + #13#10#13#10 +
    'NO borres este fichero:' + #13#10 +
    BaseAntigua + #13#10#13#10 +
    'Es el registro original y la ley obliga a conservarlo cuatro años. El ' +
    'programa lo abre en modo sólo lectura y nunca lo modifica.',
    mbInformation, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    RetirarVersionAntigua;
    AvisarDelHistorico;
  end;
end;

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
