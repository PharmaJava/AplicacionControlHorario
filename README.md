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

### Windows (recomendado): un único .exe

**Enlace de descarga directa**, siempre la última versión estable:

```
https://github.com/PharmaJava/AplicacionControlHorario/releases/latest/download/ControlHorario-Instalador.exe
```

Ese enlace no caduca ni cambia al publicar una versión nueva, así que se puede
pasar tal cual a quien vaya a instalarlo.

> **El .exe no está en el código fuente.** Los ejecutables no se guardan en el
> repositorio: se compilan y se publican en [Releases](../../releases). En la
> carpeta `instalar/` sólo está el instalador *desde el código*, que es otra
> cosa y necesita Python.

| Descarga | Cuándo usarla |
|---|---|
| [Última versión estable](../../releases/latest) | Lo normal, y lo que se comparte |
| [Última compilación](../../releases/tag/ultima) | Lo más reciente, aún sin numerar |

Y dentro de cada una:

| Fichero | Para qué |
|---|---|
| `ControlHorario-Instalador.exe` | Instala el programa y crea el acceso directo |
| `ControlHorario-Portable.exe` | Se ejecuta sin instalar, para probarlo o llevarlo en un pendrive |

| Fichero | Para qué |
|---|---|
| **ControlHorario-Instalador-*.exe** | Lo normal. Instala el programa, crea el acceso directo y ofrece abrirlo al encender el equipo. |
| ControlHorario-Portable-*.exe | Sin instalar nada. Para probarlo o llevarlo en un pendrive. |

**No hace falta tener Python**: va todo dentro. Es un solo archivo, así que se
puede pasar por USB o por un enlace de descarga.

> **Windows mostrará un aviso.** El ejecutable no está firmado digitalmente,
> así que SmartScreen dirá *«Windows protegió su PC»*. Pulsa **Más información
> → Ejecutar de todas formas**. Es lo habitual en programas sin certificado de
> firma, que cuesta unos cientos de euros al año.
>
> Ten en cuenta también que **Gmail y Outlook bloquean los .exe adjuntos**:
> para enviarlo, usa un enlace de descarga o un ZIP.

Para desinstalar, desde «Agregar o quitar programas». **Los registros de
jornada no se borran**, porque la ley obliga a conservarlos cuatro años.

### Windows: desde el código fuente

Si prefieres no usar el .exe, en la carpeta `instalar` hay un `instalar.bat`
que monta el programa con el Python del equipo (y se ofrece a instalarlo si
falta).

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

### ¿Sustituye a la versión de 2024?

**Los datos sí; el programa antiguo no, porque nunca llegó a instalarse.**

La versión de 2024 se repartía como un fichero `control.py`, y de ahí se
generó un `.exe` con alguna herramienta del tipo *auto-py-to-exe* o
*PyInstaller*. Ésas producen un ejecutable suelto: **no crean entrada en
«Agregar o quitar programas»**, así que Windows no tiene la versión antigua
registrada y ningún instalador puede desinstalarla. Lo único que la hace
visible es el acceso directo que se creara a mano.

Al instalar la versión nueva:

| | |
|---|---|
| Tus registros de 2024 | Se conservan y se importan |
| `time_tracker.db` | Intacto, abierto sólo en lectura |
| El `.exe` o el `control.py` antiguos | Siguen donde estén; el instalador no los toca |
| Accesos directos antiguos | El instalador los detecta y **ofrece quitarlos** |

Así que no hace falta desinstalar nada antes: instala la versión nueva y, si
encuentra accesos directos a la antigua, te preguntará si los quita para que no
te queden dos programas en el menú.

Busca accesos directos que apunten a `control.py` o a un ejecutable cuyo
nombre empiece por «control», enseña la ruta completa de cada uno y sólo borra
si dices que sí. Deja en paz el Panel de control de Windows, que es
`System32\\control.exe` y encajaría en esa descripción.

Después te dice dónde ha quedado el ejecutable antiguo, porque **conviene
borrarlo a mano**: se generó a partir del código que llevaba la contraseña
escrita dentro, y de un `.exe` se puede extraer.

Si prefieres hacerlo todo a mano, basta con borrar el acceso directo viejo y el
ejecutable.

> **Nunca borres `%APPDATA%\ControlHorario\time_tracker.db`** ni los
> `backup_time_tracker_*.db` que hay junto a él. Son el registro original de
> 2024 y hay que conservarlos cuatro años.

Y un aviso práctico: mientras el programa viejo siga en el equipo, alguien
podría abrirlo por error y fichar ahí. Esos fichajes irían a la base antigua y
no aparecerían en la nueva hasta volver a importar (que se puede hacer las
veces que haga falta, sin duplicar nada). Por eso conviene quitar el acceso
directo antiguo cuanto antes.

### Actualizar de una versión a otra

De la 2026 en adelante no hay nada que hacer: se instala encima. El instalador
comparte identidad entre versiones, así que reemplaza la anterior en vez de
añadir una segunda entrada, y los datos ni se tocan.

### Actualizar desde la versión de 2024

La actualización **respeta la base de datos que ya estás usando**:

- La base antigua (`time_tracker.db`) se abre **en modo sólo lectura** y no se
  modifica nunca. Además se guarda una copia intacta en `copias/`.
- Los datos se importan a un fichero nuevo (`controlhorario.db`), así que el
  original sigue ahí por si hiciera falta volver atrás.
- La importación **se puede repetir sin duplicar nada**. Si el programa antiguo
  se sigue usando unos días en paralelo, vuelve a importar y sólo traerá lo
  nuevo.
- Si ya habías dado de alta gente a mano, los importados **no se mezclan** con
  ellos: se crean aparte aunque coincida el código.

Puedes lanzarla cuando quieras desde **Ajustes → Histórico de la versión
anterior**, que además indica cuántos registros quedan por traer. Si la base
antigua está en otro equipo o en una carpeta distinta, usa **Buscar otra base
de datos**.

> Los trabajadores importados **quedan sin PIN** y no pueden fichar hasta que
> se les asigne uno en **Equipo**. El Panel avisa de ello.

## Que se abra solo al encender el equipo

Si el ordenador es el terminal donde ficha la plantilla, conviene que el
programa esté abierto siempre. Hay dos formas:

- **Durante la instalación**: el instalador lo pregunta.
- **Después**: en **Ajustes → Arranque**, marca *«Iniciar Control Horario al
  encender el equipo»*.

Junto a esa opción está *«Abrir maximizado en la pantalla de Fichar»*, que deja
el equipo listo para fichar nada más arrancar.

Se configura sólo para el usuario actual, sin permisos de administrador:

| Sistema | Dónde queda |
|---|---|
| Windows | Carpeta Inicio (`shell:startup`) |
| Linux | `~/.config/autostart/controlhorario.desktop` |
| macOS | `~/Library/LaunchAgents/com.pharmajava.controlhorario.plist` |

Se quita desde la misma casilla, o borrando ese archivo.

## Instalarlo en otra empresa

Cada instalación es **completamente independiente**: su propia base de datos,
su propia clave de cifrado y sus propios datos de empresa. No hay servidor
central y nada sale del ordenador donde se instala, así que los datos de una
empresa no pueden llegar a otra ni a quien reparte el programa.

Lo que hay que hacer en cada equipo:

1. Descargar el instalador del enlace de arriba y hacer doble clic.
2. Aceptar el aviso de Windows (*Más información → Ejecutar de todas formas*).
3. Al abrirlo, rellenar razón social, CIF y centro de trabajo, y elegir una
   contraseña de administración **distinta en cada empresa**.
4. Dar de alta a la plantilla en **Equipo**. Cada persona recibe su código y su
   PIN.

Conviene decirle a cada empresa dos cosas:

- **Las copias de seguridad son suyas.** El programa las hace solo al cerrar,
  en su carpeta de datos, pero si se pierde el disco se pierden. Hay que
  llevarlas a otro soporte, y con ellas el fichero `clave.key`.
- **El registro es suyo y deben conservarlo cuatro años.** Quien responde ante
  la Inspección es la empresa, no quien le pasó el programa.

## Primeros pasos

La primera vez el programa pide:

1. **Datos de la empresa** — aparecen en los informes que se entregan a la
   Inspección.
2. **Contraseña de administración** — protege todo lo que no sea fichar.
   Mínimo 12 caracteres; a partir de 16 basta con mezclar mayúsculas y
   minúsculas, porque una frase larga protege más que un símbolo que luego
   nadie recuerda. Apúntala en un gestor de contraseñas: sin ella no se puede
   administrar.

   > No reutilices la contraseña de la versión de 2024: sigue siendo legible
   > en el historial público de este repositorio, así que hay que darla por
   > conocida.
3. **Importar el histórico** — si encuentra la base de datos de la versión
   anterior, se ofrece a traerla. Conviene aceptar: esos registros hay que
   conservarlos cuatro años.

Después, en **Equipo → Nuevo trabajador**, da de alta a cada persona. El
programa genera un **código** (`E001`, `E002`…) y un **PIN**: entrégaselos, son
los que necesita para fichar. El PIN no se puede volver a consultar, sólo
cambiar.

El PIN se puede cambiar por uno fácil de recordar, `1234` incluido: el programa
avisa de que es de los primeros que probaría cualquiera, pero deja decidir. Es
lo que sostiene que un fichaje sea de quien dice ser, así que conviene pensarlo
si en el mostrador hay gente de paso.

El campo **Rol** es sólo informativo: marcar a alguien como `ADMIN` no le da
acceso a nada. Lo que abre la gestión es la contraseña de administración.

> **Nombre en pantalla.** El rótulo del lateral y de la pantalla de fichar sale
> de la razón social. Si prefieres que ahí se lea el nombre corto —«Farmacia
> Ejemplo» en vez de «Farmacia Ejemplo S.L.»— escríbelo en *Ajustes → Datos de
> la empresa → Nombre para la pantalla*. Los informes de la Inspección siguen
> llevando la razón social completa, que es la que identifica legalmente a la
> empresa.

## Uso diario

| Pantalla | Para qué sirve |
|---|---|
| **Fichar** | El terminal. Cada persona entra con su código y su PIN y registra entrada, pausa o salida. Basta con teclear las primeras letras del nombre o del código: la lista propone el resto. |
| **Panel** | Quién está trabajando ahora, horas del día y avisos de cumplimiento. Con **doble clic** sobre alguien se registra su salida (pide la contraseña de administración y el fichaje queda marcado como hecho desde el panel). |
| **Equipo** | Altas, bajas, reactivaciones, PIN, fichajes manuales y entrega del registro individual. |
| **Registros** | Jornadas de cada persona y rectificación de fichajes. |
| **Informes** | Informe imprimible para la Inspección, Excel para la empresa, CSV para la gestoría y expediente JSON. |
| **Ajustes** | Datos de empresa, límites de jornada, arranque automático, importación del histórico, contraseña, copias e integridad. |

Deja el programa abierto en **Fichar**: es la pantalla pensada para un puesto
compartido, y vuelve sola a la pantalla de acceso unos segundos después de cada
fichaje.

### Acceder a la gestión

**Fichar** y **Panel** están siempre disponibles: cualquiera puede fichar sin
contraseña, que para eso está el terminal.

**Equipo, Registros, Informes y Ajustes** piden la contraseña de
administración. Se entra con el botón **Acceder a la gestión** de la esquina
inferior izquierda, y se sale con **Salir de la gestión**. Si te olvidas, se
cierra sola a los 15 minutos sin usarla: el equipo suele estar en una zona
común y no conviene dejar los datos del personal a la vista.

### Si tienes una inspección de trabajo

El camino corto, con el programa ya instalado:

1. **Ajustes → Datos de la empresa**: rellena razón social, CIF y centro de
   trabajo. Sin esto los informes no identifican a la empresa.
2. **Ajustes → Histórico**: importa la base de datos del programa anterior si
   aún no lo has hecho. Te dice cuántos registros quedan por traer.
3. **Informes → Informe para entregar a la Inspección → Generar**: eliges el
   periodo y se abre en el navegador. **Ctrl+P** para guardarlo en PDF o
   imprimirlo.

Ese documento lleva los datos de la empresa, las jornadas de cada persona con
sus totales, la verificación de integridad y un espacio para firma y sello.

Mira también el **Panel**: los avisos de cumplimiento señalan lo que la
Inspección suele mirar (descansos, jornadas sin cerrar, trabajadores sin PIN).

> **Importante y honesto**: los registros importados del programa anterior van
> marcados como tales en todos los informes. La verificación de integridad
> acredita que no se han modificado **desde que se importaron**, no desde 2024.
> Presentarlos como equivalentes a los fichados aquí sería inducir a error.
> Está explicado en [docs/NORMATIVA.md](docs/NORMATIVA.md#31-qué-no-acredita-la-verificación).

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
- Fichar por otra persona desde el **Panel** exige esa contraseña, y el fichaje
  queda con la procedencia «PANEL» y el autor que lo registró.
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

## Generar el .exe

**No hay que hacer nada**: GitHub lo compila solo. Hay dos descargas:

| Descarga | Cuándo se actualiza | Para qué |
|---|---|---|
| [**Última versión**](../../releases/tag/ultima) | Con cada cambio en `main` | Tener siempre lo más reciente |
| [Versiones numeradas](../../releases/latest) | Al publicar una etiqueta `v*` | Una versión fija que no se mueve |

Cada compilación pasa las pruebas, empaqueta, comprueba que el ejecutable
arranca de verdad y sube los dos .exe. Si algo falla, no se publica nada.

Para **publicar una versión numerada**: sube el número en
`controlhorario/version.py`, y luego en la web del repositorio ve a
**Releases → Draft a new release**, escribe la etiqueta (`v2026.2.0`), elige
*Create new tag on publish* y pulsa **Publish release**. También vale desde la
terminal:

```bash
git tag -a v2026.2.0 -m "Control Horario 2026.2.0"
git push origin v2026.2.0
```

Si un cambio no toca el programa (corregir el README, por ejemplo), pon
`[skip ci]` en el mensaje del commit y GitHub se saltará la compilación.

### Fusión automática

Cuando la compilación de una rama `claude/*` termina en verde, su pull request
se fusiona sola. Unas pruebas en rojo la frenan, así que nunca entra en `main`
algo que no compile o que rompa las pruebas.

El ciclo completo: empujar → compilar → probar → publicar el `.exe` → fusionar
la PR.

Si la rama tiene cambios y no hay ninguna PR abierta, la compilación avisa pero
no falla: el `.exe` se publica igual. Crear la PR desde el propio workflow
requiere activar **Settings → Actions → General → Allow GitHub Actions to
create and approve pull requests**, que viene desactivado; fusionar una que ya
existe no necesita nada.

Sólo alcanza a ramas de este mismo repositorio: empujar a `claude/*` exige
permiso de escritura, y las propuestas venidas de una bifurcación no disparan
ese paso.

Para desactivarlo, borra el trabajo `fusionar` del workflow.

También se puede lanzar a mano desde **Actions → Construir el .exe de Windows
→ Run workflow**.

Para compilarlo en tu propio equipo Windows:

```powershell
.\construir\construir.ps1
```

Necesita Python 3.10+ y, para el instalador, Inno Setup 6
(`winget install JRSoftware.InnoSetup`). Los .exe quedan en `dist\`.

> Un .exe de Windows sólo se puede compilar **en** Windows: PyInstaller no hace
> compilación cruzada. Por eso el workflow usa un runner de Windows.

### Diagnóstico

Si el programa no arranca en algún equipo, desde una ventana de comandos:

```
ControlHorario.exe --diagnostico
```

Imprime dónde está instalado, dónde guarda los datos y si le falta alguna
dependencia. Si falla al arrancar, además deja el detalle en
`%APPDATA%\ControlHorario\error_arranque.log`.

## Desarrollo

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt pytest
python -m controlhorario          # arrancar
python -m pytest tests/ -q        # 108 pruebas
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
    arranque.py    arranque automático con el sistema
    empaquetado.py rutas cuando corre como .exe
    ui/            interfaz (tema, componentes, diálogos, vistas)
```

## Autoría

Escrito y mantenido por **PharmaJava**.

Programa de uso propio: no hay licencia pública ni se aceptan contribuciones
externas.
