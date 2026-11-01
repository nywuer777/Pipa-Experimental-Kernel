# EXP29.37 — duração explícita para A/B sustentado

## Capturas EXP29.36 recebidas

As quatro capturas formam o comparativo HOLD/FrameGen × SYNC ligado/desligado. Cada relatório mostra 1.440 presents aceitos, que correspondem a 10 segundos a 144 Hz; nenhum comprova o alvo de 60 segundos, que exige 8.640 presents aceitos.

| Perfil | Pacing / SYNC | Presents | Deadlines perdidos | Cadência WSI reportada | Intervalos >1,5 ciclos | Maior intervalo | GPU gerado + blit média / p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| FrameGen | WSI_SYNC | 1.440 (720 reais + 720 interpolados) | 0 | 143,210 Hz | 1/541 | 20,835 ms | 5,943 / 6,347 ms |
| FrameGen | FIXED_REQUEST | 1.440 (720 reais + 720 interpolados) | 243 | 143,368 Hz | 1/381 | 13,904 ms | 6,130 / 6,469 ms |
| HOLD | WSI_SYNC | 1.440 (720 reais + 720 repetidos) | 0 | 143,731 Hz | 0/591 | 7,093 ms | não aplicável |
| HOLD | FIXED_REQUEST | 1.440 (720 reais + 720 repetidos) | 0 | 143,725 Hz | 0/528 | 7,107 ms | não aplicável |

Nas duas capturas HOLD a cadência ficou praticamente igual e não houve intervalo longo. No FrameGen, SYNC ligado evitou os 243 inícios tardios contados pelo pacing fixo, embora ambas as capturas tenham um intervalo WSI longo. Cada linha é uma amostra curta; a cadência e os timestamps WSI são reportados pelo driver e não medem fótons.

Todos os quatro relatórios registram 1.440 resultados `VK_SUBOPTIMAL_KHR`, zero erros e zero divergências entre resultado global e por swapchain. IDENTITY segue habilitado para preservar a geometria validada.

## Mudança na EXP29.37

- Mantém os botões de 10 segundos.
- Acrescenta botões visíveis **3D 60s HOLD 72→144** e **3D 60s FrameGen 72→144**, cada um solicitando 8.640 presents.
- O relatório final imprime o alvo de duração e o total solicitado junto ao total aceito, facilitando confirmar a execução antes de comparar métricas.
- O gesto de toque longo permanece disponível, mas não é necessário.

Critério de captura sustentada: `presentsSolicitados=8640` e `Aceitos por vkQueuePresentKHR: 8640`. Se aparecer 1.440, a execução foi de 10 segundos.
