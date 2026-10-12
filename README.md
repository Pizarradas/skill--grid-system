# Grid System

Sistema de conocimiento autónomo, en Markdown, para diseñar y auditar retículas **en web (mobile first) y en papel** a partir de reglas matemáticas precisas. Lo usan igual una persona que un agente de IA.

Principio rector: **la retícula se calcula, no se elige.** Cada número se deriva de la letra, el uso, la densidad y el soporte, y sale de la calculadora `09-herramientas/gridcalc.py`.

## Por dónde empezar

| Si eres… | Lee |
|---|---|
| una persona | este README → `index.md` → `00-indice/leyes.md` → el estrato que necesites |
| un agente | `AGENTE.md` (procedimiento, calculadora, formato de entrega) |

## Estructura

```
grid-system/
├── README.md                  este archivo
├── AGENTE.md                  instrucciones operativas para un agente
├── index.md                   estratos y cuándo cargar cada uno
├── 00-indice/
│   ├── leyes.md               L1–L13: lo que se aplica siempre
│   └── mapa-del-sistema.md    relaciones, fuentes, pendiente de verificar
├── 01-fundamentos/            anatomía, familias, orden de derivación
├── 02-matematica/             ecuación del grid, proporciones, escalas, clamp(), cánones, Müller-Brockmann
├── 03-offline/                libro, revista, cartel, señalética, diapositivas, InDesign
├── 04-web/                    mobile first, grids de plataforma, soporte CSS (oct-2026), recetas
├── 05-creatividad/            operadores O1–O14, estilos, recetas R1–R5
├── 06-casos/
│   └── syx.md                 caso de estudio: diagnóstico medido del grid de SYX y propuesta v2
├── 07-critica/                comprobaciones C1–C13 y rúbrica Q1–Q8
├── 08-composicion/            letra → interlineado → cadena de proximidad → medida → densidad
│                              (+ metricas-de-fuente.md: qué guarda el archivo de una fuente)
└── 09-herramientas/
    ├── gridcalc.md            referencia de la calculadora y de la calibración tipográfica
    ├── gridcalc.py            calculadora (Python 3, sin dependencias)
    ├── fontread.py            lector de archivos de fuente (TTF, OTF, WOFF, WOFF2, TTC; estáticas y variables)
    ├── fontvar.py             variaciones: ejes, avar, deltas
    ├── cffread.py             contornos CFF y CFF2
    ├── brotlidec.py           descompresor WOFF2 en Python puro (+ brotli-dict.bin.z)
    ├── fontprofile.py         fuente → perfil de calibración
    ├── linebreak.py           corte de líneas como el navegador; medida por la media real
    ├── verificar_navegador.py comprobación en Chrome, Edge, Firefox (y Chromium en Linux/macOS)
    ├── medir_sitio.py         mide la tipografía de páginas web reales (referencias)
    ├── calibrar.py            ajusta los modelos a las referencias → calibracion.json
    ├── referencias/           las 15 referencias medidas
    ├── perfiles/              perfiles medidos (JSON, con el SHA-1 de cada archivo)
    ├── fuentes/               las fuentes de SYX (licencia OFL) a las que apuntan sus perfiles
    ├── corpus/                prosa por idioma (es, en, fr, de, it, pt, el, ru) y frecuencias de letras
    ├── verificar.py           comprobación de la calibración
    └── pruebas/               vectores de prueba
```

## La calculadora

```
python3 09-herramientas/gridcalc.py -h
python3 09-herramientas/gridcalc.py compose --font space-grotesk --use scanning --max 1200
python3 09-herramientas/gridcalc.py font ruta/Fuente.woff2 --save --css   # medir una fuente nueva
python3 09-herramientas/verificar.py                                     # comprobar la calibración
python3 09-herramientas/verificar_navegador.py Fuente.woff2 --fallback arial   # …y en tus navegadores
```

Requisitos: **Python 3.8 o posterior**, solo la biblioteca estándar. Funciona igual en Windows (`py` en lugar de `python3`), en WSL, en Linux y en macOS; probado con Python 3.13 en Windows y 3.14 en WSL. Opcional: `pip install fonttools brotli uharfbuzz` para que `verificar.py` compare con las referencias y para componer escrituras complejas.

## Autonomía y acoplamiento

- Los módulos 00–05 y 07–09 no dependen de ningún repositorio. Las reglas que antes se citaban de un sistema externo están ahora en `00-indice/leyes.md`.
- `06-casos/` es el único lugar con contenido específico de un sistema de diseño. Cada caso sigue la misma plantilla: qué hay · diagnóstico medido · propuesta · decisiones humanas · reglas locales.
- Para integrarlo en un sistema de diseño (p. ej. SYX), basta con copiar la carpeta como dominio de conocimiento, conectar `index.md` con los modos o rutas del sistema y mapear las leyes L1–L13 a sus reglas.

## Estado

- Versión 1.5.1 · 2026-10-12: portable a Windows. Los perfiles encuentran su archivo de fuente en cualquier máquina (ruta relativa, traducción Windows ↔ WSL o búsqueda por nombre, siempre comprobando el SHA-1). Las fuentes de SYX viajan con el sistema en `09-herramientas/fuentes/`. Probado de punta a punta con Python en Windows.
- Versión 1.5 · 2026-10-12: modelos calibrados con 15 referencias medidas en el navegador (editorial y documentación) dentro de los límites de WCAG y Bringhurst. Interlineado y escala confirmados; medida de lectura 75 de media (con techo de 80 por fuente); margen móvil 16 px; espacio entre párrafos ¾ de línea. Ver `08-composicion/calibracion.md`.
- Versión 1.4 · 2026-10-12: la medida se fija por las líneas realmente compuestas (`gridcalc.py lines`); mismos cortes que Chrome, línea a línea.
- Versión 1.3 · 2026-10-11: tamaño óptico automático (como el navegador) y verificación en Chrome, Edge y Firefox (Windows) y Chrome (Linux). Ver `08-composicion/metricas-de-fuente.md` §9.
- Versión 1.2 · 2026-10-11: el lector de fuentes es agnóstico. Mide cualquier fuente, también variable (en cualquier punto de sus ejes), en CFF2 y en escrituras no latinas; para las complejas usa HarfBuzz si está instalado.
- Versión 1.1 · 2026-10-11: calibración tipográfica leída de los archivos de fuente (antes, una tabla medida aparte).
- Las cifras de `06-casos/syx.md` están medidas en Chromium 153 sobre el CSS compilado de SYX en la base `7deff28`.
- Las métricas tipográficas se leen de los archivos de fuente con `fontread.py`. Contrastado con fontTools, HarfBuzz y la referencia de Brotli: 502/502 comprobaciones en 35 fuentes (`08-composicion/metricas-de-fuente.md` §7).
- Lo pendiente de verificar en fuente primaria está listado al final de `00-indice/mapa-del-sistema.md`.
