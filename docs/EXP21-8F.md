## EXP21.8F — HOMOLOGAÇÃO REAL WINDOWS: 6/6 DESCRITORES AUDITADOS (18/10/2026)

O usuário executou `--self-test` (**PASS**) e a ferramenta real EXP21.8F nos oito backups offline A/B. **Todos os oito hashes integrais SHA-256 dos arquivos passaram** frente aos pinos anteriores. Ambas as imagens `vbmeta` têm `flags=3`, `algorithm_type=2` e 3 descritores de HASH. Resultado literal:

```text
EXP21.8F SYNTHETIC SALTED-AVB-HASH SELFTEST: PASS
EXP21.8F REAL OFFLINE AVB HASH DESCRIPTORS; FLASH_READY=false
SLOT=a PARTITION=boot IMAGE_SIZE=51240960 STATUS=MISMATCH
SLOT=a PARTITION=dtbo IMAGE_SIZE=6402048 STATUS=MISMATCH
SLOT=a PARTITION=vendor_boot IMAGE_SIZE=21651456 STATUS=MISMATCH
SLOT=b PARTITION=boot IMAGE_SIZE=31920128 STATUS=MISMATCH
SLOT=b PARTITION=dtbo IMAGE_SIZE=692224 STATUS=MATCH
SLOT=b PARTITION=vendor_boot IMAGE_SIZE=20697088 STATUS=MISMATCH
EXP21.8F SALTED HASH DESCRIPTORS: COMPLETE total=6 match=1 mismatch=5
NO ADB. NO FASTBOOT. NO BACKUP MODIFIED. FLASH_READY=false
```

| Slot/descritor | Digest declarado | SHA256(salt + image[:image_size]) calculado | Resultado |
| --- | --- | --- | --- |
| `a/boot` | `412abe70416021da640e0ac074a98ab2692827fdc9893f2da33a7c78688fb45e` | `cc7cacc10385bf32688975bc119b713e06030876695d01403498e56d6b9ab929` | MISMATCH |
| `a/dtbo` | `3cef1bea92e530404795198b3c2863fbb2e7980155fb2b8c953a6fd717da7ba2` | `21ff7f72a77ca0dfdd2f8d8e4a0d30da02e75ec54931c5fa7abcbcd481628e39` | MISMATCH |
| `a/vendor_boot` | `7c138a410bc3dba5f0f12ec681509d206dfd4616bce1c4eb60d413b95a4280d0` | `b9d8be2a47e0b55da5befdfcf510d407aa9dafb498a1f7c0acba8c5914d629a5` | MISMATCH |
| `b/boot` | `1972e2761419d05d2ea16e6cce1182c56719778a96a6cad4af75414ccb59b7c9` | `4cb56aa6325468bbe61bff76e0c010c866537974e30ec6bb7997a012ea9dda30` | MISMATCH |
| `b/dtbo` | `0ed695518dbb2885fe0e31da603dcca1ea03d12f3021e5af5ac11da3a4c99680` | `0ed695518dbb2885fe0e31da603dcca1ea03d12f3021e5af5ac11da3a4c99680` | MATCH |
| `b/vendor_boot` | `1c63f5ea5f39f7da98a7c0418deb8366acc4b98921b71f875c54134825746ea7` | `6df2ff862636a20d672586d7a86c529717b490ac61b6e94635a19e2153915311` | MISMATCH |

**Resultado:** `EXP21.8F_REAL_DESCRIPTOR_CROSSCHECK=PASS_REAL` com `MATCH=1` e `MISMATCH=5`. Pass significa auditoria completa e fontes verificadas, **não** significa seis hashes corretos. A coleta replica o padrão de B observado na EXP13.2, fornecendo segundo caminho de confirmação. O modo exato pelo qual o firmware usa `flags=3`, que desabilita verificação e hashtree em operações libavb conformes, **não** pode ser inferido sem avaliar regras do bootloader; o estado Android `green/locked` e fastboot `unlocked=yes` permanece contraditório. Sem comprovar assinatura do próprio VBMeta, cadeia OEM, política efetiva ou bootabilidade do slot A/EXP06.

**Próximo gate EXP21.8G:** verificar offline, via chave pública RSA **embutida** no respectivo VBMeta, (a) hash assinado do header e bloco auxiliar, (b) assinatura RSA-PKCS1-v1.5 SHA256_RSA4096, (c) fingerprints das chaves públicas A/B. Essa verificação **não** estabelece a confiança do OEM no bootloader nem conserta descritores divergentes. `FLASH_READY=false`.

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

**Testes materialmente rodados pelo assistente:** compilação Python `py_compile` PASS; `EXP21.8F SYNTHETIC SALTED-AVB-HASH SELFTEST: PASS` com parsing AVB sintético positivo (3 descritores), falhas de limite e descritores ausentes, e detecção de digest alterado; conteúdo e SHA-256 do ZIP verificados. **Teste real dos oito arquivos Windows do usuário não rodado**, porque os backups permanecem no computador dele. Não declarar `EXP21.8F_REAL=PASS_REAL` antes da saída do Windows.

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
