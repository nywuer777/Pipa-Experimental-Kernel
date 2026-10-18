# EXP24 — Ethernet USB integrado ao EXP06 (variante experimental; SEM FLASH)

**Data:** 18/10/2026 | Xiaomi Pad 6 pipa, Android 16/crDroid 16.0, E404 kernel 4.19.404R | `FLASH_READY=false`.

## Objetivo e evidência de entrada

O usuário forneceu o arquivo `ethernet.config`, SHA256 **`bb561eac2eaeb15157b396f7807c30793348b65e14cb4b0821e4a66d8ecc11b0`** (909 bytes), e pediu integrar suporte ao adaptador Ethernet USB-C intermitente ao nosso kernel EXP06 para teste real. **Arquivo fornecido é um fragmento de Kconfig**, não contém um driver-fonte novo. Cobre 22 opções declaradas `=y`.

Fonte kernel experimental:
- E404 `kvsnr113/xiaomi_sm8250_kernel_e404` commit fixado `fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- Patch original EXP06 schedutil `2000→1500 µs`, Clang21 AOSP pin `b54cd2c8e9e0bb057aef3804d42d39c5ac4674c7`.
- O EXP06 **já foi iniciado temporariamente** e expôs `rate_limit_us=1500` em três políticas cpufreq, depois reboot normal retornou E404 a `2000`; não modificar essa base aprovada.
- `CONFIG_MODULES=n` na configuração pinada, por isso **drivers adicionais somente como integrados `=y`**, não módulos `.ko`.

## Comparação da entrada com a fonte real

Foi inspecionado o `arch/arm64/configs/vendor/pipa_defconfig`, `drivers/net/usb/Kconfig` e `drivers/net/usb/Makefile` no **commit E404 fixado**, via conexão GitHub.

Dos 22 símbolos: **21 reconhecidos/aplicáveis**; seis já `=y` no defconfig: `MII`, `USB_NET_DRIVERS`, `USB_USBNET`, `USB_NET_CDCETHER`, `USB_NET_CDC_NCM`, `USB_NET_CDC_SUBSET`. Os 15 restantes serão ativados e rigorosamente validados:

```text
CONFIG_VLAN_8021Q=y
CONFIG_USB_NET_CDC_EEM=y
CONFIG_USB_NET_RNDIS_HOST=y
CONFIG_USB_NET_AX8817X=y
CONFIG_USB_NET_AX88179_178A=y
CONFIG_USB_RTL8150=y
CONFIG_USB_RTL8152=y
CONFIG_USB_LAN78XX=y
CONFIG_USB_NET_SMSC75XX=y
CONFIG_USB_NET_SMSC95XX=y
CONFIG_USB_NET_DM9601=y
CONFIG_USB_NET_SR9700=y
CONFIG_USB_NET_MCS7830=y
CONFIG_USB_PEGASUS=y
CONFIG_USB_KAWETH=y
```

**Exceção explícita:** `CONFIG_USB_NET_AQC111` não é declarado em `drivers/net/usb/Kconfig` nem tem objeto/target em `drivers/net/usb/Makefile` na revisão fixada. Não é possível habilitar AQC111 por `=y` sem portar código-fonte apropriado e suas dependências. O processo EXP24 **não declara suporte AQC111** e **não aceita silenciosamente descarte de configurações**.

A base já possui infraestrutura USB host `CONFIG_USB=y`, `CONFIG_USB_DWC3=y`, rede USB (`USB_USBNET=y`) e PHYLIB. Isso não garante OTG, energia USB-C, DHCP/Android Ethernet HAL nem compatibilidade VID:PID com adaptador específico.

## Implementação material no repositório privado

- `configs/ethernet.config`: **anexo original preservado** com SHA256 fixado.
- `tools/exp24-apply-ethernet.py`: exige hash original do arquivo de entrada, permite 21 símbolos reconhecidos pelo Kconfig original; altera `pipa_defconfig` após preparação EXP06 e `out/.config` se já existente. Verificação pós-build **fail-closed**: cada um dos 21 símbolos `=y`, `CONFIG_MODULES=n`, `CONFIG_PIPA_EXP_SUGOV=y` e `CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500`. Se olddefconfig/kernel ignorar qualquer símbolo, job falha.
- `tests/test_exp24_ethernet.py`: autoteste de input pinned, aplicação idempotente, `=m` rejeitado, símbolo ausente e alteração do anexo detectados.
- `.github/workflows/exp24-ethernet-clang21-build.yml`: variante isolada baseada no workflow EXP06 original (mesmo fonte e compilador fixados), injeta Kconfig após prepare, compila ARM64 Image/dtb/dtbo.img, publica `Image`, `.config`, logs, checksums; **proíbe boot.img/vendor_boot.img** no job. EXP06 original preservado.

**Testes de implementação executados localmente pelo assistente:** leitura e SHA256 do anexo, inspeção direta da árvore E404 Kconfig/Makefile/defconfig via GitHub, `python -m py_compile`, testes sintéticos `EXP24 SYNTHETIC KCONFIG APPLY/VERIFY TESTS: PASS`. Isso comprova **integração de código e testes de configuração**, **não** compilação de todo kernel.

## CI atual (não mascarar falha)

GitHub Actions disparou automaticamente: [run #39171851569](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39171851569), `run_attempt=1` e `run_attempt=2`, ambas **failure** sem steps disponíveis no payload do job. Job original e rerun apresentaram `steps=0` e logs de job indisponíveis. **Isso não permite atribuir o erro a fonte, compilador, driver ou config; a hipótese provável é falha de provisionamento antes do build, mas a causa exata ainda não é comprovada**. Não declarar EXP24 `Image` gerado, artifact publicado ou `CONFIG_GATE=PASS_REAL` até Actions executar suas etapas e concluir. Workflow pode ser reexecutado no GitHub Actions quando runners disponíveis.

## Próximo gate: kernel compilado e candidato temporário

1. GitHub Actions aprovar compilação, `CONFIG_GATE=PASS` **com `.config` real**, `CONFIG_KSU=y`, schedutil 1500, 21 Ethernet `=y`; guardar `Image` SHA256 + tamanho + logs, artefato imutável.
2. Construir **novo boot compacto Android v3** do slot `_b` com `mkbootimg` AOSP offline (aumento do tamanho do Image muda offsets da ramdisk). Preservar header/cmdline/ramdisk do E404, validar por auditor independente e comparar com backups originais. **Não** substituir bytes cegamente no compacto EXP06.
3. Obter identidade física do adaptador USB-C (USB VID:PID) e driver correspondente, observando `/sys/bus/usb/devices` e `/sys/class/net` no E404 baseline. Isso evita atribuir falha à falta de driver quando a causa é cabo, OTG, energia USB, DHCP ou adaptador defeituoso.
4. Solicitar **nova autorização específica para uma única inicialização temporária da variante Ethernet**. A autorização anterior foi só para um EXP06 sem suporte Ethernet novo.
5. **Prova de driver carregado** após boot: `/proc/config.gz` (se disponível) com `CONFIG_USB_RTL8152=y` etc., identificação `VID:PID`, vínculo a driver em `/sys/bus/usb/drivers`, aparecimento de interface de rede `eth*` ou `usb*`, interface `UP`, aquisição IP/rota e tráfego reproduzível. Boot `/proc/version` identifica compilação, não prova periférico conectado. Apenas 'internet funcionou' **não é prova isolada** de execução do nosso kernel porque o E404 já tem suporte CDC parcial.
6. Reboot para retornar ao kernel E404 persistente e registrar reversibilidade. Não afirmar suporte 100% universal: a prova é específica do adaptador (VID/PID) e condições do teste.

## Estado

`EXP24_SOURCE_INTEGRATION=COMMITTED`; `EXP24_LOCAL_SYNTHETIC_TEST=PASS`; `EXP24_REAL_CI_BUILD=NOT_COMPLETED`; `EXP24_DEVICE_BOOT=NOT_TESTED`; `EXP24_USB_ADAPTER_BOUND=NOT_TESTED`; **`FLASH_READY=false`**. Nenhum flash, boot experimental EXP24 ou alteração no tablet foi realizado.

## Atualização: revisão do workflow e captura A/B (18/10/2026)

- EXP24 run inicial [#39171851569](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39171851569) falhou antes de executar steps (runner_id=0, steps=[]), e a tentativa 2 também. Outra execução EXP18 na mesma data falhou com o mesmo padrão. Sem evidência de falha do compilador ou dos drivers nessa execução.
- Workflow corrigido no commit `e2831a7b1b3cd6e539a7700032bfb1b3256af84b`: versão do Clang 21 era procurada incorretamente em `out/.config`; validação agora usa `exp06-clang-version.txt` produzido no próprio job.
- Nova execução [#39172615397](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39172615397) recebeu runner e confirmou: checkout PASS, testes sintéticos Ethernet PASS, verificação EXP01 PASS e instalação das dependências PASS. Última observação: aquisição Clang21 em execução; **não** atribuir aprovação de build ainda.
- Criado `tools/exp24-usb-ethernet-evidence.ps1` (PowerShell Windows; procedimento read-only; hardware não testado nesta sessão). Captura `VID:PID`, vinculação dos drivers em interfaces USB, interfaces de rede, endereço e rota IPv4, `/proc/version` e opções de configuração expostas.
- Protocolo de teste: executar primeiro no **E404 persistente**, com o adaptador conectado; em teste autorizado posterior, repetir no **EXP24 inicializado temporariamente** sob as mesmas condições; comparar VID:PID, driver vinculado e conectividade estável. Apenas conectividade, sozinha, não comprova driver novo nem kernel novo.
- Estado continua **`FLASH_READY=false`** até build real, .config resolvido, auditoria boot Android v3 e autorização específica.

## EXP24 build homologado em CI (18/10/2026, 22:43 UTC)

- GitHub Actions [#39172615397](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39172615397), workflow `exp24-ethernet-clang21-build.yml`: **SUCCESS** em todos os passos, com Clang Android 21.0.0 fixado, E404 commit fixado e KernelSU preservado.
- Log do build confirma: `EXP24 final resolved kernel .config: ALL 21 SUPPORTED CONFIG SYMBOLS = y; EXP06 SUGOV 1500 PRESERVED; MODULES DISABLED`; `EXP24 CONFIG_GATE=PASS`.
- `Image` SHA256 **`773b37133766cb6877937bc53c84b2d5ad0a94985ca754d88a685e7c00648da0`**.
- Artifact `pipa-exp24-ethernet-clang21-2` (ID 12152679061), 12.385.469 bytes ZIP, digest **`sha256:01b25af08fec6573258464ecae0bb6181794e35999d4358213980d66e97c2038`**, expira em 01/11/2026. O artifact contém evidências e a Image NÃO INSTALÁVEL diretamente.
- `tools/exp24-usb-ethernet-evidence.ps1` recebeu correção adicional em `854071e6239dab5e2ffcd22bb0b4ce7e2ecc45bb`: o Android nega leitura a `/proc/sys/kernel/osrelease` sob ADB shell; antes isso provocava `NativeCommandError` em Windows PowerShell. Agora o campo é opcional e seções de diagnóstico não interrompem a coleta por stderr. Requer baixar novamente o script para o Windows.
- **Não alterar o critério de segurança:** `FLASH_READY=false`. Próximo passo é coletar a referência E404 e auditar empacotamento Android boot v3 com backups para eventual inicialização temporária autorizada. O A/B do USB Ethernet no hardware ainda não foi realizado.

## Referência física E404 de 19:45:47 (18/10/2026)

Registro de exp24-usb-E404-20261018-194548.txt (coleta ADB Wi-Fi com USB-C ocupado):
- Interfaces USB 2-1:2.0 e 2-1:2.1 enumeradas sem symlinks de driver exibidos; isso não comprova qual adaptador é 2-1 antes do VID:PID.
- Nenhuma interface Ethernet em /sys/class/net; lo e wlan0 apareceram no ip; wlan0=192.168.1.105/24. A rota local mostrada usa wlan0.
- A identificação VID:PID saiu vazia; a identidade kernel falhou por sintaxe de shell. Logo, modelo do adaptador e razão da não vinculação ainda estão pendentes.
- ip reportou uma mensagem Permission denied, mas mostrou endereços; isso não comprova falha de kernel.

Correção no repositório: tools/exp24-usb-ethernet-evidence.ps1 v3, commit 312147c4bbbfaa1a5cf11a3b28a0fa1f436fa35b. Substitui comandos remotos com parênteses/regex/for por comandos ADB simples, enumeração dos nomes USB no PowerShell, leitura individual de VID:PID, classes de interface, symlinks de driver e dados de rede. Pendente reexecução no Windows; não declarada validação no hardware desta versão.

Próximo gate: capturar /sys/bus/usb/devices/2-1/{idVendor,idProduct} e descritores de interface, cruzar com drivers EXP24 presentes. Somente após auditoria do boot Android v3 considerar autorização de teste temporário. FLASH_READY=false.

## Premissa obrigatória: reconhecimento intermitente no E404

Observação direta informada pelo usuário (18/10/2026): **o E404 reconhece o adaptador Ethernet USB-C de forma INTERMITENTE**. Algumas conexões funcionam; em outras, não há sequer reconhecimento de dispositivo. Portanto, um teste isolado com adaptador não detectado NÃO comprova ausência de driver, nem um teste isolado com adaptador detectado na EXP24 comprova que os drivers novos causaram a melhora.

Protocolo A/B para comparação válida (somente após boot EXP24 temporário autorizado e auditado):
1. Identificar antes o adaptador pelo USB VID:PID/descritores quando for enumerado; registrar quando não houver enumeração. Não presumir que '2-1' identifica o adaptador em todas as tentativas.
2. Usar mesmo cabo, adaptador, hub, alimentação, porta, rede e condições semelhantes no E404 e na EXP24. Manter ADB Wi-Fi independente do Ethernet.
3. Repetir pelo menos 10 ciclos de desconectar/reconectar no E404, e 10 na EXP24, registrando a duração até enumerar e o resultado de cada tentativa; testes consecutivos podem ter dependências e não bastam para confiança estatística.
4. Classificar cada ciclo: A) sem evento/enumeração USB; B) USB enumerado com VID:PID, sem driver vinculado; C) driver vinculado e interface eth*/usb* criada; D) IP, rota e tráfego via interface Ethernet funcional; E) operação sustentada e recupera após reconexão.
5. Separar problema OTG/USB-C, energia, cabo/hub e enumeração USB da seleção do driver (binding), e esta da camada Android Ethernet/DHCP/roteamento. Drivers adicionais somente podem atuar quando o dispositivo enumera adequadamente; não garantem consertar uma falha física de enumeração.
6. Comparar taxas por fase e logs do kernel em cada sistema, junto de identidade da Image/EXP24 no boot. Só atribuir melhora ao novo kernel mediante diferença reproduzível e evidência técnica coerente, não pela conexão eventual.
7. Antes de qualquer teste EXP24, cumprir auditoria de boot v3, confirmar reversibilidade e obter autorização de inicialização temporária. FLASH_READY=false.

Registro original: o relatório E404 de 19:45 mostrou interfaces USB 2-1:2.0/2-1:2.1 sem driver, mas VID:PID ausente e nenhum Ethernet na rede; a intermitência impede afirmar que o resultado represente todas as tentativas.

## Evidência E404 V3 — 20:01:41 e bloqueio de identidade de kernel

Arquivo recebido: `exp24-usb-E404-20261018-200142.txt`, SHA256 `295c3c3fc8a26deb9ced03cb07ba9706a4dbe0d1ec37fd0616976aa2d519b2ed` (128 linhas; ADB Wi-Fi; device=pipa).

**USB:** `/sys/bus/usb/devices` listou apenas `usb1`, `usb2`, `1-0:1.0` e `2-0:1.0` (hubs-raiz). Nenhum dispositivo USB externo presente no instante da coleta. O caminho `2-1` que havia aparecido às 19:45 desapareceu; consultas posteriores de `/sys/bus/usb/devices/2-1/idVendor` e `idProduct` retornaram ENOENT. Sem VID:PID não se pode afirmar ainda que `2-1` era o adaptador Ethernet, mas há evidência objetiva de enumeração variável.

**Rede:** `/sys/class/net` não tinha `eth*`/`usb*`. `wlan0` tinha IPv4 `192.168.1.105/24` e a rota local registrada foi `192.168.1.0/24 dev wlan0`. `ip link show` falhou com `request send failed: Permission denied` (limitação de permissão, não diagnóstico de hardware). `dumpsys ethernet`: `Ethernet State: enabled`; filtro `(usb|eth)\d+`; `Tracking interfaces` vazio. O serviço Android está ativo, mas sem interface Ethernet registrada.

**Inconsistência de identidade CRÍTICA, não resolver por inferência:** `uname -r` devolveu **5.10.404R**, enquanto `/proc/version` reportou `Linux version 4.19.404R` e Clang 21, build #14 Sun Aug 23 2026. O kernel EXP24 foi construído com fonte E404 que se apresenta como 4.19.404R. Não confundir sucesso de CI com compatibilidade de boot. A divergência deve ser investigada antes de qualquer imagem de boot ou teste temporário. Não declarar qual das versões é verdadeira sem prova adicional independente; investigar alteração/mascaramento de versão, userspace e informações do kernel e sua configuração.

**Próximo teste:** repetir coleta v3 no instante em que o adaptador voltar a ser enumerado, capturando VID:PID e drivers. Coletar separadamente `/system/bin/toybox uname -r`, `uname -r`, `cat /proc/version`, `getprop ro.product.device` e, se possível em modo read-only, configuração `CONFIG_LOCALVERSION`/identidade do kernel. Manter relatórios A/B e 10 ciclos de conexão iguais em ambos. `FLASH_READY=false` até resolver compatibilidade, empacotamento v3 e autorização.
