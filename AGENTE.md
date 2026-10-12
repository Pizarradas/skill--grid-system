# Instrucciones para un agente

Este sistema enseña a diseñar, generar, auditar y explicar retículas para web/app (mobile first, CSS Grid, subgrid, container queries, `clamp()`) y para papel (cánones de página, Müller-Brockmann, rejilla base, spreads, carteles, diapositivas), incluidas las expresivas (compuestas, asimétricas, áureas/Fibonacci, rotadas, ritmos euclídeos).

Aquí las retículas **se derivan, no se eligen**: cada número sale del contenido (letra, interlineado, medida) y del soporte, y se calcula con `09-herramientas/gridcalc.py`, nunca a ojo. La creatividad se expresa como **operaciones declaradas sobre la retícula**, nunca como posiciones sin explicar.

Las rutas son relativas a la raíz del sistema. Responde en el idioma de quien pregunta.

## Antes de empezar

1. Lee `00-indice/leyes.md` (L1–L13). Se aplican siempre.
2. Consulta `index.md` para saber qué estratos cargar. Carga solo los que necesites.

## La calculadora

`python3 09-herramientas/gridcalc.py <comando> -h`. Solo biblioteca estándar; `--json` en todos los comandos. Referencia completa: `09-herramientas/gridcalc.md`.

| Comando | Uso |
|---|---|
| `compose` | **Solver multidisciplinar**: fuente + uso (`reading`/`scanning`/`operating`) + densidad → interlineado, unidad `u`, cadena de proximidad con `clamp()`, padding óptico, columnas en uso, span de prosa, tarjetas por fila |
| `font` | **Lee el archivo de la fuente** (`.woff2`, `.ttf`, `.otf`…): line box por plataforma, tinta medida, espacios, ancho del texto con kerning por idioma, interlineado mínimo sin colisión; `--save`, `--css`, `--fallback`, `--sample`. Sin archivo, lista los perfiles guardados |
| `web` | Pistas en cada viewport, con avisos (columna < gutter, objetivo táctil, medida, reflow); `--emit css` |
| `clamp` | Valor fluido entre dos anchos (`--unit cqi` para contenedor) |
| `scale` · `ratio` · `tracks` | Escalas modulares (`--snap` avisa de pasos colapsados), mejor reparto entero de una proporción, pistas Fibonacci/geométricas |
| `compound` | Superposición de divisiones (3 + 4 → 12) con líneas nombradas |
| `rhythm` | Ritmo euclídeo E(k, n) para colocar acentos, con selectores `:nth-child` |
| `print` · `canon` · `paper` | Müller-Brockmann (campos en líneas enteras), cánones de página, ISO 216 |
| `svg` | Diagrama acotado de la retícula para la entrega |

## Procedimiento

1. **Clasificar el encargo.** Pregunta solo lo que no se pueda inferir:
   - Soporte: pantalla (web, app o ambas), papel (libro, revista, cartel, informe), físico (señalética, exposición), diapositivas, o un sistema que cruce varios.
   - Inventario de contenido: más texto o más imagen, número de piezas, proporciones de las imágenes, densidad interactiva.
   - Expresividad: *canónica* (claridad ante todo), *editorial* (variedad con unidad) o *experimental* (tensión, ruptura).
   - Restricciones: sistema de diseño o tokens existentes, framework, breakpoints ya fijados. Si hay un sistema de diseño, mira si existe un caso en `06-casos/`.
2. **Derivar la base de la letra** (08 y 01 §4). Mide cada fuente **desde su archivo**, sea cual sea → `gridcalc.py font <archivo> --save` (con `--sample` si hay textos reales del producto o un idioma sin corpus; con `--axes`/`--instance` en fuentes variables, un punto por cada peso que se use; si tienen eje `opsz`, pasa el archivo, no el perfil, para que cada tamaño se mida en su tamaño óptico) y resuelve sus avisos (`08-composicion/metricas-de-fuente.md`): line box divergente, idiomas no cubiertos, escritura compleja sin HarfBuzz; uso + densidad → `gridcalc.py compose --font <perfil o archivo> --lang <idioma>`. Salen el interlineado, la unidad `u`, la cadena de proximidad (micro < inner < padding < gutter ≤ margen < sección), la medida en caracteres reales, las columnas en uso y el ancho mínimo de componente. En papel: interlineado `L` → campos con `gridcalc.py print`.
3. **Calcular** cada valor con `gridcalc.py`. La medida de texto se fija con `gridcalc.py lines` (media real de las líneas compuestas y línea más larga ≤ 80), no como capacidad. Muestra la salida del comando, o sus filas clave, para que los números se puedan auditar.
4. **Componer.** Lleva la jerarquía del contenido a spans. Elige de 0 a 3 operadores creativos (05 §1) y como mucho una ruptura declarada, anclada a una línea del sistema. Declara los invariantes.
5. **Planificar la transformación.**
   - Web: tabla mobile first por rango (columnas en uso, margen, gutter, medida, cambio estructural), valores continuos con `clamp()`, patrones intrínsecos antes que media queries, orden del DOM = orden de lectura (04 §6).
   - Papel: páginas maestras por variante de retícula, ajustes de rejilla base, sangre y zona segura, comportamiento en el spread (03).
6. **Validar** con `07-critica/critica.md`. Las comprobaciones duras C1–C13 tienen que pasar todas; informa de la puntuación Q1–Q8.
7. **Entregar** la *Grid Spec* de abajo más la implementación (CSS/SCSS, ajustes de InDesign/Affinity/Figma) y, cuando ayude, un SVG de `gridcalc.py svg`.

## Grid Spec (formato de entrega)

```
GRID SPEC — <nombre>
Contexto       : <soporte, público, contenido, expresividad>
Tipografía     : cuerpo <fuente> (xh, cw em) · <px/pt> / interlineado <L> · medida <N car. reales = em>
Densidad       : uso <reading|scanning|operating> · densidad <compact|default|spacious> · razón de cadena r
Cadena         : micro · inner · padding (inline / bloque óptico) · gutter · margen · sección
Retícula base  : <n> columnas · gutter <g o clamp()> · margen <m o clamp()> · máx. <ancho> · filas <R × f líneas + q>
Proporciones   : <principal:secundaria, página/canon, razón de escala> (con su comando gridcalc)
Operadores     : <O# nombre — parámetros>   (o "ninguno: canónica")
Invariantes    : <lo que nunca cambia>
Ruptura        : <elemento → línea de anclaje>   (o "ninguna")
Transformación : <tabla por rango / por formato>
Validación     : C1–C13 ✓/✗ · Q n/16
Implementación : <código o ajustes de software>
```

## Dentro de un sistema de diseño

- Expresa los tamaños con los tokens del sistema; lo calculado se guarda como **token de tema**, nunca como px sueltos en componentes. Guardarlo es decisión de una persona.
- Respeta sus capas, su nomenclatura y su mapa de breakpoints. Comprueba que el nombre de breakpoint que uses existe (en SYX, `sm`/`lg` no existían: `06-casos/syx.md` §D1).
- Prefiere los patrones intrínsecos que el sistema ya tenga (RAM con suelo dinámico, container queries, subgrid).
- Pasa sus comprobaciones automáticas antes de proponer un cambio.
- Verifica las afirmaciones de layout en un navegador real cuando puedas (p. ej. Playwright). Los números derivados solo de tokens ya fallaron una vez: los temas pueden redefinir la base de espacio y el tamaño de letra raíz.
- Trata cualquier cambio a la retícula base del sistema como propuesta: es una decisión de sistema que toma una persona.
