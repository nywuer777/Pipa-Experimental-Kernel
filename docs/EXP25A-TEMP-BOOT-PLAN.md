# EXP25A — Plano de boot temporário condicionado, SEM FLASH

## Estado concluído

- CI EXP25A #39190015939 success, Image SHA256 2dac2dd05fe3cab8b167ea10bc632512c1508fa4d26db88d002837d0dc681e08.
- Candidato Boot V3 Windows: C:\platform-tools\EXP25A-boot-prep\EXP25A-TOUCH-IRQ-NOT-FOR-FLASH.candidate.bin, 32.477.184 bytes, SHA256 12100d94c8d2cc68ebc6a4424fff0ace659cd4e2299db144cd64f0bb65aa5604; auditoria offline 13/13 PASS.
- Controle stock validado: C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img, SHA256 202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7.
- Pipa, slot b, boot_completed=1, /proc/version e /proc/sys/kernel/osrelease = 4.19.404R; uname -r reportou 5.10.404R, discrepância registrada.
- O usuário desconectou voluntariamente o hub: ausência de dongle HID na coleta não indica nova falha USB.

## Gate operacional obrigatório

O touchscreen permanece inoperante em EXP24, e o tablet depende de mouse 2.4GHz conectado ao hub. A reconexão do hub/mouse *depois* de um ciclo fastboot ainda não foi comprovada. Antes de reiniciar, operador presencial precisa comprovar que consegue conectar o hub e usar o mouse e que possui cabo USB-C direto para computador e contingência com botões físicos caso boot falhe. ADB Wi-Fi não funciona no bootloader. Não automatizar reconexão/reset de USB nem retirar controle funcional sem contingência. Se a prova física falhar, não reiniciar.

Apenas após cumprir esses gates, pode-se considerar fastboot boot <arquivo candidato> como teste temporário em RAM; é vedado fastboot flash, set_active, erase, wipe e qualquer escrita nas partições. Em fastboot exija um único dispositivo Windows, product=pipa, current-slot=b, unlocked=yes e is-userspace=no; abortar em qualquer diferença.

## Contingência

No bootloader com fastboot funcionando no PC, fastboot reboot reinicia a imagem persistente. Xiaomi publica reinício forçado por Power 10–15 s e pipa aceita Power + Volume Down para acessar fastboot quando desligado. Isso não comprova recuperação em todo cenário de travamento. Não entrar em recovery para apagar dados.

Fontes: https://www.mi.com/global/support/faq/details/KA-557238/ e https://github.com/AxionAOSP/official_devices/blob/main/Wiki/pipa.md.

## Coleta pós-boot preparada

EXP25A-postboot-diagnostico.ps1, SHA256 8edc95b553c834a2f422a174c812eac49d0b87669e59a5f1e9044d2107f411a2, arquivado como anexo na conversa. Somente ADB Wi-Fi read-only; valida pipa, slot b, boot e NVT event8; coleta IRQ do NVT antes/depois de 12 segundos de toque físico e após transição de tela por botão Power efetuada manualmente, e filtra últimas 180 linhas NVT/firmware. Revisão estática OK; PowerShell Windows ainda não executado. Preserva USB/hub e partições.

STATUS: OFFLINE_BUILD_AND_REPACK=PASS; READONLY_WIFI_PREFLIGHT=PASS; MOUSE_RECOVERY_GATE=PENDING; TEMP_BOOT=NOT_RUN; TOUCH_FIXED=UNPROVEN; FLASH_READY=false.

## Primeira execução de fastboot boot EXP25A — OKAY

Usuário realizou verificação de `Image` e candidato offline com hashes corretos. Entrou no bootloader por `adb -s <serial TLS Wi-Fi> reboot bootloader`. Em seguida, `fastboot devices` retornou **um único dispositivo** serial `6665d3e6`; `getvar product=pipa`, `current-slot=b`, `unlocked=yes`, `is-userspace=no`.

Comando físico executado no PC: `fastboot -s 6665d3e6 boot C:\platform-tools\EXP25A-boot-prep\EXP25A-TOUCH-IRQ-NOT-FOR-FLASH.candidate.bin`.

Saída literal:

```text
Sending 'boot.img' (31716 KB)                      OKAY [  0.687s]
Booting                                            OKAY [  0.239s]
Finished. Total time: 0.952s
```

Interpretação rigorosa: transferência Fastboot e comando de boot **aprovados**. `ANDROID_BOOT_COMPLETED=UNVERIFIED`, `ADB_WIFI_RECONNECTED=UNVERIFIED`, `NVT_IRQ_RECOVERY=UNTESTED`, `NOVATEK_CSOT_FW_RESUME=UNTESTED`, `USB_ETHERNET_POSTBOOT=UNTESTED`. Não confundir `Booting OKAY` com Android inicializado. O comando foi de boot temporário (não houve solicitação de flash), e kernel persistente deve permanecer intacto.

Próxima leitura segura, **somente após Android acessível**: consultar `adb get-state`, `ro.product.device`, `ro.boot.slot_suffix`, `sys.boot_completed`, `/proc/version`, estado da IRQ NVT-ts `/proc/interrupts` e mensagens `EXP25A_IRQ_RESTORE` após suspensão/retomada **manual**; não forçar suspend/reset/USB por ADB. Atenção ao mouse via hub. `FLASH_READY=false`.

## Boot EXP25A aceito pelo fastboot, Android posterior esta na imagem persistente antiga

**Nova evidência após `fastboot boot`:** o Windows ADB listou transportes USB serial `6665d3e6` e Wi-Fi TLS, ambos `device`. `ro.product.device=pipa`, `ro.boot.slot_suffix=_b`, `sys.boot_completed=1`, logo o Android está operacional. Entretanto `/proc/version` retornou:

```text
Linux version 4.19.404R (build-user@build-host) (Android (14054515, +pgo, +bolt, +lto, +mlgo, based on r563880c) clang version 21.0.0, LLD 21.0.0) #14 SMP PREEMPT Sun Aug 23 09:16:08 UTC 2026
```

**Conclusão:** esta identidade é a imagem E404 persistente/controle histórico, *não* a imagem EXP25A compilada no GitHub CI, esperada com metadados de `runner` e data de outubro de 2026. Assim, `fastboot boot ... OKAY` provou transferência e aceitação pelo bootloader, mas não a continuidade do boot da EXP25A. É possível que o aparelho tenha reiniciado durante o boot e retornado ao persistente ou que o candidato não tenha se efetivado; **a causa ainda não está determinada**. Contador IRQ `521 NVT-ts: 250 0 0 0 0 0 0 0` pertence ao **kernel antigo**; não avaliar como resultado do patch EXP25A. A tela touch estar funcional ou não nesta sessão não é diagnóstico válido do patch.

**GATE:** não repetir `fastboot boot`, não flash, não trocar slot, não resetar USB. Coletar somente informações read-only via ADB Wi-Fi: uptime, motivos de boot (`ro.boot.bootreason`, `sys.boot.reason`, `persist.sys.boot.reason`), `/proc/version`, `ro.boot.slot_suffix`, fingerprint do kernel por `su -c 'cat /proc/sys/kernel/osrelease'`, presença de `/sys/fs/pstore` (nomes, sem envio automático de dados sensíveis) e logs `dmesg` filtrados por `panic|watchdog|reboot|bootreason|NVT-ts|EXP25A_IRQ_RESTORE`. Se pstore existir, pedir apenas arquivos relevantes e discutir redação antes de compartilhar. **Não presumir kernel experimental ativo até comprovação independente.**

`FASTBOOT_TRANSFER=PASS`; `ANDROID_BOOT=PASS_STOCK_KERNEL`; `EXP25A_RUNTIME=NOT_CONFIRMED`; `IRQ_COUNT_250=STOCK`; `FLASH_READY=false`.

## Segundo teste: EXP25A realmente ativa no Android

Usuario repetiu a passagem por fastboot no PC; `getvar product=pipa`, `current-slot=b`, `unlocked=yes`, `is-userspace=no` e um unico serial `6665d3e6`. O boot temporario do candidato EXP25A foi aceito (`Sending boot.img OKAY 0.692s`, `Booting OKAY 0.239s`, total 0.964s).

Na primeira coleta imediata ADB Wi-Fi ainda nao estava disponivel; **ADB USB ja constava** em `adb devices -l`. Na segunda coleta, **ambos USB e Wi-Fi** estavam `device`. `DEVICE=pipa`, `SLOT=_b`, `BOOT_COMPLETED=1`, `EXP25A ANDROID BOOT: PASS`.

**Identidade de runtime decisiva:**

```text
Linux version 4.19.404R (runner@runnervm8k3b6) (Android (14054515, +pgo, +bolt, +lto, +mlgo, based on r563880c) Clang 21.0.0, LLD 21.0.0) #1 SMP PREEMPT Mon Oct 19 02:32:14 UTC 2026
```

Este timestamp de compilacao e ambiente `runner` sao consistentes com CI EXP25A #39190015939, diferente do kernel persistente reportado na coleta anterior (`build-user@build-host` 23/08/2026). **Agora a EXP25A esta confirmada no Android pelo conjunto de evidencias de build e boot.** IRQ 521 `NVT-ts` com contador `203 0 0 0 0 0 0 0` no instante da coleta.

**Limites:** IRQ acumulada 203 nao demonstra capacidade atual de toque nem restauraçao pos-suspend. No EXP24 a IRQ podia ficar em zero apos retomar, com falha do firmware CSOT. Proximo experimento deve ser read-only: durante tela ligada coletar contador IRQ antes e depois de 12s de toques fisicos; depois, caso seja seguro, apagar/reacender a tela manualmente e coletar mensagens `EXP25A_IRQ_RESTORE`, firmware e novo delta da IRQ. Preservar conexao de ADB Wi-Fi e mouse/hub; nenhuma mudanca em GPIO/SPI/USB/sistema de arquivos do tablet.

**Atualização da decisão:** `FASTBOOT_BOOT=OKAY`, `ANDROID_BOOT=PASS`, `EXP25A_RUNTIME=CONFIRMED`, `NVT_IRQ_AT_SAMPLE=203`, `TOUCH_FUNCTIONAL=UNTESTED`, `CSOT_FW_RESUME=UNTESTED`, `FLASH_READY=false`. A primeira retomada ao kernel persistente no teste anterior segue com causa nao determinada.

## EXP25A em hardware — IRQ responde a toques (delta +480 em 12s)

O usuário baixou o script `EXP25A-postboot-diagnostico.ps1`, confirmou no Windows o SHA-256 esperado `8edc95b553c834a2f422a174c812eac49d0b87669e59a5f1e9044d2107f411a2` (`EXP25A DIAGNOSTIC FILE: PASS`) e o executou em ADB Wi-Fi com `-TouchSeconds 12`.

Identidade em execução: `Linux version 4.19.404R (runner@runnervm8k3b6) ... #1 SMP PREEMPT Mon Oct 19 02:32:14 UTC 2026`, compatível com o EXP25A carregado temporariamente.

Saída literal principal:
```text
IRQ antes: 755
Toque fisicamente na tela por 12 segundos enquanto ela estiver ligada.
IRQ depois: 1235; delta=480
SAVED=C:\platform-tools\EXP25A-postboot-evidence\EXP25A-postboot-20261019-004121.txt
NVT_IRQ_DELTA=480
FLASH_READY=false
```

**Interpretação:** incremento de 480 interrupções da NVT-ts IRQ 521 durante janela de 12s solicitando toques físicos (~40/s). Demonstra atividade de interrupção e diferencia-se de coleta prévia da EXP24 com delta zero após resume; não demonstra que houve eventos multitouch de `/dev/input/event8`, funcionalidade do Android, nem comprova a correção de firmware/IRQ após tela dormir. O script oferece Power off/on manual *opcional* e salva `NVT_IRQ_TOTAL_AFTER_WAKE` e as 180 últimas linhas filtradas de `dmesg` com `EXP25A_IRQ_RESTORE` e firmware. **O usuário ainda não compartilhou o relatório nem afirmou que usou o botão Power**, não presumir que fez resume.

**Próximo gate:** obter conteúdo do relatório gerado pelo Windows (pelo menos `NVT_IRQ_TOTAL_AFTER_WAKE`, presença de `EXP25A_IRQ_RESTORE`, mensagens de download firmware e falha CRC); confirmar se o toque produz efeito na UI. Quando necessário, observar eventos brutos `getevent -lt /dev/input/event8` de forma somente leitura com operador disponível. Não reiniciar, não desconectar USB, não modificar SPI/GPIO, não fazer flash. `FLASH_READY=false`.

## EXP25A: log de resume confirma IRQ RESTORE e firmware CSOT bem-sucedidos

Usuário leu com PowerShell o relatório gerado pelo teste real: `C:\platform-tools\EXP25A-postboot-evidence\EXP25A-postboot-20261019-004121.txt`.

```text
NVT_IRQ_TOTAL_BEFORE=755
NVT_IRQ_TOTAL_AFTER=1235
NVT_IRQ_DELTA=480
NVT_IRQ_TOTAL_AFTER_WAKE=2081
[   12.160059] [NVT-ts] update_firmware_request 323: filename is novatek_nt36532_m82_fw_csot.bin
[   12.265226] [NVT-ts] nvt_update_firmware 845: Update firmware success! <105141 us>
[  339.211143] [NVT-ts] nvt_ts_resume 3808: start
[  339.211147] [NVT-ts] update_firmware_request 323: filename is novatek_nt36532_m82_fw_csot.bin
[  339.319124] [NVT-ts] nvt_update_firmware 845: Update firmware success! <107948 us>
[  339.329421] [NVT-ts] nvt_irq_enable 220: enable=1, desc->depth=0
[  339.329429] [NVT-ts] nvt_ts_resume 3846: EXP25A_IRQ_RESTORE db_wakeup=0x01 irq_enabled=1
[  339.329433] [NVT-ts] nvt_ts_resume 3872: reload the game mode cmd
[  339.372165] [NVT-ts] nvt_ts_resume 3878: end
```

**Resultado:** EXP25A `nvt_ts_resume` efetivamente executa a restauração da IRQ mesmo com `db_wakeup=0x01` (antes esta condição bloqueava). Firmware CSOT carregado com sucesso na sequência de `resume` (~108ms), sem indicação de CRC/reset-state failure no excerto filtrado; não generalizar para todos os ciclos sem logs completos. Após a coleta inicial delta de 480 IRQ em 12s, a contagem na coleta pós-wake chegou a 2081 (+846 sobre a medição anterior), mas não há linha de base/intervalo controlado pós-wake para atribuir esse incremento exclusivamente a toques pós-resume. Não há ainda prova de input events `ABS_MT_POSITION_X/Y` em `/dev/input/event8` nem confirmação do usuário de interação touch funcional na UI.

**Gates atualizados:** `EXP25A_RUNTIME=CONFIRMED`, `IRQ_RESTORE_LOG=PASS`, `IRQ_DESC_DEPTH_0=PASS`, `CSOT_FW_RESUME_ONE_CYCLE=PASS`, `IRQ_DELTA_PREWAKE=+480`, `NVT_IRQ_AFTER_WAKE_TOTAL=2081`, `TOUCH_UI_FUNCTION=NOT_VERIFIED`, `POSTWAKE_TOUCH_DELTA=NOT_MEASURED`, `FLASH_READY=false`.

Próximo: teste somente de leitura dos eventos multitouch `getevent -lt /dev/input/event8` durante toque físico; coletar delta IRQ delimitado após resume. Se não houver eventos ou efeito na UI, investigar protocolo/input antes de partir para EXP25B. Não reiniciar nem desconectar USB/hub ou fazer flash.

## 2026-10-24 — Homologação seis ciclos interrompida pelo gate de identidade

O usuário verificou SHA-256 do script `EXP25A-resume-estabilidade-v1.ps1` (`13e42d8de9568e7d65ca3d8077e9e443ce0907c141140d084dbe29050601a008`) e parse no Windows; `EXP25A STABILITY SCRIPT: PASS`. Tentou executar `-Cycles 6 -TouchSeconds 8`.

O script gravou relatório `C:\platform-tools\EXP25A-stability-evidence\EXP25A-resume-20261024-202453.txt` e abortou antes dos ciclos: `TEST_STOPPED_ERROR=Kernel EXP25A desta homologacao NAO confirmado`, pois `/proc/version` retornou `Linux version 4.19.404R (build-user@build-host) ... #14 SMP PREEMPT Sun Aug 23 09:16:08 UTC 2026`, não o `runner@runnervm8k3b6 ... Mon Oct 19 02:32:14 UTC 2026` documentado na sessão EXP25A.

**Interpretação**: teste de estabilidade **0/6**, nenhuma falha de resume observada; apenas gate de identidade protegeu contra atribuir resultados do kernel persistente à EXP25A. Provável reboot intermediário por transcorrerem dias desde o teste com fastboot boot temporário, mas não há prova do motivo. Não considerar regressão da EXP25A. O script declara que não alterou kernel, USB ou partições; `FLASH_READY=false`.

Próximo passo apenas quando o usuário estiver presencialmente preparado com mouse/hub e retorno físico de contingência: conferir SHA do candidato e estado ADB, USB fastboot, product=pipa/slot=b/unlocked=yes/is-userspace=no, executar apenas `fastboot boot` em RAM e reconfirmar `/proc/version` antes de repetir seis ciclos. Sem flash, erase, set_active, reset USB nem reinicializações automatizadas da fase de estabilidade.

## 2026-10-24 — EXP25A reativada para homologacao

Usuario revalidou hash do candidato (`EXP25A IMAGE: PASS`) e entrou no bootloader: unico serial 6665d3e6; product=pipa, slot=b, unlocked=yes, is-userspace=no.
Fastboot boot temporal: Sending boot.img OKAY [0.683s]; Booting OKAY [0.238s]; Finished. Total time 0.942s.
ADB USB apos boot: sys.boot_completed=1; /proc/version=Linux version 4.19.404R (runner@runnervm8k3b6) ... #1 SMP PREEMPT Mon Oct 19 02:32:14 UTC 2026.
Estado: runtime EXP25A confirmado nesta sessao. Homologacao multiciclo 0/6; executar script ja validado de seis ciclos somente apos ADB Wi-Fi estar disponivel e plano de controle fisico pronto. Sem gravacao de particao. FLASH_READY=false.

## 2026-10-24 — Homologacao multiciclo: 2 PASS, interrupcao ADB USB no terceiro

Usuario executou EXP25A-resume-estabilidade-v1.ps1 por ADB USB serial 6665d3e6 com seis ciclos pretendidos. O script validou runtime EXP25A (pipa slot b, runner@runnervm8k3b6, #1 2026-10-19) e registrou boot_id c9c5a5af-c470-4e39-9adf-9f8f8c57e809. Baseline EXP25A_IRQ_RESTORE=1, firmware Update success=2.

Ciclo 1: IRQ pre-sleep 51, after-wake 1699, restore_added=1, fw_success_added=1, touch delta=374, UI touch real=s, PASS.
Ciclo 2: IRQ pre-sleep 2285, after-wake 2285, restore_added=1, fw_success_added=1, touch delta=453, UI touch real=s, PASS.
Ciclo 3: IRQ pre-sleep 2745; apos o usuario operar Power para apagar e reacender, comando ADB pelo serial USB 6665d3e6 falhou apos quatro tentativas com adb.exe device not found, antes de verificar boot_id e novas IRQ ou firmware; teste abortou. Nao confundir com falha touchscreen; diferenciar USB gadget ou transport reset, cabo, reboot inesperado, reinicializacao kernel, outros. O script Invoke-Tablet tenta 4 vezes com 3 segundos de espera; transporte USB fixo, sem fallback Wi-Fi.

Relatorio Windows: C:\platform-tools\EXP25A-stability-evidence\EXP25A-resume-20261024-203001.txt. Arquivo completo ainda nao revisado. Sessao de kernel EXP25A durante os dois primeiros ciclos confirmada. Gates STABILITY=2/6 PASS, CYCLE_3=INTERRUPTED_ADB_LOST, TOUCH_AFTER_CYCLE_3=UNKNOWN, FLASH_READY=false.

Proximo passo estritamente read-only sem reiniciar/desconectar: adb devices -l, consultar ADB USB e Wi-Fi TLS separadamente; caso um transporte responda, coletar cat /proc/sys/kernel/random/boot_id para comparar com baseline c9c5a5af-c470-4e39-9adf-9f8f8c57e809, /proc/version, uptime, sys.boot_completed, sys.usb.state, sys.boot.reason. Se boot_id igual, tablet nao reiniciou, e confirmar restauro USB. Se mudou, registrar reboot e nao continuar estabilidade da mesma sessao. So apos diagnostico adaptar coleta multiciclo para canal Wi-Fi se valido, sem mudar porta ou reiniciar. Nenhum flash, erase, set_active ou alteracao USB. FLASH_READY=false.

## 2026-10-24 — Mesmo boot apos perda de ADB, script V2

Depois da interrupcao do ciclo 3, usuario coletou ADB read-only sem desconectar USB: USB serial 6665d3e6 em estado device; Wi-Fi TLS indisponivel. /proc/sys/kernel/random/boot_id=c9c5a5af-c470-4e39-9adf-9f8f8c57e809, exatamente igual ao baseline da homologacao. /proc/version manteve EXP25A runner@runnervm8k3b6, compilacao 2026-10-19 02:32:14 UTC. /proc/uptime=411.36 2884.09; sys.usb.state vazio, sys.boot.reason=bootloader, boot_completed=1.

Conclusao: kernel nao reiniciou no intervalo; desconexao do ADB USB foi transitoria e o transporte recuperou. Causa ainda nao isolada (USB gadget, suspensao, cabo, transporte, etc.). Nao interpretar o terceiro ciclo como falha de touchscreen. Gate de estabilidade concluido somente 2/6 PASS; ciclo 3 interrompido sem verificar.

Gerado em conversa o script local EXP25A-resume-estabilidade-v2.ps1 (8.025 bytes), SHA256 d3bc193d92844992e264670d4a6a02332f7ea3b067b429474569e1fa67166196, derivado diretamente de V1. Alteracoes: aguardar ate aproximadamente 90 segundos para retorno de ADB USB, registrar tentativas e recuperacao, opcional ExpectedBootId para bloquear reboot intermediario, revalidar boot_id apos toques, reiniciar contagem de seis ciclos em nova rodada; sem operacoes de escrita no dispositivo. Auditoria estatica read-only OK; parser Windows precisa ser validado pelo usuario; nao foi executado em hardware.

Proxima etapa: com EXP25A temporaria ativa e USB reconectado, verificar hash+parse em Windows e executar V2 com -Serial 6665d3e6 -ExpectedBootId c9c5a5af-c470-4e39-9adf-9f8f8c57e809 -ReconnectSeconds 90 -Cycles 6 -TouchSeconds 8. Evitar reboot/fastboot/desconexao. FLASH_READY=false.
