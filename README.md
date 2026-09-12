<h1 align="center">
  <img src="recursos/icono_256.png" width="96" alt=""><br>
  Control Horario
</h1>

<p align="center">
  <b>Registro de jornada laboral para pequeñas empresas.</b><br>
  Conforme al artículo 34.9 del Estatuto de los Trabajadores · versión 2026.1.0
</p>

---

Aplicación de escritorio para registrar la jornada de la plantilla: fichajes de
entrada y salida, pausas, incidencias, informes para la Inspección de Trabajo y
avisos automáticos cuando algo se sale de la norma.

Funciona sin conexión, guarda los datos en el propio equipo y no envía nada a
ningún servidor.

## Instalación

### Windows

1. Descarga o clona este repositorio.
2. Entra en la carpeta `instalar`.
3. Doble clic en **`instalar.bat`**.

El instalador busca Python (y se ofrece a instalarlo si falta), prepara un
entorno propio con las dependencias, y crea el acceso directo en el
**Escritorio** y en el **menú Inicio**. No hace falta ser administrador.

Para desinstalar: `instalar\desinstalar.bat`, o desde «Agregar o quitar
programas». **Los registros de jornada no se borran**, porque la ley obliga a
conservarlos cuatro años.

### Linux y macOS

```bash
./instalar/instalar.sh
```

Crea la entrada en el menú de aplicaciones (Linux) o la app en
`~/Applications` (macOS), más la orden `controlhorario` en la terminal.

Desinstalar: `./instalar/desinstalar.sh`

### Requisitos

- Python 3.10 o superior, **con tkinter**
  (en Windows y macOS viene incluido; en Debian/Ubuntu: `sudo apt install python3-tk`)
- Dependencias, que instala el propio instalador: `cryptography` y `openpyxl`

## Primeros pasos

La primera vez el programa pide:

1. **Datos de la empresa** — aparecen en los informes que se entregan a la
   Inspección.
2. **Contraseña de administración** — protege todo lo que no sea fichar.
   Apúntala en un gestor de contraseñas; sin ella no se puede administrar.
3. **Importar el histórico** — si encuentra la base de datos de la versión
   anterior, se ofrece a traerla. Conviene aceptar: esos registros hay que
   conservarlos cuatro años.

Después, en **Equipo → Nuevo trabajador**, da de alta a cada persona. El
programa genera un **código** (`E001`, `E002`…) y un **PIN**: entrégaselos, son
los que necesita para fichar. El PIN no se puede volver a consultar, sólo
cambiar.

## Uso diario

| Pantalla | Para qué sirve |
|---|---|
| **Fichar** | El terminal. Cada persona entra con su código y su PIN y registra entrada, pausa o salida. |
| **Panel** | Quién está trabajando ahora, horas del día y avisos de cumplimiento. |
| **Equipo** | Altas, bajas, PIN, fichajes manuales y entrega del registro individual. |
| **Registros** | Jornadas de cada persona y rectificación de fichajes. |
| **Informes** | Excel para la empresa, CSV para la gestoría y expediente JSON para la Inspección. |
| **Ajustes** | Datos de empresa, límites de jornada, contraseña, copias e integridad. |

Deja el programa abierto en **Fichar**: es la pantalla pensada para un puesto
compartido, y vuelve sola a la pantalla de acceso unos segundos después de cada
fichaje.

### Corregir un fichaje

Los fichajes **no se editan ni se borran**. Para corregir uno, en
**Registros** marca «Ver fichajes sueltos», selecciona la hora equivocada y
pulsa **Rectificar**. Se anexa una corrección con tu nombre, la fecha y el
motivo, y el dato original se conserva. Es lo que permite justificar la
corrección si alguien la cuestiona.

## Dónde están los datos

| Sistema | Carpeta |
|---|---|
| Windows | `%APPDATA%\ControlHorario` |
| Linux | `~/.local/share/controlhorario` |
| macOS | `~/Library/Application Support/ControlHorario` |

Contiene:

- `controlhorario.db` — la base de datos
- `clave.key` — la clave de cifrado de los datos personales
- `copias/` — copias de seguridad automáticas (al cerrar, se guardan las 30 últimas)

> **Guarda `clave.key` junto con las copias.** Sin ella, los nombres y DNI de
> una copia restaurada quedan ilegibles.

Copiar esa carpeta a un disco externo o a la nube de la empresa es una copia de
seguridad completa y suficiente.

## Seguridad

- Nombres y DNI **cifrados** en la base de datos (Fernet / AES-128-CBC + HMAC).
- Contraseña de administración y PIN guardados como **hash PBKDF2-SHA256** con
  600.000 iteraciones. No se guardan en claro en ninguna parte.
- Fichajes **inmutables**: los `UPDATE` y `DELETE` los bloquea el propio motor
  de base de datos.
- **Cadena de hashes SHA-256** encadenados: cualquier manipulación externa
  rompe la cadena y se detecta desde **Ajustes → Verificar la integridad**.
- Registro de **auditoría** de todas las acciones administrativas.
- La sesión de administración **caduca a los 15 minutos** de inactividad.
- No se registra geolocalización ni datos biométricos.

## Normativa

El detalle de qué exige la ley, qué cubre el programa y qué está todavía en
tramitación está en **[docs/NORMATIVA.md](docs/NORMATIVA.md)**.

En resumen, a septiembre de 2026:

- Lo que obliga hoy es el **art. 34.9 ET** (Real Decreto-ley 8/2019). El
  programa lo cumple.
- El **real decreto de registro horario digital sigue sin aprobarse** (dictamen
  desfavorable del Consejo de Estado en marzo de 2026). El programa ya cumple
  sus requisitos técnicos salvo el acceso telemático directo de la Inspección,
  que no se puede implementar hasta que se defina.
- La **jornada de 37,5 horas no está en vigor**: siguen siendo 40 h de promedio
  anual. Si tu convenio aplica menos, cámbialo en Ajustes.

## Desarrollo

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt pytest
python -m controlhorario          # arrancar
python -m pytest tests/ -q        # 80 pruebas
```

Estructura:

```
controlhorario/
    config.py      rutas multiplataforma y ajustes
    seguridad.py   cifrado, contraseñas y PIN
    db.py          esquema, inmutabilidad y cadena de integridad
    dominio.py     trabajadores, fichajes y cálculo de jornadas
    normativa.py   reglas del Estatuto de los Trabajadores
    informes.py    Excel, CSV y expediente para la Inspección
    migracion.py   importación de la versión 2024
    ui/            interfaz (tema, componentes, diálogos, vistas)
```

## Licencia

Uso interno de PharmaJava.
