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
