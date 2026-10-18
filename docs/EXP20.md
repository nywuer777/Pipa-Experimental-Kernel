## EXP20 — HOMOLOGAÇÃO REAL INDEPENDENTE: PASS (18/10/2026)

O usuário executou **duas vezes** o autoteste sintético e a auditoria independente no Windows; os dois conjuntos produziram resultados idênticos:

```text
EXP20 INDEPENDENT SYNTHETIC CANDIDATE AUDIT: PASS
CHECKS non-kernel identity, bad padding rejection, modified kernel digest rejection
NO PRIVATE FILES READ. NO DEVICE COMMANDS. FLASH_READY=false

EXP20 REAL INDEPENDENT EXP19 CANDIDATE AUDIT: PASS
INPUT original_boot_sha256=verified candidate_sha256=verified report=verified
LAYOUT header_bytes=4096 kernel_bytes=30349336 compact_bytes=32206848
REGIONS original_header_padding_ramdisk=BYTE_IDENTICAL candidate_kernel_sha256=EXP06_MATCH
CANDIDATE compact_sha256=30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c
VIRTUAL_FULL_SHA256=c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00 exp15_match=True
LIMITS: read-only structural verification. No AVB/KernelSU/bootability/rollback proof.
NO FILE WRITTEN. NO DEVICE COMMANDS. FLASH_READY=false
```

**Resultado:** `EXP20_INDEPENDENT_OFFLINE_AUDIT=PASS_REAL`, confirmado duas vezes pelo mesmo auditor. O arquivo compacto gerado na EXP19 tem SHA-256 esperado, seu kernel coincide com a EXP06, e a área não-kernel (cabeçalho, padding e ramdisk) está byte a byte idêntica ao backup original. O SHA-256 virtual da partição completa coincide com o calculado na EXP15. A execução repetida fornece consistência operacional do auditor, não validação por ferramenta diferente da EXP20.

**Limites e decisão:** nenhuma verificação de inicialização, AVB ativo, KernelSU ou recuperação de uma falha de boot foi executada; não instalar candidato. `FLASH_READY=false`.

**Próximo portão:** `EXP21` — inventário somente leitura das dependências e capacidades do ambiente de boot/rollback, sem reiniciar, gravar, executar fastboot em modo bootloader, ou tentar boot temporário.

# EXP20 — Auditoria independente do candidato EXP06 (leitura apenas)

**Data:** 18/10/2026 | **Dispositivo:** Xiaomi Pad 6 (`pipa`) | **FLASH_READY=false**.

## Evidência herdada, EXP19 aprovada no Windows real

O candidato compacto EXP06 foi produzido no computador do usuário e testado pelo wrapper AOSP da EXP19:

```text
EXP19 REAL OFFLINE OFFICIAL AOSP EXP06 CANDIDATE: PASS
SOURCE original_boot_sha256=verified exp06_zip_sha256=verified aosp_source_blobs=verified
CONTROL official_original_repack=MATCH
CANDIDATE compact_bytes=32206848 sha256=30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c
VIRTUAL_FULL_SHA256=c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00 exp15_match=True
OUTPUTS candidate_file=EXP19-EXP06-NOT-FOR-FLASH.candidate.bin audit_file=EXP19-EXP06-offline-audit.json
NO ADB. NO FASTBOOT. NO BACKUP MODIFIED. FLASH_READY=false
```

A imagem criada na pasta `Downloads\EXP19-output` é **somente para auditoria offline**; não é uma imagem homologada para flash.

## EXP20 — verificação independente

Entregue um auditor Python independente de todos os módulos e scripts de EXP19. Ele utiliza somente Python stdlib, **não executa `mkbootimg`, `adb`, `fastboot`, downloads ou comandos de escrita**, e não gera um segundo candidato. Confere os três insumos locais:

- Backup original de 192 MiB: `C:\platform-tools\pipa_backup\boot_b.img`.
- Candidato compacto: `%USERPROFILE%\Downloads\EXP19-output\EXP19-EXP06-NOT-FOR-FLASH.candidate.bin`.
- JSON: `%USERPROFILE%\Downloads\EXP19-output\EXP19-EXP06-offline-audit.json`.

Testes: SHA256 e tamanho integrais do original; SHA256 stock compacto (`202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`); SHA256 candidato (`30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c`); kernel ARM64 EXP06 exatamente em offset 4096 com 30349336 bytes e SHA256 `7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033`; bytes de header, cmdline, padding e ramdisk idênticos ao stock; cálculo independente do SHA256 virtual partição inteira `c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00`; igualdade estrita de campos críticos do JSON, incluindo `flash_ready=false` (sem conversão booleana frouxa).

### Artefato entregue

`PipaExperimental-EXP20-independent-candidate-audit.zip`:
- SHA256 ZIP `a6704d9a05c5ab0cc70078857dd82fb27f24d66adb4687e11ea3cb4760d9d6e7`.
- Script `EXP20-independent-candidate-audit.py`, SHA256 `4d615b0a7ca2a3c2d19e729b72c926d48818485d339bc94f42493501e50ef58e`.
- Instruções `EXP20-LEIA-ME.txt`, SHA256 `159330bb8e1532d574f4a12c2d4f26221886255a5ffe4aae69bfc4041693e35e`.

**Testes realmente executados pelo assistente:** sintaxe compilada no Python da sessão e autoteste sintético `EXP20 INDEPENDENT SYNTHETIC CANDIDATE AUDIT: PASS` com rejeição de corrupção do padding e alteração do kernel; verificação de membros/hashes do ZIP. **Testes não executados:** auditoria sobre backup original e candidato de 32 MiB reais do usuário, que continuam somente no computador Windows. Não afirmar homologação real da EXP20 antes da saída.

### Executar Windows / PowerShell

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\PipaExperimental-EXP20-independent-candidate-audit.zip" -DestinationPath "$env:USERPROFILE\Downloads\EXP20" -Force
python "$env:USERPROFILE\Downloads\EXP20\EXP20-independent-candidate-audit.py" --self-test

python "$env:USERPROFILE\Downloads\EXP20\EXP20-independent-candidate-audit.py" `
  --boot "C:\platform-tools\pipa_backup\boot_b.img" `
  --candidate "$env:USERPROFILE\Downloads\EXP19-output\EXP19-EXP06-NOT-FOR-FLASH.candidate.bin" `
  --report "$env:USERPROFILE\Downloads\EXP19-output\EXP19-EXP06-offline-audit.json"
```

Expansão em `Downloads\EXP20` é apenas da ferramenta; a auditoria em si **não escreve nenhum arquivo**. Se o caminho ou digest falhar, a execução é rejeitada.

**Não instalar candidato EXP19/EXP20.** Compatibilidade de inicialização, KernelSU, AVB e recuperação após boot falho não foram comprovadas. `FLASH_READY=false`.
