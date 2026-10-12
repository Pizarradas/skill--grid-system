# El grid de SYX: anatomía, diagnóstico medido y evolución

> **Caso de estudio.** Este módulo es el único del sistema que depende de un repositorio concreto. Muestra cómo se aplican las leyes (L1–L13) y la crítica (07) a un sistema de diseño real. Las referencias a *Atlas 04.x* son las reglas de matemática del propio SYX (`mind-system/atlas-rules/04-matematica-del-sistema/`); su equivalente en este sistema son las leyes de `00-indice/leyes.md`. Para un caso nuevo, copia la estructura: §1 qué hay · §2 diagnóstico medido · §3 propuesta · §4 decisiones humanas · §5 reglas locales.

> Estudio de `Pizarradas/syx` (base `7deff28`, 2026-10-10). **Todas las cifras de este módulo están medidas en Chromium 153** (Playwright, CSS compilado de cada tema) salvo donde se indica cálculo. Rama de la propuesta: `feat/grid-composicion`.

---

## 1. Qué hay

| Capa | Dónde | Qué hace |
|---|---|---|
| **Grid de columnas** `.layout-grid` | `scss/layout/grids/_grid.scss` | 12 columnas `repeat(12, minmax(0, 1fr))`; margen = `padding-inline`, gutter = `gap`, ambos por escalones (0 · 48 · 64 · 80 · 90em) desde `--layout-pad-1..5` / `--layout-gap-1..5` |
| **Primitivas** `.layout-stack`, `.layout-cluster` | `scss/layout/` | flex + `gap` desde `--semantic-space-stack-*` / `--semantic-space-inline-*` |
| **Grids de componente** | `site/_home-features.scss`, `organisms/_app-shell.scss`, `molecules/_feature-card.scss` | RAM con suelo dinámico, container queries, `subgrid` en filas, áreas |
| **Marco teórico** | `mind-system/atlas-rules/04-matematica-del-sistema/` | proporciones, escalas, ritmo, grid continuo, densidad, métricas |

Los tokens de layout viven en cada **tema** y escalan con `--primitive-space-base`, que **cambia por tema**:

| Tema | `space-base` | Cuerpo (fuente · tamaño a 1440 · interlineado) | Ancho máx. de la rejilla |
|---|---|---|---|
| syx-sketch | 0.25rem (4px) | Space Grotesk · 18px · 1.65 | 1440px |
| example-01 | 0.25rem | Inter · 16px · 1.65 | 1440px |
| example-02 | 0.4rem | Space Grotesk · 19.6px | sin tope |
| example-03 | 0.3rem | Playfair Display · 27px | ~1440px |
| example-04 | 0.18rem | DM Mono · 8.2px (raíz reducida) | 842px |
| example-05 | 0.35rem | Inter · 21px | 1890px |
| example-06 | 0.25rem | Inter · 16px | ~1920px |

### Lo que ya se hacía bien (y se conserva)
- Breakpoints en `em` (siguen la letra por defecto del navegador).
- `minmax(0, 1fr)` en vez de `1fr`.
- RAM con suelo dinámico en `features__grid`: `repeat(auto-fill, minmax(min(100%, max(18rem, (100% − 2g)/3)), 1fr))`, que limita a 3 columnas sin media queries. El modelo de composición (08) da **263px** de ancho mínimo de tarjeta para Space Grotesk, coherente con esos 18rem.
- Container queries y `subgrid` en las filas de las tarjetas.
- `gap`, nunca márgenes, en stack y cluster.

---

## 2. Diagnóstico (medido)

### D1 · Cuatro vocabularios de breakpoint
| Fuente | Cortes |
|---|---|
| `primitives/_breakpoints.scss` | sm 600 · md 768 · lg 1024 · xl 1280 · xxl 1440 |
| `$syx-breakpoints` (mixin `breakpoint()`) | phablet 600 · tablet 800 · laptop 1024 · desktop 1120 · xl 1280 · wide 1440 |
| `.layout-grid` (clases) | sm = 768 · md = 1024 · lg = 1280 · (escalón sin clases a 1440) |
| `knowledges/front/mobile-first.md` (antes de esta rama) | sm 640 · md 768 · lg 1024 · xl 1200 |

`breakpoint(sm)` y `breakpoint(lg)`, usados en ejemplos del córtex, **no existen en el mapa**: Sass emite `@warn` y no genera CSS. La rama corrige los ejemplos del córtex; unificar los mapas es decisión humana (§4).

### D2 · Saltos en los cortes
Sin interpolación, al cruzar un corte el gutter salta y **la columna encoge mientras la ventana crece**:

| Tema | 767 → 768px | 1439 → 1440px |
|---|---|---|
| syx-sketch | gap 4 → 12 · columna 58.9 → 51.0 (−13 %) | gap 24 → 32 · columna 93.9 → 85.3 (−9 %) |
| example-05 | gap 5.3 → 15.8 · columna 57.3 → 46.9 (−18 %) | gap 26.3 → 31.5 · 91.5 → 85.9 (−6 %) |
| example-06 | gap 8 → 16 · 54.6 → 46.7 (−14 %) | gap 32 → 40 · 85.3 → 76.7 (−10 %) |

La relación columna/gutter, en cambio, se mantiene sana en todos los temas (≥ 1.9). Ningún tema llega a tener un gutter mayor que la columna.

### D3 · `ch` no son caracteres
Medido con texto en español a 1440px, en la fuente de cada tema:

| Tema | `max-width: 65ch` | `max-width: 55ch` |
|---|---|---|
| syx-sketch (Space Grotesk) | **84 car.** | 72 |
| example-01/06 (Inter) | **82** | 71 |
| example-03 (Playfair) | **82** | 71 |
| example-04 (DM Mono) | 62 | 55 |

`65ch` (`.syx-max-w-65ch`) da líneas de 82–84 caracteres, fuera del rango 45–75 y por encima de WCAG 1.4.8. Motivo: `ch` mide el "0" (0.60–0.64em) y el carácter medio de texto mide 0.45–0.49em (ver 08). La medida de 66 caracteres son **≈ 50ch** en estas fuentes.

### D4 · `__nested` no hereda las líneas del padre
Es otra rejilla de 12 con su propio gap, así que sus líneas interiores no coinciden con las del padre. Convertirla en subgrid **no es compatible hacia atrás**: dentro de un `__col-8`, un subgrid ofrece 8 pistas y un `__col-xs-6` dejaría de ser "la mitad". Por eso la rama añade `__subgrid` como opción en lugar de cambiar `__nested`.

### D5 · Sin líneas de inicio
Con `auto / span n` el elemento empieza donde le toque. No había forma de desplazar un bloque ni de componer de forma asimétrica sin CSS propio.

### D6 · La proporción áurea de Atlas no cabe en 12 columnas
En 12 columnas, 8+4 da 2:1 exacto, pero la mejor aproximación áurea es 7+5 = 1.40 (−13.5 %). Con 13 columnas, 8+5 = 1.60 (−1.1 %). Fuera de la rejilla, `1.618fr 1fr` es exacto.

### D7 · Uso real
Recuento de clases en los HTML: spans de 12 (46 veces), 6 (35), 4 (14), 3 (8), 8 (6), 5 (1) y 10 (1). Nunca se usan 1, 2, 7, 9 ni 11. En la práctica el sistema son mitades, tercios y cuartos, es decir, un grid compuesto 3 + 4.

### D8 · Ritmo vertical desacoplado
El cuerpo usa un interlineado de 1.65 en todos los temas. Eso da una unidad vertical de 26.4px a 16px de cuerpo y de 29.7px a 18px, mientras que el espaciado va en múltiplos de una base de 2.9 a 6.4px según el tema. Texto y espacio nunca coinciden. Además, el modelo de interlineado (08) daría 1.50 para las fuentes de SYX con 66 caracteres: el 1.65 actual compone más aireado y menos denso.

---

## 3. Lo que implementa la rama `feat/grid-composicion`

Todo está en `scss/layout/grids/_grid.scss` (nivel `pr`), es compatible hacia atrás y está medido en Chromium:

| Pieza | Qué hace | Verificación |
|---|---|---|
| **Continuidad** | Bajo `@supports (progress())`, el gutter y el margen son una función lineal a tramos entre los mismos tokens del tema: `v₁ + Σ(vᵢ₊₁ − vᵢ)·clamp(0, progress(100vw, cᵢ, cᵢ₊₁), 1)`. Los cortes van en `rem` (20 · 48 · 64 · 80 · 90): siguen la letra del lector, como las media queries en `em`. Como la función no usa media queries, sigue siendo continua aunque un tema cambie la letra de `:root`. | Barrido de 320 a 1600px en pasos de 4px, los 7 temas: la mayor caída de columna al ensanchar la ventana pasa de 7–18 % a **0 %** (0.2 % en example-04, cuya raíz es más pequeña). Ningún reflow a 320px. En cada corte con raíz de 16px, el valor es exactamente el del tema |
| **Tope columna ≥ 1.5 × gutter** | `column-gap: min(…, 100% / 29)`, porque 12·1.5 + 11 = 29 | Ningún tema lo alcanza hoy; protege los temas futuros |
| **Densidad** | `layout-grid--compact` / `--spacious`: gutter y margen × 0.8 / × 1.25, un paso de la escala tipográfica Major Third | Gap de 24 → 19.2 en compacto |
| **`__col-xl-{n}`** | Clases de columna a 90em, donde antes había escalón de gap sin clases | ✓ |
| **`__start-{bp}-{n}` / `-auto`** | Línea de inicio para composiciones asimétricas. Inicio + span − 1 ≤ 12 | `start-md-4` cae en la línea 4 |
| **`__subgrid`** | El hijo hereda las pistas que ocupa: un `__col-md-8 __subgrid` ofrece 8 columnas alineadas con la página | El segundo hijo cae exactamente en la línea 5 del padre (129.5 y 442.7px) |
| **`__prose` (+ `--scanning`, `--operating`)** | Medida en caracteres reales: `calc(var(--layout-measure, 66) * var(--layout-char-width, 0.76ch))` | 62–65 car. con Inter, Space Grotesk y Playfair; 48–50 con `--operating`; DM Mono necesita `--layout-char-width: 1ch` (§4) |

## 4. Recomendaciones de nivel humano (no aplicadas)

Estos cambios tocan rutas `human` de `contracts/trust.json`, así que la rama no los aplica. El parche va en la descripción del PR.

1. **Acoplar el módulo** `knowledges/grid/` a los modos UI, CREATIVE, SKETCH, AUDIT y TOKEN (bloque `Knowledge`) y a `mind-system/routing.md`. Sin esto, `check:conocimiento` marca el módulo como huérfano.
2. **Tokens de tema** `--layout-char-width` (ancho medio de carácter de la fuente del cuerpo, en `ch`) y, opcionalmente, `--layout-measure`:

   | Fuente | Valor de `--layout-char-width` (español, con kerning; `char_em / ch`) |
   |---|---|
   | Inter | 0.756ch |
   | Space Grotesk | 0.751ch |
   | Playfair Display | 0.740ch |
   | DM Mono | **1ch** |
   | Syne | 0.741ch |

   > Calibración 1.1 (`gridcalc.py font`, leída de los `.woff2` del repositorio). La rama `feat/grid-composicion` usa 0.76ch por defecto en todas las proporcionales: la diferencia llega al +2.7 % (una medida de 66 caracteres da entre 66.3 y 67.8 reales). Con estos valores por tema queda exacta.
3. **Un solo mapa de breakpoints**: que `$syx-breakpoints` añada los alias `sm`, `md`, `lg` y `xl` de los primitivos, o que los primitivos adopten los nombres del mixin.
4. **Interlineado y ritmo**: valorar un `--semantic-line-height-body` por fuente según el modelo, y espaciado vertical de sección en `lh`/`rlh`.
5. **`.syx-max-w-65ch` y `.syx-max-w-50ch`** prometen caracteres que no dan (82 y 63 reales). Proponer `syx-measure-*` basadas en `--layout-char-width`. Las utilidades son nivel `pr`, pero conviene decidirlo junto con el punto 2.
6. **Line box de Bebas Neue.** No activa `USE_TYPO_METRICS` y sus `usWin*` (0.95/0.35) difieren de `hhea` (0.90/0.30), así que en Windows sus titulares colocan la línea base 0.05em más abajo. Añadir a su `@font-face` `ascent-override: 90%; descent-override: 30%; line-gap-override: 0%` (`gridcalc.py font BebasNeue-Regular.woff2 --css`). El resto de fuentes de SYX activa `USE_TYPO_METRICS` y no lo necesita.
7. **Fallbacks sin salto (CLS).** `gridcalc.py font <archivo> --fallback arial` calcula `size-adjust` y overrides para que Arial ocupe lo mismo que cada fuente mientras carga (Space Grotesk: `size-adjust` 106.95 %).

## 5. Reglas SYX para cualquier grid que genere un agente

- Los valores salen de tokens (`--layout-*`, `--semantic-space-*`), nunca de px sueltos en componentes. Lo calculado con `09-herramientas/gridcalc.py` se guarda como token de tema, y eso lo decide una persona.
- Layout en `@layer syx.base`, con BEM `layout-*`. Breakpoints con `@include breakpoint(<nombre que exista en $syx-breakpoints>)`, en `em` y solo `min-width`.
- Primero lo intrínseco (RAM con techo, container queries, `__subgrid`). Las media queries solo para cambiar la estructura.
- La prosa va en `__prose` o en un span calculado, nunca a ancho completo.
- El orden del DOM es el orden de lectura.
- Cada propuesta cita la regla Atlas que cumple (04.1–04.4) y la métrica de 04.5 que la valida.
