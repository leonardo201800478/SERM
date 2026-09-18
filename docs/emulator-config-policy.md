# Política de configuração de emuladores

## Objetivo

Centralizar no SERM somente as configurações que o aplicativo consegue identificar, validar e manter com segurança.

## Princípios

1. A instalação do emulador é um recurso externo.
2. O SERM registra paths, versão e propriedades administradas pelo próprio SERM.
3. Configurações nativas desconhecidas devem ser preservadas.
4. Alterações devem ser reversíveis sempre que possível.
5. A GUI não deve editar diretamente arquivos de configuração quando um service puder encapsular a operação.

## Execution Profile

O profile de execução relaciona plataforma, runtime/emulador/core e opções necessárias para iniciar conteúdo.

```text
Platform
   ↓
Execution Profile
   ↓
Runtime / Emulator / Core
   ↓
Content
```

Arguments, BIOS, shaders, overlays e paths podem pertencer ao profile quando fizerem parte do contrato de execução.

## Segurança

Antes de alterar configuração externa:

- validar caminho;
- confirmar o executável esperado;
- evitar sobrescrita de arquivos desconhecidos;
- registrar a operação quando houver risco de alteração persistente.
