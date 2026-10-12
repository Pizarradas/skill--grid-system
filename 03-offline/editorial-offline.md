# 03 — Grid offline: editorial, impresión y soportes físicos

## 1. Proceso de construcción (libro, revista, catálogo, informe)

1. **Formato.** Elegir proporción con intención (tabla de Bringhurst en 02 §2): 2:3 libro clásico, 1:√2 ISO (A4/A5: al plegar se conserva la proporción), 3:4 revista ancha, 8:15/1:2 alargados para guías y folletos. `09-herramientas/gridcalc.py paper`.
2. **Tipografía de texto.** Cuerpo e interlineado (p. ej. 9.5/13, 10/12, 11/14). El interlineado **L** es la unidad de todo el sistema vertical.
3. **Medida.** 45–75 caracteres a una columna (66 ideal); 40–50 en columnas múltiples (periódico, revista).
4. **Márgenes.** Canon (Van de Graaf / novenos, 2:3:4:6) en libros de lectura; márgenes más estrechos y simétricos en revistas y catálogos; el exterior y el pie, mayores, alojan pulgares y folio. `09-herramientas/gridcalc.py canon`.
5. **Columnas y gutter.** El gutter de columna ≈ L (o 1 em) para que el blanco horizontal y el vertical midan lo mismo.
6. **Filas y campos.** Müller-Brockmann: campos de un número entero de líneas, calle = 1 línea. Lo que sobra va al margen inferior. `09-herramientas/gridcalc.py print`.
7. **Retícula base en el software** (InDesign: Preferencias › Cuadrículas):
   - Incremento = L.
   - Relativo a: **margen superior**.
   - Inicio = valor que hace caer la primera línea base en la retícula (con *First Baseline Offset = Cap Height* en los marcos de texto, el borde superior del campo coincide con la altura de mayúscula).
   - Por defecto InDesign trae 36pt de inicio / 12pt de incremento: cambiarlo siempre.
8. **Estilos que respetan la retícula.** Titulares con interlineado múltiplo de L, o alineados a la retícula solo en la primera línea; espacio antes/después en múltiplos de L; pies de foto en interlineado L o L/2 (con retícula de media línea).
9. **Maestras / páginas patrón.** Una por variante de grid (p. ej. 3 col y 4 col en un compuesto 3+4), con folio, cornisa y zonas fijas.

## 2. Doble página (spread)

- La unidad de composición es la **doble página**, no la página: los márgenes interiores juntos forman el "canal" del lomo.
- Márgenes espejo: interior (lomo) a la derecha en pares (verso) y a la izquierda en impares (recto).
- Añadir pérdida de encuadernación al interior: fresado/rústica (perfect binding) 3–6mm extra; grapado: *creep* (las páginas centrales se desplazan hacia fuera ≈ grosor del papel × nº de pliegos).
- Las imágenes que cruzan el lomo evitan caras y texto en la zona del canal.

## 3. Producción

| Zona | Valor habitual |
|---|---|
| Sangre (*bleed*) | 3mm (Europa) · 0.125in = 3.175mm (EE. UU.) · 5mm en gran formato |
| Zona segura (*safe*) | 3–5mm hacia dentro del corte (texto y elementos críticos dentro) |
| *Slug* | fuera de la sangre: notas de imprenta, versión, tintas |
| Gran formato / carteles | escalar sangre y zona segura con el formato; comprobar distancia de lectura |

## 4. Tipologías editoriales y su grid típico

| Pieza | Grid de partida | Notas |
|---|---|---|
| Novela / ensayo | manuscrito, canon de novenos o 2:3:4:6 | ninguna imagen; el grid es la caja + retícula base |
| Libro ilustrado / catálogo | modular 3×4 a 6×8 | campos con la proporción de las fotos dominantes |
| Revista | compuesto 2+3 o 3+4 (12/6 unidades) | variar por sección, conservar márgenes y retícula |
| Periódico | 5–6 columnas (tabloide/berlinés) | jerarquía por número de columnas del titular |
| Informe corporativo | 6 o 12 columnas + columna de notas | margen colgado para cifras y notas |
| Cartel | modular amplio (Müller-Brockmann 4×4 – 8×8), o compuesto/rotado | lectura a distancia: pocos campos, mucho contraste de escala |
| Señalética / expositivo | módulo físico (Modulor, múltiplos de 100mm) | altura de ojo ≈ 150–160cm; distancia de lectura manda el cuerpo |
| Diapositivas 16:9 | 12 col × 6–8 filas, margen ≥ 5 % | zona segura de proyección; título siempre en la misma línea de flujo |

## 5. Traslado print → pantalla (y vuelta)

| Print | Equivalente web |
|---|---|
| Formato fijo | contenedor variable → definir rango de anchos y comportamiento en cada extremo |
| Caja tipográfica | `content` con `min(max, 100% - 2·margen)` |
| Retícula base L | `line-height` común; espaciados en `lh`/`rlh`; `text-box: trim-both cap alphabetic` para que el texto toque la línea |
| Campos de n líneas | `grid-auto-rows` en múltiplos de `1rlh` (solo si el contenido lo tolera — WCAG 1.4.12 obliga a que las filas crezcan) |
| Doble página | no existe; la unidad de composición es la **pantalla de scroll** o la **sección** |
| Sangre | líneas `full-start/full-end`; `env(safe-area-inset-*)` en móviles |
| Maestras | layouts/plantillas de página; componentes con su propio grid (container queries) |

Lo que **no** se traslada: alturas fijas de campo, justificación sin control de partición, márgenes interiores asimétricos (en pantalla no hay lomo).

## 6. Herramientas

- **InDesign:** Maquetación › Márgenes y columnas; Crear guías (filas/columnas con calle); retícula base por marco de texto para columnas con otra unidad.
- **Affinity Publisher:** Gestor de cuadrícula base + *Guides Manager* (columnas, filas, calles).
- **Figma:** *Layout grids* (columns: count, gutter, margin, type stretch/center; rows; grid de 4/8px) — sirve también para print si se trabaja en mm convertidos (1mm = 3.7795px a 96dpi). Variables para gutter/margen por modo (compact/medium/expanded).
- **Scripts/generativo:** `09-herramientas/gridcalc.py` para los números; SVG para entregar el diagrama acotado.
