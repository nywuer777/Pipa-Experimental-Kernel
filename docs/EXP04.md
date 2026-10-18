# EXP04 — identidade do kernel do slot _b (somente leitura)

Estado: **coleta local pendente**, testes de ferramenta aprovados.

## Fatos confirmados pela EXP03 no tablet e nos backups

- Equipamento: Xiaomi Pad 6 (pipa), ROM crDroid 16 (Android 16), kernel E404.
- Slot ativo: `_b` via `adb shell getprop ro.boot.slot_suffix`. A primeira tentativa ADB deu "device not found", a segunda respondeu `_b`.
- Backup `boot_b.img`: Android Boot v3, header 1580, kernel ARM64 30349336 bytes, ramdisk gzip 1849345 bytes, offsets kernel 4096 / ramdisk 30355456.
- Backup `vendor_boot_b.img`: Vendor Boot v3, header 2112, page 4096, vendor ramdisk gzip 20412235 bytes (offset 4096), FDT de 460314 bytes (offset 20418560).
- Backup `dtbo_b.img`: tabela v0, 688455 bytes, 1 entrada válida.
- Backup `vbmeta_b.img`: AVB 1.0, algoritmo 2, `flags=3` (bits 0 e 1: hashtree e verificação desativados no cabeçalho de vbmeta examinado). **Assinatura não verificada**.
- A EXP01 compilada: `Image` 30349328 bytes e SHA-256 `bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11`.

> Diferença de 8 bytes entre kernels não comprova compatibilidade. A estrutura de boot v3 permite que o deslocamento do ramdisk não mude se o tamanho alinhado a 4096 continuar igual, mas isso não garante inicialização.

## EXP04 implementada

`tools/exp04-kernel-identity.ps1` funciona em Windows PowerShell 5.1 e PowerShell 7, lê as partições `boot_b`, `vendor_boot_b`, `dtbo_b` e `vbmeta_b` **diretamente do disco** com acesso somente leitura e gera hashes SHA-256 de regiões relevantes:

- Kernel original do `boot_b` completo, e o prefixo dos primeiros 30349328 bytes comparado com o SHA da EXP01.
- Ramdisk genérico original, vendor ramdisk original, FDT do vendor_boot e a tabela DTBO.
- Flags AVB interpretadas, sem assinaturas verificadas.
- Últimos 8 bytes do kernel original para identificar eventual trailer/assinatura adicional.

**Nenhum arquivo de imagem é produzido, nenhum backup é alterado e nada é enviado ao GitHub.**

## Execução no Windows

1. Baixe do repositório privado (via navegador autenticado):
`tools/exp04-kernel-identity.ps1`.
2. Salve como `C:\platform-tools\exp04-kernel-identity.ps1` e revise o conteúdo.
3. Execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp04-kernel-identity.ps1" -BackupDir "C:\platform-tools\pipa_backup"
```

4. Compartilhe apenas as linhas textuais de saída, não os arquivos `.img`.

## Testes

O workflow `.github/workflows/exp04-kernel-identity.yml` verifica as operações de leitura e hash em imagens sintéticas no Windows Server 2022, tanto PowerShell 7 quanto Windows PowerShell 5.1.

Os testes não provam correspondência com o kernel real. O portão `FLASH_READY` continua bloqueado até analisar compatibilidade ABI de módulos, root, firmware, DTB/DTBO, cadeia AVB e meios de restauração.

## O que não fazer

- Não executar `fastboot flash` nem `dd`.
- Não substituir o kernel dentro de `boot_b.img` apenas pela diferença de tamanho.
- Não editar `vbmeta_b.img` nem confiar em flags para substituir verificação de segurança.
- Não enviar backups privados ao repositório.
