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

## EXP26.0 — Type-C partner, alimentação e contexto temporal USB gadget

Coleta complementar do usuário no tablet ainda em EXP25A no boot c9c5a5af-c470-4e39-9adf-9f8f8c57e809: `/proc/uptime = 1731.92 12985.68`, `sys.usb.config=adb`, `sys.usb.state` vazio nesta leitura, `sys.usb.controller=a600000.dwc3`.

USB Type-C registrou `/sys/class/typec/port0` e `port0-partner`, ambos relacionados ao PM8150B USB PD PHY em `.../qcom,pm8150b@2:qcom,usb-pdphy@1700/typec/port0`. A presença de partner prova partner reconhecido pela classe typec, mas NÃO confirma contrato PD, papéis específicos ou tensão. `dumpsys battery`: USB powered=true, battery level=99, status=2 (carregando), voltage=4416 (mV da bateria), Max charging voltage=4416980 (não confundir com tensão VBUS negociada).

`/sys/class/power_supply` inclui battery, bms, usb, pc_port, main, dc, wireless, bq2597x-standalone e outros; paths disponíveis para leitura de status online/real_type/usb_type/voltage_now/current_now/PD/Type-C, sem escritas.

Com root a listagem de `/sys/class/net` e `ip -o link show` confirmou apenas wlan0/1, p2p0, wifi-aware0, rmnet_ipa0, dummy0, lo, vti e tunnels; nenhum `eth0` ou `usb0`. Isto é esperado com tablet em modo USB gadget ligado ao computador, sem dongle Realtek presente. O erro anterior de `ip link show` foi privilégio, não falha de rede.

Sequências significativas do `dmesg`: 297.534 `smblib_wireless_set_rx_sleep enable: 1`, 297.539 `USB_STATE=DISCONNECTED`, healthd muda de st=2 (charging) para st=3 (discharging) e st=4 (not charging), depois recupera st=2; 628.782 `smblib_wireless_set_rx_sleep enable: 1`, 628.784 `USB_STATE=DISCONNECTED`, healthd st=3, depois st=4, 631.570 `smblib_wireless_set_rx_sleep enable: 0`, 632.521 USB CONNECTED, 632.603 USB CONFIGURED. Eventos entre 626 e 628 incluem duas reenumeracoes rapidas. A coincidência temporal motiva investigação do subsistema PMIC/SMB5/USB-C, mas NÃO prova causalidade de alimentação, nem defeito PHY/PD/cabo.

Próximo gate read-only enquanto o PC permanece conectado: ler individualmente atributos existentes sob `/sys/class/typec/port0/` (data_role, power_role, power_operation_mode, orientation), `port0-partner/supports_usb_power_delivery`, e `/sys/class/power_supply/usb/` (online, present, voltage_now, current_now, usb_type, real_type, typec_mode). Não escrever nestes atributos mesmo quando o kernel os exponha como R/W. Coletar no Android com root por ADB USB sem trocar cabo; de preferência identificar após outro evento espontâneo, sem provocar desconexão. Somente depois confirmar controle alternativo e ensaiar USB host + RTL8153.

Fontes dos significados de Type-C para Linux v4.19: https://www.kernel.org/doc/html/v4.19/driver-api/usb/typec.html e https://kernel.googlesource.com/pub/scm/linux/kernel/git/cip/linux-cip/+/refs/tags/v4.19.97/Documentation/ABI/testing/sysfs-class-typec; unidades power_supply: https://www.kernel.org/doc/html/latest/power/power_supply_class.html.

EXP26_FIX=NOT_STARTED; USB_PM_ROOT_CAUSE=UNDETERMINED; FLASH_READY=false.

## EXP26.0B — Type-C sink/device 5V sem PD no parceiro, coleta em PC

Coleta de usuario (EXP25A boot temporario, ligada ao PC diretamente via USB gadget ADB):

```text
/sys/class/typec/port0/data_role = host [device]
/sys/class/typec/port0/power_role = source [sink]
/sys/class/typec/port0/power_operation_mode = 3.0A
/sys/class/typec/port0-partner/supports_usb_power_delivery = no
/sys/class/power_supply/usb/online = 1
/sys/class/power_supply/usb/present = 1
/sys/class/power_supply/usb/voltage_now = 4916130
/sys/class/power_supply/usb/real_type = USB
/sys/class/power_supply/usb/typec_mode = Source attached (high current)
orientation/current_now/usb_type = INDISPONIVEL
```

Segundo ABI do Linux Type-C, o papel ativo aparece entre colchetes: device (dados) e sink (energia). A classe Type-C reporta modo de corrente de 3.0A em USB Type-C (não equivale à corrente realmente consumida e não representa negociação Power Delivery); a propriedade do PARCEIRO USB-PD reportou no, e o modo do sistema não reporta usb_power_delivery. O atributo voltage_now normalmente é microvolts, cerca de 4,916 V no momento, coerente com 5 V nominal; não demonstra integridade elétrica durante desconexões. Real_type USB, present=1, online=1. Orientação e current_now indisponíveis não são falhas demonstradas.

Esse baseline device/sink é esperado para Android conectado ao PC. Mesmo que 3.0A seja anunciado, não se deve inferir que o PC efetivamente fornece 3A; distinguir convenções do driver e limitações do sink. Não houve evidência de sobretensão ou evento de PD nesta foto. A alternância anterior do USB gadget e do estado charging/discharging continua sem causalidade comprovada; não alterar firmware, tensão, power_role ou data_role pelo sysfs.

Fontes ABI: https://kernel.googlesource.com/pub/scm/linux/kernel/git/cip/linux-cip/+/refs/tags/v4.19.97/Documentation/ABI/testing/sysfs-class-typec e https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-class-power.

Próximo gate: leitura passiva de tipos/correntes máximas e estado gadget/PMIC, eventualmente amostragem temporal sem provocação, depois validar Android touch e ADB Wi-Fi como controle alternativo antes de mudar fisicamente PC para hub/RTL8153. EXP26_CODE_CHANGES=NONE; FLASH_READY=false.

## EXP26.1 — ADB TLS Wi-Fi auto-reconectado, conexao TCP direta recusada

Teste de conectividade reportado pelo usuario: `adb connect 192.168.1.65:35185` falhou com erro Windows 10061 (conexao ativamente recusada). Em seguida, `adb devices -l` listou dois dispositivos em estado `device`: USB serial `6665d3e6` (transport_id 19) e ADB TLS Wi-Fi `adb-6665d3e6-i745L2._adb-tls-connect._tcp` (transport_id 20). `adb -s 192.168.1.65:35185 get-state` falhou com `device not found`.

Interpretação: a tentativa direta no endpoint IP:porta nao foi estabelecida, mas existe **aparente reconexao automatica TLS via identificador mDNS**; nao inferir falha de Wi-Fi nem deduzir que IP/porta antigo ainda esteja disponivel. Validar `adb -s adb-6665d3e6-i745L2._adb-tls-connect._tcp get-state` e identidade (`ro.product.device=pipa`, `ro.boot.slot_suffix=_b`, `sys.boot_completed=1`, `/proc/version` do EXP25A, `boot_id=c9c5a5af-c470-4e39-9adf-9f8f8c57e809`) antes de considerar trocar fisicamente cabo USB por hub/RTL8153.

Nenhum comando de reconnect/restart/reset USB ou troca de cabeamento necessarios no momento; preservar USB conectado ao PC ate verificacao do canal Wi-Fi. `FLASH_READY=false`.

## EXP26.1 — Controle alternativo ADB Wi-Fi TLS validado

O usuário confirmou o acesso TLS Wi-Fi em `adb-6665d3e6-i745L2._adb-tls-connect._tcp` com `get-state=device`; `ro.product.device=pipa`, `ro.boot.slot_suffix=_b`, `sys.boot_completed=1`, `cat /proc/sys/kernel/random/boot_id=c9c5a5af-c470-4e39-9adf-9f8f8c57e809` e `/proc/version` do EXP25A (`runner@runnervm8k3b6`, Oct 19 02:32:14 UTC). `EXP26 WIFI ADB: PASS`. Esta verificação é posterior à recusa de conexão TCP direta numa porta mDNS que não estava acessível, mas confirma o transporte TLS pelo identificador original.

**Gate de segurança para próximo teste físico:** o touchscreen foi confirmado funcional na EXP25A, mas a homologação 6/6 não está completa. Operador deve testar resposta do touch no momento da troca; deixar ADB Wi-Fi ativo; então pode, caso tenha controle físico de contingência, trocar o cabo USB do PC pelo hub (com mouse e RTL8153), sem forçar reset USB, sem mudar estado OTG por sysfs. A troca física deve ser documentada porque resultados com USB gadget ligado ao PC não são resultados do host OTG. Se ADB Wi-Fi desaparecer, usar o touchscreen para observar estado e recuperar ligação normalmente; não fazer reboot/flash.

**Próximo gate read-only:** com hub e adaptador efetivamente conectados, ler via ADB Wi-Fi as instâncias em `/sys/bus/usb/devices`, os IDs de fabricante/produto, estado de `/sys/bus/usb/drivers/r8152`, interfaces `/sys/class/net`, `ip -o link show` com root, carrier da eth0 quando presente e últimos logs USB/r8152/EPROTO. Ausência do RTL8153 deve ser qualificada como estado físico + ausência/presença em sysfs, sem concluir defeito do driver automaticamente. EXP26_CODE_CHANGES=NONE; FLASH_READY=false.


## EXP26.1: RTL8153 enumerado e Ethernet com carrier

Coleta em EXP25A: hub USB 05e3:0625 no caminho 2-1, adaptador 0bda:8153 em 2-1.1, ambos a 5000 Mb/s no barramento USB. Symlink 2-1.1:1.0 no driver r8152; eth0 criada com UP e LOWER_UP. Dmesg indica eth0 carrier on aos 2212.286s. DHCP, IP, rota e estabilidade temporal permanecem pendentes. Não modificar USB nem partições. FLASH_READY=false.

## EXP26.1 — ADB TLS inacessivel enquanto hub RTL8153 conectado

O usuario relatou que, com o hub e Ethernet RTL8153 conectados, o ADB Wi-Fi nao esta acessivel. Nao há medicao de `adb devices`, mDNS ou tela de Wi-Fi apos o evento, portanto **causa da perda de ADB nao comprovada**: o Android pode alterar o default route, o Wi-Fi pode desconectar ou a sessao ADB TLS pode deixar de anunciar endpoint. A associacao temporal nao prova que a Ethernet desativou fisicamente o Wi-Fi.

O hardware USB host e Realtek estao comprovados pela leitura imediatamente anterior: hub 05e3:0625 a 5000Mb/s, RTL8153 0bda:8153 a 5000Mb/s, driver r8152 associado, eth0 UP/LOWER_UP, carrier on. IP, DHCP e estabilidade ainda nao medidos.

Plano SEM interromper Ethernet: manter hub, RTL8153 e mouse conectados, não reiniciar; verificar no Android pelo toque se o Wi-Fi permanece associado, se Depuracao sem fio esta ligada e o endpoint atual; no Windows executar somente `adb devices -l` e `adb mdns services`, conectando somente ao endereco/porta **atual** publicado pela tela ou mDNS. Se o ADB continuar indisponivel, usar terminal local existente (Termux) com root para ler `ip -4 addr show dev eth0`, rotas e `/sys/class/net/eth0/{carrier,operstate,speed,duplex}` sem executar reset, `ifconfig up/down`, `adb tcpip` ou troca do USB. O teste principal pode continuar via terminal local. Nenhuma escrita em sysfs/particoes. `FLASH_READY=false`.

## EXP26.2 — Termux KernelSU e Ethernet 1Gb/s com IPv4

Coleta local feita diretamente no Termux do Xiaomi Pad 6, usando `su -c`, confirmou `uid=0(root) gid=0(root) groups=0(root) context=u:r:ksu:s0` e `command -v su` retornou `/data/data/com.termux/files/usr/bin/su`. Assim, acesso de diagnostico local com root funciona sem ADB Wi-Fi.

Resultado em `eth0`: `<BROADCAST,MULTICAST,UP,LOWER_UP>`, estado `UP`, `inet 192.168.1.102/24` broadcast `192.168.1.255`, `valid_lft forever preferred_lft forever`; `/sys/class/net/eth0/carrier=1`, `/sys/class/net/eth0/speed=1000` Mb/s (Ethernet). Adaptador USB `2-1.1`: `idVendor=0bda`, `idProduct=8153`; associacao r8152 e USB 5000 Mb/s ja comprovada em coleta anterior.

Conclusao: Ethernet Gigabit negociada, interface ativa e endereco IPv4 atribuido em EXP25A. Nao presumir que IPv4 tenha sido obtido via DHCP so pela linha `inet`; rota default, DNS, conectividade gateway/WAN e estabilidade nao foram testados. Nao confundir taxa Ethernet 1000Mb/s com bus USB 5000Mb/s.

Proximo gate read-only direto no Termux com hub e dongle mantidos: estado de `/sys/bus/usb/devices/2-1.1` e rede, rota `ip -4 route`, rx/tx e erros; sequencia 12 amostras a cada 5s (60s) para detectar oscilacao carrier/speed/ethernets/erros; nao alternar USB power ou fazer unbind/rebind. EXP26.2 LINK_IPV4=PASS; ROUTE_AND_STABILITY=PENDING; FLASH_READY=false.

## EXP26 — Relato de falha mecanossensivel por movimentacao do cabo

Observação nova relatada pelo usuario: ao movimentar o cabo ligado ao adaptador Ethernet por meio do hub, a conexao perde o contato e nao restabelece de maneira confiavel ('so conecta quando quer'). Em outros dispositivos, o mesmo adaptador/cabo tem funcionamento estavel mesmo ao movimentar cabos em diferentes posicoes. É uma associacao fisica forte, mas ainda nao localiza o conector afetado: o usuario nao distinguiu se movimento ocorreu no USB-C pipa, porta downstream do hub, dongle USB-A/USB-C ou cabo RJ45.

Dados anteriores na mesma sessao: 05e3:0625 hub + RTL8153 0bda:8153 enumerados a 5000Mb/s, r8152 vinculado, eth0 1000Mb/s carrier=1, IPv4 192.168.1.102/24. Drivers funcionam quando a conexão física permanece estavel; nao há evidência para patch r8152 agora. Log anterior de USB gadget desconectando sob USB-PC e alternancia charging reforca investigacao da porta/typec/power como possivel fator comum, sem comprovar causalidade.

Plano atualizado: interromper testes que provoquem movimento/flexao dos conectores; fazer inspecao visual segura (sem ferramentas metalicas, sem carga sob falha); apoiar cabo e hub para minimizar tracao; diferenciar durante eventual falha natural ou espontanea via Termux **somente leitura** `ls /sys/bus/usb/devices/2-1.1`, status `eth0`, `carrier`, e `dmesg`. Se USB 2-1.1 desaparece: upstream host/energia/hub/conector. Se USB permanece mas eth0 carrier cai: RJ45/link/switch/PHY. A estabilidade em outros dispositivos reduz suspeita do adaptador isolado mas nao exclui tolerancias ou conectores do hub. Priorizar comparacao com hub diferente conhecido bom, sem forcar cabo, com touchscreen como contingencia. Conserto de conector fisico nao deve ser tratado como patch de driver nem bypass de protecoes.

STATUS: USB_ETHERNET_BASIC_OPERATION=PASS; MECHANICAL_SENSITIVITY=REPORTED; AFFECTED_CONNECTOR=UNDETERMINED; RTL8153_DRIVER_PATCH=ON_HOLD; FLASH_READY=false.

## EXP26 — Teste cruzado: mesmo hub e adaptador estaveis em outro dispositivo

Novo teste A/B realizado pelo usuario: ao movimentar o cabo do adaptador Ethernet quando hub e adaptador estao conectados ao Xiaomi Pad 6, a conexao cai e pode nao se restabelecer. O usuario conectou **o mesmo hub com o mesmo adaptador e cabo** a outro dispositivo e movimentou o cabo repetidamente sem que ele desconectasse. Esse controle cruzado enfraquece a hipotese de defeito intrinseco no hub ou adaptador, e concentra a investigacao na **interface específica com o pipa** (porta USB-C, contato, folga, forca mecanica transmitida, controle de alimentacao VBUS/Type-C/PD/USB host ou diferenca eletromecanica entre dispositivos). O teste ainda nao isola conector fisico versus software/energia, e nao comprova que a porta esteja fisicamente danificada.

A enumeracao e driver ja foram comprovados no pipa (05e3:0625 hub e 0bda:8153 RTL8153 a USB 5000 Mb/s, r8152 associado, eth0 carrier=1, negociacao ethernet 1000 Mb/s, IPv4 192.168.1.102/24). Nao ha motivo para patch de r8152 antes de localizar a perda de conexao. **Nao repetir movimento de cabo para provocar falha**, nem forcar posicoes. Se ocorrer desconexao espontanea, coletar passivamente pelo Termux root as presencas de hub (05e3:0625) e dongle (0bda:8153) em /sys/bus/usb/devices, se eth0 persiste, carrier, dmesg de desconexao/erro -71/overcurrent e estado power_supply usb. Correlacionar em simultaneo: desaparece hub+dongle (upstream tablet USB-C/alimentacao/host), desaparece so dongle (hub/downstream/negociacao), ambos permanecem mas carrier cai (RJ45/link/PHY). A coleta passiva evita risco físico.

Opcional em visita tecnica: inspecao visual com dispositivo desligado e luz, sem metais ou liquidos; testar outro hub ou cabo USB-C conhecido bom **sem tracionar os conectores** e sem violar caminho de recuperacao. O resultado 1 bom / 1 falha nao basta para declarar reparo de conector necessario. `FLASH_READY=false`.
