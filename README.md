# Pipa Experimental Kernel

Kernel experimental para Xiaomi Pad 6 (**pipa**, Snapdragon 870), desenvolvido sobre uma revisão **fixada** do E404.

> **ATENÇÃO:** este repositório não contém nenhum ZIP flashável nem um `boot.img` validado. Não instale `PipaExperimental-EXP01-source.zip` via recovery, Magisk, KernelSU ou fastboot.

## Estado da EXP01

- Base de código: `kvsnr113/xiaomi_sm8250_kernel_e404`, branch `main-bpf`, commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- Experimento: intervalo inicial do governor `schedutil` de 2000 para **1500 µs**, habilitado somente via `vendor/pipa_defconfig`.
- Preservados: limites de frequência, proteções térmicas, governor GPU e lógica de instalação/boot.
- Original: `PipaExperimental-EXP01-source.zip` (SHA-256 `548ebb47ad0febe3c4541b9e93f2233bb9188c78d8f9ec298dd397a11216b852`).
- Patch revisado: `patches/0001-pipa-exp01-schedutil-rate-limit.patch`, usado pelo CI em substituição à primeira revisão arquivada no ZIP.

## CI sem WSL

[Executar / consultar GitHub Actions](../../actions/workflows/exp01-validate-build.yml)

O workflow é executado automaticamente em modo **validate** ao receber mudanças nos arquivos de configuração da EXP01. Também pode ser executado manualmente em **Actions → Pipa EXP01 - Validate and Build → Run workflow**.

- `validate`: checa ZIP, scripts, commit E404, aplicação do patch e configuração do kernel.
- `build`: tenta compilar uma `Image` ARM64 e salva logs. **Não gera `boot.img` nem garante compatibilidade para flash.**

## Portões antes de qualquer instalação

1. Compilação ARM64 e configuração do pipa aprovadas.
2. Análise de DTB/DTBO, vendor_boot, módulos e compatibilidade com a ROM crDroid Android 16.
3. Empacotamento reversível usando imagens originais preservadas localmente.
4. Plano de recuperação validado no dispositivo e testes graduais de inicialização.

**Nunca envie ao GitHub backups privados** (`boot_b.img`, `vendor_boot_b.img`, `dtbo_b.img`, `vbmeta_b.img`) nem dados de root.
