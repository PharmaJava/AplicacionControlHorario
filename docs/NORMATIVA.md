# Normativa aplicable al registro de jornada

**Fecha de esta revisión: septiembre de 2026.**

Este documento explica en qué se apoya cada decisión del programa. No es
asesoramiento jurídico: antes de cambiar la organización del trabajo,
consúltalo con tu asesoría laboral y con el convenio colectivo aplicable.

---

## 1. Lo que está en vigor hoy

Conviene decirlo claro, porque hay mucha confusión comercial al respecto:

> **En septiembre de 2026 la norma que obliga al registro de jornada sigue
> siendo el artículo 34.9 del Estatuto de los Trabajadores, en la redacción
> que le dio el Real Decreto-ley 8/2019, de 8 de marzo.** No hay ninguna
> norma nueva de registro horario publicada en el BOE.

### 1.1 La obligación básica

El **art. 34.9 ET** exige a la empresa:

| Obligación | Cómo la cumple este programa |
|---|---|
| Registro **diario** de jornada | Cada fichaje es un evento con fecha y hora |
| **Hora concreta de inicio y fin** de cada persona | Eventos `ENTRADA` y `SALIDA` con segundos |
| Conservar los registros **4 años** | Purga bloqueada antes de ese plazo y aviso al acercarse |
| A disposición de **las personas trabajadoras** | «Ver mi registro» en el terminal e informe individual |
| A disposición de sus **representantes legales** | Informe de empresa en Excel y CSV |
| A disposición de la **Inspección de Trabajo** | Expediente JSON con la cadena de verificación |

La ley **no** impone hoy un formato concreto: papel, hoja de cálculo o
programa son válidos siempre que el registro sea fiable, objetivo y
accesible. Lo que sí exige la jurisprudencia es que refleje el horario
**real**, no el teórico.

### 1.2 Otras normas que el programa vigila

| Norma | Qué exige | Alerta del programa |
|---|---|---|
| Art. 34.1 ET | 40 h semanales de promedio en cómputo anual | `EXCESO_SEMANAL` |
| Art. 34.3 ET | Máximo 9 h ordinarias diarias, salvo convenio | `JORNADA_DIARIA` |
| Art. 34.3 ET | **12 h** mínimas entre el fin de una jornada y el inicio de la siguiente | `DESCANSO_ENTRE_JORNADAS` |
| Art. 34.4 ET | Pausa ≥ 15 min si la jornada continuada supera 6 h (30 min para menores de 18 a partir de 4 h 30) | `PAUSA_INSUFICIENTE` |
| Art. 37.1 ET | Descanso semanal de día y medio ininterrumpido (dos días para menores) | `DESCANSO_SEMANAL` |
| Art. 35.2 ET | Máximo 80 horas extraordinarias al año | `HORAS_EXTRA_ANUALES` |
| Art. 35.5 ET | Registro específico de las horas extraordinarias | Cómputo por semana y año en los informes |

### 1.3 Protección de datos

El registro contiene datos personales, así que también aplican:

- **RGPD art. 5.1.e)** — limitación del plazo de conservación. Por eso el
  programa ofrece purgar lo que ya ha superado los cuatro años, en lugar de
  acumular registros para siempre.
- **RGPD art. 32** — seguridad del tratamiento. De ahí el cifrado de los
  datos personales en reposo y el hash de contraseñas y PIN.
- **LO 3/2018 (LOPDGDD), arts. 87 a 90** — derechos digitales en el trabajo,
  incluida la **desconexión digital** (art. 88).
- El programa **no registra geolocalización ni datos biométricos**. Es una
  decisión deliberada: son datos especialmente sensibles y para un registro
  de jornada normalmente no superan el juicio de proporcionalidad.

### 1.4 Sanciones

No llevar el registro, o llevarlo de forma incompleta, es **infracción grave**
del art. 7.5 de la LISOS (RDL 5/2000). Según el art. 40.1.b) LISOS, la multa
va de **751 € a 7.500 €**, en tres grados:

| Grado | Importe |
|---|---|
| Mínimo | 751 – 1.500 € |
| Medio | 1.501 – 3.750 € |
| Máximo | 3.751 – 7.500 € |

La Inspección gradúa según el número de personas afectadas, la reincidencia y
la intencionalidad, y en casos graves o reiterados puede recalificarse a
infracción muy grave.

---

## 2. Lo que **todavía no** está en vigor

Aquí es donde conviene tener cuidado, porque muchos proveedores venden como
obligatorio algo que aún no lo es.

### 2.1 El real decreto de registro horario digital

Está **en tramitación, no aprobado**. Situación a septiembre de 2026:

- El Ministerio de Trabajo elaboró un borrador que obligaría al registro
  **digital**, con trazabilidad, inmutabilidad, acceso remoto de la Inspección
  e interoperabilidad.
- El **Consejo de Estado emitió dictamen desfavorable** (dictamen núm.
  188/2026, de 19 de marzo de 2026), concluyendo que no procede aprobar el
  real decreto proyectado. Objeciones principales: infravaloración del impacto
  económico en pymes, obligaciones que exceden lo reglamentario y deberían ir
  por ley, insuficiente protección de datos y periodo de adaptación demasiado
  corto.
- En julio de 2026 se aplazó su aprobación a septiembre de 2026 para revisar
  el texto. **No hay fecha confirmada ni publicación en el BOE.**

**Qué implica para ti:** hoy no estás obligado a nada de esto. Pero el programa
ya lo cumple, porque son buenas prácticas con independencia de la norma y
porque, si el decreto sale adelante, no habrá que rehacer nada:

| Requisito del borrador | Estado en el programa |
|---|---|
| Formato digital | Sí, base de datos SQLite |
| Inmutabilidad de los registros | Sí, *triggers* de SQLite que bloquean `UPDATE`/`DELETE` |
| Trazabilidad de las correcciones | Sí, rectificaciones con autor, fecha y motivo; el original nunca se borra |
| Registro de las interrupciones | Sí, eventos `PAUSA_INICIO` / `PAUSA_FIN` |
| Presencial frente a teletrabajo | Sí, campo `modalidad` en cada fichaje |
| Acceso de la persona trabajadora | Sí, desde el propio terminal |
| Puesta a disposición de la Inspección | Sí, expediente JSON verificable |
| Acceso telemático directo de la ITSS | **No.** Requiere una API y un protocolo que aún no están definidos |

Esa última fila es la única pieza que no se puede construir todavía: mientras
no se publique la norma, no se sabe contra qué API habría que integrarse.

### 2.2 La jornada de 37,5 horas

**No está en vigor.** El proyecto de ley se aprobó en Consejo de Ministros el
6 de mayo de 2025, pero el Congreso lo rechazó el 10 de septiembre de 2025 al
prosperar las enmiendas a la totalidad. La jornada máxima legal sigue siendo
de **40 horas semanales de promedio en cómputo anual**.

Por eso el programa viene configurado con 40 horas. Si tu convenio ya aplica
una jornada menor, cámbiala en **Ajustes → Límites de jornada**: el aviso de
exceso semanal se recalcula solo, y también puedes fijar una jornada distinta
para cada persona.

---

## 3. Cómo se garantiza la fiabilidad del registro

Tres mecanismos, pensados para que el registro se sostenga si alguien lo
discute:

1. **Identificación personal.** Cada persona ficha con su código y su PIN. En
   la versión anterior bastaba con teclear el ID ajeno, lo que permitía fichar
   por otro y debilitaba el valor probatorio del registro.

2. **Inmutabilidad impuesta por el motor de base de datos.** Los `UPDATE` y
   `DELETE` sobre la tabla de fichajes están bloqueados por *triggers* de
   SQLite. No depende de que el código de la aplicación se porte bien.

3. **Cadena de hashes.** Cada fichaje encadena un SHA-256 con el del anterior.
   Si alguien manipula la base de datos por fuera —incluso esquivando los
   *triggers*—, la cadena se rompe y **Ajustes → Verificar la integridad** lo
   detecta y señala la fila exacta. El expediente para la Inspección incluye
   esa verificación.

Esto no convierte el registro en una prueba irrefutable —quien controla el
equipo controla los datos—, pero sí hace que **cualquier manipulación deje
rastro**, que es lo que se puede pedir a un programa que funciona en el
ordenador de la propia empresa.

---

## 4. Lo que este programa no hace

Por honestidad, conviene decir también dónde están los límites:

- **No hay fichaje desde el móvil ni en varios centros a la vez.** Es una
  aplicación de escritorio con la base de datos en el equipo. Si necesitas
  varios centros o fichaje remoto, hace falta una arquitectura cliente-servidor.
- **No sustituye al calendario laboral ni gestiona vacaciones, bajas o
  permisos.** Registra jornada efectiva; las ausencias se anotan como
  incidencias.
- **No calcula nóminas** ni exporta a sistemas de nómina concretos.
- **No hay acceso telemático de la Inspección**, por lo dicho en el punto 2.1.
- **La copia de seguridad es local.** Si se pierde el disco, se pierden los
  datos: lleva las copias a otro soporte. Y guarda `clave.key` junto a ellas,
  o los datos personales quedarán ilegibles.

---

## 5. Fuentes

Normativa (texto consolidado en el BOE):

- [Estatuto de los Trabajadores (RDLeg 2/2015)](https://www.boe.es/buscar/act.php?id=BOE-A-2015-11430)
- [Real Decreto-ley 8/2019, de 8 de marzo](https://www.boe.es/buscar/act.php?id=BOE-A-2019-3481)
- [LISOS (RDLeg 5/2000)](https://www.boe.es/buscar/act.php?id=BOE-A-2000-15060)
- [LO 3/2018 de Protección de Datos y garantía de los derechos digitales](https://www.boe.es/buscar/act.php?id=BOE-A-2018-16673)
- [Guía de la ITSS sobre registro de jornada](https://www.mites.gob.es/itss/web/Sala_de_comunicaciones/Noticias/)

Estado de la tramitación del real decreto (consultado en septiembre de 2026):

- [Estado de la normativa de registro horario digital](https://esisoluciones.es/fichajes/registro-horario-digital-2026-estado-normativa/)
- [Aplazamiento a septiembre de 2026](https://registrohorariodigital.es/registro-horario-digital-se-aplaza-septiembre/)
- [Dictamen del Consejo de Estado y efectos para pymes](https://mifichajelegal.com/blog/dictamen-consejo-estado-registro-horario-digital-pymes-que-pasa-ahora/)
- [Borrador del real decreto (portal de participación del Ministerio de Trabajo)](https://expinterweb.mites.gob.es/participa/listado/download/6cb63e79-48a8-4e99-9784-3a0b26ae6106)
- [Requisitos técnicos del borrador](https://mifichajelegal.com/blog/checklist-software-fichaje-requisitos-tecnicos-decreto-2026/)

Sanciones y jornada de 37,5 horas:

- [Art. 40 LISOS](https://www.iberley.es/legislacion/articulo-40-ley-sobre-infracciones-sanciones-orden-social-lisos)
- [Estado de la jornada de 37,5 horas en 2026](https://www.fichahoy.com/jornada-laboral-37-5-horas-2026/)

> **Revisa este documento cuando se publique el real decreto.** Si en el momento
> de leer esto ya está en el BOE, la sección 2.1 se ha quedado obsoleta.
