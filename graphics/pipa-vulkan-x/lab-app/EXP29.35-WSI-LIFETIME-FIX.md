# EXP29.35 — correção de vida útil do timing WSI

O teste da EXP29.34 concluiu 1.440 apresentações e destruiu a swapchain, mas não terminou a montagem do relatório. A causa no caminho de código era uma nova consulta `vkGetPastPresentationTimingGOOGLE` feita durante o resumo depois de a swapchain já ter sido destruída.

EXP29.35 faz `collectTiming()` retornar quando o handle da swapchain é nulo. O relatório também grava checkpoints entre cada bloco para confirmar a conclusão. Reproduza **3D 10s FrameGen 72→144** e cole o histórico copiado. A build valida compilação e contratos de fonte; a confirmação final depende do teste no Xiaomi Pad 6.
