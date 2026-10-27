# EXP29.41 — episódios de atraso no pacing da CPU

## Evidência que motivou a revisão

A captura EXP29.40 sem GPU Guard aceitou 8.640 apresentações Vulkan e gerou 4.320 quadros interpolados, sem repetição. Ainda assim, o contador de pacing marcou 972 amostras com retomada mais de um período depois do prazo. A captura com Guard teve 8.640 apresentações aceitas, 4.319 interpolados e uma repetição.

O contador mede o relógio de pacing da thread da aplicação, não perdas de apresentação. Um único desvio persistente da fase de prazo pode marcar muitas iterações consecutivas. Contá-las como 972 eventos independentes sugere mais incidentes do que os dados demonstram.

## Mudança

A EXP29.41 mantém o agendamento, a cena, o GPU Guard, a geometria e a interface de controles. O relatório passa a nomear a quantidade como amostras atrasadas e acrescenta:

- número de episódios contínuos de atraso;
- intervalo de frames do primeiro ao último frame atrasado;
- maior sequência contínua já registrada.

O estado térmico `NONE` é o valor normal que o Android reportou, não uma falha de leitura. A nova legenda deixa isso explícito. Nenhuma telemetria de pacing prova, por si só, que um frame foi perdido no painel; para isso, o relatório continua separado dos timestamps de apresentação WSI.

## Limites

A alteração melhora a interpretação dos contadores e não muda o comportamento do FrameGen. O APK precisa de nova captura no Xiaomi Pad 6 para confirmar se as 972 amostras formam um único episódio e em que faixa de frames ele ocorre. Build de CI não equivale a teste em dispositivo. Não instala nem altera kernel.
