# EXP29.43 — capacidades de uso da superfície Vulkan

## Resultado EXP29.42

A sonda observou uma swapchain de 2844x545, formato Vulkan 37, `usageBits=2`, modo de apresentação 2 e 5 imagens. Esses valores são metadados fornecidos na criação da swapchain. No Vulkan, formato 37 corresponde a `VK_FORMAT_R8G8B8A8_UNORM`, modo 2 a `VK_PRESENT_MODE_FIFO_KHR` e uso bit 2 a `VK_IMAGE_USAGE_TRANSFER_DST_BIT`: a aplicação pediu a imagem como destino de transferência.

Esse uso pedido não informa sozinho se a superfície permite que uma swapchain seja criada também com `TRANSFER_SRC` ou `SAMPLED`. A camada ainda não pode inferir acesso de leitura aos pixels.

## Mudança EXP29.43

Durante a sonda da swapchain, a camada consulta `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` para a superfície associada e registra `supportedUsageFlags`. O relatório apresenta o bitmask e dois indicadores: `supportsTransferSrc` e `supportsSampled`.

A consulta não modifica `VkSwapchainCreateInfoKHR`, não adiciona flags de uso e não altera a aplicação. Não há cópia, leitura ou retenção de pixels e não há novos submits GPU.

## Próxima validação

Executar `3D 10s FrameGen 72→144` no Xiaomi Pad 6. Comparar `usageBits` com `surfaceUsageBits`, em especial os campos `supportsTransferSrc` e `supportsSampled`. Isso determina a próxima investigação de acesso suportado no dispositivo; não prova que a camada consegue extrair uma imagem de um jogo ou inserir quadros.
