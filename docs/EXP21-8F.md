# EXP21.8F — Recalcular os seis hashes AVB com salt (somente arquivos offline A/B)

**Data:** 18/10/2026 | **Entrada:** `EXP21.8E_REAL_AB_AUDIT=PASS_REAL`, oito imagens A/B verificadas e descritores HASH lidos em ambos `vbmeta`. **`FLASH_READY=false`**.

## Motivo

A EXP21.8E identificou em cada `vbmeta` 3 descritores SHA256 do tipo HASH (`boot`, `dtbo`, `vendor_boot`) com sal de 32 bytes, digest de 32 bytes e `image_size` declarado. O formato AOSP define a comparação `SHA256(salt || image[0:image_size])` para descritores HASH. Isso difere do SHA-256 de **partição inteira** usado no backup. Não inferir correspondência de descritores só porque arquivo de origem SHA256 foi homologado.

Referência oficial do algoritmo e layout: https://android.googlesource.com/platform/external/avb/+/main/avbtool.py (`AvbHashDescriptor.verify`) e https://android.googlesource.com/platform/external/avb/+/refs/heads/main/libavb/avb_hash_descriptor.h .

## Implementação

Ferramenta independente `EXP21-8F/EXP21-8F-avb-hash-descriptors.py`: Python stdlib; valida comprimento e SHA-256 **integral** das 8 imagens com os hashes aprovados nas EXP12 e EXP21.8B, rejeita qualquer diferença, interpreta os descritores diretamente a partir de `vbmeta_a`/`vbmeta_b` em Big Endian, valida `flags=3`, `algorithm_type=2`, três entradas HASH distintas, cada uma com algoritmo `sha256`, `flags=0` e sal/digest de 32 bytes. Em seguida recalcula os seis digests sobre os prefixos exatos declarados.

Os resultados `MATCH` ou `MISMATCH` são **achados**, não o código de êxito/fracasso da execução. Em `MISMATCH`, reporta ambos os digests (declarado e recalculado). Uma entrada não conforme, ausente ou corrompida causa `AUDIT_REJECTED` e código de saída 2. Todas as imagens são abertas em `rb` no Windows; **nenhuma** escrita, ADB, Fastboot, leitura em dispositivo, cópia integral adicional ou alteração de slot.

### Distribuição

Arquivo criado na conversa e verificado: `PipaExperimental-EXP21-8F-avb-descriptor-audit.zip`.

- ZIP 5.951 bytes, SHA-256: `79854ff683a87cb1f73e2ef4511edc3fbe23f6089f387728d301e978e3c265b9`.
- `EXP21-8F/EXP21-8F-avb-hash-descriptors.py`, SHA-256: `8989c1b28900eb4ef85b8273aadd03749a6c07f59e28e34a7dbe5578a2228d3b`.
- `EXP21-8F/EXP21-8F-LEIA-ME.txt`, SHA-256: `f9f7011d706667dfd52ea44ac54561850c062b1f4cd00518bf41437bf796ed5c`.

**Testes materialmente rodados pelo assistente:** compilação Python `py_compile` PASS; `EXP21.8F SYNTHETIC SALTED-AVB-HASH SELFTEST: PASS` com parsing AVB sintético positivo (3 descritores), falhas de limite e descritores ausentes, e detecção de digest alterado; conteúdo e SHA-256 do ZIP verificados. **Teste real dos oito arquivos Windows do usuário não rodado**, porque os backups permanecem no computador dele. Não declarar `EXP21.8F_REAL=PASS` antes da saída do Windows.

## Executar no Windows PowerShell

```powershell
Expand-Archive `
  -LiteralPath "$env:USERPROFILE\Downloads\PipaExperimental-EXP21-8F-avb-descriptor-audit.zip" `
  -DestinationPath "$env:USERPROFILE\Downloads" -Force

python "$env:USERPROFILE\Downloads\EXP21-8F\EXP21-8F-avb-hash-descriptors.py" --self-test

python "$env:USERPROFILE\Downloads\EXP21-8F\EXP21-8F-avb-hash-descriptors.py" `
  --slot-a "C:\platform-tools\pipa_backup_a" `
  --slot-b "C:\platform-tools\pipa_backup"
```

## Como interpretar

- `INPUT [part]_[slot] SHA256=PASS`: SHA-256 integral do arquivo de origem coincide com o pino.
- `SLOT=a/b PARTITION=... STATUS=MATCH`: digest SHA-256 com sal do prefixo declarado coincide com descritor.
- `STATUS=MISMATCH`: digest declarado diverge do conteúdo efetivo, **não equivale automaticamente a corrupção da partição** nem diz sozinho a política de bootloader. A EXP13.2 já havia registrado `boot_b MISMATCH`, `dtbo_b MATCH`, `vendor_boot_b MISMATCH`.
- `COMPLETE total=6 match=N mismatch=M`: verificação de descritores concluída; realizar análise sem alterar políticas AVB ou instalar kernel.
- `AUDIT_REJECTED`: dados ausentes/corrompidos/inconsistentes, interromper investigação.

**Limites:** este algoritmo não valida a assinatura digital do blob VBMeta, cadeia de confiança OEM, valores de antirollback armazenados no bootloader, estado real de AVB durante boot, KernelSU do candidato EXP06, compatibilidade de firmware ou recuperação de boot falho. **`FLASH_READY=false`.**
