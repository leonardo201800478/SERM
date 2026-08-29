# SERM V2 — Arquitetura

## Princípio

V2 é a arquitetura ativa. V1 permanece no repositório como referência histórica e fonte de aprendizado, mas não é uma dependência de runtime, banco, configuração ou testes.

## Camadas

```text
GUI
 ↓
Application
 ↓
Domain
 ↓
Repositories / Services
 ↓
SQLite
```

Providers externos entram por adapters:

```text
No-Intro / Redump / MAME / FBNeo
RetroArch RDB
LaunchBox DB/XML
WHDLoad / Retroplay
exDOS
        ↓
Source Adapters
        ↓
V2 Catalog / Identity / Provenance
```

## Banco

SQLite será a fonte de verdade local para dados administrados pelo SERM. SQLAlchemy será usado para persistência e migrations versionadas.

O schema será criado do zero. Compatibilidade com o schema V1 não é requisito.

## Configuração

Configurações administradas pelo SERM vivem no banco. XML/CFG/JSON externos são formatos de interoperabilidade ou artefatos derivados.

## Home

A Home V2 é o primeiro ponto executável e não deve descobrir, carregar ou consultar qualquer serviço V1. Funcionalidades serão conectadas incrementalmente conforme cada domínio V2 ficar pronto.

## Legacy boundary

É proibido importar de `app.*` legado para `v2/serm_v2/*`.

A referência à V1 deve ocorrer somente em documentação, auditoria, fixtures de conhecimento ou ferramentas de análise explicitamente isoladas.
