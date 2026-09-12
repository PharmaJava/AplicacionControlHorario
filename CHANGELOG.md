# Registro de cambios

## 2026.1.0 — septiembre de 2026

Reescritura completa a partir de la versión de 2024. Los datos se conservan:
al arrancar, el programa se ofrece a importar la base de datos anterior.

### Instalador .exe

- **Instalador único para Windows** (`ControlHorario-Instalador-*.exe`), hecho
  con PyInstaller e Inno Setup: instala el programa completo sin necesidad de
  Python en el equipo de destino, crea los accesos directos, ofrece el arranque
  automático y registra el desinstalador. Se instala en la carpeta del usuario,
  sin pedir permisos de administrador.
- **Versión portátil** (`ControlHorario-Portable-*.exe`), un único fichero que
  se ejecuta sin instalar nada.
- **Compilación automática en GitHub Actions**: cada etiqueta `v*` pasa las
  pruebas, compila, comprueba que el ejecutable arranca y publica los .exe como
  release descargable.
- **Corregido antes de empaquetar**: `arranque.py` calculaba las rutas desde
  `__file__`, que dentro de un .exe apunta a la carpeta temporal que PyInstaller
  crea y borra en cada ejecución. El acceso directo de arranque automático
  habría quedado apuntando a una carpeta inexistente. Ahora el nuevo módulo
  `empaquetado.py` distingue entre la carpeta de recursos y la del ejecutable.
- **Modo `--diagnostico`** en el ejecutable, que imprime rutas y dependencias
  para resolver incidencias sin estar delante del equipo, y registro del fallo
  en `error_arranque.log` si el programa no llega a abrir la ventana.
- La ventana ya tiene **icono propio**.

### Arranque automático

- Opción de **abrir el programa al encender el equipo**, pensada para el
  ordenador que hace de terminal de fichaje. Se activa desde el instalador o
  desde **Ajustes → Arranque**, y usa el mecanismo de usuario de cada sistema
  (carpeta Inicio en Windows, `~/.config/autostart` en Linux, agente de sesión
  en macOS): no requiere administrador y se quita desde la misma casilla.
- Opción de **abrir maximizado en la pantalla de Fichar**.

### Conservación de los datos ya existentes

- La base de datos de 2024 se abre **en modo sólo lectura** y no se modifica;
  además se guarda una copia intacta antes de importar.
- **La importación es idempotente**: se puede repetir sin duplicar fichajes, lo
  que importa ahora que se puede lanzar a mano y que el programa puede
  arrancar solo.
- **No mezcla personas**: la correspondencia entre el trabajador antiguo y el
  nuevo se guarda de forma explícita en lugar de deducirla del código, así que
  un `E001` dado de alta previamente no absorbe el histórico de otra persona.
- **Importación manual** desde Ajustes, indicando cuántos registros quedan por
  traer, con selector para bases de datos guardadas en otra carpeta.

### Cumplimiento normativo

- **Pausas y descansos** se registran como fichajes propios (`PAUSA_INICIO` /
  `PAUSA_FIN`), no como un hueco sin justificar.
- **Modalidad** presencial o teletrabajo en cada jornada.
- **Conservación de 4 años** (art. 34.9 ET): la purga está bloqueada antes del
  plazo, avisa cuando se acerca y queda auditada.
- **Acceso de la persona trabajadora** a su propio registro desde el terminal.
- **Expediente para la Inspección de Trabajo** en JSON, con la cadena de
  verificación de integridad.
- **Motor de reglas** con avisos citando el precepto: descanso entre jornadas
  (art. 34.3), descanso semanal (art. 37.1), pausas (art. 34.4), jornada diaria
  y semanal (art. 34.1 y 34.3), tope de horas extra (art. 35.2), con reglas
  reforzadas para menores de 18 años.
- **Límites configurables** por convenio y por trabajador.

### Integridad y trazabilidad

- Los fichajes pasan a ser un **libro de sólo anexado**: no se editan ni se
  borran. Los `UPDATE` y `DELETE` los bloquean *triggers* de SQLite.
- **Rectificaciones trazables**: corregir un fichaje anexa una corrección con
  autor, fecha y motivo; el original se conserva.
- **Cadena de hashes SHA-256** sobre fichajes y auditoría, verificable desde la
  propia aplicación: detecta modificaciones y borrados hechos por fuera.
- **Registro de auditoría** de todas las acciones administrativas.

### Seguridad

- **Corregido un fallo grave**: la clave de cifrado se regeneraba en cada
  arranque, así que el campo cifrado era irrecuperable y el nombre se guardaba
  además en claro. Ahora la clave persiste con permisos `0600` y los datos
  personales se cifran de verdad.
- **Corregido**: la contraseña de administración estaba escrita en el código
  fuente y publicada en el repositorio. Ahora se elige en la primera ejecución
  y se guarda como hash PBKDF2-SHA256 (600.000 iteraciones).
- **PIN personal por trabajador**: antes bastaba con teclear el ID ajeno para
  fichar por otra persona.
- Índice ciego (HMAC) para detectar DNI duplicados sin guardarlos en claro.
- La sesión de administración caduca a los 15 minutos de inactividad.

### Corrección de errores

- **Multiplataforma**: `os.getenv('APPDATA')` devolvía `None` fuera de Windows
  y el programa no arrancaba. Ahora resuelve la carpeta de datos en Windows,
  Linux y macOS.
- **Copias de seguridad consistentes** con la API de respaldo de SQLite. La
  versión anterior hacía `shutil.copy2` de la base abierta, lo que puede
  producir copias corruptas en modo WAL.
- **Fechas en ISO-8601 UTC** con desplazamiento horario. Antes se guardaban
  como texto `dd/mm/aaaa` y había que ordenarlas troceando la cadena.
- **Copia de seguridad al cerrar** desde el cierre de ventana, no desde
  `__del__`, cuya ejecución no está garantizada.
- La salida cierra automáticamente una pausa que se quedó abierta.
- Se rechazan los fichajes anteriores al último registrado.

### Interfaz

- Tema claro y oscuro, tipografía nativa de cada sistema y escalado según la
  densidad de la pantalla.
- Navegación lateral con seis pantallas: Fichar, Panel, Equipo, Registros,
  Informes y Ajustes.
- Terminal de fichaje con reloj, estado de la persona y vuelta automática a la
  pantalla de acceso.
- Panel con quién está trabajando, horas del día y avisos de cumplimiento.
- Tablas ordenables con filas alternas en lugar del cuadro de texto plano.

### Técnico

- Un solo fichero de 298 líneas → paquete de nueve módulos con
  responsabilidades separadas.
- **99 pruebas automáticas** (`pytest`).
- **Eliminada la dependencia de pandas**: los informes usan `openpyxl`
  directamente, lo que ahorra unos 60 MB de descarga en la instalación y
  permite dar formato al Excel.
- Instaladores de un clic para Windows, Linux y macOS, con acceso directo,
  desinstalador y registro en «Agregar o quitar programas».

## 2024 — versión inicial

Registro de entradas y salidas, incidencias, exportación a Excel y copia de
seguridad. Un único fichero `control.py`.
