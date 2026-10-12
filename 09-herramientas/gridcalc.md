# gridcalc.py y la calibración tipográfica

Calculadora de retículas: todas las cifras del sistema salen de aquí. Python 3, solo biblioteca estándar; `--json` en todos los comandos.

```
python3 09-herramientas/gridcalc.py <comando> -h
```

En Windows, `py` en lugar de `python3`. Python 3.8 o posterior.

## Comandos

| Comando | Para qué |
|---|---|
| `font` | **Lee cualquier archivo de fuente** (`.ttf`, `.otf`, `.woff`, `.woff2`, `.ttc`; estática o variable): line box por plataforma, tinta medida en los glifos de cada alfabeto, espacios, ancho del texto con kerning por idioma y escritura, interlineado mínimo sin colisión. `--save` guarda el perfil; `--css` genera `@font-face` con overrides; `--fallback arial` calcula `size-adjust`; `--sample` mide tu propio texto; `--axes wght=700,opsz=24` o `--instance Bold` miden un punto de una fuente variable; `--instances` las compara todas. Sin archivos, lista los perfiles guardados |
| `compose` | **Solver multidisciplinar**: fuente (perfil o archivo) + idioma + uso (`reading`/`scanning`/`operating`) + densidad → interlineado, unidad `u`, cadena de proximidad con `clamp()`, padding óptico (vertical y lateral), titulares en la retícula base, columnas en uso, span de prosa y tarjetas por fila **con la medida de las líneas compuestas** (no la capacidad) |
| `lines` | **Compone el texto en una medida** como el navegador (corte *first-fit*, sin guiones) y da las líneas reales: caracteres por línea (media, rango del 90 %, la más larga), relleno, bandera, líneas cortas, finales de una palabra. Calcula la medida cuyas líneas tienen de **media** N caracteres (`--measure 66`). `--engine firefox` aplica el kerning como Firefox |
| `web` | Pistas en cada viewport, con avisos (columna < gutter, objetivo táctil, medida, reflow); `--typeface` toma el ancho de carácter de una fuente medida; `--emit css` |
| `print` | Müller-Brockmann (campos en líneas enteras); con `--typeface` y `--size`, desplazamientos de primera línea base medidos en los glifos (opciones de InDesign) |
| `clamp` | Valor fluido entre dos anchos (`--unit cqi` para contenedor) |
| `scale` · `ratio` · `tracks` | Escalas modulares, repartos enteros de una proporción, pistas Fibonacci/geométricas |
| `compound` | Superposición de divisiones (3 + 4 → 12) con líneas nombradas |
| `rhythm` | Ritmo euclídeo E(k, n) para colocar acentos, con selectores `:nth-child` |
| `canon` · `paper` | Cánones de página, ISO 216 |
| `svg` | Diagrama de la retícula |

Ejemplos:

```
python3 09-herramientas/gridcalc.py font                                   # perfiles guardados
python3 09-herramientas/gridcalc.py font Marca-Regular.woff2 --save --css --fallback arial
python3 09-herramientas/gridcalc.py compose --font space-grotesk --lang es --use reading --max 1200
python3 09-herramientas/gridcalc.py compose --font Marca-Regular.woff2 --sample textos.txt
python3 09-herramientas/gridcalc.py print --page 210,297 --margins 20,30,20,20 --leading 13 --typeface playfair-display --size 10
```

`--font` (en `compose`) y `--typeface` (en `web` y `print`) aceptan el nombre de un perfil (`space-grotesk-regular`, o el de la familia, `space-grotesk`, para el estilo Regular) o la ruta de un archivo de fuente. Con un archivo variable, los cuatro comandos aceptan `--axes` e `--instance`. Si la fuente tiene eje `opsz`, cada tamaño se mide en su propio tamaño óptico, como lo dibuja el navegador (`font-optical-sizing: auto`); `--optical-sizing none` o un `opsz` explícito lo desactivan, y `font --size <px>` mide a un tamaño concreto.

**Escrituras complejas** (árabe, índicas, tailandés…): instala HarfBuzz (`pip install uharfbuzz`) y el texto se compone con él; sin HarfBuzz, el ancho se marca como no fiable y `compose` no lo usa (ver `08-composicion/metricas-de-fuente.md` §8).

## Archivos

| Archivo | Qué es |
|---|---|
| `gridcalc.py` | La calculadora |
| `fontread.py` | Lector de fuentes: sfnt, WOFF, WOFF2 (con la transformación de `glyf`/`hmtx`), TTC; tablas `head`, `hhea`, `OS/2`, `post`, `name`, `cmap` (4/12), `hmtx`, `glyf`/`loca`, `GPOS` (kerning de parejas por escritura, formatos 1 y 2, extensiones, deltas variables) y `kern`; variaciones `gvar` (con IUP y componentes), `HVAR`, `MVAR` |
| `fontvar.py` | Variaciones: normalización `fvar` + `avar`, `ItemVariationStore`, mapas de índices, escalares de tuplas |
| `cffread.py` | Contornos CFF y CFF2 (charstrings Type 2 con extremos exactos de curva, `blend`, `seac`) |
| `brotlidec.py` + `brotli-dict.bin.z` | Descompresor Brotli (RFC 7932) en Python puro, para WOFF2. Si está instalado el módulo `brotli`, se usa ese |
| `fontprofile.py` | Convierte una fuente en un perfil de calibración (ver `08-composicion/metricas-de-fuente.md`) |
| `linebreak.py` | Corte de líneas como el navegador y búsqueda de la medida por la media real de caracteres |
| `perfiles/*.json` | Perfiles medidos, cada uno con el SHA-1 de su archivo y la ruta de su fuente: relativa si está en `fuentes/`, absoluta si es del sistema. Al usarlos, el archivo se busca por la ruta, su versión Windows ↔ WSL o el nombre en las carpetas de fuentes habituales, y solo se acepta si coincide el SHA-1 |
| `fuentes/` | Las fuentes de SYX (OFL, con su licencia), para que sus perfiles funcionen en cualquier máquina. Las del sistema (Arial, Calibri…) no se copian: se buscan donde estén instaladas |
| `corpus/{es,en,fr,de,it,pt,el,ru}.txt` | ~30 000 caracteres de prosa de dominio público por idioma (fuente en la primera línea) |
| `corpus/frecuencias.json` | Frecuencias de letras por idioma (Wikipedia), para el modelo de contraste |
| `verificar.py` + `pruebas/` | Comprobación de la calibración (ver abajo) |
| `medir_sitio.py` | Mide la tipografía que aplica una página web real (cuerpo, interlineado, x-height del archivo de su fuente, caracteres por línea reales, párrafos, márgenes, titulares) en Chrome sin ventana, vía DevTools. Guarda la medición en `referencias/`; las fuentes que descarga quedan en la carpeta temporal (`medir-sitio-fuentes`) para no repetir descargas |
| `calibrar.py` + `calibracion.json` | Ajusta los coeficientes de los modelos a las referencias dentro de los límites de la evidencia y escribe `calibracion.json`, que `gridcalc` lee (`--sin-calibracion` lo ignora). Ver `08-composicion/calibracion.md` |
| `verificar_navegador.py` | Comprobación en navegadores reales: abre una página de prueba en Chrome, Edge, Firefox (Windows, también desde WSL) o Chrome/Chromium (Linux, macOS) sin ventana y con perfil temporal, y compara line box, ancho, `opsz`, `text-box-trim` y fallback con lo previsto. Último resultado en `pruebas/navegador-resultados.json` |

## Perfiles incluidos

Fuentes de SYX: Inter (Regular, Medium), Space Grotesk (Light → Bold), Playfair Display (Regular, Bold), DM Mono (Regular, Medium), Syne (Regular, Medium, Bold) y Bebas Neue. Fallbacks de sistema (medidos en los archivos de Windows): Arial, Times New Roman, Georgia, Verdana, Segoe UI y Calibri.

## Verificación

```
python3 09-herramientas/verificar.py                       # sin dependencias
python3 09-herramientas/verificar.py ruta/a/fuentes/*.woff2
```

Sin dependencias, comprueba el descompresor con vectores fijos, la coherencia de cada perfil y, si se le pasan fuentes, que una medición nueva coincide con el perfil guardado (mismo SHA-1). Si están instalados `fonttools`, `brotli` y `uharfbuzz` (`pip install fonttools brotli uharfbuzz`), compara además campo a campo, glifo a glifo y el ancho del texto con HarfBuzz. Última ejecución completa: **502/502** comprobaciones en 35 fuentes (ver `08-composicion/metricas-de-fuente.md` §7).
