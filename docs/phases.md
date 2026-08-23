# Roadmap do ARCADE MANAGER

**Estado de referência:** 23/08/2026

A evolução deixa de ser organizada apenas como um construtor de sets. O núcleo de ROMs permanece prioritário, mas passa a coexistir com execução, controles, FFB e gerenciamento de software.

## Fase 1 — Dataset e filtros

**Estado:** implementada em evolução.

- MAME/listxml;
- parser/modelos;
- SQLite/migrations;
- classificação;
- filtros;
- XML filtrado.

## Fase 2 — Scan físico

**Estado:** implementada em evolução.

- Scan ROMs;
- diagnóstico físico;
- estados de integridade;
- `current_scan.jsonl`;
- origem física.

## Fase 3 — Reconstrução

**Estado:** implementada estruturalmente; integração ainda em validação.

- Split;
- Merged;
- Non-Merged;
- streaming;
- staging;
- publicação atômica;
- residual;
- retry/recuperação.

## Fase 4 — Dependency Resolver

**Estado:** parcial/pendente.

- ROM;
- parent/clone;
- BIOS;
- device;
- sample;
- disk;
- CHD;
- compartilhamentos.

## Fase 5 — Plataforma de emuladores

**Estado:** arquitetura iniciada.

Consolidar:

- MAME;
- Flycast;
- FBNeo;
- Supermodel;
- runtime discovery;
- capabilities;
- configuração segura;
- backends de execução.

## Fase 6 — RetroArch

**Estado:** planejada.

- RetroArch runtime;
- core manager;
- MAME core;
- FBNeo core;
- Flycast core;
- detecção de versões;
- seleção de core;
- system/assets/shaders/saves/states;
- execução integrada ao catálogo.

## Fase 7 — Plugin Manager / FFB

**Estado:** planejada.

- arquitetura genérica de plugins;
- instalação/remoção;
- compatibilidade;
- configuração;
- integração FFBArcadePlugin;
- perfis FFB por família/jogo;
- preparação automática do runtime.

## Fase 8 — Controles

**Estado:** planejada.

- descoberta de dispositivos;
- Control Profiles;
- Control Families;
- mappings;
- overrides por jogo;
- aplicação em lote;
- MAME per-game/per-family configuration;
- Flycast/FBNeo/Supermodel/RetroArch.

Objetivo especial:

```text
configurar 1 jogo
      ↓
criar perfil
      ↓
aplicar à família
      ↓
validar conflitos
      ↓
gerar configurações dos backends
```

## Fase 9 — Hardware arcade

**Estado:** planejada.

- Hardware Profiles;
- Arcade Hardware Profiles;
- G27;
- volante;
- pedais;
- clutch;
- câmbio H-pattern;
- rotação original;
- ranges analógicos;
- controles especiais.

Casos de alta complexidade, como Hard Drivin', devem ser suportados por perfis avançados de hardware/mapeamento.

## Fase 10 — Download Manager

**Estado:** planejada.

Criar gerenciador genérico com providers.

Primeiro provider: RetroArch.

Funções:

- catálogo de versões;
- seleção de arquitetura;
- download;
- progresso;
- validação de tamanho/hash;
- staging;
- instalação;
- backup;
- atualização;
- rollback quando possível.

A arquitetura conceitual será estudada a partir do StellarUpdater/Stellar.

## Fase 11 — Aquisição / Torrent

**Estado:** futura.

- qBittorrent;
- metadata/infohash;
- matching;
- download seletivo;
- residual → aquisição → Scan/reconstrução.

## Fase 12 — Qualidade e integração

**Estado:** contínua.

- testes unitários;
- testes de integração;
- fixtures parent/clone;
- testes de interrupção;
- testes de arquivos grandes;
- validação de mappings;
- testes com dispositivos físicos quando possível;
- testes de FFB;
- testes de instalação/rollback;
- medição de I/O, CPU e memória.

## Ordem de implementação recomendada

1. Fechar Reconstrução.
2. Fechar Dependency Resolver.
3. Consolidar domínio de emuladores/backends.
4. Adicionar RetroArch.
5. Criar Plugin Manager.
6. Integrar FFBArcadePlugin.
7. Criar domínio de controles.
8. Criar famílias e aplicação em lote.
9. Criar Hardware Profiles/Arcade Hardware Profiles.
10. Integrar volante/G27 e FFB avançado.
11. Criar Download Manager.
12. Implementar Torrent/qBittorrent.

## Regra de conclusão

Uma fase só é considerada concluída quando o fluxo real correspondente estiver implementado e testado. Modelos, placeholders, telas vazias ou documentação não equivalem à funcionalidade concluída.
