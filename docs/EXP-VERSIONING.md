# Identidade e numeração do kernel EXP

**Nome do projeto:** EXP  
**Versão de desenvolvimento atual:** **EXP25A** — compilada no CI, teste de boot e touchscreen pendentes  
**Última versão com inicialização temporária comprovada no tablet:** **EXP24**  
**Canal:** experimental — não homologado para instalação persistente.

## Política de versões

- **EXP24**: base testada em `fastboot boot` temporário, Clang21, driver Ethernet Realtek `r8152` funcional quando o USB enumera, porém hotplug intermitente e touchscreen sem resposta.
- **EXP25A**: correção *isolada* e instrumentada da restauração da IRQ do Novatek NT36532 ao acordar a tela; CI aprovado na execução #39190015939; boot e touch ainda precisam ser validados. O firmware CSOT não foi modificado.
- **EXP25B**: reservado para experimento isolado no caminho de retorno/recovery do firmware Novatek **somente após obter os logs de EXP25A**. Não presumir solução nem release.
- **EXP26+**: evolução orientada por evidências, com estabilidade USB-C/RTL8153, touchscreen e desempenho medido. Números ainda não são releases aprovadas.

## Nome, fonte e compatibilidade

O nome e a numeração oficiais passam a ser **EXP** e **EXP25A**. O E404 deixa de identificar o produto; é registrado exclusivamente como **proveniência da árvore de origem** e referência de compatibilidade/reprodutibilidade, pois o pipeline de build ainda baixa `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`. O repositório ainda **não** contém uma árvore kernel totalmente autônoma: por isso, não alegar migração integral até que o código-fonte versionado próprio, licenças, histórico de patches, workflows e builds reprodutíveis estejam estabelecidos.

A versão da linha Linux `4.19.404R` em `uname -r` é **diferente** da versão do produto EXP. Não falsificar/remover a identificação ABI 4.19 só por mudança de marca. Qualquer sufixo `LOCALVERSION=-EXP25A` deve ser testado e inspecionado separadamente para evitar incompatibilidade de módulos. Não mudar `uname` nesta fase.

## Critérios de liberação

1. Compilar um `Image` ARM64 com toolchain fixo Clang21 e verificar preservação de configuração (KernelSU, governor, Ethernet, touch).
2. Embalar candidato temporário usando o mesmo método validado para EXP24, auditando imagem e DTB/DTBO. Não usar flash nesta fase.
3. Testar exclusivamente com `fastboot boot` reversível, quando houver plano de recuperação e usuário autorizar reboot. Preservar hub/mouse, pois a tela touch está inoperante.
4. Verificar inicialização, USB e Ethernet, touch Novatek (`/proc/interrupts`, `getevent`), suspender/acordar e estabilidade prolongada.
5. Não promover para versão estável sem evidência. **`FLASH_READY=false`**.

Ver [Touchscreen no slot B](EXP24-TOUCH-SLOT-B.md) e [USB Ethernet e Type-C](EXP24-ETHERNET.md).

**Build EXP25A aprovado:** [handoff, SHA-256 e gates](EXP25A-CI-HANDOFF.md).