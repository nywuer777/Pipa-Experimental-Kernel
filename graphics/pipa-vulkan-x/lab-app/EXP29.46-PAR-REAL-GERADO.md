# EXP29.46 — amostras do par real e interpolado

## Evidência de entrada

A EXP29.45 leu uma região de 64×64 do último frame apresentado pela swapchain do laboratório. O relatório registrou `captured=1` e FNV64 não zero, com 1.440 apresentações aceitas, 720 interpoladas, zero repetidas, zero erros Vulkan e zero atrasos de CPU acima de um período.

O mesmo relatório mostrou `success=0`, `suboptimal=1440`, `errors=0`. `VK_SUBOPTIMAL_KHR` significa que as chamadas não falharam, mas o WSI sinalizou condição subótima em todas elas.

## Mudança

A EXP29.46 copia uma região central de 64×64 do último frame real e do último frame interpolado para posições separadas do buffer de leitura e registra FNV64 de cada uma. A leitura ocorre apenas nesses dois frames. O relatório também apresenta `accepted`, calculado como sucesso mais subótimo, mantendo as contagens separadas.

## Teste no Xiaomi Pad 6

Executar `3D 10s FrameGen 72→144` com SYNC e 3D IDENTITY WSI ligados, GPU GUARD desligado. Confirmar `real64x64=1`, `generated64x64=1`, hashes não zero, `accepted=1440`, `errors=0`, e observar se os hashes diferem. Comparar o pacing com a EXP29.45, pois os dois últimos frames agora incluem cópias para CPU.

Os pixels continuam limitados à cena analítica do próprio app; não há leitura de outro processo nem injeção em jogos externos.
