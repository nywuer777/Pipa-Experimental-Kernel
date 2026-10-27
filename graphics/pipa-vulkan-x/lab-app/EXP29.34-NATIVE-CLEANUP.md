# EXP29.34 — checkpoints de encerramento Vulkan

EXP29.34 mantém os checkpoints da EXP29.33 e marca a destruição da swapchain, a montagem do relatório, a limpeza dos objetos Vulkan e a preparação do retorno JNI. Isso localiza um encerramento depois do loop de apresentação, sem alterar a geometria ou os controles visuais.

Reproduza **3D 10s FrameGen 72→144**. Se retornar à tela inicial, reabra **Abrir Vulkan Presenter — Frames reais + gerados**, toque em **Copiar relatório** e cole o histórico. A última linha entre `NATIVE_SWAPCHAIN_DESTROY_BEGIN`, `NATIVE_CLEANUP_BEGIN`, `NATIVE_RETURN_PREP` e `RUN_END` aponta o estágio que não completou.
