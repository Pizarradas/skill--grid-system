# Métricas de fuente: qué guarda el archivo y cómo se usa para calibrar

Un archivo de fuente (`.ttf`, `.otf`, `.woff`, `.woff2`, `.ttc`) es una pequeña base de datos de tablas binarias. Casi todo lo que la retícula necesita saber de la letra está escrito ahí: el tamaño del em, las alturas que declara el diseñador, el contorno exacto de cada glifo, el avance de cada carácter, las parejas de kerning y, en una fuente variable, cómo cambia todo eso a lo largo de sus ejes. **El sistema lo lee directamente** y no estima nada que se pueda medir.

**Es agnóstico:** sirve para cualquier fuente, no para una lista cerrada. Los perfiles guardados en `perfiles/` son solo ejemplos ya medidos; una fuente nueva se mide desde su archivo con el mismo procedimiento.

```
python3 09-herramientas/gridcalc.py font Fuente.woff2                 # informe completo
python3 09-herramientas/gridcalc.py font Fuente.woff2 --save          # guarda el perfil en perfiles/
python3 09-herramientas/gridcalc.py font Fuente.woff2 --css --fallback arial
python3 09-herramientas/gridcalc.py font Fuente.woff2 --sample textos-del-producto.txt
python3 09-herramientas/gridcalc.py font Variable.ttf --instances          # todas las instancias con nombre
python3 09-herramientas/gridcalc.py font Variable.ttf --axes wght=650,opsz=18
python3 09-herramientas/gridcalc.py compose --font Fuente.woff2 --lang es …
```

El lector (`fontread.py`) y el descompresor WOFF2 (`brotlidec.py`) usan solo la biblioteca estándar de Python. Cada perfil guarda el SHA-1 del archivo medido, así que siempre se sabe de qué archivo exacto sale cada número.

---

## 1. Anatomía: cada parámetro, su tabla y su uso

Todas las medidas se expresan en **em** (unidades de fuente ÷ `unitsPerEm`), así que valen para cualquier tamaño: `px = em × font-size`.

### Vertical

| Parámetro | Dónde está en el archivo | Qué es | Para qué lo usa el sistema |
|---|---|---|---|
| `unitsPerEm` | `head` | Resolución del em (1000, 2048…) | Divisor de todo lo demás |
| ascender · descender · lineGap | `hhea` | Line box que construyen macOS y Linux | Posición de la línea base dentro de la línea; padding óptico |
| sTypoAscender · sTypoDescender · sTypoLineGap | `OS/2` | Line box "tipográfico" | Se usa en lugar de `hhea` cuando `USE_TYPO_METRICS` está activo |
| usWinAscent · usWinDescent | `OS/2` | Recorte vertical de Windows | Line box de Windows cuando `USE_TYPO_METRICS` está apagado |
| `USE_TYPO_METRICS` | `OS/2.fsSelection`, bit 7 | Indica qué juego deben usar los motores | Decide cuál de los anteriores es el line box web |
| sxHeight · sCapHeight | `OS/2` (v2+) | x-height y altura de mayúscula **declaradas** | Solo como contraste: el sistema usa la **medida** |
| x-height medida | contorno del glifo "x" (`glyf`/`CFF`) | Altura real de la banda de minúsculas | Tamaño aparente, interlineado, `font-size-adjust` |
| altura de mayúscula medida | contorno de "H" | Altura real de las mayúsculas | `text-box-trim`, primera línea base en impresión |
| overshoot | "o" frente a "x"; "O" frente a "H" | Lo que las formas redondas sobresalen para parecer iguales | Alineación óptica de bordes |
| ascendente y descendente medidos | b, d, h, k, l, f · g, j, p, q, y | Extremos reales de las minúsculas | Colisión entre líneas |
| altura de cifras | "0" frente a "H" | Cifras de caja alta (*lining*) o de caja baja (*oldstyle*) | Tablas y datos |

### Horizontal

| Parámetro | Dónde está | Qué es | Uso |
|---|---|---|---|
| avance de cada carácter | `hmtx` + `cmap` | Anchura que ocupa cada glifo | Base del ancho de texto |
| kerning | `GPOS` (lookup tipo 2 bajo la característica `kern`) o tabla `kern` | Ajuste de parejas (AV, To, «L…») | Ancho real del texto compuesto |
| `ch` | avance del "0" | Lo que CSS llama `1ch` | Convertir medidas `ch` ↔ caracteres reales |
| espacio, guiones, cifras | avances de U+0020, – , —, 0–9 | | Densidad; cifras tabulares o proporcionales |
| *sidebearings* | `xMin` y `avance − xMax` de H, O, n, o, a | Blanco a cada lado de la tinta | Espaciado óptico; padding lateral |
| xAvgCharWidth | `OS/2` | Media de **todos** los glifos | Solo informativo: no representa el texto |

### Estilo

`usWeightClass`, `usWidthClass` (OS/2), `italicAngle` e `isFixedPitch` (`post`), panose, y los ejes de variación (`fvar`). En una fuente variable, las medidas son las de la instancia por defecto.

---

## 2. El line box y la plataforma

El `line-height` de CSS reparte el espacio sobrante (el *half-leading*) por igual arriba y abajo del **área de contenido**, que mide `ascendente + descendente` según las métricas que use el motor. De ahí sale **dónde cae la línea base**, y con ella la alineación con una retícula base y el padding óptico.

| Motor | Qué métricas usa | Estado |
|---|---|---|
| Windows: Chrome 154, Edge 155, Firefox 157 | `usWinAscent`/`usWinDescent` si `USE_TYPO_METRICS` está apagado; OS/2 typo si está activo | **medido** (Bebas Neue 0.95/0.35, Calibri 0.952/0.269) |
| Linux: Chrome 155 (FreeType) | `hhea`, o OS/2 typo si `USE_TYPO_METRICS` está activo | **medido** (Bebas Neue 0.90/0.30, Calibri 0.75/0.25) |
| macOS (CoreText): Safari, Chrome | `hhea`, o OS/2 typo si `USE_TYPO_METRICS` está activo | según implementaciones conocidas; sin medir (no hay Mac en las pruebas) |

Si los dos juegos difieren, **la misma hoja de estilos coloca la línea base a distinta altura en Windows**. El informe lo marca como *line box divergente*. De las fuentes medidas, les pasa a **Bebas Neue** (0.05em) y **Calibri**.

**Corrección:** fijar el line box en `@font-face` con los valores web medidos. `gridcalc.py font <archivo> --css` lo genera:

```css
@font-face {
  font-family: "Bebas Neue";
  src: url("BebasNeue-Regular.woff2") format("woff2");
  ascent-override: 90%;
  descent-override: 30%;
  line-gap-override: 0%;
}
```

> Medido con `09-herramientas/verificar_navegador.py` (§9). La corrección con `*-override` es válida sea cual sea el motor, porque sustituye las métricas de la fuente.

---

## 3. Tinta medida, no declarada

Los valores de `OS/2` los escribe a mano quien publica la fuente y a veces no coinciden con el dibujo (Space Grotesk declara x-height 0.486, pero su "x" mide 0.489). El sistema mide los contornos:

- **TrueType (`glyf`)**: la caja que guarda cada glifo. En WOFF2 se reconstruye a partir de los puntos del contorno, como exige la especificación.
- **CFF (`.otf`)**: se interpretan los *charstrings* Type 2 y se calculan los **extremos exactos de cada curva cúbica**, no solo los puntos de control. También los glifos acentuados antiguos (`seac`) y el formato variable **CFF2**.

### Interlineado mínimo sin colisión

```
lh_min = (tinta más alta) − (tinta más baja)      en em, sin unidades como line-height
```

Por debajo de `lh_min`, la tinta de una línea toca la de la anterior. Se calcula con los caracteres de cada idioma (las letras de su tabla de frecuencias, en minúscula y en mayúscula, más la puntuación de su corpus) en tres niveles:

| Nivel | Qué cubre | Uso |
|---|---|---|
| `lower` | Solo minúsculas | **Suelo del interlineado del cuerpo** (`compose` lo impone) |
| `letters` | Todas las letras, también las mayúsculas acentuadas | **Interlineado de titulares** |
| `all` | Además, la puntuación (¿, ¡, paréntesis) | Peor caso |

En español, la colisión que decide suele ser "Ñ" o "Á" sobre "y" o "¿". `compose` coloca cada paso de la escala tipográfica en la retícula base: el interlineado de un titular es el menor múltiplo de `u/4` que cumple `≥ lh_min(letters) × tamaño`.

---

## 4. El ancho del texto: corpus + kerning

El número que más pesa en la retícula es **`char_em`**, el avance medio por carácter del texto corrido. De él salen la medida de prosa, el ancho mínimo de tarjeta y las columnas en uso. Se mide así:

1. **Corpus por idioma** (`09-herramientas/corpus/`): unos 30 000 caracteres de prosa de dominio público por idioma (es, en, fr, de, it, pt), sin cabeceras ni versos. Fuente de cada uno en su primera línea.
2. El texto se **compone como lo haría un navegador**: avance de cada glifo según `cmap` + `hmtx`, más el kerning de cada pareja según `GPOS` (o `kern`).
3. `char_em = (Σ avances + Σ kerning) / nº de caracteres / unitsPerEm`.

**Contraste:** el mismo valor se recalcula con un modelo independiente (`corpus/frecuencias.json`, frecuencias de letras de Wikipedia, más la proporción de espacios, mayúsculas, cifras y puntuación del corpus). La diferencia entre ambos (`gap_%`) es la incertidumbre del modelo: en las fuentes medidas queda por debajo del 1 % en todos los idiomas.

**El texto real manda.** Si el producto tiene textos propios (una interfaz con muchas cifras, mayúsculas o siglas), `--sample archivo.txt` mide exactamente ese texto con esa fuente y sustituye al corpus.

| Efecto | Magnitud medida |
|---|---|
| Kerning | −0.1 % a −0.8 % del ancho (Inter −0.11 %, Space Grotesk −0.57 %, Playfair −0.65 % en español) |
| Idioma | hasta un 5 % (en Space Grotesk, italiano 0.466 frente a portugués 0.490) |
| Ligaduras por defecto (`liga`, `clig`, `calt`) | ≤ 0.04 %: despreciable. El sistema no las aplica |
| Peso | Syne Bold es un 25 % más ancha que Syne Regular: cada peso necesita su perfil |

---

## 5. Espacios: blanco que ya trae la letra

- **Blanco inicial** (`start_white`): media del lado izquierdo de la primera letra de cada palabra del corpus. Un párrafo dentro de una caja ya empieza con ese blanco. Para alinear la **tinta** (no la caja) con una línea de la retícula, `padding-inline-start: calc(var(--padding) - <start_white>em)`. `compose` lo calcula.
- **Padding vertical óptico**: el line box añade blanco por encima de la altura de mayúscula (`half-leading + ascendente − mayúscula`) y por debajo de la línea base (`half-leading + descendente`). `compose` lo resta, o usa `text-box: trim-both cap alphabetic`, que recorta a la altura de mayúscula y a la línea base.
- ***Sidebearings* de H, O, n y o**: son la referencia clásica del espaciado (método Tracy). Si una fuente tiene un espaciado muy abierto o muy cerrado respecto a otra, se nota aquí antes que en el ancho medio.

---

## 6. Fallback sin salto de maquetación (CLS)

Mientras carga la fuente web, el navegador pinta con una fuente local. Para que ocupe **el mismo espacio**:

```
size-adjust        = char_em(fuente web) / char_em(fallback)       mismo idioma, con kerning
ascent-override    = ascendente web  / size-adjust
descent-override   = descendente web / size-adjust
line-gap-override  = lineGap web     / size-adjust
```

`gridcalc.py font <archivo> --fallback arial` genera la regla `@font-face` (nombres locales incluidos). Comparar anchos medios de **texto real** es más preciso que comparar `xAvgCharWidth`, que promedia todos los glifos de la fuente. Hay perfiles medidos de Arial, Times New Roman, Georgia, Verdana, Segoe UI y Calibri.

---

## 7. Fuentes variables

Una fuente variable guarda un diseño por defecto y las instrucciones para moverlo por sus **ejes** (`wght` peso, `wdth` anchura, `opsz` tamaño óptico, `slnt` inclinación y ejes propios). El sistema calcula la fuente **en cualquier punto** de ese espacio:

| Paso | Tabla | Qué hace |
|---|---|---|
| Ejes e instancias | `fvar` | Rango de cada eje e instancias con nombre ("Bold", "Condensed Light"…) |
| Normalización | `fvar` + `avar` | Valor de diseño → coordenada −1…1, redondeada a F2Dot14 como hacen HarfBuzz y FreeType |
| Contornos | `gvar` (TrueType) · `CFF2` | Deltas por punto, con interpolación de los puntos no tocados (IUP) y componentes |
| Avances | `HVAR` (o los puntos fantasma de `gvar`) | Delta por glifo, redondeado a unidades enteras como los motores (`floor(x + 0.5)`) |
| Métricas verticales | `MVAR` | Ascendente, descendente, x-height, altura de mayúscula… en ese punto |
| Kerning | `GPOS` + `GDEF` | Las parejas también varían con los ejes |

```
gridcalc.py font Inter.ttf --instances         # tabla: cómo cambian x-height, char_em, lh_min… por instancia
gridcalc.py font Inter.ttf --instance Bold --save
gridcalc.py compose --font RobotoFlex.ttf --axes wght=650,wdth=80,opsz=18
```

**Comprobación cruzada:** Inter variable en su instancia Regular da `char_em` 0.4770, y en Medium 0.4804: los mismos valores, a cuatro decimales, que los archivos estáticos de Inter Regular y Medium. Lo mismo pasa con Source Sans 3 (CFF2 variable frente a CFF estático): 0.4141 en ambos. Son dos caminos independientes (contornos guardados frente a contornos reconstruidos con deltas) que llegan al mismo número.

El peso cambia la anchura de forma continua: en Inter, de Thin a Black `char_em` pasa de 0.455 a 0.496 (+9 %), y una medida de 66 caracteres de 30.1 a 32.7em. Por eso cada peso de texto que se use necesita su punto medido.

### Tamaño óptico automático

Si la fuente tiene eje `opsz`, **el navegador no dibuja la instancia por defecto**: con `font-optical-sizing: auto`, que es el valor inicial, pone `opsz` igual al tamaño de letra en px de CSS (CSS Fonts 4 §8.1: "close to the used value for font-size"; Chrome, Firefox y Safari usan px). Cada tamaño es, en la práctica, un diseño distinto:

| Inter variable | `char_em` | x-height |
|---|---|---|
| instancia por defecto (opsz 14) | 0.4770 | 0.546 |
| cuerpo a 16 px | 0.4722 (−1.0 %) | 0.542 |
| cuerpo a 18 px | 0.4675 (−2.0 %) | 0.539 |
| titular a 32 px o más (máximo del eje) | 0.4339 (−9.0 %) | 0.516 |

En Roboto Flex, a 48 px el ancho medio baja un 13 %. Por eso el sistema **mide cada tamaño en su propio `opsz`**: `compose` mide el cuerpo en cada viewport y cada paso de titular a su tamaño (la tabla de titulares muestra `opsz` y `char_em` de cada uno); `web --typeface` mide al tamaño de `--font`; `font --size 18` mide como se dibuja a 18 px.

- Se desactiva igual que en CSS: con un `opsz` explícito en `--axes` (como `font-variation-settings`) o con `--optical-sizing none` (como `font-optical-sizing: none`).
- Con `--instance`, la instancia fija los demás ejes y `opsz` sigue al tamaño, igual que hace el navegador con `font-weight`.
- Un perfil guardado está congelado en un `opsz`; `compose` lo avisa y pide el archivo.
- En impresión (`print --typeface --size`), `opsz` = cuerpo en pt (convención de las aplicaciones de maquetación; pendiente de verificar en InDesign).

## 8. Escrituras

El sistema detecta la **escritura dominante** del texto por las propiedades Unicode de sus letras, y con ella:

1. **Aplica el kerning de esa escritura.** Las tablas `GPOS` agrupan sus reglas por escritura (`latn`, `cyrl`, `grek`, `arab`…); se usan las del texto, con DFLT y latn como respaldo, igual que el *shaper*.
2. **Mide la tinta con los glifos de referencia de su alfabeto**: latino x/H/o/O, cirílico х/Н/о/О, griego κντ/Η/ο/Ο (mediana). Una fuente sin alfabeto latino ya no depende de "x" y "H".
3. **Comprueba la cobertura.** Si a la fuente le falta más del 2 % de los caracteres de un idioma, ese idioma no se mide: lo dibujaría una fuente de respaldo y el número no sería de esta fuente. El informe lo dice.

Corpus incluidos: español, inglés, francés, alemán, italiano, portugués, **griego** y **ruso**. Para cualquier otro idioma o escritura: `--sample texto.txt`.

| Tipo de escritura | Ejemplos | Cómo se mide | Precisión medida frente a HarfBuzz |
|---|---|---|---|
| Alfabetos | latino, cirílico, griego, armenio, georgiano, hebreo sin vocales | avances + kerning de la escritura | **exacta** (0.0000 %) |
| CJK | chino, japonés, coreano | avances + kerning | **exacta** (0.00 % en japonés) |
| Complejas | árabe, índicas (devanagari, bengalí…), tailandés, jemer, birmano, tibetano; cualquier texto con marcas combinantes | ***shaping* completo** con HarfBuzz si está instalado (`pip install uharfbuzz`) | **exacta** con HarfBuzz |

**Por qué las complejas necesitan *shaping*:** en árabe cada letra cambia de forma según sus vecinas (inicial, media, final), hay ligaduras obligatorias (lam-alif) y marcas sin avance. Sumar avances de las formas aisladas **sobrestima el ancho entre un 21 y un 25 %** (medido en Noto Sans Arabic, Segoe UI y Arial). Por eso, sin HarfBuzz, el informe marca ese valor como **no fiable** y `compose` se niega a calibrar con él. Con HarfBuzz instalado, el texto se compone con el mismo motor que Chrome y Firefox, también en WOFF2 y en cualquier punto de una fuente variable.

**CJK:** el ancho por carácter es exacto, pero la x-height y la medida de 45–75 caracteres son convenciones latinas y no se aplican. El informe lo avisa; la medida de línea de estas escrituras se fija con el criterio tipográfico de cada idioma (pendiente de documentar en el sistema).

## 9. Precisión verificada

`09-herramientas/verificar.py` repite estas comprobaciones. Resultados de la versión actual (2026-10-11):

| Comprobación | Referencia | Resultado |
|---|---|---|
| Campos de `head`, `hhea` y `OS/2`, todos los avances, `cmap` completo | fontTools 4.66 | idénticos en 35 fuentes: WOFF2, TTF, TTC, CFF, CFF2, estáticas y variables |
| Caja de **cada glifo** en el diseño por defecto (TrueType, WOFF2 transformado, CFF con curvas) | fontTools (`glyf`, `BoundsPen`) | diferencia máxima 0.0000 unidades |
| Caja y avance de cada glifo en 3 instancias de 11 fuentes variables (hasta 13 ejes, con `avar`) | fontTools (`getGlyphSet(location)`) | ≤ 0.020 unidades (fontTools no redondea las coordenadas a F2Dot14; los motores sí) |
| Ancho de texto con kerning, ~30 000 caracteres por idioma (es, en, fr, de, it, pt, el, ru) e instancia | HarfBuzz 0.56 (el motor de Chrome y Firefox) | 281 de 282 comparaciones en 0.0000 %; la otra, −0.0059 % (sustitución contextual de Roboto Flex en griego, §10) |
| Árabe compuesto con HarfBuzz desde el sfnt reconstruido (TTF, WOFF2, instancia variable) | HarfBuzz sobre el archivo original | 0.0000 % |
| Total `verificar.py` (2026-10-11) | — | **502/502** comprobaciones en 35 fuentes; 26/26 sin dependencias |
| Descompresión Brotli (WOFF2) | `brotli` 1.2 | idéntica byte a byte: 15 fuentes y 864 casos de *fuzzing*, incluidos diccionario y transformaciones |

### En navegadores reales

`09-herramientas/verificar_navegador.py` abre una página de prueba en cada navegador instalado (sin ventana y con un perfil temporal: no toca el navegador que tengas abierto) y compara lo que maqueta con lo que predice el sistema. Ejecución del 2026-10-11, 12 fuentes (estáticas, variables TrueType y CFF2, latinas, griegas y cirílicas), texto de 4 idiomas a 16 y 100 px:

| Comprobación | Chrome 154 · Edge 155 (Windows) | Firefox 157 (Windows) | Chrome 155 (Linux) |
|---|---|---|---|
| Line box por plataforma | `usWin*` — **como se predice** | `usWin*` — **como se predice** | `hhea` — **como se predice** |
| Ancho del texto (74 medidas) | ≤ 0.1 %; fuentes variables **CFF2**: −0.1 a −0.6 % (ver abajo) | **≤ 0.052 %** | *hinting*: −1.2 a +1.3 % a 16 px (monoespaciada: +4.2 %); con `geometricPrecision`, **≤ 0.026 %** |
| `opsz` automático | **confirmado** (sin él, el error sería de −1 % a −21 %) | **confirmado** | **confirmado** |
| `text-box: trim-both cap alphabetic` | recorta a la altura de mayúscula **declarada** (`OS/2`) | igual | igual |
| Fallback con `size-adjust` (37 medidas) | residuo por idioma **predicho con ≤ 0.54 puntos** | ≤ 0.22 puntos | sin Arial ni clones instalados: no aplica |
| **Cortes de línea** (corpus español a 16 px en la medida de media 66; ~5 830 líneas) | **idénticos** salvo empates por debajo de 1/64 px (2 párrafos de Calibri): 99.8 %; con Source Serif 4 VF (CFF2), 77.9 % por su ancho | **99.67 %** idénticas (el resto, empates por debajo de 1/60 px) | 58.8 % con *hinting*; **99.78 %** con `geometricPrecision` |

Lo que enseñó la prueba, y ya está incorporado:

- **Firefox compone palabra a palabra** salvo que una regla por defecto que no sea de kerning (sustitución, marcas…) implique al espacio. En ese caso, las parejas de kerning con espacio no se aplican. El perfil guarda `cw_firefox` cuando cambia el ancho (Space Grotesk: +0.21 %) y `compose` lo avisa.
- **`text-box-trim` usa la altura de mayúscula declarada**, no la dibujada. Si difieren (Calibri: 0.6318 frente a 0.6348), `compose` dice cuánto sobresale la tinta.
- **El fallback es exacto en un idioma.** En los demás queda un residuo que el sistema predice (Space Grotesk/Arial en inglés: predicho −2.27 %, medido −2.27 %). Con eje `opsz`, se calcula al tamaño del cuerpo (`font --size`). La regla incluye clones métricamente compatibles (Liberation Sans o Arimo para Arial, Carlito para Calibri, Gelasio para Georgia…), porque Linux no trae Arial.
- **Firefox corta las líneas con anchos redondeados a su unidad interna**, 1/60 px: cada avance y cada valor de kerning por separado. Con ese modelo (`lines --engine firefox`), el 99.67 % de las líneas son idénticas; sin él, el 98.3 %.
- **Cortes de línea:** el simulador (`linebreak.py`) corta como el navegador (*first-fit*, oportunidades de corte de Unicode UAX #14 para prosa, incluida la de después de raya). Las diferencias que quedan son empates de menos de una unidad interna del motor.
- **Hinting en Linux**: Chrome redondea cada avance (con su kerning) a píxeles enteros. A 16 px DM Mono pasa de 9.6 a 10 px por carácter. `text-rendering: geometricPrecision` lo desactiva y el ancho coincide con el previsto. Es una decisión de diseño: más fidelidad al dibujo frente a más nitidez en pantallas de baja densidad.
- **Chrome y Edge en Windows con fuentes variables CFF2** (Source Serif 4 VF) dan un texto entre un 0.1 y un 0.6 % más estrecho que HarfBuzz, Firefox y Chrome en Linux, que coinciden con el sistema. Es una particularidad de ese motor con CFF2; con las variables TrueType (Inter, Roboto Flex) Chrome en Windows es exacto.

## 10. Límites conocidos

- **Rasterizado.** Las medidas son las del diseño. Medido: Chrome en Linux redondea los avances a píxeles (−1.2 a +1.3 % a 16 px; +4.2 % en monoespaciadas) salvo con `text-rendering: geometricPrecision`; Chrome, Edge y Firefox en Windows no (≤ 0.1 %). macOS y Safari no se han medido.
- **Chrome/Edge en Windows con variables CFF2**: hasta −0.6 % de ancho (§9).
- **CSS que cambia el texto**: `letter-spacing`, `word-spacing`, `font-kerning: none`, `font-feature-settings`, `text-transform` y la negrita sintética no están en el perfil. Si se usan, se mide con `--sample` y se suma su efecto.
- **Escrituras complejas sin HarfBuzz**: el ancho no es fiable (ver §8) y el sistema no lo usa para calibrar.
- **Sustituciones contextuales en alfabetos**: se aplican las sustituciones simples de las *features* activas por defecto (`rvrn`, `ccmp`, `locl`), no las contextuales ni las ligaduras. Efecto medido: como máximo −0.006 % (Roboto Flex en griego, por un `locl` contextual de la propia fuente); en las otras 31 fuentes, 0. Con HarfBuzz instalado se puede componer cualquier texto con `--sample` y comparar.
- **Idioma dentro de la escritura**: se usan las reglas por defecto de la escritura, como un navegador sin atributo `lang`. Las formas localizadas por idioma (búlgaro, serbio, rumano…) que dependen de `lang` no se aplican.
- **Fuentes variables**: no se admite `avar` versión 2 (rara). Las *feature variations* (sustituciones que cambian con los ejes) no afectan al kerning medido.
- **CFF**: `seac` con los juegos de caracteres Expert (muy raro). El informe lo indica.
- **Colecciones (TTC)**: se lee la primera cara (`index` en el código). Las colecciones WOFF2 no se admiten.
- **Texto vertical** (CJK en vertical, `vmtx`): no se mide.
- **Fuentes sin contornos** (solo mapas de bits o color `sbix`/`CBDT`): la tinta no se mide; se usan los valores declarados.
- **Fuentes con datos defectuosos**: si una fuente apunta a deltas que no existe (le pasa a Segoe UI Variable en su kerning), se toma delta 0, como HarfBuzz.
