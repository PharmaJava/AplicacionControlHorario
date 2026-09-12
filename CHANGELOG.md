# Registro de cambios

## 2026.1.0 — septiembre de 2026

Reescritura completa a partir de la versión de 2024. Los datos se conservan:
al arrancar, el programa se ofrece a importar la base de datos anterior.

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
- **80 pruebas automáticas** (`pytest`).
- **Eliminada la dependencia de pandas**: los informes usan `openpyxl`
  directamente, lo que ahorra unos 60 MB de descarga en la instalación y
  permite dar formato al Excel.
- Instaladores de un clic para Windows, Linux y macOS, con acceso directo,
  desinstalador y registro en «Agregar o quitar programas».

## 2024 — versión inicial

Registro de entradas y salidas, incidencias, exportación a Excel y copia de
seguridad. Un único fichero `control.py`.
