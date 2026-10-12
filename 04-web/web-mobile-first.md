# 04 — Grid online: web y apps, mobile first

## 1. Principios

1. **Worst case first.** Se diseña primero para 320 CSS px (WCAG 1.4.10 Reflow = 1280px al 400 %), con entrada táctil y atención fragmentada. La base CSS no lleva media query.
2. **Continuo antes que escalonado.** Margen, gutter, tipografía y espaciado son funciones del ancho (`clamp()`), no tablas por breakpoint. Los breakpoints solo **cambian la estructura**: número de columnas útiles, paneles, posición de la navegación.
3. **Intrínseco antes que extrínseco.** Si el contenido puede decidir (RAM, Switcher, Sidebar, container queries), no decide el viewport.
4. **El orden del DOM es el orden de lectura.** El grid coloca; no reordena contenido con significado (WCAG 1.3.2, 2.4.3).
5. **Las filas crecen.** Nunca alturas fijas para texto (WCAG 1.4.12: line-height 1.5, párrafo 2em, letter 0.12em, word 0.16em deben caber).

## 2. Contextos y su grid de partida

| Contexto | Rango | Estructura recomendada |
|---|---|---|
| Móvil (compact) | < 600 | 4 columnas o 1 columna de flujo; margen 16px (M3 16dp) |
| Tablet vertical / ventana media | 600–839 | 8 columnas, margen 24px; 1 panel |
| Tablet horizontal / portátil pequeño | 840–1199 | 12 columnas; 1–2 paneles (lista + detalle) |
| Escritorio | 1200–1599 | 12 columnas + medida limitada; 2+ paneles |
| Pantalla grande | ≥ 1600 | contenido centrado con `max`; columnas exteriores como espacio activo o 3.er panel |

Referencias de plataforma:

| Sistema | Cortes | Notas |
|---|---|---|
| Material 3 (window size classes, ancho) | compact < 600 · medium 600–839 · expanded 840–1199 · large 1200–1599 · extra-large ≥ 1600 dp | margen 16dp en compact, 24dp después; separador entre paneles 24dp; trabaja con **paneles**, no con columnas; unidad 4dp |
| Apple HIG | — | márgenes de layout 16–20pt; *readable content guide* ≈ 672pt máx. con Dynamic Type por defecto; safe areas; objetivos 44×44pt |
| Bootstrap 5.3 | 576 · 768 · 992 · 1200 · 1400 | 12 col, gutter 1.5rem |
| Tailwind v4 | 40 · 48 · 64 · 80 · 96rem | `--spacing: 0.25rem`; container queries @3xs (16rem) … @7xl (80rem) |

Usar **em** en media queries (siguen el tamaño de letra del navegador) y **rangos** (`@media (width >= 48em)`).

## 3. Tecnología disponible (octubre 2026)

| Capacidad | Estado | Uso en grids |
|---|---|---|
| CSS Grid, `gap`, `minmax()`, `fr`, áreas, líneas nombradas | universal | base |
| `min()` `max()` `clamp()` | universal | márgenes, gutters, medidas fluidas |
| **Subgrid** | Baseline *widely* (mar-2026) | hijos y nietos heredan las líneas: tarjetas alineadas, grid anidado coherente |
| **Container queries + `cqi`** | Baseline *widely* (ago-2025) | componentes que se adaptan a su pista |
| `round()` `mod()` `rem()` | Baseline *newly* (may-2024) | ajustar a rejilla base: `round(up, X, 1rlh)` |
| `lh` / `rlh` | Baseline (nov-2023) | ritmo vertical nativo |
| `text-box` (`trim-both cap alphabetic`) | Baseline *newly* (ago-2026) | el texto toca la línea del grid (alineación por mayúscula, como en print) — con respaldo |
| `sibling-index()` / `sibling-count()` | Baseline *newly* (ago-2026) | grids generativos sin JS: spans, desplazamientos y ritmos según el índice |
| `progress()` | Baseline *newly* (sep-2026) | interpolaciones más legibles que el `clamp()` manual |
| Anchor positioning | Baseline *newly* (ene-2026) | notas al margen ancladas a una columna |
| **Grid lanes (masonry)** `display: grid-lanes` | solo Safari 26.4+; flag en Chrome/Firefox | mejora progresiva con `@supports` y grid normal de respaldo |
| `reading-flow` / `reading-order` | solo Chromium 137+ | alinear foco con orden visual; nunca la única defensa |
| `if()`, `@function`, `calc-size()` | solo Chromium | mejora progresiva |

## 4. Recetas (CSS genérico; en un sistema de diseño se reescriben con sus tokens — ver 06)

### 4.1 Página con *breakout* (líneas nombradas)
```css
.page {
  --margin: clamp(1rem, 0rem + 4.4444vw, 4rem);      /* gridcalc clamp 16→64, 360→1440 */
  --measure: min(32em, 100% - 2 * var(--margin));     /* 66 car. reales × 0.48em (Inter); 66ch serían ~86 */
  display: grid;
  grid-template-columns:
    [full-start] minmax(var(--margin), 1fr)
    [wide-start] minmax(0, 8rem)
    [content-start] var(--measure) [content-end]
    minmax(0, 8rem) [wide-end]
    minmax(var(--margin), 1fr) [full-end];
}
.page > * { grid-column: content; }
.page > .wide { grid-column: wide; }
.page > .full { grid-column: full; }
```

### 4.2 Colección intrínseca con techo de columnas (RAM + máximo)
```css
.collection {
  --min: 16rem; --max-cols: 4; --gap: clamp(1rem, 0.6667rem + 1.4815vw, 2rem);
  display: grid;
  gap: var(--gap);
  grid-template-columns: repeat(auto-fill,
    minmax(min(100%, max(var(--min), (100% - (var(--max-cols) - 1) * var(--gap)) / var(--max-cols))), 1fr));
}
```
`auto-fit` estira los ítems si sobran pistas; `auto-fill` conserva las pistas vacías (alineación entre filas incompletas).

### 4.3 Rejilla de columnas mobile-first (4 → 8 → 12) con gutter continuo
```css
.cols {
  --cols: 4;
  display: grid;
  grid-template-columns: repeat(var(--cols), minmax(0, 1fr));
  column-gap: clamp(1rem, 0.6667rem + 1.4815vw, 2rem);
}
@media (width >= 37.5em) { .cols { --cols: 8; } }
@media (width >= 52.5em) { .cols { --cols: 12; } }
/* spans expresados en fracción del total, no en número: sobreviven al cambio de --cols */
.span-half  { grid-column: span calc(var(--cols) / 2); }
.span-third { grid-column: span max(1, round(down, var(--cols) / 3, 1)); }
```
(`span calc()` necesita un entero: dividir solo por divisores del número de columnas o usar `round()`. Es la parte menos probada de la receta: comprobarla en los navegadores objetivo; el respaldo seguro es redefinir los spans dentro de cada media query.)

### 4.4 Subgrid para alinear piezas internas
```css
.cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.5rem; }
.card  { display: grid; grid-row: span 3; grid-template-rows: subgrid; }  /* imagen / título / texto alineados */
```

### 4.5 Rejilla base nativa
```css
:root { line-height: 1.5; }
h1, h2, h3, p, figure { margin-block: 0 1rlh; }
h1, h2, h3 { text-box: trim-both cap alphabetic; }
img, video { block-size: round(up, 100%, 1rlh); object-fit: cover; }
```

### 4.6 Sidebar y Switcher (Every Layout)
```css
.with-sidebar { display: flex; flex-wrap: wrap; gap: 1rem; }
.with-sidebar > :first-child { flex-basis: 18rem; flex-grow: 1; }
.with-sidebar > :last-child  { flex-basis: 0; flex-grow: 999; min-inline-size: 60%; }

.switcher { display: flex; flex-wrap: wrap; gap: 1rem; --threshold: 40rem; }
.switcher > * { flex-grow: 1; flex-basis: calc((var(--threshold) - 100%) * 999); }
```

### 4.7 Masonry como mejora progresiva
```css
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 14rem), 1fr)); gap: 1rem; }
@supports (display: grid-lanes) {
  .gallery { display: grid-lanes; }
}
```

## 5. Apps y producto

- **Paneles, no columnas:** lista / detalle / herramientas. Cada panel lleva su propio grid interno por container query.
- **Densidad**: modo compacto/cómodo cambia la unidad (4 → 8) y el alto de fila, no el grid de columnas.
- **Dashboards**: 12 o 24 columnas con filas de altura `minmax(unidad, auto)`; los widgets ocupan spans múltiplos de un módulo (p. ej. 3×2); evitar `dense` si el orden del teclado importa.
- **Zonas fijas**: barras de navegación y *safe areas* (`env(safe-area-inset-*)`), objetivos ≥ 24px (WCAG 2.5.8), mejor 44–48.

## 6. Plan de transformación (lo que el agente debe entregar)

Para cada propuesta web, una tabla así (los valores, de `09-herramientas/gridcalc.py compose` o `web`; la medida, en caracteres reales — ver 08):

| Rango | Columnas útiles | Margen | Gutter | Medida texto | Cambio estructural |
|---|---|---|---|---|---|
| 320–599 | 4 (o flujo) | 16 | 16 | ~36 car. | navegación colapsada, todo apilado |
| 600–839 | 8 | 24→32 | 16→20 | ≤ 66 car. | 2 columnas en colecciones |
| 840–1199 | 12 | 32→48 | 20→28 | ≤ 66 car. | sidebar visible |
| ≥ 1200 | 12 + `max` | 48→64 | 28→32 | ≤ 66 car. | breakout, 3 paneles |

Y la comprobación: en cada rango `columna ≥ 1.5 × gutter`, span mínimo interactivo ≥ 24px, sin scroll horizontal a 320.
