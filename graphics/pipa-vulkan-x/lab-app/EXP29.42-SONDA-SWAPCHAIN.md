# EXP29.42 — sonda de metadados da swapchain

## Contexto

As capturas EXP29.41 concluíram a comparação do GPU Guard. O contador de 972 amostras CPU atrasadas não se repetiu; as capturas seguintes registraram zero amostras atrasadas em ambos os perfis. A próxima prova de engenharia é confirmar o que a camada Vulkan consegue observar no ponto em que a aplicação cria sua swapchain.

## Mudança

`VK_LAYER_PIPA_present_trace` agora registra, após criação bem-sucedida da swapchain, os metadados enviados pela aplicação: extent, formato Vulkan, flags de uso da imagem, modo de apresentação e número de imagens. O relatório da bancada exibe os valores observados pela camada junto aos contadores existentes.

A mudança não lê conteúdo de imagem, não guarda handles de imagem, não injeta comandos GPU e não interpola quadros. Ela não altera o pacing, o Guard, a cena, a geometria ou os controles. O registro representa a última swapchain criada durante o ensaio, suficiente para esta bancada que cria uma swapchain por execução.

## Próxima prova

Instalar a EXP29.42 no Xiaomi Pad 6 e executar `3D 10s FrameGen 72→144`. Confirmar no relatório `layerSwapchain extent=... formatVk=... usageBits=... presentModeVk=... imageCount=...` e verificar que `VK_LAYER_PIPA active=1` continua presente. Isso valida a observação dos metadados nesta aplicação de teste; ainda não prova leitura dos pixels, integração com outro processo ou suporte a jogos externos.
