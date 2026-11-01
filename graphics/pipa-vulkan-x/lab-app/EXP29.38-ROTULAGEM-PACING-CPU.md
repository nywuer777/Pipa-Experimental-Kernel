# EXP29.38 — separar atraso do loop CPU de presents aceitos

## Evidência EXP29.37 recebida

As quatro capturas 31776–31779 são execuções de 60 s: cada relatório registra `alvo=60s`, `presentsSolicitados=8640` e 8.640 resultados aceitos por `vkQueuePresentKHR`.

| Perfil | SYNC | Reais | Interpolados/repetidos | Inícios CPU >1 período | Cadência WSI reportada |
|---|---|---:|---:|---:|---:|
| FrameGen | WSI_SYNC | 4.320 | 4.320 interpolados | 0 | 143,606 Hz |
| HOLD | WSI_SYNC | 4.320 | 4.320 repetidos | 6.397 | 143,753 Hz |
| FrameGen | FIXED_REQUEST | 4.320 | 4.320 interpolados | 6.697 | 143,671 Hz |
| HOLD | FIXED_REQUEST | 4.320 | 4.320 repetidos | 6.464 | 143,734 Hz |

No FrameGen com WSI_SYNC, o custo `GPU gerado+blit` foi 5,984 ms de média e 6,310 ms p95. A amostra WSI é parcial (aprox. 38–48% de cobertura); taxa e timestamps são fornecidos pelo driver e não medem fótons.

## Correção

O contador antes chamado `deadlines perdidos` comparava o despertar da thread CPU com `deadline + um período`. Ele não mede resultado de `vkQueuePresentKHR` nem perdas de scanout. EXP29.38 o rotula como `inícios CPU atrasados >1 período`, explicita o critério e mantém separados os totais de presents aceitos e os intervalos WSI reportados. Interface, duração, geometria, shader e pipeline Vulkan não mudam.

## Próxima rodada

Repetir o par FrameGen/HOLD com WSI_SYNC ligado, raio 4, IDENTITY ativo e os botões 3D 60s. Comparar os contadores de presents e amostras WSI, ignorando a métrica CPU como se representasse quadros exibidos. Esta build continua sendo o laboratório Vulkan sintético; não altera nem instala kernel.
