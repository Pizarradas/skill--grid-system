# Calibración: los modelos frente a referencias medidas

Las métricas de la letra se leen del archivo y se comprueban en el navegador (`metricas-de-fuente.md`). Pero las **decisiones** que se toman con ellas (cuánto interlineado, qué medida, qué margen) salen de modelos con coeficientes. Este módulo explica cómo se ajustan esos coeficientes: **hacia lo que hacen referencias tipográficas reconocidas, sin salir nunca de los límites que fija la evidencia**.

```
python3 09-herramientas/medir_sitio.py URL… --uso reading --grupo editorial   # medir referencias
python3 09-herramientas/calibrar.py                                           # analizar
python3 09-herramientas/calibrar.py --escribir                                # escribir calibracion.json
python3 09-herramientas/gridcalc.py compose … --sin-calibracion               # comparar con los valores previos
```

---

## 1. Dos tipos de fuente, dos papeles

| Papel | Qué es | Se calibra |
|---|---|---|
| **Límites** | Evidencia y normas: WCAG 1.4.8 (líneas ≤ 80 caracteres, interlineado ≥ 1.5), WCAG 1.4.10 y 1.4.12, el rango 45–75 de Bringhurst | **No.** Son suelos y techos fijos (ley L9) |
| **Referencias** | Lo que aplican sitios con buena tipografía, medido en un navegador real | **Sí.** Los coeficientes se acercan a ellas dentro de los límites |

## 2. Cómo se miden las referencias

`medir_sitio.py` abre cada página en Chrome sin ventana (protocolo DevTools, perfil temporal) a 375 y 1440 px, y mide el texto corrido, es decir, el grupo de párrafos con más caracteres:

- tamaño, interlineado y peso del cuerpo, y la fuente que se dibuja de verdad;
- x-height y `char_em` **del archivo de la fuente**: descarga las fuentes web de la página y las mide con `fontprofile` en el `opsz` del tamaño. Si la página usa una fuente genérica o no se encuentra el archivo, usa una medida de canvas a 1000 px, marcada como aproximada;
- **caracteres por línea de las líneas reales**, carácter a carácter, con `Range`;
- espacio entre párrafos, márgenes a 375 px, y tamaño, interlineado y espacio de h1–h3.

Cada medición queda en `09-herramientas/referencias/<sitio>.json`, con la URL y la fecha.

## 3. Referencias usadas (medidas el 2026-10-12)

| Grupo | Páginas |
|---|---|
| Editorial | The Guardian · BBC News · elDiario.es · Practical Typography (M. Butterick) · Smashing Magazine · Wikipedia (inglés) · Wikipedia (español) |
| Documentación y sistemas de diseño | MDN · GOV.UK Service Manual · GOV.UK Design System · Material 3 · IBM Carbon · Apple HIG · GitHub Docs · web.dev |

Las 15 cuentan como uso **leer** (editorial, documentación, artículo), según la definición del sistema (`composicion-densidad.md` §3). No hay referencias de **escanear** (marketing, landing, catálogo) ni de **operar** (aplicaciones, paneles), así que esos perfiles siguen sin calibrar.

## 4. Resultados

### Interlineado: el modelo actual se confirma

Se compararon cuatro modelos por **validación cruzada dejando uno fuera** (13 referencias con fuente conocida):

| Modelo | Error (RMSE de line-height) |
|---|---|
| **actual**: `lh = xh + 0.95 + 0.2·(N/66 − 1)` | **0.106** |
| reajustado (W₀, λ) | 0.132 |
| reajustado (a, b, λ) | 0.153 |
| constante (mediana) | 0.147 |

Los ajustes con más parámetros explican mejor las referencias que ya conocen y peor la que dejan fuera: con 13 puntos, se sobreajustan. **El modelo actual predice mejor y se mantiene.** El suelo de 1.5 también se mantiene, aunque 6 de las 15 referencias componen por debajo (GOV.UK 1.32, The Guardian 1.40, BBC 1.44, Practical Typography 1.45, Apple 1.47). La práctica habitual no rebaja un requisito de accesibilidad.

### Medida: más larga, con techo por fuente

| | Caracteres por línea reales (1440 px) |
|---|---|
| Editorial | mediana **74.4** (69–85) |
| Documentación | mediana **85.0** (37–116); 6 de 8 tienen líneas de más de 80 |
| Las 15 | mediana 76.5 |

La media objetivo de **leer** pasa de 66 a **75**, el techo de Bringhurst. Además, `compose` la **baja fuente a fuente** hasta que ninguna línea compuesta pase de 80. Con Space Grotesk queda en 71, con líneas entre 66 y 76 y la más larga de 80. 10 de las 15 referencias tienen alguna línea de más de 80: la referencia marca la dirección y el límite, el tope.

### Margen en móvil, párrafos y titulares

| Modelo | Antes | Referencias | Ahora |
|---|---|---|---|
| Margen a 375 px (leer) | μ = 1/12 → 31 px | mediana **16 px** (10–27) | 16 px (el mínimo de *reflow*) |
| Espacio entre párrafos | no se calculaba | mediana **0.65 líneas** (0.50–1.00) | ¾ de línea en la retícula `u/4` (`margin-block: 0.75lh`) |
| Escala tipográfica | 1.25 por paso | h2/cuerpo 1.5 → **1.225** por paso | 1.25 confirmado (diferencia del 2 %) |
| Interlineado de h2 | regla de colisión en `u/4` | mediana **1.25** | confirmado: la regla da 1.20–1.24 |
| Cuerpo a 1440 px | 16→18 px | mediana **17 px** (16–21.8) | sin cambio |

## 5. Lo que no se ha calibrado

- **Escanear y operar**: no hay referencias. Para calibrarlos, mide páginas de ese tipo con `--uso scanning` u `--uso operating`.
- **Margen en escritorio**: las referencias centran una columna con ancho máximo, así que su margen a 1440 px no se puede comparar con el del modelo.
- **Razón de la cadena de proximidad** (r): no se mide de forma fiable desde fuera (habría que identificar padding, gutter y sección en cada página).
- **Bandas de ocupación** de la densidad.

## 6. Límites de esta calibración

- **15 páginas son una muestra pequeña.** Por eso se compara con validación cruzada y se prefiere el modelo más simple que generaliza.
- Las referencias se midieron con Chrome en Linux. Con una fuente genérica (Wikipedia: `sans-serif`) la letra depende del sistema, y esas páginas no entran en el ajuste del interlineado.
- Las páginas cambian: cada medición guarda su fecha. Recalibrar es repetir los comandos del principio.
- "Buena tipografía" es un criterio. Si prefieres otras referencias, mídelas y vuelve a calibrar: el sistema dirá cómo cambian los modelos y si el ajuste generaliza.
