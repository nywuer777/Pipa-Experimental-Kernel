# EXP29.39 — janela temporal dos timestamps WSI

## Comparação EXP29.38 recebida

As duas capturas 31781–31782 são execuções de 60 s com SYNC ligado, raio 4, IDENTITY ativo e GPU Guard desligado. Ambas registram `presentsSolicitados=8640` e 8.640 resultados aceitos.

| Modo | Reais | Interpolados/repetidos | Inícios CPU >1 período | Cadência WSI reportada | Intervalos >1,5 ciclos | GPU gerado + blit |
|---|---:|---:|---:|---:|---:|---:|
| FrameGen | 4.320 | 4.320 interpolados | 1 | 143,677 Hz | 1/3.676 | média 5,978 ms; p95 6,241 ms |
| HOLD | 4.320 | 4.320 repetidos | 6.452 | 143,777 Hz | 0/2.264 | não aplicável |

As métricas WSI disponíveis indicam cadência semelhante nos dois modos. HOLD teve muitos inícios CPU tardios, mas isso não equivale a presents rejeitados: o relatório confirma 8.640 aceitos e a contagem de intervalos WSI longos foi zero. A cobertura WSI foi parcial (55,05% FrameGen; 38,70% HOLD), portanto a comparação não comprova regularidade visual nem latência de fótons.

## Mudança na EXP29.39

O resumo agora informa o intervalo entre o primeiro e o último timestamp WSI válido e seus IDs de apresentação. Isso permite ver se as amostras parciais cobrem o período inteiro do ensaio de 60 s. Não altera interface, geometria, cena, pacing nem chamadas de apresentação.

Próximo comparativo: repetir FrameGen e HOLD com SYNC ligado e verificar que ambos cobrem aproximadamente a mesma janela WSI, antes de usar essas medições para orientar o protótipo de driver.
