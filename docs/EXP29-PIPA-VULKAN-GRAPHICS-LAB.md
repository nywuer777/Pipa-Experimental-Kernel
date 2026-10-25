# EXP29 — Pipa Vulkan / Competitive Graphics Lab (Xiaomi pipa)

## Decisão de direção

Após EXP27.7 em hardware real — RTL8153 USB3, r8152 v1.10.11, eth0 gigabit, IPv4, ICMP 20/20 e counters sem erros — o operador considerou priorizar otimização gráfica Vulkan/sistema para jogos mobile competitivos, em vez de continuar mudanças no USB. Esta é a **proposta técnica EXP29**, não uma instalação ou substituição efetiva do driver GPU. Preservar o kernel EXP27 que iniciou com sucesso e o driver USB Ethernet funcional; EXP28 USB host pode ser retomada caso surja falha natural.

**Hardware alvo:** Xiaomi Pad 6 (pipa), Qualcomm Snapdragon 870 / Adreno 650 (A6xx), Android 16 da sessão de testes, kernel Qualcomm E404 4.19.404R com KGSL. A GPU do dispositivo vem de documentação pública da árvore de dispositivos pipa: https://github.com/Xiaomi-pad-6-development/android_device_xiaomi_pipa . O estado exato do driver Vulkan OEM e extensões **ainda requer leitura no tablet**.

**Base open-source escolhida:** Mesa Turnip (Vulkan para Adreno 6xx), utilizando backend KMD KGSL para builds Android em arm64. Documentos oficiais:
- https://docs.mesa3d.org/drivers/freedreno.html
- https://docs.mesa3d.org/android.html
- https://source.android.com/docs/core/graphics/implement-vulkan
- https://developer.android.com/games/optimize/overview

Não iniciar driver independente do zero: primeiro compilar fork reproduzível do Turnip, fixando commit e dependências. Não usar builds comunitárias aleatórias como baseline. Android Vulkan loader é componente separado do HAL/driver, e apps só o utilizam se renderizam via Vulkan. Jogos GLES exigem experimentação independente em Freedreno ou camada compatível explicitamente suportada; não prometer ganho global com driver Vulkan. Driver do usuário e kernel KGSL precisam ser compatíveis com a ABI antiga 4.19 do projeto. Não substituir /vendor nem driver global neste ciclo.

## Matriz de componentes

| Camada | Código de referência | Objetivo |
| --- | --- | --- |
| Vulkan user space | Mesa src/freedreno/vulkan (Turnip) | shader compilation, pipeline cache, GMEM/sysmem, command scheduling, WSI e compatibilidade |
| Driver GPU kernel | drivers/gpu/msm/{kgsl.c,kgsl_pwrctrl.c,adreno.c} | instrumentação de erros/reset, DVFS, memória/sincronização; **sem overclock ou desativar limites térmicos** |
| Loader Android | framework Vulkan loader e HAL vendor | compatibilidade de versões, ICD, seleções de driver em apps de teste sob controle |
| Surface / jogo | SurfaceFlinger, Android Frame Pacing, ADPF | frametime e jank; caminhos distintos da implementação GPU |

Fonte E404 auditada: commit `fed88a6024cd4d46c52eda607a95d97d7371ba81` do repositório `kvsnr113/xiaomi_sm8250_kernel_e404`; arquivos `drivers/gpu/msm/kgsl.c` blob `2ea2ce92fefc4de33f71876ec096f4eb489c1aba`, `kgsl_pwrctrl.c` blob `a4188f33f2e2a7c373467df98dda1623f7fea342`, `adreno.c` blob `28262d8a2eafb70f1cd9148dc5bff7efe4ba2a00`. Presença da fonte KGSL NÃO prova todos os nós/interfaces de usuário ativos nem compatibilidade do Turnip, que serão aferidos no dispositivo.

## Ciclos de desenvolvimento

**EXP29.0 — inventário read-only**: registrar Adreno realmente detectada, implementação Vulkan OEM e sua biblioteca HAL, Vulkan feature levels, módulo KGSL, perfis de temperatura e clocks expostos. Não modificar nada. Guardar baseline para não atribuir melhoria ao novo driver sem A/B.

**EXP29.1 — build reproduzível**: versionar fonte/commit Mesa upstream, configurar Meson Android arm64 `-Dplatforms=android -Dvulkan-drivers=freedreno -Dfreedreno-kmds=kgsl`; validar dependências/licenças e símbolo da biblioteca, sem escrever /vendor; smoke test offline, CI e CTS Vulkan possível em app do laboratório.

**EXP29.2 — testes em isolamento**: criar APK próprio de teste Vulkan, capaz de selecionar nossa implementação de maneira suportada no app ou ambiente de desenvolvimento. Validar enumerar GPU, swapchain, shaders, descriptor sets, memória e robustez em cenários de carga. Comparar OEM e Turnip na **mesma resolução, qualidade, frequência de tela e carga térmica inicial**. Não injetar driver em processos protegidos ou burlar anticheat de jogos comerciais.

**EXP29.3 — otimização mensurada**: priorizar gargalos mostrados pelo perfil (tempo de compilação de shader, stalls na pipeline, GC/cache, fence/sync, uploads, GMEM/sysmem, uso de memória). Uma alteração por vez com rollback. Objetivo: p95/p99 de frametime menores, 1% low maior, menos jank, sem regressão de artefatos ou crash. Manter paridade visual.

**EXP29.4 — sistema/kernel só se necessário**: se Perfetto/AGI ou métricas de KGSL revelarem gargalo real de governor/thermal/memória/IRQ, criar experimento kernel separado (EXP29K) com patch mínimo e boot temporário, nunca sobrescrevendo EXP27 funcional. Alterar limites térmicos/corrente/frequência sem segurança não faz parte do projeto. ADPF e Swappy/Frame Pacing só podem ser integrados diretamente em apps/jogos cujo código controlamos ou que forneçam integração legítima.

## Critérios de aceitação

- Estabilidade: 0 GPU reset/hang observados no ensaio, 0 crash gráfico, sem corrupção visual, memória controlada.
- Competitivo: p50/p95/p99 frametime, 1% low, pacing entre quadros, latência de entrada→apresentação e temperatura/frequência sob 15–30 minutos de sessão.
- Correlação correta: distinguir GPU-bound, CPU-bound, engine frame cap, display refresh e rede. Latência de rede e driver Ethernet não implicam ganho gráfico.
- A/B: três ou mais execuções em ambiente/sessão reproduzíveis, preservando qualidade/render resolution e registrando versão do driver/thermal state. Comparar OEM e Pipa Vulkan; voltar ao OEM sem reiniciar ou escrever /vendor se o mecanismo de teste permitir.
- Segurança: não promover VulkanCTS/CI para prova de eficácia em jogos, não substituir driver system-wide, não desabilitar assinaturas, não mascarar instrumentação de anticheat.

## Coleta inaugural somente leitura no Termux

```sh
su -c '
echo "=== SISTEMA / GPU ==="
getprop ro.product.device
getprop ro.board.platform
getprop ro.build.version.release
for f in /sys/class/kgsl/kgsl-3d0/gpu_model /sys/class/kgsl/kgsl-3d0/gpuclk /sys/class/kgsl/kgsl-3d0/gpubusy; do
  [ -r "$f" ] && echo "$f=$(cat "$f")"
done
echo "=== KGSL ==="
ls -l /dev/kgsl* 2>/dev/null
echo "=== VULKAN / VENDOR ==="
getprop ro.hardware.vulkan
pm list features | grep -i vulkan
ls -l /vendor/lib64/hw/vulkan*.so 2>/dev/null
echo "=== FIM ==="
'
```

O comando acima não escreve no tablet, não muda frequências, não reinicia ou habilita debug. Arquivos sysfs opcionais podem não existir em certos ROMs. `getprop ro.hardware.vulkan` vazio não demonstra ausência de Vulkan; biblioteca HAL e `pm list features` são sinais complementares.

**Status inicial:** `EXP29_DECISION=PROPOSED`; `EXP29_DEVICE_BASELINE=NOT_COLLECTED`; `EXP29_TURNIP_BUILD=NOT_STARTED`; `EXP29_RENDER_TEST=NOT_RUN`; `EXP27_KERNEL_PRESERVED=true`; `GPU_SYSTEM_DRIVER_REPLACED=false`; `FLASH_READY=false`.
