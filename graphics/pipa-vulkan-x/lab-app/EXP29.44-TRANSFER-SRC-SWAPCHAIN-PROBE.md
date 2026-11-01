# EXP29.44 — solicitação condicional de `TRANSFER_SRC`

## Evidência de entrada

A captura EXP29.43 de 10 s registrou 1.440 apresentações aceitas, 720 quadros reais, 720 interpolados, zero repetidos e zero atrasos de CPU acima de um período. A consulta de capacidades estava disponível e indicava suporte a `TRANSFER_SRC` e `SAMPLED`.

## Mudança

A swapchain da cena analítica passa a pedir `VK_IMAGE_USAGE_TRANSFER_SRC_BIT` junto de `TRANSFER_DST` somente quando `VkSurfaceCapabilitiesKHR.supportedUsageFlags` anuncia suporte. A camada de apresentação já registra `usageBits` do `VkSwapchainCreateInfoKHR` efetivamente recebido, permitindo confirmar que a combinação foi criada. Se a superfície não anunciar esse uso, o app mantém o caminho anterior.

Não há alteração na geometria da cena nem na sincronização de apresentação. Esta etapa não grava comandos de cópia, não lê nem retém pixels e não injeta quadros em outro processo.

## Teste no Xiaomi Pad 6

Executar `3D 10s FrameGen 72→144` com SYNC e `3D IDENTITY WSI` ligados e GPU GUARD desligado. Confirmar `surfaceCapsAvailable=1`, `supportsTransferSrc=1`, `usageBits=3`, 1.440 apresentações aceitas e ausência de falhas Vulkan. O resultado valida a criação de uma swapchain da própria cena de laboratório com uso de origem e destino de transferência; não valida captura de jogo externo.
