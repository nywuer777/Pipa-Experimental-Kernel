# EXP29.36 — teste sustentado de 60 segundos

## Referência pareada no Xiaomi Pad 6

Capturas EXP29.25 de 3D FrameGen e 3D HOLD, ambas com SYNC ligado, Motion FAST desligado, IDENTITY ligado e GPU Guard desligado:

| Métrica | FrameGen | HOLD |
|---|---:|---:|
| Presents aceitos | 1.440 (720 reais + 720 interpolados) | 1.440 (720 reais + 720 repetidos) |
| Deadlines perdidos | 0 | 0 |
| Cadência WSI reportada | 143,414 Hz | 143,739 Hz |
| Intervalos acima de 1,5 ciclos | 1/443 | 0/623 |
| Maior intervalo consecutivo | 13,918 ms | 7,133 ms |
| GPU gerado + blit, média / p95 | 6,146 / 6,240 ms | não aplicável |

A amostra de 10 segundos confirma interpolação 2× sem deadlines perdidos, mas não mostra vantagem de regularidade sobre HOLD. Cadência e timestamps WSI são reportados pelo driver e não medem fótons; os tamanhos de amostra diferem.

## Mudança

- Toque curto nos botões 3D mantém o teste atual de 10 segundos.
- Toque longo em **3D 10s HOLD 72→144** ou **3D 10s FrameGen 72→144** roda 8.640 apresentações solicitadas (60 segundos a 144 Hz).
- O relatório registra a duração solicitada e os contadores do teste. O teste não muda o pacing, os shaders, a geometria nem as opções selecionadas.
- Frame count nativo permitido sobe para 9.000, suficiente para os 8.640 pedidos do teste sustentado.

## Próxima coleta

Manter SYNC ligado, Motion FAST desligado, IDENTITY ligado e GPU Guard desligado. Fazer um teste HOLD de 60 s e um FrameGen de 60 s, permitindo o tablet voltar à mesma condição térmica entre execuções. Comparar cadência WSI, lacunas acima de 1,5 ciclos, deadlines, custo GPU gerado e completude do relatório.

O APK precisa ser compilado pelo workflow Android; este ambiente não tem Android SDK/Gradle instalado. Nenhum kernel é alterado ou gravado no dispositivo.
