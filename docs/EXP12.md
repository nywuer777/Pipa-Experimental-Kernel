## Homologação em hardware: auditoria offline dos backups reais (18/10/2026)

**RESULTADO: PASS, fornecido pelo usuário no PowerShell do Windows**, usando `C:\platform-tools\exp12-run.ps1` corrigido com o ZIP original da EXP06. Abaixo as evidências mais relevantes extraídas da saída real:

```text
EXP12 REAL SLOT-B OFFLINE PREFLIGHT: PASS
BACKUPS sha256=verified count=4 device=pipa slot=_b
BOOT version=3 original_kernel_bytes=30349336 offset=4096 generic_ramdisk_bytes=1849345 offset=30355456
VENDOR_BOOT version=3 vendor_ramdisk_bytes=20412235 dtb_bytes=460314 dtb_sha256=9b92c1aa019fffdfaf3bfe36dcd84c2858c804109c100b684e08f62228881117
DTBO table_bytes=688455 entries=1 table_sha256=6a0e109590742ce67713d738aef1320e015e9abc6b509d5be7f6e9ed46dd4f9c
VBMETA version=1.0 algorithm=2 flags=3 signature_verified=False
EXP06 image_sha256=7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033 kernel_size_preserves_offsets=True dtb_dtbo_same_as_backup=True
NO IMAGE CREATED. NO FILE MODIFIED. FLASH_READY=false
```

**Confirmações e limites:** os quatro hashes originais de backup e os componentes internos passaram na auditoria local; o ZIP da EXP06 também passou. O uso de `SHA-256` e a análise de offsets provam integridade do conjunto fornecido e compatibilidade *estrutural* do layout, não inicialização. A assinatura AVB, a aceitação da imagem pelo bootloader, integridade do KernelSU, recovery/rollback e desempenho continuam sem comprovação. Não gerar/instalar `boot.img` enquanto as barreiras não forem fechadas. **`FLASH_READY=false`.**


## EXP12.1 — correção permanente do PowerShell 5.1 (18/10/2026)

A execução local no Windows confirmou que a auditoria passava na validação de integridade dos quatro backups, cabeçalhos, ramdisks, DTB, DTBO e vbmeta antes de falhar na linha de leitura do ZIP com `TypeNotFound: [IO.Compression.ZipFile]`. A causa foi a ausência do carregamento da assembly `System.IO.Compression.FileSystem` no script, apesar de o teste original de CI carregar essa assembly separadamente.

O script `tools/exp12-windows-preflight.ps1` foi **corrigido**, carregando agora `System.IO.Compression` e `System.IO.Compression.FileSystem` no próprio processo. Adicionou-se `-ZipOnlySelfTest` para validar o ZIP real EXP06, sua Image, seu DTB e seu DTBO sem necessitar dos backups privados.

**Validação EXP12.1:** [GitHub Actions #39146270295](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39146270295) **success**, incluindo leitura real do ZIP nos ambientes Windows PowerShell 5.1 e PowerShell 7. O workflow publica também o script corrigido em um ZIP privado `pipa-exp12-windows-fixed-3` (artefato 12143795806).

**Recomendação ao usuário:** substituir a cópia anterior `C:\platform-tools\exp12-run.ps1` pelo script corrigido (fornecido no chat como arquivo direto ou obtido no GitHub autenticado) e executar novamente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp12-run.ps1" -BackupDir "C:\platform-tools\pipa_backup" -Exp06Zip "$env:USERPROFILE\Downloads\pipa-exp06-clang21-1.zip"
```

Até obter a linha **`EXP12 REAL SLOT-B OFFLINE PREFLIGHT: PASS`** da execução no Windows real, o gate de auditoria local permanece **pendente**. `FLASH_READY=false`.


# EXP12 — Pré-auditoria real no Windows (sem flash)

## Status de implementação

- Ferramenta implementada: [`tools/exp12-windows-preflight.ps1`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp12-windows-preflight.ps1).
- Testes sintéticos e negativa: [GitHub Actions #39145107412](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39145107412), **success**.
- Windows PowerShell 5.1 e PowerShell 7 testados.
- O tablet e os backups privados do usuário **não foram acessados pelo GitHub Actions**.
- Execução contra backups reais no computador do usuário: **pendente**.

## O que o script verifica

Lê diretamente os arquivos locais `C:\platform-tools\pipa_backup\boot_b.img`, `vendor_boot_b.img`, `dtbo_b.img`, `vbmeta_b.img` e o artefato original do Actions `pipa-exp06-clang21-1.zip`.

Falha se qualquer hash integral de imagem ou ZIP diferir dos hashes verificados anteriormente:

| Entrada | SHA-256 exigido |
| --- | --- |
| boot_b.img | `31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4` |
| vendor_boot_b.img | `a24ea921db6014a49f9895cc5c18efbb6c6674d697f25cde3b7a1670a643c28c` |
| dtbo_b.img | `f4168f76d092362ac438543d74938d83e3e567a37abb16e4d61fe7ba764588e2` |
| vbmeta_b.img | `86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff` |
| EXP06 artifact ZIP | `e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402` |
| EXP06 kernel Image | `7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033` |

Também confere os hashes das subpartes originais (kernel, ramdisk genérica, ramdisk vendor, DTB e DTBO) e os componentes da EXP06, os offsets calculados de boot-v3, vendor_boot-v3, tabela DTBO FDT e cabeçalho AVB.

**Não** verifica AVB criptograficamente; o `vbmeta_b.img` é apenas analisado estruturalmente, sem interpretação de uma cadeia de confiança de boot comprovada. Não cria boot.img, não modifica backup, não usa adb e não oferece flash.

## Como executar no Windows

Usando PowerShell na máquina que contém as imagens do backup, primeiro baixe o script do GitHub diretamente em um nome que não conflita com a antiga pasta `exp05-compare-kernels.ps1`:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/nywuer777/Pipa-Experimental-Kernel/main/tools/exp12-windows-preflight.ps1" -OutFile "C:\platform-tools\exp12-run.ps1"
Test-Path "C:\platform-tools\exp12-run.ps1" -PathType Leaf
```

O `Test-Path` precisa retornar `True`. Caso a origem não esteja publicamente disponível, baixe o arquivo pelo [GitHub](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp12-windows-preflight.ps1), em `Download raw file`.

Baixe o artefato original [EXP06 `pipa-exp06-clang21-1`](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39136149722/artifacts/12140930183) e deixe o ZIP em `C:\Users\User\Downloads\pipa-exp06-clang21-1.zip`. Não descompacte nem recompacte, porque o hash exato do arquivo ZIP é validado.

Execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp12-run.ps1" -BackupDir "C:\platform-tools\pipa_backup" -Exp06Zip "$env:USERPROFILE\Downloads\pipa-exp06-clang21-1.zip"
```

Se o ZIP tiver outro nome, ajuste só o valor de `-Exp06Zip` para o caminho real. O script não cria nem salva arquivos; o resultado é texto no PowerShell. Envie apenas essa saída.

## Testes sintéticos realizados

A CI confirmou:

- Validade estrutural de boot v3 sintético com `ANDROID!`, cabeçalho 1580, `ARMd`, ramdisk gzip e offsets;
- Rejeição de kernel sem magic `ARMd`;
- Falha fechada se o diretório de backup ou o ZIP estiverem ausentes;
- Leitura do ZIP EXP06 autêntico com SHA256 exato e três entradas ARM64/DTB/DTBO corretas;
- Proibição estática de comandos de flash e de gravações.

As rotinas para vendor_boot, DTBO e vbmeta também foram testadas anteriormente em fixtures do EXP11 Python; nesta CI EXP12 específica não há teste PowerShell sintético de cada variação daquelas estruturas. Não declarar essa validação adicional.

## Portão de segurança

`FLASH_READY=false`.

A passagem dessa pré-auditoria comprovará apenas integridade, layout e preservação estrutural de offsets (se o script passar). Não garante que o kernel inicialize, que o root KernelSU persista, que o AVB aceite uma imagem modificada, que haja método de recuperação comprovado ou que a mudança no schedutil melhore FPS.
