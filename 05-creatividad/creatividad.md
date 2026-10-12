# 05 — Grids creativos: variación con reglas

La creatividad en un grid no consiste en ignorarlo, sino en **elegir operaciones matemáticas sobre él y declararlas**. Una composición es expresiva y a la vez sistemática cuando cualquier borde se puede explicar con una regla.

> Fórmula de trabajo: **grid base + 1–3 operadores + 1 ruptura declarada**.
> Más de tres operadores a la vez casi siempre se lee como desorden.

---

## 1. Operadores

Cada operador tiene una regla (lo que se puede calcular) y un efecto (lo que se percibe).

| # | Operador | Regla | Efecto | Herramienta |
|---|---|---|---|---|
| O1 | **Subdivisión** | n → n·k (12 → 24) dentro de una zona | detalle, densidad local | `repeat()` anidado o subgrid |
| O2 | **Superposición (compuesto)** | divisiones d₁, d₂ sobre MCM(d₁, d₂) | variedad con unidad; tensión en líneas no comunes | `gridcalc compound` |
| O3 | **Desplazamiento (offset)** | el inicio se mueve k unidades; repetir el mismo k | asimetría estable, aire activo | `grid-column: k+1 / span s` |
| O4 | **Proporción progresiva** | pistas en serie Fibonacci / geométrica / armónica | dirección, foco, perspectiva | `gridcalc tracks` |
| O5 | **Escala modular de spans** | los tamaños de bloque siguen una escala (1, 2, 3, 5, 8 módulos) | jerarquía "natural" | `gridcalc scale --base 1 --ratio golden` |
| O6 | **Ritmo euclídeo** | k acentos sobre n posiciones: E(k, n) | regularidad no monótona | `gridcalc rhythm`, `:nth-child` |
| O7 | **Espejo / simetría de grupo** | reflexión, traslación con reflexión (glide) entre secciones o páginas | unidad entre spreads o secciones | alternar `grid-column` con la regla `n+1 − línea` |
| O8 | **Rotación** | el grid gira un ángulo con significado (30° isométrico √3, 45°, ángulo de la diagonal del formato `atan(H/W)`) | dinamismo (cartel, portada) | print/SVG; en web solo en capas decorativas |
| O9 | **Grid radial / polar** | divisiones angulares 360/n y radios en escala | centro absoluto, señal | SVG, `transform: rotate(calc(360deg / n * i))` + `sibling-index()` |
| O10 | **Gradiente de densidad** | el tamaño de módulo varía con la posición según una función (lineal, geométrica) | movimiento, profundidad | pistas progresivas + spans |
| O11 | **Solapamiento reglado** | dos elementos comparten celdas; el solape es un número entero de módulos | capas, profundidad editorial | áreas que se cruzan + `z-index` |
| O12 | **Ruptura (sangre / salto)** | un elemento sale del grid hasta **otra línea del sistema** (corte, eje, línea de la otra división) | énfasis | líneas `full`/`feature`; sangre en print |
| O13 | **Contragrid** | un segundo grid ligado a otra unidad (p. ej. la retícula base) gobierna un tipo de contenido (pies, notas) | contrapunto | contenedor propio, subgrid en un eje |
| O14 | **Vacío activo** | columnas o campos vacíos con número fijo y posición regulada | lujo, pausa, foco | columnas sin contenido declaradas |

### Reglas de buena práctica
- **Una ruptura por unidad** (spread, sección, pantalla) y siempre hacia una línea del sistema.
- **Repetir** cada decisión arbitraria al menos dos veces: el ojo lee la repetición como intención.
- **Conservar al menos un invariante** visible (margen, línea de flujo superior, retícula base) mientras los demás varían.
- **Accesibilidad no se negocia:** los operadores son visuales; el DOM sigue el orden de lectura; nada de texto encima de imagen sin contraste suficiente; las rotaciones no afectan al texto de lectura.

## 2. Estilos con su gramática

| Estilo | Gramática | Ejemplo de reglas |
|---|---|---|
| **Suizo / internacional** | modular, asimétrico, texto en bandera, flowlines fuertes | 6 col × 6 filas, titular en 4 col, imagen 3×3, texto 2 col; todo arranca en dos flowlines |
| **Editorial clásico** | canon de página, caja simétrica en el spread | novenos, 1–2 columnas, imágenes a la caja o a sangre completa |
| **Compuesto (Gerstner)** | una unidad que admite varias divisiones | 58 unidades → 1…6 col con gutter 2 |
| **Brutalista web** | grid visible (bordes de celda), módulos de tamaño entero, monoespaciado | `gap: 0` + bordes de 1px como líneas; spans de escala 1-2-4 |
| **Bento** | modular 4×n con piezas de 1×1, 2×1, 2×2 | distribución por E(k, n) para que las piezas grandes no se agrupen |
| **Deconstruido** | dos grids en conflicto (rotación, compuesto sin líneas comunes, solapes) | 3+5 sin líneas comunes; un grid girado 7°; solapes de 1 módulo |
| **Generativo** | reglas paramétricas: el índice del elemento decide span/posición | `grid-column: span calc(1 + mod(sibling-index(), 3))` (con respaldo) |

## 3. Recetas creativas (con su matemática)

### R1 · Portada asimétrica áurea en 13 columnas
- `gridcalc ratio --ratio golden --columns 13` → 8 + 5 (−1.1 %).
- Imagen: líneas 1–9 (8 col); texto: 9–14 (5 col). Titular desplazado O3 k = 1 en el bloque de texto.
- Mobile: una columna; la imagen conserva la proporción 8:5 en su `aspect-ratio`.

### R2 · Revista 3+4 (12 unidades)
- Secciones "lentas" (reportaje) en 3 columnas (4u), "rápidas" (breves) en 4 (3u).
- Las dos comparten margen, flowline superior y retícula base: el invariante.
- Ruptura: la apertura usa la línea 2/3 de la división 3 contra la 3/4 de la 4 (tensión de 1 unidad).

### R3 · Galería con ritmo euclídeo
- 8 ítems por ciclo, 3 destacados: E(3,8) = `x..x..x.` → `:nth-child(8n+1), (8n+4), (8n+7)` ocupan 2×2.
- Rejilla de 4 columnas, `grid-auto-flow: row` (sin `dense`, el orden se conserva); comprobar que los huecos resultantes son aceptables o compensar con un ítem 2×1.

### R4 · Cartel con grid rotado
- Formato A2 (420×594, 1:√2), grid 6×8 modular desde `gridcalc print`.
- Segundo grid girado `atan(594/420) ≈ 54.7°` (la diagonal del formato): solo para el titular.
- Invariante: los márgenes y la retícula base del texto informativo.

### R5 · Landing con pistas Fibonacci espejo
- `gridcalc tracks --series fibonacci --count 4 --mirror odd` → `1fr 1fr 2fr 3fr 2fr 1fr 1fr`.
- El contenido principal en la pista central (3fr); los laterales, vacío activo o elementos de apoyo.
- Mobile (< 600): una sola columna; desde 840 se activa la progresión.

## 4. Cómo justificar una propuesta creativa

Cada composición se entrega con:
1. **Grid base** (números de `gridcalc`).
2. **Operadores** usados (O1–O14) con sus parámetros.
3. **Invariantes** (lo que nunca cambia).
4. **Ruptura** declarada y la línea a la que se ancla.
5. **Transformación** a móvil (o a otro formato impreso).
6. **Riesgos** y cómo se mitigan (orden de lectura, medida, contraste).
