# EXP29.40 — telemetria térmica do sistema durante o ensaio

## Resultado guardado EXP29.39

A captura 31789 confirma FrameGen 60 s com WSI_SYNC e GPU Guard pareado ativo. Foram aceitos 8.640 presents: 4.320 reais, 4.319 interpolados e 1 repetido. O governor observou 4.319 pares; 3 excederam o teto de 11,840 ms e uma sequência de três acionou 1 HOLD. O custo real+FrameGen teve média 7,173 ms e p95 7,794 ms. Janela WSI: 60,149 s, cobertura 55,94%, cadência reportada 143,501 Hz e 6 intervalos acima de 1,5 ciclos entre 3.753 pares consecutivos válidos.

Conclusão: nessa execução, o guard preservou 4.319/4.320 slots interpolados. A amostra sustenta o orçamento pareado para esta cena e este perfil, mas não mede a temperatura do SoC nem prova desempenho em outro app.

## Mudança na EXP29.40

Adiciona leitura do `PowerManager` térmico do Android e registra no relatório o status no início, o pico observado durante o teste e o status final. A telemetria não altera a cena, o pacing, a geometria, os controles ou o cálculo do governor. Estado térmico é uma classificação do Android, não uma leitura em graus Celsius.

Próximo ensaio: repetir FrameGen 60 s com SYNC, IDENTITY e GPU Guard ligados. Comparar status térmico inicial/pico/final junto do número de pares acima do teto e de HOLDs.
