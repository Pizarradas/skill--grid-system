# 07 — Crítica y validación de un grid

Un grid se valida por **comportamiento medible**, no por gusto (ley L8). Esta lista se recorre antes de entregar cualquier propuesta.

## 1. Comprobaciones duras (fallo = no se entrega)

| # | Comprobación | Cómo se mide |
|---|---|---|
| C1 | Todos los números salen de una regla | cada valor tiene su comando `gridcalc` o su token |
| C2 | Sin scroll horizontal a 320 CSS px (WCAG 1.4.10) | `gridcalc web --viewports 320`; mínimos de pista con `min(100%, X)` |
| C3 | Orden visual = orden del DOM para contenido con significado (1.3.2 / 2.4.3) | ningún `order`, `dense` o colocación que reordene texto/controles |
| C4 | Filas de texto sin altura fija (1.4.12) | `auto` / `minmax(x, auto)` |
| C5 | Medida de texto 45–75 caracteres **de media en las líneas compuestas**, y ninguna línea > 80 (1.4.8) | `gridcalc lines` (media real, rango del 90 %, línea más larga); `max-inline-size` = el ancho que da esa media |
| C6 | `columna ≥ 1.5 × gutter` en todo el rango usado | tabla `col/gut` de `gridcalc web` |
| C7 | Objetivos ≥ 24×24 (2.5.8), idealmente 44–48 | span mínimo que contiene un control |
| C8 | Print: campos = número entero de líneas; primera línea base en la retícula | `gridcalc print` |
| C9 | Print: sangre y zona segura definidas | 3mm / 3–5mm, o el estándar del impresor |
| C10 | Medidas en caracteres reales (em × char_em, con kerning), no `ch` sin corregir | `gridcalc font` |
| C11 | Orden de proximidad micro < inner < padding < gutter ≤ margen < sección | `gridcalc compose` (avisos) |
| C12 | Espaciado vertical múltiplo de `u` (o `u/2`), o en `lh`/`rlh` | revisar tokens de espaciado vertical |
| C13 | Métricas tipográficas **medidas en el archivo real de la fuente** (perfil con SHA-1; en variables, en el punto de los ejes que se usa), sin avisos abiertos: line box igual en todas las plataformas (o fijado con `*-override`), interlineado ≥ mínimo sin colisión, idioma cubierto, escritura compleja compuesta con HarfBuzz | `gridcalc font <archivo>` (avisos) · `verificar.py` |

## 2. Comprobaciones de calidad (puntuar 0–2)

| # | Criterio | 0 | 1 | 2 |
|---|---|---|---|---|
| Q1 | Derivación | números elegidos | parcialmente derivados | todo deriva del contenido (L, medida) |
| Q2 | Líneas activas | bordes por todas partes | algunas líneas repetidas | 3–5 ejes claros y repetidos |
| Q3 | Jerarquía | spans iguales | jerarquía por tamaño | jerarquía por proporción de escala |
| Q4 | Ritmo | espacios irregulares | múltiplos de la unidad | múltiplos + patrón reconocible |
| Q5 | Continuidad (web) | saltos > 20 % en una pista | escalones suaves | fluido; breakpoints solo estructurales |
| Q6 | Ruptura | ninguna o accidental | intencional pero sin ancla | una, anclada a una línea del sistema |
| Q7 | Economía | > 3 operadores / reglas redundantes | — | mínimo número de reglas para el resultado |
| Q8 | Transferencia | solo funciona en un tamaño | funciona con ajustes manuales | mismo sistema en móvil, escritorio y/o print |

≥ 12/16: listo · 8–11: revisar los criterios a 0 · < 8: replantear el grid base.

## 3. Señales típicas de fallo y su corrección

| Síntoma | Causa | Corrección |
|---|---|---|
| Bordes que "casi" coinciden | dos sistemas de medida (px sueltos + grid) | todo a líneas del grid o a la unidad |
| Columna que encoge al ensanchar la ventana | escalón de gutter/margen en un breakpoint | gutter/margen con `clamp()` (04 §4; caso real en `06-casos/syx.md` §D2) |
| Grid anidado desalineado | grid hijo independiente | `subgrid` |
| Texto de 150 caracteres por línea | contenedor sin medida | `max-inline-size` / pista `content` |
| Huecos al final de colecciones | `auto-fit`/`dense` sin control | `auto-fill`, ritmo E(k,n), o ítem compensador |
| Composición "creativa" que parece error | ruptura sin ancla, una sola vez | repetir la decisión o anclarla a una línea |
| Móvil que es el escritorio apretado | diseño desktop-first | rehacer desde 320 con la jerarquía, no con la retícula |

## 4. Formato del informe de crítica

```
Grid: <nombre>  ·  Contexto: <web/app/print>  ·  Puntuación: n/16
Duras: C1 ✓ C2 ✓ C3 ✗ (motivo) …
Calidad: Q1 2 · Q2 1 · …
Tres cambios de mayor impacto:
  1. <cambio> — <regla/valor> — <qué métrica mejora>
```
