# EXP29.33 — checkpoints do presenter nativo

EXP29.33 amplia o diagnóstico persistente da EXP29.32. O presenter registra entrada JNI, começo/fim da inicialização Vulkan, progresso em blocos de 120 apresentações e fim do loop. O botão existente **Copiar relatório** copia o histórico para a área de transferência.

Após reproduzir a falha, reabra **Abrir Vulkan Presenter — Frames reais + gerados**, toque em **Copiar relatório** e cole o texto. O último checkpoint separa falha na inicialização Vulkan de encerramento durante o loop de apresentação. O registro de progresso grava em torno de uma linha por segundo durante o teste de 10 s e pode acrescentar pequeno custo ao perfil; use os timings do teste anterior como referência de desempenho.
