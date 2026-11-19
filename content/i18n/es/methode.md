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
- **Variaciones**: la media del día comparada con la del día anterior, o con la media de los siete días previos cuando tenemos suficiente historial. Estas comparaciones solo usan mediciones completas: el juego debe haberse medido en al menos tres cuartas partes de las mediciones de cada día comparado (18 horas de 24).
- **Subidas y bajadas**: solo se tienen en cuenta los juegos con al menos mil jugadores de media, para evitar porcentajes espectaculares en juegos casi vacíos.
- **Visitas en 24 horas**: la diferencia entre dos mediciones separadas de 23 a 25 horas. Sin un par de mediciones válido, no publicamos esta cifra.

- **Pico puntual**: los juegos se clasifican por su pico del día. Cuando ese pico supera en más de tres veces las mediciones vecinas, a menudo un evento de una hora, el artículo lo señala como puntual e indica también el puesto del juego según la media del día.
- **Entradas en el top 50**: un juego solo cuenta como nueva entrada si se midió por completo el día anterior, fuera del top 50. Un juego ausente de nuestras mediciones el día anterior (medición perdida, juego no disponible) que estuvo en el top 50 durante los siete días previos es un regreso, no una entrada.

Un juego solo se clasifica si aparece en al menos la mitad de las mediciones del día. Cuando faltan mediciones, el artículo lo indica; por debajo de 18 mediciones en el día, precisa que la jornada está incompleta. Cuando la API de Roblox limita nuestras peticiones, el programa vuelve a intentar los juegos no medidos antes de guardar la medición; los que siguen sin medirse figuran en el archivo de estado de la medición.

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
2. El diario lo escribe un programa a partir de plantillas fijas; los análisis los redacta una IA. Ninguno escribe cifras por sí mismo: las cifras se toman del archivo.
3. Un verificador automático bloquea la publicación si una cifra no procede de los datos, si una frase sugiere un vínculo oficial con Roblox o si una formulación habitual contradice los datos (jornada incompleta sin aviso, «sigue en cabeza» sin ser el n.º 1 el día anterior, entrada en el top 50 no establecida, pico puntual presentado como duradero).
4. Los análisis los revisa un agente que controla el sentido de las frases. El diario, que sigue plantillas fijas, se publica en cuanto pasa el verificador.
5. Los diarios en inglés, español y portugués siguen plantillas traducidas; los demás artículos los traduce una IA a partir del original en francés. Las cifras son las mismas, tomadas de los mismos archivos.

En cada artículo, las cifras subrayadas son enlaces: abren la línea exacta del archivo de datos del que proceden.

## Independencia

{{nom}} no está afiliado a Roblox Corporation ni cuenta con su respaldo. Roblox es una marca de Roblox Corporation. Cuando un artículo trata un juego con el que el editor tiene un vínculo, el artículo lo indica.

## Errores

¿Un error? Señálalo desde la página de [Correcciones](../corrections/). Cada corrección se publica.
