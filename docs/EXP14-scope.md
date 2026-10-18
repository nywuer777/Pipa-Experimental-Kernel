# EXP14 — Escopo seguro

Auditar o boot v3 original em modo somente leitura, conferindo segmentos do header, kernel, padding, ramdisk genérica e restante da partição, sem criar uma nova imagem e sem comandos de flash. A reprodução é comprovada por um hash calculado sobre os segmentos na ordem original e confrontado com o SHA-256 do backup intacto. Validar primeiro com fixtures sintéticas, depois executar a conferência nos backups originais do Windows. Estado: FLASH_READY=false.
