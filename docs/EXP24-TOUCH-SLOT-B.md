# EXP24 — Touchscreen inoperante no Xiaomi Pad 6 pipa / slot _b

## Problema e restricoes

- O usuário relata touchscreen sem resposta no slot `_b`, com recorrências anteriores à análise atual. Causa ainda desconhecida; não atribuir ao slot, ROM, kernel experimental, firmware, painel nem componente físico sem evidência.
- O usuário depende de **hub USB + receptor 2.4GHz/mouse** para controlar o tablet. Não remover o hub como condição da investigação. O kernel EXP24 foi iniciado **temporariamente** via `fastboot boot`; persistente E404 conservado. **FLASH_READY=false**.
- Informações de slot: pipa slot `b`, bootloader desbloqueado, `fastboot boot` EXP24 bem sucedido. Não foi feito teste A/B em estado equivalente, nem verificado touchscreen no slot A.
- Evidência histórica do mesmo aparelho: touchscreen ativo em `/dev/input/event8`, com ABS_MT, em testes anteriores de software Android. Índices eventN são dinâmicos: não assumir event8 hoje.

## Investigacao read-only do build concreto EXP24

Artefato original de CI #39179600330, `pipa-exp24-ethernet-clang21-4.zip`, analisado independentemente: `exp06-work/out/.config` registra `CONFIG_TOUCHSCREEN_NT36532_HOSTDL_SPI=y`, `CONFIG_TOUCHSCREEN_XIAOMI_TOUCHFEATURE=y`, `CONFIG_TOUCHSCREEN_COMMON=y`, `CONFIG_FW_LOADER=y`. Ou seja, **driver Novatek NT36532 por SPI está compilado embutido**, mas isso não demonstra que o controlador tenha sido detectado, firmware carregado ou eventos enviados.

Na base exata `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`: `drivers/input/touchscreen/nt36532/Kconfig` define driver de touchscreen Novatek NT36532 no-flash por SPI. `drivers/input/touchscreen/nt36532/nt36xxx.h` define `NVT_SPI_NAME="NVT-ts"`, `NVT_TS_NAME="NVTCapacitiveTouchScreen"`, fallback `BOOT_UPDATE_FIRMWARE_NAME="novatek_nt36532_m82_fw_tm.bin"`. `drivers/input/touchscreen/nt36532/nt36xxx.c` escolhe nome firmware **dinamicamente conforme painel** via `nvt_match_fw()`; portanto ausência do fallback em um caminho não comprova ausência do firmware real. O `probe` deveria registrar input `NVTCapacitiveTouchScreen`, solicitar IRQ e abrir o caminho de download de firmware. Conferir erros de `NVT-ts`, `nt36`, request_firmware e entrada IRQ.

## Critérios para isolar falha

1. `getevent -pl` e `/proc/bus/input/devices` **não mostram** `NVTCapacitiveTouchScreen`: priorizar falha no SPI/probe/firmware/DT ou driver não inicializado; conferir também dmesg e `/sys/bus/spi/{devices,drivers}`. Conferir vendor_boot/DTB compatível, **sem reempacotar** antes de prova.
2. Input NVT presente, mas **nenhum EV_ABS/SYN_REPORT** sob toque na tela: inspecionar IRQ/controller/firmware/inicialização; capturar evento de forma controlada depois de identificar eventN corretamente, sem bloquear o shell indefinidamente.
3. EV_ABS presente, mas Android ignora: investigar InputReader, arquivos `.idc`, surface/display, rotação e configurações/overlays.
4. Contraste EXP24 vs E404 ou slot A/B requer ambientes equivalentes e backup. `fastboot boot` EXP24 não altera slot; slot sozinho não explica falha sem comparação. Reboot para testar E404 apenas após coletar logs e reconhecer que se perderá a sessão EXP24.

## Instrumento

Arquivo de diagnóstico oferecido na conversa `EXP24-pipa-slotB-touch-readonly.ps1`: exige ADB Wi-Fi com `su`, `pipa` slot `_b` kernel com Clang21; coleta `/proc/bus/input/devices`, `getevent -pl` (capacidades, **sem stream/event capture**), dispositivos/drivers SPI, `dumpsys input` filtrado, `dmesg` touch/firmware/probe, `/proc/interrupts` touch/SPI e diretórios firmware. Coleta é somente leitura; não escreve em firmware/sysfs, não altera configuração do sistema/boot, não mexe no hub. SHA256 do arquivo ofertado: `cb4e20517e6463f9495f88b38de5035c12a315477f8d5e585ae780a0c4d991be`. Revisão estática de `$PID` reservado, interpolação PowerShell e balanceamento de chaves passou. PowerShell Parser/ADB real **ainda não foram executados neste ambiente**; exigir parser em Windows antes da coleta.

## Contexto USB relacionado mas separado

Em amostragem V2 de 18 pontos do mesmo EXP24, hubs Genesys `05e3:0610` (USB2) e `05e3:0625` (USB3) ficaram listados enquanto dongle RTL8153 `0bda:8153` ausente (`0/18`); houve várias novas entradas de input de mouse sem fio `32c2` no `dmesg` e erros de protocolo USB `r8152 ... -71` em eventos anteriores. Também foi relatada oscilação com certos carregadores desde antes do EXP24. Podem ser pistas de subsistema de porta/host/energia, **não provas da causa do touchscreen** (controlador interno SPI).

## Estado de testes

- DRIVER_TOUCH_NT36532_CONFIG: CONFIRMED
- PHYSICAL_TOUCHSCREEN_INPUT_PRESENT: PENDING
- NVT_SPI_PROBE_AND_FW: PENDING
- IRQ_AND_INPUT_EVENTS: PENDING
- ANDROID_INPUT_DISPATCH: PENDING
- SLOT_A_VS_B: NOT_TESTED
- FLASH_READY=false

## Coleta 23:05 — Novatek firmware falha em cinco retomadas

Foi analisado o relatorio privado `EXP24-touch-slotB-20261018-230535.txt`, capturado em pipa slot b e kernel EXP24 Clang21 via ADB Wi-Fi root. A versao original do relatorio nao foi comitada porque inclui dados do sistema.

**Deteccao OK:** `NVTCapacitiveTouchScreen` em `/dev/input/event8` com suporte `ABS_MT` e `NVTCapacitivePen` event9; dispositivo SPI `spi0.0`, driver `NVT-ts`, probe do chip `This is NVT touch IC`, IRQ 521 `request irq succeed`, e InputReader Android em touch DIRECT associado ao display 0 ativo.

**Painel concreto CSOT:** o driver detectou painel pelo lockdown `0x53,0x42` e selecionou `novatek_nt36532_m82_fw_csot.bin` em vez de `novatek_nt36532_m82_fw_tm.bin`. O primeiro download terminou em `Update firmware success!` em uptime ~12.297s (fw_ver 0x12, PID 0x5975). A falta do arquivo TM num caminho consultado nao explica este evento e nao prova CSOT ausente.

**Defeito reproduzivel:** em **5 de 5 retomadas** registradas apos tela apagar, `nvt_ts_resume` inicia novo download CSOT, `nvt_check_fw_reset_state` le sequencia zerada apos repeticoes, `nvt_download_firmware_hw_crc` atinge retry=3, `crc_done=0` e `golden=0`, e reporta `Download Firmware failed. (-1)` mais `download firmware failed, ignore check fw state`. Up times proximos: 34s, 73s, 98s, 1014s, 2782s. O `resume` ainda emite `end` nas cinco falhas. IRQ `NVT-ts` 521 apresenta contadores zero no momento da coleta, mas nao houve teste dinamico de evento sob toque, logo ausencia de IRQ fisica ainda a confirmar.

**Achado de codigo na base E404 fixa** `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`: `drivers/input/touchscreen/nt36532/nt36xxx.c::nvt_ts_resume()` inclui `if (nvt_update_firmware(ts->fw_name)) NVT_ERR("download firmware failed, ignore check fw state"); else nvt_check_fw_reset_state(RESET_STATE_REK);`, e depois marca `bTouchIsAwake = 1` e retorna `0` mesmo no caminho de erro. Isso pode declarar dispositivo acordado apesar de firmware nao executavel, sem tentativa adicional nesta rotina. `nvt_irq_enable(true)` no resume e condicionado a `!ts->db_wakeup`, tambem requer instrumentacao, mas nao justifica modificacao direta sem observacao.

**Proximo teste nao invasivo:** tela ligada, ler linha `NVT-ts` de `/proc/interrupts`, tocar a tela repetidamente por 10 segundos, ler linha novamente e filtrar dmesg; opcional capturar getevent com timeout apos validar comando Android. Diferenciar falha fisica do IRQ vs evento entregue mas descartado pelo Android. EXP25 potencial deve focar reinicializacao segura do controlador SPI/firmware CSOT com estrategia limitada, preservar mouse/hub, sem flashing de firmware em particoes, sem troca de slot e sem alterar sistema vivo. `FLASH_READY=false`.

## EXP25-PRE — Auditoria de IRQ Novatek e coleta controlada

Auditoria adicional do relatório de 23:05: foram encontrados **exatamente três logs** `nvt_irq_enable` desde o boot: em uptime ~0.841303s `enable=0 depth=1`, ~0.841421s `enable=1 depth=0`, e ~33.655903s `enable=0 depth=1`. **Nenhum log posterior `enable=1` nas cinco retomadas** registradas. O contador `/proc/interrupts` `521 NVT-ts` estava em zero em todos os oito CPUs no momento da coleta. Isso é evidência forte de um segundo problema de IRQ possivelmente mantida desabilitada, além das cinco falhas de firmware CSOT.

Fonte do driver conferida no commit E404 pinado: `nt36xxx.c::nvt_ts_suspend()` desabilita a IRQ **somente se** `!ts->db_wakeup`; `nvt_ts_resume()` habilita novamente com a mesma condição atual, isto é, também **somente se** `!ts->db_wakeup`. Alteração de `db_wakeup` entre essas fases pode deixar IRQ desligada permanentemente. Essa hipótese combina com os logs, mas **a mudança de estado não foi diretamente medida neste ciclo**, e mensagens de log sozinhas não substituem leitura dinâmica do contador de IRQ durante toque. Além disso, o callback de resume ignora falha firmware, ainda marca `bTouchIsAwake=1` e retorna 0.

Fonte `nt36xxx.h`: `NVT_TOUCH_SUPPORT_HW_RST=0`, `NVT_TOUCH_ESD_PROTECT=0`, `NVT_TOUCH_WDT_RECOVERY=1`. A rotina `nvt_download_firmware_hw_crc()` ja faz ate **3 tentativas**, cada uma iniciada por `nvt_bootloader_reset`, antes do erro `nvt_check_fw_reset_state`. Aumentar o numero de retries nao e uma correcao fundamentada sem diagnostico adicional. Nao forcar `reset_gpio` em dispositivo com suporte HW reset desligado. Firmware selecionado pelo painel CSOT, nao firmware TM ausente em um caminho.

Gerado `EXP25-pipa-touch-irq-confirmacao.ps1` (somente leitura, sem alterar tablet), **SHA256 `bb2338e91a3bbf6e6a1782b706f677478ba08119df18b9fdada23490d1d2f111`**, ~5.4 KB. Script valida ADB TLS Wi-Fi, root, pipa, EXP24 Clang21 e evento `NVTCapacitiveTouchScreen=event8`; confirma display via `dumpsys power`, coleta IRQ antes e depois de janela limitada de toques fisicos (`-TouchSeconds 12`), delta de IRQ, e salva dmesg de NVT. A saída de `dmesg` é somente leitura. Script revisado staticamente para variáveis reservadas `$PID`, pontuacao de interpolacao e balanço de delimitadores, **PowerShell real nao executado aqui**. Nao capturar eventos brutos sem confirmar eventN/tela, nem fazer rebind/firmware/sysfs.

**Gate de experimento antes do EXP25 driver:** se IRQ delta=0 com tela ligada e usuario tocando, priorizar restauracao de IRQ e recarga de firmware sob controle de estados/lock com telemetria, compilacao Clang21, teste CI e `fastboot boot` temporario. Se delta>0, isolar `getevent`/InputReader antes de mudar driver. Nao assumir que somente reabilitar IRQ corrige o firmware; podem ser duas causas independentes. **Nenhum patch executado nem EXP25 compilada ainda**. `FLASH_READY=false`.
