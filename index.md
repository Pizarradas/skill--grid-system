# Grid System — Índice

La retícula como disciplina completa, en web y en papel: **qué es**, **qué matemática la sostiene**, **cómo se construye impresa y en pantalla desde el móvil**, **cómo se vuelve expresiva sin perder el sistema**, **cómo se deriva de la letra y de la densidad** y **cómo se revisa**. El principio rector: *se calcula, no se elige* — cada número sale de `09-herramientas/gridcalc.py`.

```
fuente ─► interlineado ─► unidad u ─► cadena de proximidad ─► padding · gutter · margen
  │                                                   │
  └─► ancho real de carácter ─► medida ─► columnas en uso ─► composición (operadores) ─► crítica
```

## Estratos

| Estrato | Contenido | Cargar cuando… |
|---|---|---|
| `00-indice/` | `leyes.md` (L1–L13) · `mapa-del-sistema.md` (relaciones, fuentes y lo pendiente de verificar) | las leyes, siempre |
| `01-fundamentos/` | Anatomía, familias de grid, orden de derivación, principios de composición | se propone un grid desde cero |
| `02-matematica/` | Ecuación del grid, divisores, √2/φ/Fibonacci, escalas, `clamp()`, rejilla base, compuestos (Gerstner), cánones, Müller-Brockmann | hay que fijar proporciones, escalas o cánones |
| `03-offline/` | Libro, revista, cartel, señalética, diapositivas; InDesign; sangre y spreads; traslado papel ↔ pantalla | el soporte es impreso o físico |
| `04-web/` | Mobile first, grids de plataforma (M3, HIG, Bootstrap, Tailwind), soporte CSS (oct-2026), recetas | el soporte es web o app |
| `05-creatividad/` | Operadores O1–O14, estilos, recetas R1–R5 | se pide algo expresivo o editorial de autor |
| `06-casos/` | Aplicación del sistema a sistemas de diseño reales. `syx.md`: diagnóstico medido D1–D8 y propuesta v2 | el trabajo ocurre dentro de un sistema de diseño existente |
| `07-critica/` | Comprobaciones duras C1–C13 y rúbrica Q1–Q8 | siempre antes de entregar; auditorías |
| `08-composicion/` | **Composición multidisciplinar**: `metricas-de-fuente.md` (qué guarda el archivo de una fuente y cómo se mide), `calibracion.md` (los modelos frente a referencias medidas), interlineado, cadena de proximidad (micro · inner · padding · gutter · margen · sección), padding óptico, medida real, columnas en uso, densidad | siempre que haya texto |
| `09-herramientas/` | `gridcalc.py` (Python 3, sin dependencias), lector de fuentes, perfiles medidos, corpus por idioma, `verificar.py` | para cualquier número |

Precedencia: el sistema informa, no autoriza. Si se integra en un sistema de diseño con reglas propias (tokens, capas, breakpoints, nivel de confianza), esas reglas mandan sobre las recetas genéricas; las leyes L1–L13 se mantienen salvo excepción declarada.
