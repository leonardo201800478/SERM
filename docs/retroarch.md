# RetroArch no SERM

**Produto:** Strife Emulator and Roms Manager (SERM)
**Estado:** Home concluída e validada em fluxo real.
**Referência:** 29/08/2026

## Runtime

RetroArch é um runtime. Cores Libretro são módulos independentes executados por ele.

```text
RetroArch
├── MAME core
├── FBNeo core
├── Flycast core
└── outros cores futuros
```

O catálogo de conteúdo não deve ser duplicado apenas porque existe execução standalone e via RetroArch.

## Home — estado concluído

A Home de RetroArch possui:

- instalação/atualização do runtime;
- seleção Stable/Nightly;
- descoberta de versões;
- download para staging;
- extração com 7-Zip externo quando disponível;
- fallback `py7zr`;
- validação do executável;
- atualização de cores pelo índice oficial;
- comparação CRC local × índice;
- seleção automática somente dos cores desatualizados;
- retry de até três tentativas por core;
- continuidade para o próximo core após falha;
- estado READY após conclusão/falha;
- log operacional.

A Home não deve receber novos botões sem funcionalidade real.

## Core Manager

O índice oficial de cores é consultado quando necessário. A comparação deve distinguir:

```text
instalado + CRC igual       → atualizado
instalado + CRC divergente  → atualização disponível
não instalado + índice      → novo
instalado sem correspondência → sem correspondência
```

Falha de um core não deve cancelar a fila inteira. O log deve identificar claramente o core e o número da tentativa.

## Diretórios

O runtime pode utilizar:

- executável;
- cores;
- system;
- assets;
- shaders;
- saves;
- states;
- downloads.

## BIOS

BIOS de RetroArch é uma próxima área da reconstrução, separada dos DATs No-Intro e Redump.

Fluxo planejado:

```text
.info / fonte confiável
 ↓
catalogação
 ↓
scan/hash
 ↓
OK / renomeável / movível / reconstruível / MISSING
 ↓
reconstrução/instalação
```

O objetivo é ser rápido e limpo, processando apenas o que realmente precisa de intervenção.

## Shaders e apresentação

RetroArch deve usar seu mecanismo nativo de shaders.

Arquitetura por sistema:

```text
Sistema
├── Core
├── Override
├── Shader
└── Overlay
```

Shaders de terceiros não são incorporados ao repositório do SERM. O projeto armazena metadados e baixa o conteúdo diretamente do repositório de origem quando necessário.

Prioridade visual:

1. CRT limpo e fiel;
2. baixo custo de processamento;
3. compatibilidade por renderer;
4. ausência de efeitos agressivos.

Shaders/presets com reflexos de borda ou overlays pesados não devem ser padrões.

Aspect ratio representa o sistema/emulação. Não forçar 16:9 apenas porque a tela do usuário possui 16:9.

## Configuração

Não sobrescrever `retroarch.cfg` válido apenas para registrar estado no SERM. Alterar somente propriedades conhecidas e suportadas, preservando o restante.

## Próximas etapas

1. finalizar infraestrutura Catalog Manager;
2. No-Intro;
3. Redump;
4. Amiga/Retroplay;
5. BIOS;
6. shaders/overrides/overlays por sistema;
7. integração com execução completa.
