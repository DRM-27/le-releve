# Método

O {{nom}} publica números sobre a Roblox que qualquer pessoa pode conferir de novo. Esta página explica de onde eles vêm, como são calculados e o que eles não dizem.

## O que medimos

A cada hora, um programa consulta as APIs web públicas da Roblox, as mesmas usadas pelo próprio site roblox.com:

- os rankings da página Descobrir (jogos mais jogados do momento, tendências, jogos em alta);
- para cada jogo que apareceu em um desses rankings nos últimos catorze dias: o número de jogadores online, as visitas acumuladas, os favoritos e os votos.

Um jogo continua sendo acompanhado por duas semanas depois da última aparição em um ranking, para que possamos medir também as quedas. Espaços patrocinados são excluídos dos rankings.

Cada medição é arquivada como está, em arquivos CSV legíveis por todos, no nosso [repositório de dados abertos]({{donnees}}).

## Como calculamos

Todos os números são calculados por um programa, nunca à mão nem por uma IA. Um dia vai de meia-noite a meia-noite, horário de Paris.

- **Pico de jogadores**: a maior das medições horárias do dia. Como medimos uma vez por hora, o pico real pode ser um pouco maior.
- **Média de jogadores**: a média das medições horárias do dia.
- **Variações**: a média do dia comparada à do dia anterior, ou à média dos sete dias anteriores quando temos histórico suficiente. Essas comparações só usam medições completas: o jogo precisa ter sido medido em pelo menos três quartos das medições de cada dia comparado (18 horas de 24).
- **Altas e quedas**: só entram jogos com pelo menos mil jogadores em média, para evitar porcentagens espetaculares em jogos quase vazios.
- **Visitas em 24 horas**: a diferença entre duas medições com 23 a 25 horas de intervalo. Sem um par de medições válido, não publicamos esse número.

- **Pico pontual**: os jogos são classificados pelo pico do dia. Quando esse pico passa de três vezes as medições vizinhas, muitas vezes um evento de uma hora, o artigo o indica como pontual e informa também a posição do jogo pela média do dia.
- **Entradas no top 50**: um jogo só conta como nova entrada se foi medido por completo no dia anterior, fora do top 50. Um jogo ausente das nossas medições no dia anterior (medição perdida, jogo indisponível) que esteve no top 50 nos sete dias anteriores é um retorno, não uma entrada.

Um jogo só é classificado se aparecer em pelo menos metade das medições do dia. Quando faltam medições, o artigo informa; abaixo de 18 medições no dia, avisa que o dia está incompleto. Quando a API do Roblox limita nossas requisições, o programa tenta de novo os jogos não medidos antes de salvar a medição; os que continuam sem medição ficam listados no arquivo de estado da medição.

## Alertas

A cada medição, um programa compara cada jogo com a medição anterior. Ele publica um alerta quando um jogo com pelo menos 2.000 jogadores ganha 50% ou mais em uma hora, ou quando um jogo entra no top 10 vindo de fora do top 20. Um mesmo jogo não dispara o mesmo alerta duas vezes em menos de seis horas.

## Páginas de jogos e dados abertos

Cada jogo acompanhado tem sua página, com a curva horária e os números principais. Uma página só é oferecida aos buscadores depois de sete dias de histórico. Todos os dados estão disponíveis livremente em JSON e CSV (veja [Dados abertos](../donnees/)).

## O que esses números não dizem

- A Roblox não publica em tempo real o número total de jogadores conectados. O total que mostramos cobre apenas os jogos que acompanhamos.
- Os números anuais e trimestrais da plataforma (usuários ativos, receita, horas jogadas) vêm das publicações oficiais da Roblox Corporation para seus investidores. Nós os citamos com um link para o documento original.
- Não publicamos nenhuma estimativa de receita de um jogo: nenhum dado público permite verificá-la.

## Como os artigos são escritos

1. O programa calcula os fatos do dia e os grava em um arquivo.
2. O diário é escrito por um programa a partir de modelos fixos; as análises são redigidas por uma IA. Nenhum dos dois escreve números por conta própria: os números são buscados no arquivo.
3. Um verificador automático bloqueia a publicação se um número não vier dos dados, se uma frase sugerir um vínculo oficial com a Roblox ou se uma formulação comum contradisser os fatos (dia incompleto sem aviso, «segue na liderança» sem ter sido o n.º 1 no dia anterior, entrada no top 50 não comprovada, pico pontual apresentado como duradouro).
4. As análises são revisadas por um agente que confere o sentido das frases. O diário, que segue modelos fixos, é publicado assim que passa no verificador.
5. Os diários em inglês, espanhol e português seguem modelos traduzidos; os demais artigos são traduzidos do original em francês por uma IA. Os números são os mesmos, buscados nos mesmos arquivos.

Em cada artigo, os números sublinhados são links: eles abrem a linha exata do arquivo de dados de onde vêm.

## Independência

O {{nom}} não é afiliado à Roblox Corporation nem apoiado por ela. Roblox é uma marca da Roblox Corporation. Quando um artigo fala de um jogo com o qual o editor tem vínculo, o artigo informa.

## Erros

Achou um erro? Informe pela página de [Correções](../corrections/). Toda correção é publicada.
