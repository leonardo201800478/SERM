# Controles e hardware

O SERM trata dispositivos de entrada como recursos de hardware externos e mantém a configuração necessária para perfis de execução quando suportado.

## Escopo

- identificação de dispositivos;
- associação a sistemas/emuladores;
- profiles de controle;
- configuração específica de runtime quando o backend permitir.

## Princípios

A camada de controle não deve conhecer regras de catálogo ou scan. Configuração persistente deve passar pelo modelo de configuração V2.

## Compatibilidade

Dispositivos e APIs podem variar por sistema operacional e emulador. O SERM deve detectar capacidades disponíveis e degradar de forma segura quando uma integração não estiver presente.
