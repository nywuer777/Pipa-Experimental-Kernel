# EXP29.27 — auditoria do caminho de integração do FrameGen

## Estado observado no branch EXP29.26

- O FrameGen Vulkan é um componente de usuário que recebe imagens Vulkan pertencentes ao próprio app e registra compute work em um command buffer fornecido pelo chamador.
- O presenter da bancada cria sua própria cena, swapchain e chamadas de apresentação. Não captura buffers de outro processo.
- O contrato e o README da biblioteca declaram explicitamente: sem alteração de KGSL, SurfaceFlinger, kernel, root ou imagem vendor.
- A área de kernel deste repositório não contém uma árvore completa do kernel nem patch de GPU/FrameGen. O diretório `patches/` contém somente `0001-pipa-exp01-schedutil-rate-limit.patch`; a bancada Vulkan está em `graphics/pipa-vulkan-x/`.
- As capturas EXP29.26 validam o governor em uma cena própria sob sobrecarga controlada. Elas não são um teste de interceptação ou interpolação de um jogo.

## O que cada camada permite

### App ou plugin integrado ao jogo

O renderer conhece os quadros, o estado e, quando disponível, dados como motion vectors e depth. É o ponto com maior controle para evitar interpolar HUD, menus e efeitos de tela. Exige integração por jogo ou acesso ao código do jogo.

### Vulkan layer

Uma layer fica entre o app e o loader/driver Vulkan. É um caminho experimental para observar e instrumentar chamadas Vulkan em um app de teste. No Android, o loader procura layers no pacote do app; as locations de desenvolvimento são limitadas a apps depuráveis, e layers de outro APK são uma facilidade de desenvolvimento. Isso não fornece suporte transparente e universal para qualquer jogo instalado.

### SurfaceFlinger / Hardware Composer

SurfaceFlinger reúne buffers das camadas visíveis e solicita composição ao Hardware Composer. Uma extensão aqui poderia alcançar mais apps, mas precisa distinguir a camada do jogo da interface sobreposta, respeitar fences e formatos, e não interferir em buffers protegidos. É uma mudança de sistema/compositor, não uma alteração isolada de driver Vulkan.

### Driver gráfico do kernel (KGSL)

O driver de kernel participa de submissão, memória, sincronização e energia da GPU. Ele não recebe semântica de cena, motion vectors nem uma noção de quais pixels pertencem ao HUD. Colocar optical flow/interpolação dentro de KGSL não é a rota adequada. O kernel pode apoiar a experiência com telemetria, escalonamento e controle de frequência, medidos separadamente.

## Rota escolhida

1. Manter EXP29.25 como referência normal e EXP29.26 como prova diagnóstica do governor.
2. Criar um protótipo opt-in de instrumentação Vulkan em um app controlado, com imagens reais de entrada, fences e medição de latência. Isso fecha o caminho de captura e apresentação sem alterar outros apps.
3. Só depois avaliar uma extensão AOSP do compositor no kernel/OS EXP, com teste reversível e uma tela não protegida. Medir atraso toque-a-fóton externamente; timestamps WSI não substituem essa medição.
4. Tratar as mudanças de KGSL como trabalho auxiliar de scheduling/energia. Não anunciar compatibilidade universal nem promessa de ultrapassar limites de jogo até existir uma integração permitida e testada por app.

## Fontes primárias

- AOSP, [Implementar Vulkan no Android](https://source.android.com/docs/core/graphics/implement-vulkan): loader, layers e locais de carregamento.
- AOSP, [Vulkan no Android](https://source.android.com/docs/core/graphics/arch-vulkan): o driver Vulkan traduz a API para comandos de GPU e interage com o driver gráfico do kernel.
- AOSP, [SurfaceFlinger e WindowManager](https://source.android.com/docs/core/graphics/surfaceflinger-windowmanager): fluxo dos buffers de camadas para SurfaceFlinger e HWC.
- AOSP, [Implementar o Hardware Composer HAL](https://source.android.com/docs/core/graphics/implement-hwc): composição e caminhos de hardware/cliente.
