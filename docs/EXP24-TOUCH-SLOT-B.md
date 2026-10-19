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
