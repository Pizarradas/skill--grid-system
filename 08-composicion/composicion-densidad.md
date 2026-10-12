# 08 — Composición multidisciplinar: tipografía → densidad → espacio → grid

El grid no se dibuja antes que el contenido: **es la consecuencia de cómo es la letra, de para qué se lee y de cuánta información cabe**. Este módulo une tipografía, percepción (Gestalt), densidad y retícula en una sola cadena de cálculo. Todo lo cuantificable sale de `09-herramientas/gridcalc.py compose` y `09-herramientas/gridcalc.py font`.

```
fuente (métricas) ─► interlineado ─► unidad u ─► cadena de proximidad ─► gutter · margen · padding
      │                                   │                                   │
      └─► ancho real de carácter ─► medida ─► spans de prosa / mínimo de tarjeta ─► columnas en uso
                                                    │
                               uso (leer · escanear · operar) + densidad (compacta · normal · amplia)
```

---

## 1. La letra decide (métricas que importan)

Las métricas **se leen del archivo de la fuente**, no se estiman: `gridcalc.py font <archivo>` abre el `.woff2`/`.ttf`/`.otf`, mide los glifos y compone texto real con kerning. Qué es cada parámetro, en qué tabla del archivo vive y cómo se mide: **`metricas-de-fuente.md`**.

| Métrica | Qué controla | De dónde sale |
|---|---|---|
| **x-height** (xh, em) | tamaño aparente, interlineado necesario | caja del glifo "x" (y OS/2 `sxHeight` como contraste) |
| **ancho medio de carácter** (`char_em`, em) | caracteres por línea → ancho de columna | texto corrido del idioma compuesto con avances + kerning, como lo maqueta un navegador |
| **`ch`** (ancho del "0") | lo que CSS mide con `ch` | avance del glifo "0" |
| line box: ascendente / descendente | dónde cae la línea base dentro de la línea, padding óptico | `hhea` u OS/2 typo según `USE_TYPO_METRICS`; Windows puede usar `usWin*` |
| **lh mínimo sin colisión** | interlineado mínimo de titulares | tinta más alta (mayúsculas acentuadas) − tinta más baja (descendentes) del idioma |
| blanco inicial | padding-inline óptico | sangría lateral media de la primera letra de cada palabra |

Medidas de las fuentes de referencia (`gridcalc.py font`; perfiles en `09-herramientas/perfiles/`):

| Fuente | x-height (glifo · OS/2) | char_em es (con kerning) | ch (em) | ch/char | 66 car. reales | lh mín. sin colisión (es) | line box | densidad (car./1000px², 16/24) |
|---|---|---|---|---|---|---|---|---|
| Inter | 0.546 · 0.546 | 0.4770 | 0.631 | 1.32 | 31.48em ≈ 50ch | 1.158 | typo | 5.46 |
| Space Grotesk | 0.489 · 0.486 | 0.4814 | 0.641 | 1.33 | 31.77em ≈ 50ch | 1.084 | typo | 5.41 |
| Playfair Display | 0.515 · 0.514 | 0.4442 | 0.600 | 1.35 | 29.32em ≈ 49ch | 1.127 | typo | 5.86 |
| DM Mono | 0.496 · 0.496 | 0.6000 | 0.600 | 1.00 | 39.60em ≈ 66ch | 1.163 | hhea | 4.34 |
| Syne Regular | 0.500 · 0.500 | 0.4357 | 0.588 | 1.35 | 28.76em ≈ 49ch | 1.102 | typo | 5.98 |
| Syne Bold | 0.497 · 0.500 | 0.5426 | 0.738 | 1.36 | 35.81em ≈ 49ch | 1.092 | typo | 4.80 |
| Bebas Neue (solo mayúsculas) | 0.700 · 0.700 | 0.3339 | 0.400 | 1.20 | — (titulares) | 0.931 | hhea · **difiere en Windows** | 7.09 |
| Arial (fallback) | 0.519 · 0.519 | 0.4501 | 0.556 | 1.24 | 29.71em ≈ 53ch | 1.107 | hhea | 5.79 |
| Georgia (fallback) | 0.481 · 0.481 | 0.4386 | 0.614 | 1.40 | 28.95em ≈ 47ch | 1.129 | hhea | 5.94 |

Conclusiones operativas:
1. **`Nch` no son N caracteres.** En fuentes proporcionales, `ch` sobrestima el carácter medio entre un 24 % (Arial) y un 40 % (Georgia): `65ch` ≈ 86 caracteres reales en Space Grotesk (fuera del rango 45–75). Medida correcta: `N × char_em` **en em**, o `≈ 0.74–0.76·N ch` en las proporcionales de referencia.
2. **Misma medida, distinta letra, distinto espacio.** DM Mono necesita un 26 % más de ancho que Inter para el mismo texto: tarjetas, columnas de prosa y número de tarjetas por fila se recalculan por tema, no se heredan.
3. **El peso cambia la anchura**: Syne Bold es un 25 % más ancha que la Regular. Un titular en bold necesita su propia medida (y su propio perfil).
4. **Tamaño aparente = x-height.** Space Grotesk a 16px se ve como Inter a 14.3px. Para igualar temas: `font-size-adjust: ex-height <xh>` o ajustar el cuerpo por `16 × xh_ref / xh`.
5. **El kerning estrecha el texto entre un 0.1 % y un 0.8 %** según fuente e idioma; los valores de la tabla lo incluyen. El idioma cambia `char_em` hasta un 5 % (el italiano es el más estrecho; el alemán y el portugués, los más anchos).
6. **El line box puede cambiar de plataforma.** Bebas Neue (y Calibri) no activan `USE_TYPO_METRICS` y sus `usWin*` difieren de `hhea`: en Windows la línea base cae en otra altura con el mismo `line-height`. Se corrige con `ascent-override`/`descent-override`/`line-gap-override` (`gridcalc.py font <archivo> --css`).

## 2. Interlineado y unidad vertical

**Modelo de blanco interlineal constante** (heurística calibrada, parámetros expuestos en `compose`):

```
lh = max( piso,  xh + W₀ + λ·(N/66 − 1) )      W₀ = 0.95em · λ = 0.2 · piso = 1.5 (WCAG 1.4.8)
                                                  validado frente a 13 referencias medidas: mejor que
                                                  cualquier reajuste en validación cruzada (calibracion.md)
u  = ⌈ fs · lh ⌉₄                               unidad vertical, ajustada a múltiplo de 4px
```

- Más x-height → más interlineado (la banda de minúsculas ocupa más; el blanco entre líneas debe conservarse).
- Más medida → más interlineado (el ojo necesita encontrar la línea siguiente).
- Titulares: el interlineado es **el menor múltiplo de `u/4` que no deja chocar la tinta** (`lh ≥ lh_min × tamaño`, con `lh_min` medido en la fuente para el idioma). Sale entre 1.1 y 1.25 sin elegirlo; la tabla la da `compose` para cada paso de la escala tipográfica. El bloque completo ocupa un número entero de `u`.
- El interlineado del cuerpo nunca baja del mínimo sin colisión de minúsculas (`compose` lo impone).
- **Todo espaciado vertical en `u`** (en CSS: `lh`/`rlh`). Si el cuerpo es fluido, `u` también: definir los espacios verticales en `rlh` garantiza que texto y espacio son congruentes por construcción.

## 3. Cadena de proximidad (márgenes, gutters y paddings)

Ley de proximidad: **lo que está dentro de un grupo está más cerca que lo que separa grupos**. Formalizado como una progresión geométrica anclada en una línea:

```
gutter  g  = u · δ                         (δ = factor de densidad)
padding p  = g / r        inner i = g / r²     micro μ = g / r³
section S  = g · r²
margin  m  = max(16px, g, μ_uso · ancho)   (en pantallas pequeñas: m = max(16, min(g, μ·ancho)) y g ≤ m)
orden obligatorio: micro < inner < padding < gutter ≤ margin < section
```

| Uso | r (razón de la cadena) | μ (margen/ancho) | medida | texto mín. en tarjeta |
|---|---|---|---|---|
| **Leer** (editorial, docs, artículo) | 2 (octava: grupos muy separados) | 16 px en móvil (calibrado); 1/12 en escritorio | **75** de media real (calibrado), rebajada por fuente hasta que ninguna línea pase de 80 | 34 car. |
| **Escanear** (marketing, landing, catálogo) | φ = 1.618 | 1/20 | 60 (sin calibrar) | 30 car. |
| **Operar** (app, dashboard, formularios) | 1.5 (quinta: denso pero ordenado) | 1/40 | 50 (sin calibrar) | 24 car. |

**Densidad** (`compacta · normal · amplia`) = un paso de la **escala tipográfica** (δ = r_tipo^−1, 1, r_tipo): la densidad espacial "rima" con el contraste tipográfico. Afecta a padding, gutter, margen y sección; **no** al cuerpo de texto (16px mínimo en web), ni a los objetivos táctiles (≥ 24px), ni al interlineado mínimo.

**Padding interno óptico.** La caja de línea añade blanco arriba (medio interlineado + ascendente − altura de mayúscula) y abajo (medio interlineado + descendente). Sin recorte:

```
δ_top = ((lh − (asc + desc)) / 2 + asc − cap) · fs
δ_bot = ((lh − (asc + desc)) / 2 + desc) · fs
padding-block ≈ padding-inline − (δ_top + δ_bot)/2      → mismo blanco visible en los cuatro lados
```

Con `text-box: trim-both cap alphabetic` el recorte lo hace el navegador y `padding-block = padding-inline`.

**Contenedor ⇄ contenido.** Un componente con padding p y texto de cuerpo fs necesita un ancho mínimo:

```
W_min(tarjeta) = N_tarjeta · cw · fs + 2p
```

Ese número decide el `minmax()` de las colecciones y cuántas tarjetas caben por fila (`cards/row` en `compose`). Con Space Grotesk/escanear: 30 · 0.489 · 16 + 2·14 = 263px ≈ 16.4rem (en el caso SYX, coherente con su `18rem`: ver `06-casos/syx.md`).

### Medida real: capacidad frente a líneas compuestas

Las palabras no se parten, así que una línea termina antes de llenar la medida y cada línea mide distinto. Una medida calculada como **capacidad** (`N × char_em`) promete N caracteres y da menos. `gridcalc.py lines` compone el texto como el navegador (corte *first-fit*, sin guiones, con los avances y el kerning medidos) y dice lo que sale. Space Grotesk, español, 18 px:

| Medida | Caracteres por línea (media) | El 90 % de las líneas | Línea más larga | Líneas cortas (< 85 %) |
|---|---|---|---|---|
| capacidad 45 (21.66em) | 41.2 | 35–46 | 49 | 11.6 % |
| capacidad 66 (31.77em) | 62.2 | 57–67 | 73 | 1.5 % |
| capacidad 75 (36.10em) | 71.2 | 66–76 | **80** | 1.0 % |
| **media 66 (33.61em)** | **66.0** | 60–71 | 74 | 0.2 % |

- La medida que se entrega es **la que da la media buscada** (`lines --measure 66` o, en `compose`, `--measure`). Sale entre un 5 y un 6 % más ancha que la capacidad.
- La **línea más larga** decide WCAG 1.4.8 (≤ 80): una capacidad de 75 ya produce líneas de 80.
- Las medidas estrechas sufren más: con 45 de capacidad, el 12 % de las líneas queda por debajo del 85 % de la medida (bandera irregular). Si la columna tiene que ser estrecha, valora `hyphens: auto` con `lang` (no simulado todavía).
- Comprobado en navegadores reales, línea a línea: Chrome y Edge cortan igual salvo empates por debajo de 1/64 px; Firefox, en el 99.67 % de las líneas (`lines --engine firefox`). Detalle en `metricas-de-fuente.md` §9.

`compose` usa estas medidas para el span de prosa y para el ancho mínimo de tarjeta (con un texto de tarjeta de 30 caracteres de media, la tarjeta pasa de 259 a 288 px en Space Grotesk y en 1024 px caben 2 por fila, no 3).

## 4. Columnas en uso (la retícula no cambia; cambia cuánta se usa)

```
n_uso = máx{ n divisor de N : (W − (n−1)·g)/n ≥ 1.5·g }      (≥ 4 cuando quepa)
span_prosa = mín{ k : k·c + (k−1)·g ≥ medida·cw·fs }
```

- Las líneas del grid de 12 existen siempre; en móvil se componen sobre 4 o 6 (divisores), de modo que lo que se coloca en 1/2 o 1/3 cae en las mismas líneas a cualquier tamaño.
- La prosa **se detiene en su span**; nunca ocupa el ancho completo en escritorio. El espacio sobrante es vacío activo, notas al margen o imagen.

## 5. Densidad de contenido

Tres medidas, de la más objetiva a la más perceptiva:

| Medida | Fórmula | Bandas orientativas |
|---|---|---|
| **Densidad textual** | caracteres / 1000px² = 1000 / (cw·fs · lh·fs) | Inter 16/24: 5.4 · DM Mono 16/24: 4.3 |
| **Ocupación** | área de elementos (con su padding) / área de la región | leer 0.35–0.55 · escanear 0.45–0.65 · operar 0.60–0.80 |
| **Carga por bloque** (ley L7) | elementos visibles por grupo | 3–7 por grupo (agrupar por encima) |

Cómo se usa: se fija el **uso** (decide r, μ, medida), se elige la **densidad** dentro de la banda, y la tipografía ajusta los anchos. Si la ocupación queda fuera de la banda, se corrige primero con agrupación (cadena de proximidad), después con spans, y solo al final con tamaño de letra.

## 6. Ritmo vertical y módulos de imagen

- Alturas de módulo en múltiplos de `u`: `block-size: round(up, X, 1rlh)` en imágenes y tarjetas para que el texto siguiente siga en la retícula.
- Proporción de una imagen en un span: `alto = n·u`, `n = round(ancho / (ratio · u))` — la imagen conserva aproximadamente su formato y el ritmo se mantiene.
- Separación entre secciones = `S` (cadena), separación titular→texto ≤ ½ de la separación texto→titular siguiente (el titular pertenece a lo que introduce).

## 7. Protocolo (lo que hace el agente)

1. Medir la fuente de cuerpo y la de titulares **desde sus archivos** → `gridcalc font <archivo> --save` (con `--sample` si hay texto real del producto). Revisar los avisos: line box divergente, `sxHeight` que no coincide con el glifo, caracteres que faltan.
2. Fijar uso y densidad → `gridcalc compose --font <perfil o archivo> --lang <idioma> --use … --density … --max …`.
3. Leer la cadena y la tabla por viewport: columnas en uso, span de prosa, tarjetas por fila.
4. Comprobar los avisos (orden de proximidad, gutter < línea entre columnas de texto, tarjeta que no cabe).
5. Componer encima (05-creatividad) sin romper la cadena ni la medida.
6. Validar con 07-critica (este módulo añade C10–C13).

**Comprobaciones duras añadidas:**
- **C10** Medidas de texto expresadas en caracteres **reales** (em × cw), no en `ch` sin corregir.
- **C11** Orden de proximidad: micro < inner < padding < gutter ≤ margen < sección, en todo el rango.
- **C12** Todo espaciado vertical es múltiplo de `u` (o de `u/2`), o está en `lh`/`rlh`.
- **C13** Las métricas tipográficas salen del archivo real de la fuente (perfil con SHA-1) y no quedan avisos abiertos (line box, colisión, caracteres que faltan).

> Los coeficientes de la heurística se calibran con referencias medidas y dentro de los límites de la evidencia (ley L8): `calibracion.md`. Calibrados: interlineado (confirmado), medida de leer, margen en móvil, espacio entre párrafos, escala de titulares (confirmada). Sin calibrar todavía: escanear, operar, r de la cadena, bandas de ocupación.
