# Mapa del sistema

Cómo se relacionan los módulos y en qué orden se recorren. La tabla de "cargar cuando…" está en `../index.md`; el procedimiento completo, en `../AGENTE.md`.

```
                    00-indice/leyes.md  (L1–L13, se aplican siempre)
                               │
  01-fundamentos ──► 02-matematica ◄── 09-herramientas/gridcalc.py (todos los números)
          │                │
      03-offline         04-web
          └───────┬────────┘
            05-creatividad      (operadores O1–O14)
                  │
            08-composicion      (letra → densidad → espacio)
                  │
            06-casos            (aplicación a un sistema concreto)
                  │
             07-critica         (C1–C13 · Q1–Q8: cierra el bucle)
```

### La cadena de derivación

```
fuente ─► interlineado ─► unidad u ─► cadena de proximidad ─► padding · gutter · margen
  │                                                   │
  └─► ancho real de carácter ─► medida ─► columnas en uso ─► composición (operadores) ─► crítica
```

## Fuentes

**Libros (canon):**
- Josef Müller-Brockmann, *Grid Systems in Graphic Design* (1961/1981) — grids modulares de 8 a 32 campos, campos en líneas enteras.
- Karl Gerstner, *Designing Programmes* (1964) — grid "móvil" de *Capital*, 58 unidades.
- Jan Tschichold, *The Form of the Book* (1975) — cánones de página, proporciones "claras e intencionadas".
- Robert Bringhurst, *The Elements of Typographic Style* (4.ª ed.) — medida, escala cromática de proporciones (cap. 8).
- Timothy Samara, *Making and Breaking the Grid* (2.ª ed., 2017) — tipologías y su ruptura.
- Le Corbusier, *Le Modulor* (1948).
- Heydon Pickering & Andy Bell, *Every Layout* — primitivas intrínsecas.

**Web (verificadas oct-2026):**
- Canons of page construction — https://en.wikipedia.org/wiki/Canons_of_page_construction
- Gerstner, análisis del grid de *Capital* — https://ms-studio.net/notes/karl-gerstners-layout-grid/
- Bringhurst, escala cromática — https://vasilis.nl/nerd/code/bringhurst-studies/chromatic-scale/
- Utopia, `clamp()` y escalas fluidas — https://utopia.fyi/blog/clamp/
- Every Layout, Switcher — https://every-layout.dev/layouts/switcher/
- Breakouts con líneas nombradas — https://ryanmulligan.dev/blog/layout-breakouts/
- Baseline digest marzo 2026 (subgrid widely) — https://web.dev/blog/baseline-digest-mar-2026
- Web platform ago/sep 2026 (`text-box`, `sibling-index()`, `progress()`) — https://web.dev/blog/web-platform-08-2026 · https://web.dev/blog/web-platform-09-2026
- Stepped value functions — https://web.dev/blog/css-stepped-value-functions
- Grid lanes — https://caniuse.com/css-grid-lanes · https://webkit.org/?p=17862
- `reading-flow` — https://developer.chrome.com/blog/reading-flow
- WCAG 2.2 Understanding: Reflow, Focus Order, Text Spacing, Target Size — https://www.w3.org/WAI/WCAG22/Understanding/
- Material 3 window size classes — https://developer.android.com/develop/ui/compose/layouts/adaptive/window-size-classes
- Readable content guide (Apple) — https://useyourloaf.com/blog/readable-content-guides/
- InDesign, cuadrículas — https://helpx.adobe.com/indesign/using/grids.html
- Bootstrap 5.3 breakpoints — https://getbootstrap.com/docs/5.3/layout/breakpoints/ · Tailwind — https://tailwindcss.com/docs/responsive-design

**Formatos de fuente (base del lector de `09-herramientas/`):**
- OpenType spec (tablas `head`, `hhea`, `OS/2`, `post`, `cmap`, `hmtx`, `glyf`, `CFF`, `GPOS`, `kern`) — https://learn.microsoft.com/typography/opentype/spec/
- WOFF 2.0 (W3C Recommendation; transformaciones de `glyf`/`hmtx`) — https://www.w3.org/TR/WOFF2/
- Brotli, RFC 7932 — https://www.rfc-editor.org/rfc/rfc7932
- CFF (Adobe TN 5176) y Type 2 Charstrings (Adobe TN 5177)
- CSS Fonts 5: `size-adjust`, `ascent-override`, `descent-override`, `line-gap-override` — https://www.w3.org/TR/css-fonts-5/

**Corpus (dominio público):** Project Gutenberg: Cervantes, *Don Quijote* (#2000) · Austen, *Pride and Prejudice* (#1342) · Verne, *Le tour du monde en quatre-vingts jours* (#800) · Kafka, *Die Verwandlung* (#22367) · Manzoni, *I promessi sposi* (#45334) · Machado de Assis, *Dom Casmurro* (#55752) · Karkavitsas, *Ο αρχαιολόγος* (#31631). Wikisource en ruso: Dostoievski, *Белые ночи*. Frecuencias de letras: Wikipedia, *Letter frequency*.

**Variaciones y escrituras:** OpenType Font Variations Overview (`fvar`, `avar`, `gvar`, `HVAR`, `MVAR`, `ItemVariationStore`) — https://learn.microsoft.com/typography/opentype/spec/otvaroverview · OpenType script tags — https://learn.microsoft.com/typography/opentype/spec/scripttags · HarfBuzz — https://harfbuzz.github.io/

**Pendiente de verificar en fuente primaria:** márgenes M3 en large/extra-large; márgenes HIG por dispositivo; proporciones de Bringhurst pp. 148–149; cita literal de Müller-Brockmann sobre la calle de una línea; soporte de `if()` en Firefox; qué métricas verticales usa Safari/macOS (Windows y Linux ya medidos: `metricas-de-fuente.md` §2 y §9); causa del ancho de Chrome/Edge en Windows con fuentes variables CFF2; definición exacta de la opción *Ascent* de InDesign para la primera línea base (el sistema usa la altura del glifo "d"); medida de línea recomendada para chino, japonés y coreano (caracteres por línea) y referencias de x-height en escrituras sin ella; `opsz` automático en Safari (hay errores abiertos en WebKit: bugs 227353 y 258944) y en InDesign (¿pt?).
