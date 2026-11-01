# EXP29.26 — resultados no Xiaomi Pad 6

Data do ensaio: 2026-10-25. Dispositivo reportado pelo app: Adreno 650, tela configurada em 144 Hz. Cena 3D de identidade, Vulkan FIFO, WSI_SYNC, Motion FAST raio 3 e viewport 16:9.

A build manteve a interface e a geometria validadas. O cabeçalho visual continua dizendo EXP29.25; a identificação de build é EXP29.26 (versionCode 316), e `passes stress cena=4` confirma a carga diagnóstica.

## Guard ativo — carga controlada

A repetição da cena só foi ativada com o GPU Guard. Cada real processado recebeu quatro passes extras da mesma cena para elevar o custo do par sem alterar a imagem apresentada.

| Métrica | Resultado |
| --- | ---: |
| Apresentações Vulkan aceitas | 1.440 |
| Quadros reais / interpolados / repetidos | 720 / 625 / 95 |
| Passes extras de estresse da cena | 4 |
| Teto do par (85% de dois períodos WSI) | 11,826829 ms |
| Pares medidos / acima do teto | 625 / 291 |
| Trips de três violações | 96 |
| HOLDs adaptativos | 95 |
| Último par medido | 13,445208 ms |
| Custo do par real + FrameGen, média / p95 | 11,902230 / 13,491250 ms |
| Deadlines CPU perdidos | 136 / 1.440 |
| Intervalos WSI maiores que 1,5 ciclos | 3 / 363 |
| Cadência WSI reportada pelo driver | 142,411247 Hz |

Os contadores confirmam que a lógica de três violações consecutivas acionou o HOLD adaptativo. A diferença de uma unidade entre trips (96) e HOLDs (95) é compatível com o último trip ocorrer no fim da janela, sem outro quadro ímpar no qual aplicar o HOLD.

## Controles sem passes de estresse

| Perfil | Real / interpolado / repetido | Deadlines perdidos | Intervalos WSI > 1,5 ciclos | Cadência WSI reportada |
| --- | ---: | ---: | ---: | ---: |
| FrameGen, Guard inativo | 720 / 720 / 0 | 0 / 1.440 | 3 / 626 | 143,289646 Hz |
| HOLD, sem FrameGen | 720 / 0 / 720 | 0 / 1.440 | 0 / 720 | 143,742394 Hz |

As janelas têm amostras e durações diferentes; portanto, os valores de cadência não são uma comparação A/B controlada. O resultado mais claro é funcional: sem Guard, o FrameGen conservou 2×; sob o estresse diagnóstico, o Guard substituiu 95 quadros gerados por HOLD. A carga artificial também coincidiu com 136 deadlines perdidos, então este ensaio valida o acionamento do governor, mas não recomenda habilitar o estresse ou o Guard por padrão.

## Decisão

- EXP29.25 sem Guard permanece a referência de fluidez.
- EXP29.26 comprova o caminho de trip/HOLD em hardware sob carga Vulkan deliberada.
- Os quatro passes extras não representam carga típica de jogo e não demonstram FrameGen em quadros de um jogo real.
- WSI é timing informado pelo driver; não mede FPS físico de scanout, latência toque-a-fóton nem latência de entrada.
- Nenhuma mudança de kernel, flash ou alteração persistente foi feita.
