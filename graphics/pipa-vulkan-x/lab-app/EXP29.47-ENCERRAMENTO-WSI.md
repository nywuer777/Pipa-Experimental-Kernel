# EXP29.47 — encerramento ordenado após perda da superfície

## Evidência de entrada

O ensaio de 10 s com `IDENTITY` ligado apresentou 1.440 `VK_SUBOPTIMAL_KHR`; com `IDENTITY` desligado, `preTransform=2` correspondeu a `currentTransform=2` e houve 1.440 apresentações aceitas, `success=1440`, `suboptimal=0`, `errors=0`. As amostras reais e interpoladas foram lidas com hashes diferentes.

O ensaio de 60 s foi interrompido após a `Surface` ser destruída em torno do frame 2.760. A aquisição subsequente da swapchain virou um erro genérico, apesar de o callback Android já solicitar parada nativa.

## Mudança

O loop agora verifica o pedido de parada depois de acordar do pacing e trata `VK_ERROR_OUT_OF_DATE_KHR` e `VK_ERROR_SURFACE_LOST_KHR` em `vkAcquireNextImageKHR` e `vkQueuePresentKHR` como encerramentos WSI. O resumo registra `runStatus=completed`, `stop_requested`, `surface_out_of_date` ou `surface_lost`. Erros Vulkan não relacionados continuam sendo reportados como falha.

## Teste no Xiaomi Pad 6

Executar `3D 60s FrameGen 72→144` com SYNC ligado, `3D IDENTITY WSI` desligado e GPU GUARD desligado. Se a superfície continuar ativa, esperar 8.640 apresentações e `runStatus=completed`. Se sair do app ou a superfície for recriada, confirmar encerramento sem `Acquire swapchain image failed` e `runStatus=stop_requested` ou `surface_lost`. Para pacing estável, preferir permanecer no app durante os 60 s.
