# EXP03 — compatibilidade estrutural do boot (SOMENTE LEITURA)

**Alvo:** Xiaomi Pad 6 (`pipa`), Android 16 / crDroid 16, boot slot `_b` nos backups anteriores.

## Evidência já disponível (EXP02)

- `boot_b.img`: Android Boot v3; partição 201326592 bytes; kernel embutido declarado 30349336 bytes; ramdisk genérico 1849345 bytes.
- `vendor_boot_b.img`: Vendor Boot v3; partição 100663296 bytes.
- `dtbo_b.img`: tabela DTBO detectada; partição 33554432 bytes.
- `vbmeta_b.img`: AVB metadata detectado; partição 131072 bytes.
- `Image` EXP01, compilada: 30349328 bytes; SHA256 `bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11`.
- Os kernels tem tamanhos que diferem em **8 bytes**. Não sabemos ainda se o binário original e a EXP01 são compatíveis. Não inferir equivalência com base em tamanho.

## Código implementado

`tools/exp03-boot-structure.ps1` abre somente leitura os quatro backups **locais**, sem rede e sem gravar nenhum arquivo. Para o layout v3, verifica:

1. `boot`: número de versão, header_size, limites e offsets do kernel e ramdisk genérico, magic ARM64 e tipo de compressão.
2. `vendor_boot`: tamanho de página, header_size, limites e offsets do ramdisk fornecedor e DTB e magic FDT.
3. `dtbo`: tabela big endian, tamanho da tabela, quantidade de entradas, intervalos de dados e magic FDT das entradas.
4. `vbmeta`: versão, tamanhos de blocos, identificador de algoritmo e flags. **Não verifica a assinatura AVB nem rollback.**

A execução só lê imagens; não produz `boot.img`, não grava partições nem envia backups.

## Testes automatizados

`.github/workflows/exp03-boot-structure.yml` executa no GitHub (Windows) testes com imagens sintéticas, cobrindo PowerShell 7 e **Windows PowerShell 5.1** e um teste negativo com DTBO corrompido.

A aprovação do CI prova o funcionamento com **amostras sintéticas**, não a compatibilidade com os backups reais.

## Próximo comando no Windows

1. Acesse pelo navegador autenticado a página `tools/exp03-boot-structure.ps1` no GitHub e clique em **Download raw file**.
2. Salve o arquivo em `C:\\platform-tools\\exp03-boot-structure.ps1`.
3. Revise o arquivo. No PowerShell, execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\\platform-tools\\exp03-boot-structure.ps1" -BackupDir "C:\\platform-tools\\pipa_backup"
```

4. Envie só a **saída textual**. Não envie os `.img` ao GitHub.
5. Se tiver tablet conectado por ADB, um comando complementar **somente leitura** para confirmar slot ativo:

```powershell
.\\adb -s 6665d3e6 shell getprop ro.boot.slot_suffix
```

## Bloqueios antes de qualquer imagem instalável

- Inspecionar estrutura interna real dos backups (saída EXP03).
- Confirmar que `boot_b` é da instalação crDroid atualmente ativa e identificar slot e origem.
- Validar DTB/DTBO, dependências e módulos vendor e assinatura/AVB.
- Comprovar integração do root e ter retorno realista de restauração (backups de slot B sozinhos não garantem recovery).
- Construir somente então um candidato `boot.img` para análise, com checagem de layout, integridade e riscos.

**EXP03 permanece NON_FLASHABLE.**
