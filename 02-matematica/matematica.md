# 02 — Matemática del grid

Todas las fórmulas tienen su comando en `09-herramientas/gridcalc.py`. Notación: `W` ancho disponible, `n` columnas, `g` gutter, `m` margen, `c` columna, `L` interlineado.

---

## 1. Ecuación fundamental de un grid de columnas

```
W = 2m + n·c + (n − 1)·g
c = (W − 2m − (n − 1)·g) / n
span(k) = k·c + (k − 1)·g          // ancho de un elemento que ocupa k columnas
pitch  = c + g                      // distancia entre inicios de columna
```

Restricciones recomendadas:

| Restricción | Valor | Por qué |
|---|---|---|
| `c / g` | ≥ 1.5 (ideal 2–4) | si `c < g`, un span de 1 es menor que el hueco: la rejilla deja de leerse |
| `m / g` | ≥ 1 | el margen debe separar más que el gutter, o la página parece cortada |
| medida | 45–75 caracteres (~66) | `chars ≈ span / (font_px × 0.5)`; 0.45–0.55 según la fuente |
| span mínimo interactivo | ≥ 24px (WCAG 2.5.8) | un control debe caber en una celda |

**Divisibilidad.** Elige `n` por sus divisores, no por costumbre:

| n | divisores útiles | nota |
|---|---|---|
| 4 | 1, 2, 4 | móvil, tablet vertical |
| 5 | 1, 5 | asimétrico natural (2+3), áureo aproximado 3:2 |
| 6 | 1, 2, 3, 6 | editorial clásico |
| 8 | 1, 2, 4, 8 | áureo 5+3 (+3 %), M3 en tamaños medianos |
| 9 | 1, 3, 9 | Van de Graaf (novenos) |
| 10 | 1, 2, 5, 10 | porcentajes 10 % |
| 12 | 1, 2, 3, 4, 6, 12 | MCM de 3 y 4 → máxima flexibilidad, 7+5 para "casi áureo" (−13.5 %) |
| 13 | 1, 13 | áureo 8+5 (−1.1 %), fuerza asimetría |
| 16 | 1, 2, 4, 8, 16 | dashboards densos |
| 24 | 1, 2, 3, 4, 6, 8, 12, 24 | sistemas de producto amplios |

`09-herramientas/gridcalc.py ratio --ratio golden --columns 5,8,12,13` calcula el mejor reparto entero para cualquier proporción.

## 2. Proporciones de referencia

| Nombre | Valor | Origen / uso |
|---|---|---|
| 1:1 | 1 | cuadrado; módulo neutro |
| 2:3 | 1.5 | quinta justa; página clásica de libro |
| 3:4 | 1.333 | cuarta justa; fotografía, tablet |
| √2 | 1.4142 | ISO 216 (A4…): al doblar por la mitad conserva la proporción |
| φ (áurea) | 1.6180 | φ = (1+√5)/2; `φ² = φ + 1`; `1/φ = φ − 1` |
| √3 | 1.7321 | triángulo equilátero, rejillas isométricas (30°) |
| 16:9 | 1.7778 | pantallas, diapositivas |
| 2:1 | 2 | octava; principal/secundaria (ley L2) |
| √5 | 2.2361 | rectángulo dinámico; = φ + 1/φ |

**Rectángulos dinámicos (raíz).** El rectángulo √n se construye abatiendo la diagonal del √(n−1). Un rectángulo √n se divide exactamente en n rectángulos √n semejantes → permite subdividir el formato **sin cambiar de proporción** (útil para que los módulos tengan la proporción de la página).

**Escala cromática de proporciones de página (Bringhurst, *Elements of Typographic Style*, cap. 8):** ancho:alto = 1:1, 15:16, 8:9, 5:6, 4:5, 3:4, 1:√2, 2:3, 5:8, 3:5, 9:16, 8:15, 1:2 (unísono → octava), más la sección áurea 1:1.618 tratada aparte. Las mismas proporciones sirven para la página y para la caja.

**Modulor (Le Corbusier, versión 1.83 m):** serie roja … 43.2 · 69.8 · 113 · 183 cm; serie azul (doble) … 53.4 · 86.3 · 139.7 · 226 cm; cada término = anterior × φ. Útil como escala de tamaños de bloques en entornos físicos (expositores, señalética).

**Fibonacci** aproxima φ con enteros: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144. Totales Fibonacci (8, 13, 21) dan grids donde el reparto áureo es entero.

## 3. Escalas (tipo, espacio, tamaños)

```
geométrica (modular):  v(i) = base · r^i
aritmética (lineal):   v(i) = base · i            // 4pt / 8pt
armónica:              v(i) = base / i            // divisiones de un todo: 1, 1/2, 1/3…
Fibonacci:             v(i) = v(i−1) + v(i−2)
```

Ratios musicales usados en tipografía (Tim Brown, *modular scale*): segunda menor 16:15, segunda mayor 9:8, tercera menor 6:5, tercera mayor 5:4, cuarta 4:3, cuarta aumentada √2, quinta 3:2, sexta menor 8:5, áurea, sexta mayor 5:3, séptima menor 16:9, séptima mayor 15:8, octava 2:1.

Ley L2: **una escala por función** (tipo modular, espacio lineal, layout por proporción) y nunca dos escalas para la misma función. `09-herramientas/gridcalc.py scale --snap 4` avisa cuando redondear a la unidad colapsa pasos.

## 4. Interpolación fluida (web)

Valor lineal entre dos anchos `(v1, y1)` y `(v2, y2)`:

```
pendiente  s = (y2 − y1) / (v2 − v1)
intercepto b = y1 − s · v1
CSS:  clamp(min(y1,y2), b/16 rem + s·100 vw, max(y1,y2))
```

- Con `cqi` en vez de `vw` el valor depende del contenedor (componente portable).
- El término en `rem` conserva la respuesta al zoom; si `y2/y1 > 2.5` en texto, el zoom al 200 % puede no cumplirse (WCAG 1.4.4).
- **Escalas fluidas (Utopia):** se define la escala en el mínimo (base₁, r₁) y en el máximo (base₂, r₂) y se interpola cada paso i entre `base₁·r₁^i` y `base₂·r₂^i`. Así la jerarquía se vuelve más contrastada en pantallas grandes sin breakpoints.

`09-herramientas/gridcalc.py clamp --min 16 --max 24 --vmin 360 --vmax 1440 --check 320,768,1440`

## 5. Rejilla base (ritmo vertical)

```
unidad vertical u = L (interlineado del cuerpo)
todo espacio vertical = k · u           (k entero o, como mucho, k/2)
alto de campo  = f · u                   (f líneas)
alto de área   = R·f·u + (R − 1)·q·u     (R filas, q líneas de calle; q suele ser 1)
```

Para otros cuerpos: interlineado = u · (p/q) con p/q simple (2 líneas de titular cada 3 de texto, etc.), o bien el titular ocupa un número entero de líneas base aunque su interlineado no sea múltiplo.

## 6. Grid compuesto (superposición)

Superponer divisiones `d1, d2, …` produce una retícula de `MCM(d1, d2, …)` unidades. Las líneas comunes son **ejes fuertes**; las exclusivas, tensiones.

| combinación | unidades | líneas distintas | lectura |
|---|---|---|---|
| 2 + 3 | 6 | 3 interiores (1/3, 1/2, 2/3), ninguna común | clásico de revista |
| 3 + 4 | 12 | 5 interiores, ninguna común | el "12" de la web es esto |
| 4 + 6 | 12 | 7 interiores, 1/2 común | eje central fuerte |
| 2 + 3 + 5 | 30 | 7 interiores, ninguna común | muy expresivo |
| 3 + 5 | 15 | 6 interiores, ninguna común | fuerte tensión, posters |

Karl Gerstner (*Capital*, 1962): un campo de **58 unidades** que admite a la vez 1, 2, 3, 4, 5 y 6 columnas con gutter de 2 unidades — se cumple porque `58 = 6c + 5·2` con c = 8, `58 = 5·10 + 4·2`, `58 = 4·13 + 3·2`, `58 = 3·18 + 2·2`, `58 = 2·28 + 2` → es decir, `(58 + 2)` = 60 es divisible por 1…6. **Regla general:** un campo de `T` unidades con gutter `G` admite `n` columnas iguales si `(T + G)` es divisible por `n`. Para `n ∈ {1..k}`, `T = MCM(1..k)·j − G`.

`09-herramientas/gridcalc.py compound --divisions 3,4`

## 7. Progresiones de pistas (grids no uniformes)

```
Fibonacci:   1fr 1fr 2fr 3fr 5fr          (espejo: …5fr 3fr 2fr 1fr 1fr)
geométrica:  1fr r fr r² fr …             (r = 4/3, φ…)
armónica:    1fr 1/2fr 1/3fr …            (perspectiva, "fuga")
```

Útiles para composiciones con dirección (crecimiento hacia un foco). `09-herramientas/gridcalc.py tracks --series fibonacci --count 5 --mirror odd`.

## 8. Ritmos de colocación

Distribuir `k` acentos (tarjetas grandes, imágenes, rupturas) entre `n` posiciones lo más uniformemente posible = **ritmo euclídeo E(k, n)** (algoritmo de Bjorklund): `item i acentuado ⇔ (i·k) mod n < k`.

E(3,8) = `x..x..x.` (tresillo), E(5,12) = `x..x.x..x.x.`, E(2,5) = `x..x.`. Da patrones regulares pero no monótonos, y se traduce a `:nth-child(8n + 1), …`. `09-herramientas/gridcalc.py rhythm --k 3 --n 8`.

## 9. Cánones de página (print)

| Canon | Márgenes (interior : cabeza : exterior : pie) | Caja |
|---|---|---|
| Van de Graaf / Villard / Rosarivo (novenos) | W/9 : H/9 : 2W/9 : 2H/9 → 1 : 1 : 2 : 2 en sus unidades | 2/3 × 2/3 del formato; misma proporción que la página |
| Tschichold "canon áureo" | igual, sobre página 2:3 → 2 : 3 : 4 : 6 | alto de caja = ancho de página |
| Duodécimos | W/12 : H/12 : 2W/12 : 2H/12 | 3/4 × 3/4, más denso |
| Proporción 2:3:4:6 libre | escalar k para un ancho de caja objetivo | la caja no siempre conserva la proporción |

`09-herramientas/gridcalc.py canon --page 140,210`

## 10. Grid modular de Müller-Brockmann (algoritmo)

1. Fija formato, cuerpo y **interlineado L**.
2. Fija márgenes provisionales → alto disponible `Hₐ`.
3. Líneas disponibles `N = ⌊Hₐ / L⌋`.
4. Para R filas y q líneas de calle: `f = ⌊(N − (R−1)·q) / R⌋` líneas por campo.
5. Alto real `= (R·f + (R−1)·q)·L`; la diferencia con `Hₐ` se suma al **margen inferior**.
6. Gutter de columna = L (o 1 em) para que columnas y calles "midan" lo mismo.
7. El primer renglón de cada campo se alinea por **altura de mayúscula** con el borde del campo; el último, por línea base.

`09-herramientas/gridcalc.py print --page 210,297 --margins 20,30,20,25 --leading 12 --columns 6 --rows 3,4,6`
