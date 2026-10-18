## EXP19 — HOMOLOGAÇÃO REAL NO WINDOWS: PASS (18/10/2026)

O usuário executou novamente o procedimento offline usando o ZIP EXP06 original, já localizado. Evidência reproduzida no PowerShell:

```text
EXP19 PYTHON_RUNTIME=VALIDATED selector=py
EXP19 SYNTHETIC VIRTUAL SPLICE SELFTEST: PASS
EXP19 REAL OFFLINE OFFICIAL AOSP EXP06 CANDIDATE: PASS
SOURCE original_boot_sha256=verified exp06_zip_sha256=verified aosp_source_blobs=verified
CONTROL official_original_repack=MATCH
CANDIDATE compact_bytes=32206848 sha256=30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c
VIRTUAL_FULL_SHA256=c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00 exp15_match=True
OUTPUTS candidate_file=EXP19-EXP06-NOT-FOR-FLASH.candidate.bin audit_file=EXP19-EXP06-offline-audit.json
NO ADB. NO FASTBOOT. NO BACKUP MODIFIED. FLASH_READY=false
```

**Resultado:** candidato compacto EXP06 offline gerado por AOSP `mkbootimg`, com controle de reempacotamento stock exato, hashes de origem aprovados e SHA256 da partição virtual batendo com EXP15. O erro anterior `ZIP EXP06 nao encontrado` foi resolvido pelo usuário; o arquivo estava disponível para a execução bem-sucedida. A imagem candidata foi gerada **somente no computador Windows do usuário**, não no tablet. Não é imagem aprovada para instalação. A homologação EXP19 é de construção e integridade offline; não prova bootabilidade, KernelSU, AVB, DTB ou possibilidade de restauração.

**Próximo gate EXP20:** auditoria independente, em modo somente leitura, dos bytes do candidato contra o backup original e os hashes EXP06, com conferência integral das regiões não-kernel e do relatório JSON; `FLASH_READY=false`.

## EXP19 — execução real inicial bloqueada por caminho de ZIP ausente (18/10/2026)

O usuário executou a ferramenta do pacote EXP19 no Windows com `-SelfTest`, **PASS**:

```text
EXP19 PYTHON_RUNTIME=VALIDATED selector=py
EXP19 SYNTHETIC VIRTUAL SPLICE SELFTEST: PASS
AOSP_STOCK_CONTROL_EXECUTED=False PRIVATE_BACKUPS_READ=False
NO BOOT IMAGE CREATED. NO DEVICE COMMANDS. FLASH_READY=false
```

A execução seguinte falhou **antes de abrir o backup** com `EXP19: ZIP EXP06 nao encontrado.` O caminho de entrada fornecido era `C:\Users\User\Downloads\pipa-exp06-clang21-1.zip`, não existente na ocasião. Isso não refuta a homologação EXP06 ou as fases EXP12–18; falta localizar o arquivo EXATO.

### Arquivo EXP06 recuperável do GitHub Actions

Conferência feita em GitHub no mesmo dia:
- Workflow [#39136149722](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39136149722) aprovado.
- Artifact ID `12140930183` nome `pipa-exp06-clang21-1` (Actions ZIP), tamanho informado 12.261.845 bytes, não expirado no momento da consulta; expiração programada para **2026-11-01**.
- SHA-256 aprovado do ZIP EXP06 é `e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402`.

O usuário deve localizar o ZIP em Downloads/Desktop ou baixá-lo novamente via Actions autenticado e verificar o hash antes de executar `EXP19-run-windows.ps1 -Exp06Zip <caminho encontrado>`. É proibido aceitar outro arquivo por semelhança de nome: rejeitar hash divergente.

**Estado histórico após a primeira tentativa:** `EXP19_SELFTEST=PASS_REAL`, `EXP19_CANDIDATE_REAL=NOT_EXECUTED` (ZIP ausente). **Situação posterior:** corrigida e homologada, conforme seção principal acima. `FLASH_READY=false`.

# EXP19 — Candidato EXP06 AOSP somente offline (NAO INSTALAR)

Data: 18/10/2026 | Xiaomi Pad 6 `pipa` | referência ao slot `_b`.

## Estado imediatamente anterior

- EXP18.1: inventário de recuperação Windows, ADB, 4/4 backups e EXP06 ZIP aprovados.
- EXP18.2: transporte real Fastboot no bootloader aprovado (`product=pipa`, `current_slot=b`, `is_userspace=no`, `unlocked=yes`, `slot_count=2`).
- EXP18.3: `fastboot reboot` normal e retorno ao Android homologados: `adb devices -l` reconheceu `pipa`, `ro.boot.slot_suffix=_b`. `uname -r=5.10.404R` pode ser mascarado pela customização antiga do kernel `kernel/sys.c` e não comprova versão real 5.10.
- AVB top-level: descritores `boot` e `vendor_boot` **MISMATCH** em EXP13.2, enquanto `dtbo` MATCH; `flags=3`; não supor bootabilidade de imagem nova.
- EXP17 original AOSP `mkbootimg` compacta v3: `RESULT=MATCH`, 32.206.848 bytes, SHA256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`.
- EXP15 candidato virtual (nenhum arquivo gerado): SHA256 hipotético de partição inteira `c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00`.

## Implementação EXP19

Pacote entregue à conversa: `PipaExperimental-EXP19-EXP06-offline-candidate.zip`, SHA-256 **`446bcc3f4e818eb15ab2963b67271b283ab5cd66768200b8c748042b038932f3`**.

Conteúdo exato do pacote:

| Arquivo | SHA256 |
| --- | --- |
| `EXP19-exp06-offline-candidate.py` | `1af39e0c1952eba9de0ad431fe6e20a1affde3ad4f7197e34d36d9fa2d40e480` |
| `EXP19-run-windows.ps1` | `1b390f542dd860e0e8fca4e184806882e56e4bb754481f0eb909f63b42b2eb28` |
| `EXP17-aosp-mkbootimg-compare.py` | `642d8c8158ae95fd731f7ee16ccc85b7ba155dc8b11922c2232749b45b2fec63` |
| `EXP19-LEIA-ME.txt` | `f56268a72b3af811a7891c8a2d412f2bb3aa8aacad7b017fc9cb167eb7bfc065` |

O script Python carrega somente a implementação EXP17 cujos bytes correspondam a SHA256 fixado. Compara SHA256 da partição original de 192MiB e do ZIP EXP06 (pinos EXP12 e EXP06); também verifica kernel ARM64 e SHA256 fixados de `Image` (30349336 bytes), `dtb` (460314 bytes) e `dtbo.img` (688455 bytes). Extrai kernel e ramdisk originais para pasta temporária e baixa `mkbootimg.py` oficial AOSP (ou usa fontes locais verificadas com Git blob SHA1). **Antes de criar a candidata**, recria o boot original compacto com ferramenta oficial e exige coincidência byte a byte. Depois cria o candidato compacto EXP06, compara-o com um splice lógico do backup e comprova o digest virtual da partição de 192MiB **igual à EXP15**, sem gerar uma partição inteira.

O output fica separado em `Downloads\EXP19-output`, não substitui qualquer arquivo original e recusa sobrescrever uma candidata já existente:

- `EXP19-EXP06-NOT-FOR-FLASH.candidate.bin` (compacta AOSP com kernel EXP06, 32.206.848 bytes)
- `EXP19-EXP06-offline-audit.json` (hash SHA-256 e as limitações)

A extensão `.candidate.bin` e rótulo `NOT-FOR-FLASH` evitam apresentá-la como pacote instalável.

## Evidência de testes

- Compilação sintática Python: PASS.
- EXP19 autoteste sintético (substituição virtual, digest esperado, rejeição de kernel truncado): **PASS**.
- Checagem estática da ausência de caminhos `fastboot.exe`/`adb.exe` e de comandos de flash/boot no Python: PASS.
- Conteúdo do ZIP e SHA256 conferidos: PASS.
- **Execução real com boot_b.img no Windows do usuário: PENDENTE.** A origem contém hash fixado e não está no ambiente local do assistente. Não declarar `candidate_real=PASS` até receber a saída Windows.
- Nenhum candidato foi gerado no computador do usuário por esta entrega, apenas a ferramenta.

## Comandos no Windows

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\PipaExperimental-EXP19-EXP06-offline-candidate.zip" -DestinationPath "$env:USERPROFILE\Downloads\EXP19" -Force
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\EXP19\EXP19-run-windows.ps1" -SelfTest
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\EXP19\EXP19-run-windows.ps1" -FetchAosp -BootPath "C:\platform-tools\pipa_backup\boot_b.img" -Exp06Zip "$env:USERPROFILE\Downloads\pipa-exp06-clang21-1.zip" -OutDir "$env:USERPROFILE\Downloads\EXP19-output"
```

**NAO instalar a candidata.** Criar arquivo offline ≠ comprovar inicialização. Ainda faltam plano de rollback após boot falho, KernelSU, verificação de DTB/DTBO junto ao firmware e aceite AVB. `FLASH_READY=false`.
