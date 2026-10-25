# EXP27.4 — Empacotamento Android Boot V3 exclusivamente offline

## Resultado

A execução [EXP27.4 run 40154584112](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/40154584112) foi concluída com **success**. Código entregue em [tools/exp27-4-build-offline.py](../tools/exp27-4-build-offline.py), com testes em [tests/test_exp27_4_offline.py](../tests/test_exp27_4_offline.py).

O CI comparou uma reconstrução sintética produzida por nosso algoritmo com o **mkbootimg AOSP oficial**, bytes idênticos, origem fixada ao commit d2bb0af5ba6d3198a3e99529c97eda1be0b5a093 e git blob ec2958179691a434df917cd1b6f196edaa80e31d. Testes de rejeição de cabeçalho corrompido, ramdisk modificado e ZIP duplicado também passaram. O CI confirmou, independentemente, o hash da Image EXP27.1 extraída do build e os marcadores de origem r8152, link RTL8153 e IRQ Novatek.

**Limite:** o GitHub não recebeu o controle original privado do Windows. Nenhum candidato Boot V3 real EXP27.1 foi gerado no CI; a reconstrução fiel contra mkbootimg foi validada apenas em fixture sintética.

## Entradas fixadas

- Controle compacto original Windows: C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img, tamanho 32206848, SHA-256 **202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7**.
- Kernel Image EXP27.1: Actions run 40152429269, artefato **pipa-exp27-r8152-v11011-clang21-3.zip**, SHA-256 da Image **a14b536b471c97db877482afe97bcbeb97daa74ebc48a3a344d90ead57d56967**.
- Código do r8152 v1.10.11: fonte 5.4.290 pinada ao git blob **92b51c4c46f57b660f3053804ba74f6df9e71c76**.
- Kernel original stock: SHA256 a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd, 30349336 bytes.
- Ramdisk original: SHA256 d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9, 1849345 bytes.
- Layout: Android Boot v3, header 1580 bytes, alinhamento 4096 bytes.

## Executar no Windows sem acesso ao tablet

Salvar tools/exp27-4-build-offline.py na pasta C:\platform-tools. Baixar e manter no Downloads o artefato original do Actions EXP27.1. O script faz verificações SHA-256 antes de produzir candidato. Ele recusa a existência prévia da pasta de saída.

~~~powershell
Get-FileHash "C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img" -Algorithm SHA256
cd C:\platform-tools
py -3 .\exp27-4-build-offline.py --stock "C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img" --artifact "$env:USERPROFILE\Downloads\pipa-exp27-r8152-v11011-clang21-3.zip" --output-dir "C:\platform-tools\EXP27.4-boot-prep"
Get-FileHash "C:\platform-tools\EXP27.4-boot-prep\EXP27.4-RTL8153-NOT-FOR-FLASH.candidate.bin" -Algorithm SHA256
~~~

Saídas locais: **EXP27.4-RTL8153-NOT-FOR-FLASH.candidate.bin** e **EXP27.4-offline-audit.json**. Compartilhar somente a saída textual e metadados JSON, não o controle original privado. O report indica ramdisk, cmdline, word de OS/version e demais bytes do cabeçalho inalterados. Apenas o kernel e seu kernel_size diferem, com padding recalculado.

## Segurança / gates

A extensão candidate.bin e o rótulo NOT-FOR-FLASH são avisos operacionais, não proteção física contra gravação. Não executar fastboot boot, flash, erase, set_active, reboot, rebind USB ou mudanças de alimentação. Nenhuma alteração do Xiaomi pipa ou da EXP25A ocorreu neste ciclo.

**EXP27_4_SYNTHETIC_AOSP=PASS; EXP27_4_CI_IMAGE_PROVENANCE=PASS; EXP27_4_REAL_WINDOWS_REPACK=PENDING; RECOVERY_VERIFIED=false; TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false.**
