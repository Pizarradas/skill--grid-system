# Leyes del sistema

Trece leyes que se aplican siempre, sea cual sea el soporte. Los módulos las citan como **L1–L13**. Si una propuesta incumple una ley, se corrige la propuesta, no la ley; y si una ley necesita excepción, la excepción se declara y se justifica en la especificación.

| Ley | Enunciado | Se comprueba con |
|---|---|---|
| **L1 · Ningún número sin regla** | Todo valor se rastrea a un paso del orden de derivación (01 §4): contenido, letra, unidad, proporción, escala o canon. Un número que no se puede rastrear es arbitrario y se recalcula. | C1 · Q1 |
| **L2 · Una escala por función** | Tipo con escala modular, espacio con escala lineal y layout por proporción. Nunca dos escalas para la misma función. Las proporciones tienen nombre (2:1 principal/secundaria, √2, φ…) y comando (`gridcalc ratio`/`scale`). | 02 §2–§3 |
| **L3 · Continuo antes que escalonado** | En pantalla, gutter, margen y tipo varían de forma continua (`clamp()`, `progress()`). Los breakpoints cambian la **estructura** (columnas en uso, paneles), no el tamaño de un gutter. Ninguna pista encoge cuando la ventana crece. | Q5 · `gridcalc web` |
| **L4 · Medida en caracteres reales** | La medida es la **media de caracteres de las líneas realmente compuestas**: el texto se corta en la medida como lo hace el navegador, con los avances y el kerning leídos de la fuente. Una "medida de 66" calculada como capacidad (`66 × char_em`) da líneas de 62 de media. Rango 45–75 de media, ideal ~66, **ninguna línea > 80**. `Nch` sobrestima entre un 24 y un 40 % en fuentes proporcionales. | C5 · C10 |
| **L5 · Proximidad y ritmo** | Orden micro < inner < padding < gutter ≤ margen < sección en todo el rango. El espaciado vertical va en múltiplos de la unidad `u` (o `u/2`), en `lh`/`rlh` cuando se pueda. | C11 · C12 · Q4 |
| **L6 · Columna ≥ 1.5 × gutter** | En todo el rango en uso. Si no cabe, se reducen las columnas en uso; no se engorda el gutter. | C6 |
| **L7 · Carga por bloque** | De 3 a 7 elementos visibles por grupo; por encima, se agrupa. La densidad (compacta, por defecto o amplia) se declara y cambia la unidad y el alto de fila, no el grid de columnas. | 08 §5 |
| **L8 · Validación por comportamiento** | Un grid se valida midiendo, no por gusto: comprobaciones duras C1–C13 y rúbrica Q1–Q8. Los coeficientes de los modelos (08) se calibran con referencias medidas, dentro de los límites de la evidencia, y el cambio se documenta (`08-composicion/calibracion.md`). | 07 |
| **L9 · La accesibilidad gana** | Reflow a 320px, orden visual = orden del DOM, filas de texto sin altura fija, objetivos ≥ 24px y líneas ≤ 80 caracteres por encima de cualquier decisión de composición. | C2–C5 · C7 |
| **L10 · Mejora progresiva** | Lo que no es Baseline (`grid-lanes`, `reading-flow`, `if()`, `@function`, `calc-size()`) lleva siempre una alternativa que funciona. Lo Baseline reciente (`text-box`, `sibling-index()`, `progress()`) también. | 04 §3 |
| **L11 · Impresión en líneas enteras** | Cada campo ocupa un número entero de líneas y la calle mide una línea. Lo que sobra va al margen inferior. Sangre y zona segura, declaradas. | C8 · C9 |
| **L12 · Fuente con nombre, certeza medida** | Las decisiones clásicas citan su canon o autor (Van de Graaf, Müller-Brockmann, Gerstner, Bringhurst). Lo pendiente de verificar sigue marcado como tal (`mapa-del-sistema.md`). | — |
| **L13 · La letra se lee, no se supone** | Las métricas de una fuente (alturas, line box, avances, kerning) se leen de su archivo y se guardan como perfil con el SHA-1 del archivo. Un valor declarado (`sxHeight`, `xAvgCharWidth`) solo vale como contraste de uno medido. | C13 |
