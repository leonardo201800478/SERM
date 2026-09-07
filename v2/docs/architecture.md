# Arquitetura do SERM V2

## 1. Objetivo

O SERM V2 é organizado para separar apresentação, regras de negócio, persistência, aquisição de dados externos, análise do filesystem e execução de ferramentas externas.

A regra central é simples: **a GUI coordena a interação; serviços e componentes de domínio executam o trabalho.**

## 2. Camadas

```text
┌──────────────────────────────────────────────┐
│ GUI / PySide6                                │
│ Home · Emulators · Filters · Scan · Rebuild │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│ Services / Application workflows             │
│ catalog · scan · emulator · reconstruction   │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│ Domain / Contracts / Adapters                 │
│ identities · sources · catalog models         │
└───────────────┬──────────────────┬─────────────┘
                ↓                  ↓
        ┌──────────────┐   ┌──────────────────┐
        │ SQLite       │   │ Filesystem/tools │
        │ SQLAlchemy   │   │ MAME · 7z · etc. │
        └──────────────┘   └──────────────────┘
```

## 3. Pacote `serm_v2`

| Pacote | Responsabilidade |
|---|---|
| `gui` | Janelas, páginas, diálogos e apresentação |
| `services` | Orquestração e regras de aplicação |
| `database` | Engine, bootstrap, modelos e migrations |
| `sources` | Contratos, routing e aquisição de fontes |
| `catalog` | Namespace para o domínio de catálogos |
| `emulation` | Integrações específicas de emulação, incluindo MAME |
| `runtime` | Paths e ferramentas do ambiente |
| `integrations` | Providers externos, como LaunchBox |
| `reconstruction` | Namespace do domínio de reconstrução |
| `library` | Namespace da biblioteca física/lógica |
| `tools` | Utilitários de auditoria e manutenção |

## 4. Persistência

SQLite é a persistência local principal. SQLAlchemy fornece a camada ORM/engine e as migrations versionadas definem a evolução do schema.

O banco contém metadados, configurações, catálogo normalizado, relações, estado de scan e informações necessárias aos workflows. Não deve armazenar cópias dos arquivos físicos.

## 5. Source → Catalog → Identity → File

Uma fonte externa pode fornecer XML, DAT, JSON, banco de dados ou outro formato. O adapter converte essa representação para o modelo canônico do SERM.

```text
External Source
      ↓ adapter
Catalog Version
      ↓ normalization
Canonical Entry / Identity
      ↓ matching
Physical File / Hash
```

Uma fonte pode ser authoritative para determinado domínio sem ser authoritative para todos os demais domínios.

## 6. Scan

O scanner é um serviço independente da GUI. O pipeline conceitual é:

```text
Catalog
  ↓
Scan settings / filters
  ↓
Filesystem discovery
  ↓
File metadata + hashes
  ↓
Identity matching
  ↓
Scan result / persistence
  ↓
Reconstruction candidates
```

O scan deve produzir evidência reprocessável. Checkpoints, cache e JSONL são mecanismos operacionais; a GUI não deve implementar essas regras.

## 7. MAME

MAME ListXML é ingerido e normalizado para o banco V2. Serviços específicos tratam classificação, filtros fundamentais, resolução, VSync, CHDs, auditoria e configuração.

O `mame.exe -listxml` é tratado como fonte factual para o catálogo MAME que está sendo ingerido. Dados externos podem complementar o catálogo, mas não devem substituir silenciosamente os campos provenientes do ListXML.

## 8. Reconstrução

Reconstrução é posterior ao scan e trabalha sobre evidências e dependências conhecidas.

```text
Scan result
    ↓
Dependency resolution
    ↓
Candidate selection
    ↓
Staging
    ↓
Transformation
    ↓
Validation
    ↓
Atomic publication
```

As origens são somente leitura. A publicação ocorre em destino controlado pelo usuário.

## 9. Emulação e execução

Emulador, backend/runtime, core e plataforma são entidades distintas. Um `ExecutionProfile` deve representar a combinação necessária para executar determinado conteúdo sem transformar configurações nativas do emulador em metadados canônicos do SERM.

## 10. Integrações externas

LaunchBox e outros providers podem fornecer metadata, IDs, relações ou dados auxiliares. A integração deve permanecer desacoplada: o SERM mantém sua identidade, schema e ciclo de vida próprios.

## 11. Segurança operacional

Workflows que manipulam arquivos devem:

- tratar caminhos externos como não confiáveis;
- impedir path traversal;
- usar staging para operações destrutivas ou transformadoras;
- validar hashes antes da publicação quando houver referência disponível;
- evitar publicar arquivos parciais;
- não executar conteúdo baixado apenas para validá-lo;
- registrar falhas de forma reproduzível.

## 12. Testabilidade

Serviços devem ser testáveis sem GUI sempre que possível. Testes de integração cobrem banco, filesystem, fontes e ferramentas externas quando necessários. A suíte V2 em `tests/` é parte do contrato de manutenção.

## 13. V1

V1 não participa da arquitetura de execução da V2. Seu código pode ser consultado para entender comportamento histórico, mas qualquer implementação reaproveitada deve ser reescrita contra os contratos V2.
