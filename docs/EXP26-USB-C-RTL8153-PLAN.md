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

## EXP26 — Falha capturada: hub presente, RTL8153 ausente e eth0 desaparecida

**Coleta Termux root durante a falha real de contato/reenumeracao:** loop em `/sys/bus/usb/devices/*` comparando `idVendor:idProduct` trouxe apenas `2-1 => 05e3:0625` (hub). **Não trouxe** `2-1.1 => 0bda:8153` (Realtek). Teste `/sys/class/net/eth0` respondeu `ETH0=AUSENTE`.

Nos logs filtrados do `dmesg` existiam apenas mensagens antigas de registro `r8152` no boot e de associação/carrier on do adaptador aos ~2209–2212s. **Nenhuma mensagem contemporânea de desconexão física downstream do RTL8153 foi mostrada**, mas o filtro (`usb.*disconnect|r8152|eth0|error -71|over-current`) não cobriu todos os tipos de falha do host/xHCI e não se sabe se o ring buffer reteve evento; ausência de log filtrado não prova falta de falha USB.

Conclusão limitada: este evento é **perda da enumeração do adaptador USB**, não apenas `eth0` sem carrier. O hub permanece enumerado no momento da coleta. A investigacao deve focar na ligação downstream hub→RTL8153, conector/energia/port-power, negociação xHCI e integridade mecanica; dado que mesmo conjunto opera estavel em outro aparelho, tambem considerar variacao da alimentacao/controle host Type-C do pipa. O hub continuar enumerado reduz hipotese de desconexao TOTAL upstream, mas nao a elimina como causa de interrupção seletiva na porta downstream.

Próxima coleta **somente leitura e sem manipular cabo**: fotografar estado lógico e consultar `/sys/bus/usb/devices/2-1/{authorized,bConfigurationValue,product,manufacturer,speed}` e, se existir, `/sys/bus/usb/devices/2-1.1` ou paths irmãos; consultar `dmesg | tail -n 150` e filtrar `usb|xhci|dwc3|r8152|eth0|vbus|over-current|under-voltage|ep?roto|error -71|port` para evitar perder erros do host não chamados disconnect. Não escrever sysfs, unbind/rebind, reset hub/host, mudar tensão, repetir stress físico ou flash. Se quiser comparação A/B de portas, fazer apenas em sessão física segura futura com respaldo touch e controle local.

STATUS: HUB_ENUMERATED_DURING_FAILURE=YES; RTL8153_ENUMERATED_DURING_FAILURE=NO; ETH0_PRESENT=NO; ROOT_CAUSE=UNDETERMINED; RTL8153_DRIVER_PATCH=ON_HOLD; FLASH_READY=false.

## EXP26: hub permanece em SuperSpeed e HID enumerado, RTL8153 ausente; VBUS 8,59 V

Nova coleta Termux root durante ausência do RTL8153: hub SuperSpeed `/sys/bus/usb/devices/2-1` continua presente, idVendor=05e3, idProduct=0625, speed=5000, authorized=1, bConfigurationValue=1. `2-1.1=AUSENTE`. Relatório anterior já havia mostrado `ETH0=AUSENTE`. Isso comprova falha de enumeração downstream do hub em vez de mero link carrier=0; ainda sem causalidade determinada.

Fonte `/sys/class/power_supply/usb`: online=1, present=1, voltage_now=8588922 (interpretação ABI microvolts, ~8,589 V **na entrada de alimentação reportada pela classe USB**, diferente da leitura anterior ~4,916 V com PC conectado), typec_mode='Source attached (high current)'. Estes números são de cenários elétricos diferentes; a classe USB não mede diretamente a tensão das portas downstream do hub. Não inferir sobretensão ou defeito: pode refletir acordo de carga próximo de 9V se existir carregador/PD pass-through. Obter identidade da fonte, papel Type-C e status PD antes de julgar o valor.

Recorte de `dmesg` mais recente mostra enumerações de mouse 2.4GHz USB ID 32c2:0066 por `/usb1/1-1/1-1.3/` e teclado SDCINNOVATION Gaming Keyboard 36ae:fe9c por `/usb1/1-1/1-1.4/` aos 3460s. Os periféricos são enumerados no barramento USB 2.0 associado ao hub, enquanto hub 05e3:0625 continua visível na árvore USB 3 SuperSpeed. Não há no trecho filtrado mensagem contemporânea que explique a queda seletiva do RTL8153, porém o filtro `tail -n 250` do ring buffer e regex não garantem captura exaustiva.

Próxima leitura segura: listar `1-1`/`1-1.3`/`1-1.4` e `2-1`/`2-1.1`, status Type-C data_role e power_role, partner supports_usb_power_delivery, `/sys/class/power_supply/usb/{online,voltage_now,real_type}` e, se disponíveis, PD properties; capturar `dmesg | grep -Ei 'usb [12]-1|xhci|dwc3|over.current|error -71|r8152' | tail -n 80` sem alterar energia. Perguntar se o carregador está ligado à entrada PD do hub; não forçar desconexões e não fazer unbind, power cycling, USB reset ou patch r8152.

STATUS: HUB_USB3=ACTIVE, USB2_HID_ENUMERATED_IN_LOGS=YES, REALTEK_ENUMERATED=NO, ETH0=ABSENT, USB_SUPPLY_REPORTED=8.589V, VOLTAGE_SOURCE=UNVERIFIED, CAUSE=UNDETERMINED, FLASH_READY=false.


## EXP26 — Companion USB2 e USB3 com RTL8153 ausente

Nova coleta Termux: USB2 hub 05e3:0610 em 1-1 a 480Mb/s, mouse 32c2:0066 em 1-1.3, teclado 36ae:fe9c em 1-1.4; USB3 hub 05e3:0625 em 2-1 a 5000Mb/s. RTL8153 em 2-1.1 AUSENTE. Type-C data role host, power role sink, partner USB-PD yes, fonte USB_PD, voltage_now=8613450 microvolts (8,61V na entrada reportada; nao no RTL8153). Perda seletiva de enumeracao de periferico SS, sem identificacao causal de driver ou conector. Evitar movimentacao de cabo e escrita USB/sysfs. FLASH_READY=false.

## EXP26 — Usuario confirma carregador conectado a entrada PD do hub

Usuário confirmou explicitamente que há um carregador conectado à entrada USB-C PD do hub enquanto o hub está ligado ao Xiaomi Pad 6. A evidência da mesma sessão é data_role=[host] device, power_role=source [sink], supports_usb_power_delivery=yes, usb/real_type=USB_PD, usb/voltage_now=8613450 microvolts (~8,61 V), compatível com alimentação negociada próxima de 9V para o tablet. A leitura não é a tensão downstream entregue ao adaptador Realtek. Datasheet específico do hub, potência do carregador, contrato PD, energia real da porta downstream e comportamento sem carregador permanecem desconhecidos.

Com hub USB2/USB3 enumerado e dongle RTL8153 ausente em 2-1.1, não culpar automaticamente o carregador: hipóteses incluem perda de sinal SS, conector/folga, proteção por corrente de downstream ou diferenças na política Type-C/PD do tablet. O mesmo hub e dongle são estáveis no outro dispositivo ao movimentar cabo; **ainda não foi esclarecido se o mesmo carregador PD também estava conectado nesse controle A/B**. Este é o próximo detalhe comparativo mais importante.

Não provocar perda mecânica nem remover PD enquanto mouse/hub possam ser necessários para operar o tablet; sem unbind/reset/port-power/fastboot ou flash. Comprovado: driver r8152 e eth0 com carrier funcionam quando dongle é enumerado. `FLASH_READY=false`.

## EXP26 — Controle A/B confirmou PD ligado também no outro dispositivo

O usuario confirmou que, no controle cruzado feito com **o mesmo hub e adaptador Ethernet em outro dispositivo**, **o carregador permanecia conectado à entrada USB-C PD do hub**. Nesse controle o usuário movimentou os cabos repetidamente e a conexão Ethernet não caiu. No Xiaomi Pad 6, cabo/adaptador movimentado causa perda seletiva de enumeração do RTL8153, enquanto os hubs companion 05e3:0610/0625 e HID continuam enumerados no snapshot obtido após falha.

Essa comparação reduz a hipótese de defeito isolado no adaptador/hub/carregador ou do simples uso de pass-through PD como causa, mas não demonstra porta USB-C danificada: podem diferir características mecânicas, margens USB3/PHY, comportamento CC/PD, potência do dispositivo e controle por porta do hub quando ligado ao pipa. No pipa `voltage_now` da fonte USB foi aproximadamente 8,61 V e o parceiro reportou PD=yes, sem prova da tensão downstream.

**Próximas ações conservadoras:** não provocar quedas por movimentação, nem forçar cabos/tensões ou resetar portas. Registrar eventos durante falha espontânea pelo Termux; documentar fotos/inspeção visual não invasiva da porta com dispositivo desligado quando apropriado; ensaio com outro hub/conector conhecido bom ou assistência técnica para inspecionar porta USB-C se a falha continuar. Não criar patch de r8152 nem liberar flash com essa evidência. `FLASH_READY=false`.

## EXP26.4 — Comparacao root com rodin: RTL8153 funciona em USB2 480Mb/s

Coleta realizada no outro dispositivo, identificado por `ro.product.model=2412DPC0AG`, `ro.product.device=rodin`, kernel `6.6.118-android15-8-ge56cf6b09cca-ab15511674-4k`, driver `r8152 v1.12.13`. Mesmo hub + RTL8153 + carregador PD ligado, com relato de estabilidade mecanica no teste cruzado.

Arvore USB rodin: `1-1 05e3:0610 speed=480`, `1-1.1 0bda:8153 speed=480`, `1-1.3 32c2:0066 speed=12`, `1-1.4 36ae:fe9c speed=12`; root hubs `usb1 1d6b:0002 speed=480`, `usb2 1d6b:0003 speed=20000`. Nao ha enumeracao do hub SuperSpeed `05e3:0625` em `2-1` no snapshot. O adaptador Realtek estavel **opera via USB 2.0 High Speed de 480 Mb/s**, nao USB3 SuperSpeed de 5000Mb/s como no Xiaomi Pad 6 antes da falha. Isto e o principal fator de confusao na comparacao A/B; estabilidade USB2 no rodin nao prova integridade da rota SuperSpeed, seus contatos ou PHY. `speed` do sysfs e taxa do barramento USB conectada (kernel ABI), distinta do link PHY Ethernet.

Rodin rede: `eth0 UP,LOWER_UP`, IPv4 `192.168.1.102/24` dynamic, negociacao PHY `1000 Mb/s full duplex`, carrier=1, `r8152 carrier on`; valor de 1000 no `/sys/class/net/eth0/speed` NAO garante throughput 1000Mb/s no cabo USB 480Mb/s. `wlan0` está `NO-CARRIER`, `state DOWN` nessa coleta: simultaneidade real Wi-Fi+Ethernet **nao demonstrada** pelo snapshot apesar de relato anterior. `ip -4 route show` mostra apenas rota local 192.168.1.0/24, nao necessariamente ausente default em tabelas por-network Android.

Rodin dmesg: `r8152-cfgselector` de idVendor 0bda idProduct 8153 (bcdDevice 31.fd), reset high-speed com xhci-mtk; tentativas de firmware `rtl_nic/rtl8153b-2.fw` falharam `error -2` e, apesar disso, `r8152 v1.12.13` registrou `eth0` e carrier on. Ausencia do blob nao impede link nesta coleta; investigar somente se desempenho/funcoes adicionais exigirem. usb2/usb1 root hubs sofreram disconnect ~190s antes do novo detect ~193s, nao equivale a falha atual de hardware.

Rodin `/sys/class/power_supply/usb/voltage_now=8337` com USB_PD, que NAO deve ser comparado numericamente aos `8613450` reportados pelo pipa sem verificar a unidade efetivamente implementada pelo vendor. Valor 8337 pode ser fornecido em mV por firmware/vendor divergente da ABI microvolts; nao afirmar 0,008V nem 8,337V categoricamente. Nenhum indica tensao downstream do Realtek.

Proxima verificacao recomendada: analisar logs especificos do USB SuperSpeed com coleta somente leitura em ambos, sem induzir queda. Se for permitido e houver hardware externo, ensaio opcional de RTL8153 via adaptador/hub **USB2-only** conhecido bom no pipa em sessao segura, para comparar estabilidade ao caminho de 480 Mb/s, sem alterar kernel nem forcar conexoes fisicas. Evitar escrita sysfs/reset/flash. `FLASH_READY=false`.

## EXP26.5 — Plano de leitura USB3 sem reset em rodin

Partindo da coleta EXP26.4, verificar **somente leitura** no rodin a topologia dos caminhos `usb1`, `usb2`, `1-1`, `1-1.1`, `2-1`, `2-1.1` e atributos `speed`, `authorized`, `bConfigurationValue`, `power/runtime_status`; procurar logs de `usb 2-`, `xhci-mtk`, `r8152`, `SuperSpeed`, erros de enumeracao e resets. O objetivo e distinguir: (a) hub downstream realmente operando apenas em USB2; (b) tentativa de enumeracao no companion SuperSpeed com falha; (c) evento de energia/runtime PM. `usb2 speed=20000` descreve capacidade do root hub e NAO implica link SuperSpeed de periferico.

Sem evidencias novas, o criterio seguro continua: nenhuma escrita em sysfs, reconfiguracao de PD, desmontagem, alteracao de firmware, reset USB, reinicio do pipa ou flash. Caso dispositivo padrao nao reporte logs SuperSpeed, isso nao prova inexistencia do evento — nao intensificar log via configuracao dinamica sem backup.

Separar do teste com pipa: quando realizar em sessao futura, nao forcar a falha movendo cabos; comparar estabilidade e enumeracao sob uso normal. A causa fisica/eletrica segue indeterminada e patch de `r8152` permanece suspenso. `FLASH_READY=false`.

## EXP26.5 — Coleta rodin: usb2 root hub suspenso e RTL8153 ativo em HS

Termux root rodin: `usb1 1d6b:0002 speed=480 authorized=1 config=1 runtime_status=active control=auto`; `usb2 1d6b:0003 speed=20000 authorized=1 config=1 runtime_status=suspended control=auto`; `1-1 Genesys 05e3:0610 speed=480 runtime_status=active control=auto`; `1-1.1 Realtek 0bda:8153 speed=480 runtime_status=active control=on`; `2-1` e `2-1.1` ausentes. Type-C data_role host ativo e power_role sink ativo. Assim o dongle opera em USB2 High-Speed e nao no companion SuperSpeed. Root hub SS suspenso sem perifericos pode representar gerenciamento normal de energia, nao evidencia de defeito ou motivo para desabilitar autosuspend. Fonte: documentacao Linux USB PM https://cdn.kernel.org/doc/html/latest/driver-api/usb/power-management.html.

Trecho de dmesg colado pelo usuario interrompeu na linha `[ 621.1884` e NAO permite interpretar logs USB/SS. Proxima coleta curta e dirigida, estritamente read-only: `dmesg | grep -Ei 'usb 2-|usb usb2|SuperSpeed|xhci-mtk|r8152|error -71|error -110' | tail -n 35` e, se necessario, leitura de runtime_status dos hubs. Foco em tentativa de enumeracao do SuperSpeed e mensagem de fallback, sem inferir causa pela ausencia de linhas. Sem alterar `power/control`, modulo r8152, PD, sysfs, nem provocar desconexao. `FLASH_READY=false`.

## EXP26.6 — rodin: full host xHCI re-registration and successful RTL8153 re-enumeration

Logs Termux root no controle rodin capturaram sequencia de transicao de host USB: `r8152-cfgselector 1-1.1 USB disconnect` em t=699.247873; `xhci-mtk 11200000.xhci0 USB bus 2 deregistered` em t=713.244641 e USB bus 1 deregistered em t=713.253238; `xhci-mtk` novo USB bus 1 e 2 em t=713.944970–713.945467; `Host supports USB 3.2 Enhanced SuperSpeed` t=713.945472; `usb 1-1 new high-speed USB device` em 714.359097, `usb 1-1.1 new high-speed USB device` em 716.106829; reinit `r8152 1-1.1:1.0 eth0: v1.12.13` em t=716.548769; `carrier on` em 721.888799. Consequentemente, rodin consegue voltar a enumerar adaptador High-Speed apos novo registro do host, mas não se pode afirmar que o novo registro foi disparado automaticamente para recuperar o dongle: o gatilho da remoção xHCI é desconhecido.

Rodin log `r8152 1-1.1:1.0 Direct firmware load rtl_nic/rtl8153b-2.fw failed -2` em 716.499470 e `unable to load firmware patch`, porém `eth0` e carrier retornam. O firmware ausente nao impede o link nesta condicao. Outros logs `supply vbus not found, using dummy regulator` e `supply vusb33 not found, using dummy regulator` nao comprovam falha; devem ser avaliados separadamente apenas se existir sintoma relevante.

Rodin `usb2` root hub presente runtime_status=suspended; `2-1`/`2-1.1` ausentes. A capacidade xHCI USB3 nao equivale a periferico negociando SuperSpeed. Em pipa RTL8153 originalmente USB 5000Mb/s (2-1.1) mas desaparece durante falha. Control A/B difere na negociacao USB2 vs USB3; o driver Ethernet `r8152 v1.09.9` (pipa) vs `v1.12.13` (rodin) pode afetar operacao apos o bind, mas nao e uma causa comprovada da falta de enumeracao do dispositivo USB.

Proximo plano: monitorar passivamente eventos de `usb 2-`, `xhci`, e `dwc3` no pipa quando ocorrer falha natural, registrar primeiro se o adaptador some ou se interface persiste, sem resets, unbind, alteracoes de power/control, quedas induzidas ou flashing. `FLASH_READY=false`.


## EXP26.8 — Hub USB2 ausente e hub SuperSpeed suspenso

Coleta Termux root no pipa, mesma sessão EXP25A: `1-1=AUSENTE`, `2-1=PRESENTE`, `/sys/bus/usb/devices/2-1/power/runtime_status=suspended`, `2-1.1=AUSENTE`. O histórico filtrado de `dmesg` mostra os últimos vínculos do RTL8153 em ~2209–2212s e mensagens de entrada mouse/teclado em ~3460s; não mostra causa posterior de remoção. A ausência do hub USB2 é nova relativamente à coleta anterior, e não permite atribuir a falha apenas a `r8152`. O estado suspended, isoladamente, é compatível com runtime PM normal. Confirmar funcionamento atual de mouse/teclado e coletar snapshot de `usb1`, `usb2`, `1-1`, `2-1` e estado Type-C sem induzir novas quedas. Preservar a EXP25A; nenhuma escrita em sysfs; `FLASH_READY=false`.

## EXP26.9 — pipa root hubs presentes, companions ausentes

Termux KSU leitura somente no Xiaomi Pad 6: `usb1 speed=480 authorized=1 power/runtime_status=suspended power/control=auto`, `usb2 speed=10000 authorized=1 power/runtime_status=suspended power/control=auto`; `1-1=AUSENTE`; `2-1 speed=5000 authorized=1 power/runtime_status=suspended power/control=auto`; `2-1.1=AUSENTE`. Type-C `data_role=[host] device` e `power_role=source [sink]`.

Leitura: ambos root hubs enumerados e autorizados, hub SuperSpeed 05e3:0625 anteriormente identificado em 2-1 permanece enumerado a 5000 Mb/s, enquanto caminho companion USB2 e RTL8153 nao enumerados neste instante. O `speed=10000` do usb2 representa root hub, nao velocidade do periférico. Os estados `suspended` com `control=auto` sao compatíveis com runtime PM ocioso e nao demonstram falha nem necessidade de forçar power/control=on. Informacao crucial pendente: se mouse/teclado continuam fisicamente conectados e funcionam no hub; o usuario ainda nao confirmou. Sem comprovação de que nao houve mudança na ligação fisica entre sessões. Nao fazer reset, unbind nem power-cycle; FLASH_READY=false.


## EXP26.10 — Diagnostico passivo de USB e registros de entrada

Plano a partir da coleta EXP26.9: identificar periféricos USB presentes enumerando `/sys/bus/usb/devices/*` sem supor numeros de caminho; ler `/proc/bus/input/devices` para ver quais entradas de mouse/teclado continuam registradas; checar a árvore `usb1`, `usb2`, hub `1-1`/`2-1`, Realtek `0bda:8153` e estado de runtime PM; avaliar log filtrado por USB/xHCI/dwc3, sem provocar desconexões. Este diagnóstico permite distinguir ausência atual de dispositivos da mera presença de entradas históricas no dmesg, mas não determina a causa sem eventos contemporâneos. Não modificar `power/control`, não resetar portas/controlador, não movimentar conectores nem reiniciar o tablet EXP25A temporário. `FLASH_READY=false`.

## EXP26.10 — USB2 hub retorna; repetidas enumeracoes HID em ~50 s

Nova coleta Termux KSU no Xiaomi Pad 6: `1-1 05e3:0610 speed=480`, `1-1.3 mouse 32c2:0066 speed=12`, `1-1.4 teclado 36ae:fe9c speed=12`, `2-1 05e3:0625 speed=5000`, root hubs `usb1 speed=480` e `usb2 speed=10000`. `2-1.1` nao enumerado, RTL8153 ausente. Runtime PM: usb1=active, usb2=suspended, 1-1=active, 2-1=suspended. `/proc/bus/input/devices` contem mouse e teclado, mas isso sozinho nao verifica atividade fisica atual.

`dmesg` indica enumeracoes repetidas do par mouse/teclado com novos caminhos `input`: ~5833.78/5834.34s; ~5863.22/5863.74s; ~5870.97/5872.06s; ~5883.80/5884.38s, no mesmo boot. Esse padrao e consistente com reenumeracao/reinicio parcial do caminho USB2 em intervalos curtos, mas o grep usado capturou linhas `input` e nao mostra o motivo de cada ocorrencia. Sem informacao de movimentacao do cabo, nao classificar como espontaneo nem culpar r8152 ou LPM.

Proximo teste somente leitura, mantendo conexoes sem mover: amostragem curta de `/sys/bus/usb/devices/{1-1,1-1.3,1-1.4,2-1,2-1.1}` e dos respectivos `devnum`, `speed` e estados de runtime para identificar churn, seguida de logs filtrados por hub, usb e xhci em intervalo pertinente. Nao alterar registros, autorizar, suspensao, VBUS/PD ou controlador. EXP25A temporario preservado, FLASH_READY=false.

## EXP26.11 — Monitoramento USB estável por 12 amostras; RTL8153 ainda ausente

Termux root no Xiaomi Pad 6 (sessão EXP25A), 12 amostras entre 22:11:17 e 22:12:14, espaçadas ~5s: **nenhum `devnum` mudou e nenhum dos dispositivos monitorados desapareceu**. `1-1` hub USB2 permanece `DEV49 speed=480`; `1-1.3` mouse `DEV54 speed=12`; `1-1.4` teclado `DEV55 speed=12`; `2-1` hub USB3 `DEV2 speed=5000`. `2-1.1` Realtek `0bda:8153` AUSENTE em **12/12** amostras. São ~57s entre primeira e última amostra, com resolução de 5s; eventos passageiros entre amostras não foram excluídos, embora `devnum` constante reduza evidência de reenumeração completa.

Trecho de dmesg enviado depois das amostras inclui novas enumeracoes anteriores de mouse/teclado em ~5833, 5863, 5871 e 5884s, mas não identifica causa (movimentação de cabo vs reconexão espontânea). Não há falha atual comprovada dos hubs na janela de 12 amostras. O RTL8153 não reapareceu enquanto a topologia permaneceu estável. Isto mantém prioridade para integridade/energia/enumeracao da porta downstream SuperSpeed `2-1.1` e sua interação com host pipa; `r8152` e firmware não explicam necessariamente ausência da entrada no barramento.

Gate seguinte recomendado (read-only, sem movimento): inspecionar apenas dispositivos/porta descendente `2-1`/`2-1-port1` no sysfs, `power/runtime_status`, existência de entradas `2-1*`, e opcionalmente `/sys/kernel/debug/usb/devices` se disponível; não fazer port reset, unbind/bind, `authorized=`, alteração de autosuspend, Type-C, USB-PD, recompilação ou flash. Registrar dados antes de atribuir causa. `FLASH_READY=false`.


## EXP26.12 — Drivers hub presentes; corrigir caminho sysfs de portas

Coleta pipa Termux root: `1-1:1.0` vinculado ao driver genérico `hub`, `2-1:1.0` também vinculado a `hub`; Realtek ausente em `1-1.1` e `2-1.1`. A busca inicial por `/sys/bus/usb/devices/1-1-port1` e `2-1-port1` retornou `NAO_EXPOSTA` porque buscava no nível errado. Conforme ABI e documentação do kernel Linux, os objetos de porta ficam sob a interface do hub: `/sys/bus/usb/devices/1-1:1.0/1-1-port1` e `/sys/bus/usb/devices/2-1:1.0/2-1-port1` (quando expostos). A correção é apenas do comando de leitura; ausência nos caminhos anteriores NÃO prova ausência nem desligamento de porta. Próximo passo: descobrir e ler sem escrita, `over_current_count`, `connect_type`, `usb3_lpm_permit`, `power/runtime_status`, `power/pm_qos_no_power_off` e `peer`, onde disponíveis. Referências: https://kernel.org/doc/html/v4.18/driver-api/usb/power-management.html e https://www.kernel.org/doc/html/v5.12/admin-guide/abi-testing.html . Não provocar desconexões, reset do hub, power cycling ou alteração de LPM; `FLASH_READY=false`.
