# Método

{{nom}} publica cifras sobre Roblox que cualquiera puede volver a comprobar. Esta página explica de dónde vienen, cómo se calculan y lo que no dicen.

## Qué medimos

Cada hora, un programa consulta las API web públicas de Roblox, las mismas que usa el propio sitio roblox.com:

- las clasificaciones de la página Descubrir (juegos más jugados del momento, tendencias, juegos en ascenso);
- para cada juego aparecido en una de esas clasificaciones durante los últimos catorce días: el número de jugadores en línea, las visitas acumuladas, los favoritos y los votos.

Un juego se sigue durante dos semanas después de su última aparición en una clasificación, para poder medir también las caídas. Los espacios patrocinados están excluidos de las clasificaciones.

Cada medición se archiva tal cual, en archivos CSV legibles por todos, en nuestro [repositorio de datos abiertos]({{donnees}}).

## Cómo calculamos

Todas las cifras las calcula un programa, nunca a mano ni una IA. Un día va de medianoche a medianoche, hora de París.

- **Pico de jugadores**: la más alta de las mediciones horarias del día. Como medimos una vez por hora, el pico real puede ser algo mayor.
- **Media de jugadores**: la media de las mediciones horarias del día.
- **Variaciones**: la media del día comparada con la del día anterior, o con la media de los siete días previos cuando tenemos suficiente historial.
- **Subidas y bajadas**: solo se tienen en cuenta los juegos con al menos mil jugadores de media, para evitar porcentajes espectaculares en juegos casi vacíos.
- **Visitas en 24 horas**: la diferencia entre dos mediciones separadas de 23 a 25 horas. Sin un par de mediciones válido, no publicamos esta cifra.

Un juego solo se clasifica si aparece en al menos la mitad de las mediciones del día. Cuando faltan mediciones, el artículo lo indica.

## Alertas

En cada medición, un programa compara cada juego con la medición anterior. Publica una alerta cuando un juego con al menos 2.000 jugadores gana un 50 % o más en una hora, o cuando un juego entra en el top 10 desde fuera del top 20. Un mismo juego no puede activar la misma alerta dos veces en menos de seis horas.

## Páginas de juegos y datos abiertos

Cada juego seguido tiene su página, con su curva horaria y sus cifras clave. Una página solo se ofrece a los buscadores tras siete días de historial. Todos los datos están disponibles libremente en JSON y CSV (ver [Datos abiertos](../donnees/)).

## Lo que estas cifras no dicen

- Roblox no publica en tiempo real el número total de jugadores conectados. El total que mostramos solo cubre los juegos que seguimos.
- Las cifras anuales y trimestrales de la plataforma (usuarios activos, ingresos, horas jugadas) proceden de las publicaciones oficiales de Roblox Corporation a sus inversores. Las citamos con un enlace al documento original.
- No publicamos ninguna estimación de ingresos de un juego: ningún dato público permite verificarla.

## Cómo se escriben los artículos

1. El programa calcula los datos del día y los guarda en un archivo.
2. Una IA redacta el artículo a partir de ese archivo. No escribe ninguna cifra por sí misma: las toma del archivo.
3. Un verificador automático bloquea la publicación si una cifra no procede de los datos, o si una frase sugiere un vínculo oficial con Roblox.
4. Un agente revisor controla el sentido de las frases. Durante las primeras semanas, cada artículo lo revisa también el editor antes de publicarse.
5. Los artículos en inglés, español y portugués los traduce una IA a partir del original en francés; las cifras son las mismas, tomadas de los mismos archivos.

En cada artículo, las cifras subrayadas son enlaces: abren la línea exacta del archivo de datos del que proceden.

## Independencia

{{nom}} no está afiliado a Roblox Corporation ni cuenta con su respaldo. Roblox es una marca de Roblox Corporation. Cuando un artículo trata un juego con el que el editor tiene un vínculo, el artículo lo indica.

## Errores

¿Un error? Señálalo desde la página de [Correcciones](../corrections/). Cada corrección se publica.
