# EXP29.32 — diagnóstico persistente do app

EXP29.32 mantém um registro local da execução Vulkan para casos em que `logcat` não pode ser lido pelo shell do dispositivo. O registro inclui início/fim da chamada nativa, exceções Java e eventos de ciclo de vida da Activity e da superfície.

O botão existente **Copiar relatório** copia o histórico persistido para a área de transferência. Depois de reabrir o app, abra **PIPA FRAMEGEN**, entre na tela do laboratório e toque em **Copiar relatório**; cole o texto no chat. Se o processo cair dentro do código nativo, a última linha `RUN_START` sem `RUN_END` indica o teste interrompido. Os eventos `ACTIVITY_STOP`, `ACTIVITY_DESTROY` e `SURFACE_DESTROYED` ajudam a distinguir saída da tela de encerramento do processo.

O arquivo fica no armazenamento privado do app; não requer permissão de armazenamento nem acesso root. A compilação do APK não confirma comportamento no Xiaomi Pad 6; o novo log precisa ser coletado após reproduzir o problema no aparelho.
