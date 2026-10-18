# EXP07 — comparação da configuração REAL do tablet com a compilação EXP06

## Estado

- EXP06 ARM64 compilada com Android Clang21 build 14054515: [execução #39136149722](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39136149722) **success**.
- Artefato: `pipa-exp06-clang21-1` ID `12140930183`, SHA-256 do ZIP `e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402`.
- Binário `Image` (30349336 bytes): `7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033`.
- DTB (460314 bytes) hash `9b92c1aa019fffdfaf3bfe36dcd84c2858c804109c100b684e08f62228881117`, **igual ao do vendor_boot_b original**.
- DTBO (688455 bytes) hash `6a0e109590742ce67713d738aef1320e015e9abc6b509d5be7f6e9ed46dd4f9c`, **igual ao da tabela dtbo_b original**.
- Config EXP06: `CONFIG_KSU=y`, `CONFIG_MODULES=n`, `CONFIG_PIPA_EXP_SUGOV=y`, `CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500`.
- O usuário confirmou no tablet: `/proc/version` apresenta a mesma versão do E404 do backup (`4.19.404R`, Android Clang 21.0.0, build 14054515) e `/proc/config.gz` **existe e está legível** (44819 bytes no momento do comando).
- Ainda não foi obtido o conteúdo de `/proc/config.gz` para comparação.

## Evidência e limites

O mesmo tamanho do kernel e hashes idênticos de DTB/DTBO são bons indícios de paridade estrutural, mas **não garantem boot, root, ABI, AVB ou FPS**.

## Coleta segura (Windows com ADB)

```powershell
C:\platform-tools\adb.exe pull /proc/config.gz "C:\platform-tools\pipa-running-config.gz"
Get-Item "C:\platform-tools\pipa-running-config.gz" | Select-Object Name,Length
```

É um arquivo comprimido pequeno com **configuração**, não uma imagem de partição. Pode ser anexado diretamente à conversa para auditoria, **não ao repositório**.

Como alternativa inteiramente local, baixe do GitHub o ZIP `pipa-exp06-clang21-1` e o script `tools/exp07-compare-running-config.ps1` e execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp07-compare-running-config.ps1" -LiveConfigGz "C:\platform-tools\pipa-running-config.gz" -Exp06Zip "$env:USERPROFILE\Downloads\pipa-exp06-clang21-1.zip"
```

O script valida o SHA-256 do artefato original antes da leitura, descomprime o `config.gz`, lê o `.config` do ZIP sem extrair imagens, mostra indicadores críticos e conta todas as diferenças.

## Testes automatizados

Workflow [EXP07 #39138619758](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39138619758) aprovado em PowerShell 5.1 e 7, com configurações sintéticas idênticas e diferentes; detectou corretamente os flags KernelSU e schedutil alterados.

## Segurança

**Sem flash, sem geração boot.img, sem edição das partições.** A comparação com a configuração real está pendente.
