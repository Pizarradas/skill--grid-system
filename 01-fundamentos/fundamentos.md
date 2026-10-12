# 01 — Fundamentos: qué es un grid y para qué sirve

## 1. Definición operativa

Un grid es **un conjunto de líneas de referencia derivado del contenido y del soporte**, que limita dónde puede empezar y acabar un elemento. No es un dibujo de columnas: es un **sistema de restricciones** que convierte miles de decisiones de posición en unas pocas decisiones de proporción.

Sirve para cuatro cosas, y cada propuesta debe decir cuál persigue:

| Función | Pregunta que responde | Se nota cuando falta |
|---|---|---|
| **Orden** | ¿dónde empieza cada cosa? | bordes que casi coinciden (el peor error: 2-4px de diferencia) |
| **Jerarquía** | ¿qué es más importante? | todo ocupa lo mismo |
| **Ritmo** | ¿cómo se recorre? | saltos irregulares, lectura cansada |
| **Continuidad** | ¿cómo sobrevive el sistema a otro tamaño, otra página, otro autor? | cada pantalla/página reinventada |

## 2. Anatomía (vocabulario común print/web)

| Término | Print | Web/CSS |
|---|---|---|
| **Formato / soporte** | página, pliego, cartel | viewport, contenedor (`cqi`), ventana de app |
| **Margen** | blanco entre caja y corte; interior (lomo), exterior, cabeza, pie | `padding-inline` del contenedor o pistas exteriores del grid |
| **Caja tipográfica / área de contenido** | *type area*, *text block* | pista `content`, `max-inline-size` |
| **Columna** | unidad vertical de composición | pista (`track`) |
| **Medianil / gutter** | espacio entre columnas | `column-gap` |
| **Calle horizontal** | espacio entre filas de módulos (≈ 1 línea) | `row-gap` |
| **Módulo / campo** | intersección columna × fila | celda; en web a menudo implícita |
| **Región / zona espacial** | grupo de módulos con una función | `grid-area`, span |
| **Línea de flujo (*flowline*)** | horizontal que ancla inicios (titulares, imágenes) | línea de fila nombrada, `align-self: start` |
| **Rejilla base (*baseline grid*)** | líneas cada interlineado | `line-height` común + múltiplos (`lh`, `rlh`) |
| **Sangre (*bleed*)** | lo que sobrepasa el corte (3-5mm) | *breakout* / *full-bleed* (líneas `full-*`) |
| **Marcadores** | folio, cornisa, notas | cabeceras sticky, navegación, pie |

## 3. Familias de grid

| Familia | Cuándo | Riesgo |
|---|---|---|
| **Manuscrito (1 columna)** | texto continuo: libro, artículo, docs, móvil | monotonía; se rompe con imágenes de varios tamaños |
| **De columnas (n columnas)** | periódico, revista, web de contenido | demasiadas columnas sin uso real |
| **Modular (columnas × filas)** | catálogos, carteles, dashboards, portadas | rigidez si los campos no salen de las líneas de texto |
| **Jerárquico** | home pages, posters, interfaces con zonas de distinta naturaleza | arbitrariedad si las zonas no se relacionan por proporción |
| **Rejilla base** | todo lo que tiene texto en columnas paralelas | en web, imágenes y componentes rompen el múltiplo |
| **Compuesto** (p. ej. 3 + 4) | publicaciones que necesitan variedad con unidad | ambigüedad si no se declara qué división manda en cada página |
| **Intrínseco / de contenido** (web) | colecciones de ítems sin número fijo | perder control del número máximo de columnas |
| **Asimétrico / roto / deconstruido** | expresión, marca, editorial de autor | caos si la "ruptura" no está también reglada |

## 4. Orden de derivación (de dónde salen los números)

Un grid bien hecho **se deriva**, no se elige. El orden canónico:

1. **Contenido** → inventario: tipos de pieza, cuántos, cuánto texto, imágenes y sus proporciones.
2. **Tipografía de lectura** → tamaño de cuerpo, interlineado (*leading*) y medida (45–75 caracteres; ~66 ideal).
3. **Unidad** → el interlineado (print) o una unidad base de espacio (web: 4/8px o `1rlh`). Todo espacio vertical es múltiplo de ella.
4. **Columna** → la medida de lectura cabe en un número entero de columnas + gutters.
5. **Gutter** → en print ≈ 1 interlineado (o 1 em); en web una función continua del ancho, nunca mayor que la columna.
6. **Margen** → proporcional al formato (cánones en print; `clamp()` en web), mayor o igual que el gutter.
7. **Filas / campos** → número entero de líneas por campo + 1 línea de calle.
8. **Ajuste** → lo que sobra va al margen inferior (print) o al `1fr` exterior (web); nunca se estiran los gutters para cuadrar.

Si un número no se puede rastrear a uno de estos pasos, es arbitrario (ley L1, `00-indice/leyes.md`).

## 5. Principios de composición sobre el grid

- **Alineación > proximidad > tamaño > color** como orden de herramientas de agrupación: primero la posición en la rejilla.
- **Pocas líneas activas.** Un grid de 12 rara vez usa 13 líneas: identifica las 3–5 líneas que de verdad reciben bordes y haz que se repitan (el "eje" de la página).
- **Contraste de escala con el mismo grid.** La variedad se consigue con spans distintos sobre las mismas líneas, no con líneas nuevas.
- **Espacio activo.** Las columnas vacías son parte del sistema (columna de respiración, columna de notas, margen colgado).
- **Una ruptura por unidad de lectura** (spread, sección, pantalla): rompe el grid una vez, de forma que se vea intencional, y alinea la ruptura con otra línea del sistema (sangre, eje central, línea de otra división).
- **Optical > matemático en los bordes.** Signos de puntuación, letras redondas e iconos se cuelgan ópticamente (*hanging punctuation*, overshoot) — la matemática fija la línea, la óptica decide qué toca la línea.

## 6. El grid como sistema vivo

- Declarar **qué es fijo y qué varía**: el número de columnas puede cambiar por tamaño; la relación margen/gutter/columna y la unidad no.
- Documentar el grid como **especificación** (plantilla *Grid Spec* en `AGENTE.md`) para que diseño, desarrollo e impresión hablen de lo mismo.
- Medir: la pregunta no es "¿se ve bien?", sino "¿cuántos bordes caen fuera de las líneas del sistema?".
