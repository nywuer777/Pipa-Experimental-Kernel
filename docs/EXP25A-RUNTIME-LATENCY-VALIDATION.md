# EXP25A — critérios de validação de latência em execução (planejamento, sem flash)

## Evidência já confirmada no CI (2026-11-01)
- Branch isolada: `exp25a-latency-tracers-probe`.
- GitHub Actions #41 (`41272493630`), #42 (`41273897141`) e #43 (`41274709383`): `success`.
- SHA-256 de `out/arch/arm64/boot/Image` nos três builds: `02f85b02957a578fb8449108a35d1f19abb394eca29bf33fc78c2bf378e79178`.
- Gate do #43 confirmou `IRQSOFF_TRACER=y`, `PREEMPT_TRACER=y`, `TRACE_IRQFLAGS=y`, `LTO_CLANG_THIN=y`, ausência de `FUNCTION_TRACER` e `PREEMPT_RT` habilitados, e ausência de `boot.img`/`vendor_boot.img` nos caminhos verificados.
- Os resultados demonstram compilação e integridade; NÃO demonstram inicialização, disponibilidade efetiva de tracefs, melhoria de latência ou estabilidade no tablet.
- Artefato `pipa-exp25a-latency-probe-NONFLASH-43`; `FLASH_READY=false`.

## Condições de entrada para um futuro ensaio em dispositivo
1. Revisão independente da compatibilidade da imagem com o boot do dispositivo, do método de recuperação e da possibilidade de reversão; nenhuma operação de flash é autorizada por este documento.
2. Identidade da imagem e configuração confirmadas após extração, incluindo SHA-256, origem do artefato e versão da ferramenta.
3. Aprovação explícita do usuário antes de qualquer procedimento no dispositivo; não presumir que sucesso no CI equivale a segurança de boot.
4. Definir workload comparável entre baseline e experimento: estado térmico, frequência/política de CPU, tela, carga em segundo plano e número de repetições.
5. Confirmar em execução se os tracers podem registrar intervalos IRQ-off e preempt-off. A configuração compilada não garante a captura em runtime.

## Plano de medição e campos obrigatórios
- Identificação: dispositivo, versão do kernel, SHA-256 da Image, `.config`, build, data, operador, workload, condições térmicas.
- Por sessão e por tracer: duração, quantidade de eventos, unidades, perdas/overruns, maior duração observada, distribuição de durações se disponível, e metodologia de extração.
- Reportar p50, p95, p99 e p99.9 SOMENTE se houver amostra de eventos suficiente, dados brutos e definição explícita da unidade estatística. Caso contrário, marcar `NOT_MEASURED`.
- `tracing_max_latency` representa máximo observado, NÃO p99.9.
- Separar IRQ-off, preempt-off, latência de toque e tempo de resposta de rede; são métricas diferentes e não intercambiáveis.
- Preservar logs brutos e hashes; comparar baseline e experimento com mesmo protocolo; informar incerteza e possíveis vieses.
- Checar funcionalidade básica e regressões: boot, toque/IRQ 521, resume, firmware CSOT, USB-C/RTL8153, estabilidade e travamentos.

## Critérios de decisão
- `CI_REPRODUCIBLE=PASS` para os builds #41–#43, restrito à Image e condições observadas.
- `DEVICE_BOOT=NOT_TESTED`; `TRACEFS_RUNTIME=NOT_TESTED`; `IRQOFF_P99_9=NOT_MEASURED`; `PREEMPTOFF_P99_9=NOT_MEASURED`.
- `LATENCY_IMPROVED=UNPROVEN`; `FLASH_READY=false`.
- Nenhuma alegação de ganho de desempenho até comparação controlada de dados de execução.
- Caso surjam divergências, não alterar `main` ou a baseline; investigar exclusivamente na branch experimental.

## Próximo gate
Solicitar evidência de ambiente de teste e autorização específica antes de planejar qualquer ensaio real. Até lá, manter o trabalho estritamente documental e de CI, sem produzir ou recomendar imagem flashável.
