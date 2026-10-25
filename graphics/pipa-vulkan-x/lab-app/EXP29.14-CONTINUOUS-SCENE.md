# EXP29.14 — Contínuo 2×, Vulkan WSI, Adreno 650 (NO FLASH)

## EXP29.13 — evidência real (Xiaomi Pad 6, Android 16 / Adreno 650)

Capturas fornecidas: três execuções distintas de VkSwapchainKHR FIFO com a tela informando 144 Hz e suporte comprovado a VK_GOOGLE_display_timing. O app repetia dois quadros de origem estáticos A/B.

| Output solicitado | VkQueuePresent aceitos | WSI actualPresentTime reportados | Intervalos ID-consecutivo | média ms | p95 ms | cadência WSI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 60 Hz | 240 | 206 | 176 | 16.680312 | 27.849010 | 59.950917 Hz |
| 120 Hz | 240 | 151 | 121 | 8.335798 | 13.930833 | 119.964525 Hz |
| 144 Hz | 240 | 121 | 91 | 7.034081 | 6.977396 | 142.164974 Hz |

O driver reportou refresh de aproximadamente 6.96 ms e o Android 144.00 Hz. Os intervalos incluídos no cálculo são somente de IDs adjacentes com actualPresentTime crescente; amostras faltantes NÃO devem virar zeros ou ser contadas como exibições perdidas. O p95 de 60 Hz mostra irregularidade marcante dos espaçamentos sob modo de tela 144 Hz; 120 Hz também mostra durações de aproximadamente dois ciclos. A média e p95 de 144 Hz não são inconsistentes: cauda rara eleva média embora 95% dos valores fiquem abaixo de 6.98ms.

São tempos *do mecanismo WSI/driver*, superiores a contar chamadas aceitas, mas não uma medição independente de varredura ótica do display ou da latência de input. Nada prova aumento real de FPS em jogos de terceiros.

## EXP29.14 — modo de entradas contínuas

A EXP29.12 e a EXP29.13 usavam **dois** quadros sintéticos estáticos e revezavam A/mid/B/mid. A EXP29.14 preserva esses controles para regressão e adiciona **dois cenários 2× novos**:

- Fonte 60 quadros/s únicos → 120 solicitações/s, alternando real(t), gerado(t+0.5), real(t+1)...
- Fonte 72 quadros/s únicos → 144 solicitações/s, alinhamento de dois presentes por quadro de origem ao modo 144 Hz informado pelo dispositivo.

O novo `shaders/pipa_scene.comp` gera nativamente em Vulkan Compute duas imagens *únicas e temporalmente ordenadas* na GPU a cada par de apresentações. São padrões deslocados 2 pixels por novo quadro de origem, com faixas contrastantes móveis e marcadores HUD de ID; não há captura de jogos, permissão MediaProjection ou novos kernels. Um segundo shader `pipa_motion_sparse.comp` estima deslocamento e o `pipa_interpolate_tiled.comp` cria o intermediário no mesmo pipeline controlado. Dados persistem em imagens de GPU e cada par mantém apenas uma fila de comandos/fence. O shader de cena tem descriptor e pipeline próprios, com barreiras COMPUTE→COMPUTE e esquema de despachos 16×16. O presenter preserva Vulkan WSI opcional e registra quadros reais e gerados aceitos, deadlines de CPU perdidos, cadência WSI/driver e modo estático/contínuo.

**Importante:** embora duas imagens sejam temporalmente distintas, essa fonte sintética do próprio aplicativo ainda NÃO é um jogo com uma renderização complexa, HUD real, occlusões, input ou dados de profundidade; a qualidade precisa de testes independentes. O campo de movimento só procura deslocamentos até 4 pixels por bloco. A extensão VK_GOOGLE_display_timing cobre apresentação reportada pelo driver, não mede input-to-photon.

## Próxima homologação no dispositivo

1. Instalar somente APK de CI aprovado, verificar Android reportado 144 Hz.
2. Abrir Presenter e executar **2× 60 reais → 120 Hz**, depois **2× 72 reais → 144 Hz**. Observar movimento gradual da tarja, marcador variável e imagens intermediárias, evitando se fiar apenas na taxa de API.
3. Ler contadores: 120 reais+120 gerados para 240 chamadas aceitas; deadlines perdidos, WSI actualPresentTime presentes, intervalos válidos e p95. Considerar gaps de ID explicitamente.
4. Repetir 60/120/144 estáticos (controles antigos) se houver regressão. Capturar erro Vulkan ou crash com logcat. Se o relatório de timing continuar parcial, a taxa relatada é da amostra WSI observada, não de todos os 240 quadros.
5. Nenhum FPS extra deve ser anunciado como ganho em jogo, nem como menor latência, sem uma aplicação 3D própria simulando/renderizando quadros reais e aferição de latência.

## CI / reversibilidade

Workflow: `.github/workflows/exp29.14-continuous-scene-apk.yml`, compila todos os shaders SPIR-V e executa os testes legados de Vulkan e o novo `test_continuous_scene_contract.py`, monta assina/verifica APK Android arm64-v8a. Versão Android 29.14-lab (304).

Apenas software de laboratório, sem root, sem alteração de kernel EXP27, KGSL, Turnip ou SurfaceFlinger. `FLASH_READY=false`. Não ativar automações de reinicialização.
