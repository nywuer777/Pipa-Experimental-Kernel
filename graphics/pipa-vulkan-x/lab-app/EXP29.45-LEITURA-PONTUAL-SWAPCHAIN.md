# EXP29.45 — leitura pontual da swapchain própria

## Evidência de entrada

A captura EXP29.44 confirmou `usageBits=3` na swapchain da cena analítica (transferência para destino e origem), 1.440 apresentações aceitas, 720 quadros interpolados, zero repetidos, zero erros Vulkan e zero atrasos de CPU acima de um período.

## Mudança

Na última apresentação da execução, o app copia uma região central de 64×64 pixels da própria imagem da swapchain para um buffer host-coherent e calcula FNV-1a de 64 bits. A leitura ocorre depois de `vkQueueWaitIdle`; nenhum conteúdo de pixel é salvo ou exibido. Execuções sem suporte a `TRANSFER_SRC`, formato RGBA8 ou extensão mínima da imagem reportam a sonda como indisponível.

É uma leitura única por execução e pode adicionar custo ao último quadro. Não altera a geometria da cena, não copia imagens de outros apps e não implementa injeção de quadros.

## Teste no Xiaomi Pad 6

Executar `3D 10s FrameGen 72→144` com SYNC e `3D IDENTITY WSI` ligados, GPU GUARD desligado. Confirmar `usageBits=3`, `pixel probe own-swapchain 64x64 captured=1`, hash não zero, 1.440 apresentações aceitas, zero erros Vulkan e comparar CPU pacing com a EXP29.44. Repetir a execução deve produzir um hash válido; não se exige que seja igual caso o frame final da cena varie.
