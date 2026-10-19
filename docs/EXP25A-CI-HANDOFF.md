# EXP Kernel — EXP25A, handoff da compilação

## EXP25A — CI compilado e aprovado (2026-10-18, horário America/Sao_Paulo)

- GitHub Actions [#39190015939](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39190015939), job #117860543809, `status=completed`, `conclusion=success` (aproximadamente 15m55s).
- Commit de código **exatamente testado**: `8e77fcb4cefb112a4258af36f9a9f855f333bb9b`; mudanças posteriores no README/docs não integram esta imagem.
- Artefato publicado: `pipa-exp25a-touch-irq-clang21-1`, ID `12160460604`, arquivo ZIP comprimido 12.387.363 bytes segundo metadados do Actions; expiração prevista 2026-11-02 02:42:54 UTC (sujeito às políticas do GitHub). Conteúdo previsto no workflow: `exp06-work/out/arch/arm64/boot/Image`, DTB, DTBO, .config e evidências.
- SHA-256 do arquivo **Image** segundo o log CI: `2dac2dd05fe3cab8b167ea10bc632512c1508fa4d26db88d002837d0dc681e08`. Verificar este valor novamente após download local (artefato ZIP tem hash próprio diferente).
- Toolchain confirmada: `Android (14054515, clang version 21.0.0)`, AOSP Clang pinado `b54cd2c8e9e0bb057aef3804d42d39c5ac4674c7`.
- Gates aprovados: `EXP25A_HERMETIC_TESTS=PASS`; `EXP24 CONFIG_GATE=PASS`; `EXP25A_NVT_IRQ_GATE=PASS`; `EXP24_RTL8153_LINK_PASS`; `EXP25A_IMAGE_BUILT=YES`.
- Preservados: `CONFIG_TOUCHSCREEN_NT36532_HOSTDL_SPI=y`, `CONFIG_USB_RTL8152=y`, `CONFIG_KSU=y`, `CONFIG_PIPA_EXP_SUGOV=y`, `CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500`; módulos desabilitados.
- A mudança no Novatek é **somente restauração idempotente e incondicional da IRQ no resume** com marcador `EXP25A_IRQ_RESTORE`. Não modifica firmware CSOT, sistema de arquivos do tablet, controle de energia USB-C nem retentativas SPI.
- **Gates ainda pendentes:** inspecionar localmente bytes e SHA do artefato; produzir candidato de `boot.img` apenas por método reversível auditado (Image sozinha não é boot.img); aprovação explícita de reinicialização temporária; medir boot, IRQ 521, firmware CSOT, eventos de toque e reconexão RTL8153.
- Status de liberação: `BUILD_CI=PASS`, `DEVICE_BOOT=NOT_TESTED`, `TOUCH_FIXED=UNPROVEN`, `FIRMWARE_RECOVERY=UNCHANGED`, `USB_HOTPLUG=UNRESOLVED`, **`FLASH_READY=false`**.

