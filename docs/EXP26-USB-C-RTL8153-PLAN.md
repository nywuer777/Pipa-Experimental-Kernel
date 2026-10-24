# EXP26 — Investigacao de USB-C/OTG e Ethernet Realtek RTL8153

## Decisao de escopo

Avancar da correcao funcional de touchscreen EXP25A para USB-C/OTG/Realtek. NAO alterar driver nem compilar nova Image ate a falha ser isolada por evidencias de hardware. Codinome de investigacao EXP26; versao do artefato atual de kernel permanece EXP25A ate uma compilacao aprovada.

## Evidencias ja confirmadas

- EXP25A boot temporario em pipa slot b, Android ativo, kernel runner compilado 2026-10-19. NVT IRQ 521 restaurada em resume com `EXP25A_IRQ_RESTORE`, firmware CSOT recarregado com sucesso, eventos ABS_MT reais em event8 e interface touchscreen funcional relatada pelo usuario.
- Teste inicial multiciclo V1: dois ciclos completos com toque funcional. V2: tres ciclos completos com restauracao e firmware novos, toque funcional e IRQ positivas, mais quarto ciclo com toque real funcional (IRQ +80) mas leitura de logs cedo demais (`RESTORES_ADDED=0` e `FW_SUCCESS_ADDED=0`); resumo final indica mais um sucesso de cada. **Homologacao 6/6 nao concluida**, logo estabilidade de longo prazo permanece aberta.
- USB ADB sumiu no ciclo 3 da V1, mas reapareceu com o MESMO `/proc/sys/kernel/random/boot_id` c9c5a5af-c470-4e39-9adf-9f8f8c57e809; isto exclui reboot do kernel naquele intervalo, nao identifica a origem da desconexao.
- EXP24 Ethernet: RTL8153 USB VID:PID `0bda:8153` identificado em sessoes anteriores com driver r8152, SuperSpeed 5000Mb/s, interface eth0, IP e DHCP/carrier. Em outras sessoes houve 0/18 amostras presentes e erros USB -71/EPROTO. Hub 05e3. Nao presumir que dongle esteve fisicamente conectado em todas as observacoes.
- Usuario relatou instabilidade de carregamento USB-C em alguns cabos/carregadores ANTERIOR ao EXP24; origem nao estabelecida. O dongle funciona em outro dispositivo.

## Objetivos em ordem

1. EXP26.0: **linha de base passiva** na EXP25A atual sem trocar cabos: confirmar boot ID, runtime, dmesg USB/Type-C/PD, `ls /sys/bus/usb/devices`, `dumpsys usb`, `ip link`, e estado ADB USB. Registrar se o periférico Ethernet esta fisicamente presente ou ausente.
2. EXP26.1: **separar falha de enumeração vs driver**: somente quando existir caminho alternativo de controle confirmado (touchscreen + ADB Wi-Fi + hub/mouse de contingencia), conectar fisicamente o hub/RTL8153 e coletar VID/PID, bus speed, link driver, eth interface, carrier, IP e dmesg com marcas temporais. Nao reconectar repetidamente na fase zero.
3. EXP26.2: **teste de continuidade e retomada** em configuracao fisica estavel, comparando before/after de USB class/typec/pmic, sem injetar comandos que reiniciem USB ou alterem negociacao de energia. Medir perdas de enumeracao, erros -71, speed downgrade, rebind espontaneo r8152 e retorno Ethernet.
4. EXP26.3: **diagnostico causal e fix minimo se houver reproducao**, com gate de regressao para touchscreen Novatek, USB mouse, carga, USB ethernet e ADB; compilar no GitHub CI, testar apenas por fastboot boot temporario, sem flash ate certificacao separada.

## Regras de seguranca

- Nao usar `fastboot flash`, `set_active`, `erase`, reboots automatizados, reset de controlador USB, `unbind`/`bind` de drivers, escrita em `sysfs`, trocar tensoes PD ou forcar alimentacao. `FLASH_READY=false`.
- ADB via USB e dongle no mesmo USB-C competem pela mesma porta. **Nao trocar cabo USB para hub ate comprovar caminho ADB Wi-Fi e que touchscreen esta funcional no momento.** Mouse/hub devem ser recuperaveis, pois touch pode voltar a falhar apos resume.
- Se houver calor excessivo, cheiro, sinais eletricos anormais ou desconexoes repetidas com uma fonte, nao continuar testes de carregamento.
- Dados do USB sem receptor HID quando o usuario voluntariamente desconectou hub sao baseline esperado, nao erro do kernel.

## Primeiro gate passivo solicitado ao usuario

Enquanto o ADB USB ainda estiver disponivel, colher `adb devices -l`, `getprop ro.product.device`, `getprop ro.boot.slot_suffix`, `getprop sys.boot_completed`, `/proc/version`, `/proc/sys/kernel/random/boot_id`, `dumpsys usb`, `ls -l /sys/bus/usb/devices`, `dmesg` filtrado por `usb|dwc3|xhci|typec|vbus|pd|r8152|8153|EPROTO|error -71` e interfaces de rede. Somente leitura. Perguntar apenas qual periferico esta fisicamente conectado (PC direto ou hub/RTL8153), para correlacionar observacoes, sem pressupor conexao.

## Estados

TOUCH_FUNCTIONAL=PASS; TOUCH_SIX_CYCLE_STABILITY=INCOMPLETE; USB_ETHERNET_DRIVER_CAPABILITY=DEMONSTRATED_EXP24; USB_HOTPLUG_RELIABILITY=NOT_CERTIFIED; USB_TRANSPORT_SUSPEND=INTERMITTENT; EXP26_CODE_CHANGES=NONE; FLASH_READY=false.

## EXP26.0 — Coleta USB por ADB no kernel EXP25A

Leitura read-only reportada pelo usuario no Android EXP25A: `/proc/version` indica `runner@runnervm8k3b6`, Clang 21, kernel `4.19.404R`, compilado 2026-10-19 02:32:14 UTC; boot ID `c9c5a5af-c470-4e39-9adf-9f8f8c57e809` permanece igual ao da homologacao touch. ADB USB serial `6665d3e6` operacional no momento da coleta.

`/sys/bus/usb/devices`: `total 0`; USB host não apresentou perifericos externos. `/sys/bus/usb/drivers` inclui `r8152`, `cdc_ether`, `cdc_ncm`, `asix`, `ax88179_178a`, `usbhid`, `hub` e outros. Isso atesta registro de drivers, nao deteccao/binding do RTL8153. `dumpsys usb` retornou `connected=true`, `configured=true`, `host_connected=false` para estado de dispositivo Android ligado a PC, sem prova de host/OTG.

`ip link show` sem root falhou `request send failed: Permission denied`; essa falha de coleta nao constitui falha de rede. Consultar `su -c ip ...` e/ou `/sys/class/net` read-only.

Mensagens dmesg USB gadget (uptime segundos) confirmam desconexoes com reconexoes do USB gadget Android:

```text
297.539515 DISCONNECTED; 299.778273 CONNECTED; 299.861334 CONFIGURED
626.788655 DISCONNECTED; 626.871673 CONNECTED; 626.892553 CONFIGURED
627.545364 DISCONNECTED; 627.840578 CONNECTED; 627.922545 CONFIGURED
628.784875 DISCONNECTED; 632.521769 CONNECTED; 632.603088 CONFIGURED
```

Essa sequencia e compativel com perda transitoria do ADB USB observada na homologacao touchscreen, mas **nao prova** se a causa foi dispositivo gadget, cabo/porta, power, suspensao ou host Windows. Nao relacionar automaticamente aos problemas de deteccao em modo OTG/RTL8153, pois o tablet opera como dispositivo USB conectado a um PC no teste atual. `dmesg` de inicializacao mostra `usbcore: registered new interface driver r8152` em uptime 0.600676s; isso apenas prova driver registrado.

**Proximo passo:** analisar vizinhanca temporal dos eventos gadget na mesma sessao, checar propriedades `sys.usb.*`, `dumpsys usb` e estados power_supply/Type-C e redes read-only. Nao reconectar cabos nem mudar para host/OTG ate documentar caminho alternativo de acesso confiavel. `FLASH_READY=false`.
