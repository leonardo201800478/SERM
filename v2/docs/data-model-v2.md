# SERM V2 — Modelo Conceitual de Dados

**Status:** aprovado para detalhamento SQL, ainda sem schema físico.  
**Data:** 29/08/2026

## 1. Regra de projeto

O banco V2 será desenhado do zero. Não haverá compatibilidade estrutural obrigatória com o banco V1.

V1 é somente referência histórica, fonte de aprendizado, comparação e eventual origem de fixtures. Nenhuma entidade V2 deve importar models ou serviços V1.

## 2. Princípio de identidade

O SERM deve distinguir quatro conceitos:

```text
SOURCE
  quem publicou/forneceu o dado

CATALOG
  qual conjunto/edição da fonte descreve o conteúdo

IDENTITY
  qual entidade lógica o item representa

FILE
  qual artefato físico existe no filesystem
```

Relação conceitual:

```text
Source
  ↓
SourceVersion
  ↓
Catalog
  ↓
CatalogEntry
  ↓
SourceIdentity
  ↕
CanonicalIdentity
  ↓
Release
  ↓
File / Hash
```

## 3. Source

Representa um fornecedor/provedor de dados ou conteúdo.

Exemplos:

- No-Intro;
- Redump;
- MAME;
- FBNeo;
- RetroArch;
- LaunchBox;
- WHDLoad/Retroplay;
- eXoDOS.

Campos conceituais:

- id;
- slug;
- nome;
- tipo;
- autoridade;
- descrição;
- URL de referência, quando houver;
- ativo;
- timestamps.

`authority` não deve ser usado para apagar outras fontes; serve para resolução de conflitos.

## 4. SourceVersion

Representa uma versão identificável da fonte.

Deve registrar, quando disponível:

- versão;
- data;
- identificador externo;
- checksum do arquivo fonte;
- URL/origem;
- parser/schema utilizado;
- estado de validação;
- data de importação.

Uma versão nova não substitui fisicamente a anterior até ser validada.

## 5. Catalog e CatalogEntry

`Catalog` representa a família de catálogo dentro de uma fonte. `CatalogEntry` representa um registro individual.

Exemplos:

```text
No-Intro / Mega Drive
No-Intro / NES
Redump / PlayStation
MAME / machines
RetroArch / database
LaunchBox / games
```

A entrada deve preservar o identificador original da fonte.

## 6. CanonicalIdentity

É a identidade interna do SERM.

Ela não pertence a No-Intro, Redump, LaunchBox ou qualquer outro provider.

Uma identidade pode possuir várias identidades de fonte:

```text
CanonicalIdentity
├── No-Intro identity
├── LaunchBox identity
├── RetroArch identity
├── WHDLoad identity
└── eXoDOS identity
```

O mesmo conceito deve funcionar para jogos, software, máquinas arcade e outros conteúdos catalogáveis sem forçar todas as fontes a terem o mesmo schema semântico.

## 7. Release

`Release` representa uma publicação/edição concreta de uma identidade para determinada plataforma/sistema e contexto.

Exemplo:

```text
Doom
├── DOS release
├── PlayStation release
└── Saturn release
```

A release pode possuir região, idioma, versão, serial, revisão e outros atributos relevantes à fonte.

## 8. Names

Não usar uma única coluna `name` para todos os usos.

Quando aplicável, distinguir:

```text
source_name
canonical_name
display_name
scraper_name
filename
normalized_name
```

O nome original nunca deve ser destruído durante uma transformação.

## 9. Platform e System

`Platform` representa a plataforma/sistema alvo catalogado pelo SERM.

`System` representa uma classificação técnica quando for útil separar hardware/plataforma de famílias ou arquiteturas.

Exemplo conceitual:

```text
Platform
  └── Sega Saturn

System metadata
  ├── fabricante
  ├── CPU
  ├── memória
  ├── vídeo
  ├── áudio
  └── mídia
```

A taxonomia final será definida antes do schema SQL.

## 10. File

Representa um artefato físico conhecido pelo SERM.

Deve registrar, conforme necessário:

- caminho lógico/normalizado;
- nome;
- extensão;
- tamanho;
- tipo de conteúdo;
- archive/container;
- timestamps controlados;
- estado de disponibilidade.

O caminho absoluto não deve ser usado como identidade global do arquivo.

## 11. FileHash

Relação entre arquivo e algoritmo/hash.

Exemplo:

```text
File
├── SHA1
├── MD5
├── CRC32
└── SHA256
```

A estrutura deve permitir múltiplos hashes sem adicionar colunas infinitamente.

## 12. Archive

Arquivo contêiner é diferente de seu conteúdo.

```text
Archive
└── ArchiveMember
      └── File identity / observed member
```

Isso permite trabalhar com ZIP/7Z/LHA e outras representações sem confundir pacote com jogo.

## 13. Disc

Discos devem ter modelo próprio quando a fonte fornecer estrutura de trilhas.

```text
Release
└── Disc
     ├── Track
     ├── Track hash
     └── Disc metadata
```

Isso atende Redump e futuras reconstruções CHD sem forçar dados de disco dentro do modelo de ROM de cartucho.

## 14. BIOS

BIOS deve ser entidade própria porque pode ser compartilhada por várias plataformas/releases e possui matching por hashes.

```text
BIOS
├── identidade
├── arquivos
├── hashes
└── plataformas compatíveis
```

## 15. Runtime / Emulator / Core

```text
Runtime
  └── Emulator / Backend
        └── Core (quando aplicável)
```

Exemplo:

```text
RetroArch
  └── Libretro
       └── Mesen
```

Um backend standalone pode não possuir Core.

## 16. ExecutionProfile

Representa como uma release/plataforma deve ser executada.

Pode relacionar:

- plataforma;
- runtime;
- emulator/backend;
- core;
- extensões;
- argumentos;
- BIOS;
- shader;
- overlay;
- input profile;
- working directory;
- regras específicas.

A configuração externa não é a fonte de verdade.

## 17. Path

Paths devem ser entidades/configuração independente do código.

Categorias previstas:

```text
application
user_data
database
catalog
cache
scan
staging
content
runtime
logs
export
backup
```

O SERM deve trabalhar com caminhos relativos/identificadores internos e resolver o caminho físico pelo `PathManager`.

## 18. Source Mapping

Relaciona uma entrada de fonte a uma identidade/release canônica.

```text
SourceEntry
     ↕
SourceMapping
     ↕
CanonicalIdentity / Release
```

Campos conceituais:

- tipo de mapping;
- confiança;
- evidência;
- regra;
- origem da resolução;
- versão da fonte;
- data;
- estado.

## 19. Scan

Scan é observação do filesystem em determinado momento, não alteração da identidade catalogada.

```text
ScanRun
└── ScanFile
      ├── observed path
      ├── size
      ├── hashes
      └── matches
```

`ScanMatch` registra a hipótese/resultado de correspondência com catálogo/identidade.

## 20. Transformation

Transformação registra uma operação realizada sobre conteúdo.

```text
TransformationJob
├── input
├── rule
├── output
├── hashes before
├── hashes after
└── result
```

Exemplos:

- rename;
- move;
- extract;
- repack;
- merge;
- split;
- reconstruct;
- convert.

## 21. Regras de normalização

Não normalizar tudo para uma única semântica.

Cada provider primeiro preserva sua representação e depois fornece um normalizador que produz os campos comuns.

```text
Provider parser
     ↓
Provider model
     ↓
Normalizer
     ↓
Common domain
```

## 22. Integridade

O schema físico deverá usar:

- foreign keys;
- unique constraints onde a regra de negócio exigir;
- índices para consultas reais;
- checks para estados inválidos;
- timestamps consistentes;
- transações atômicas.

SQLite deverá operar com foreign keys habilitadas.

## 23. O que fica fora do modelo comum

Não devem ser generalizados à força:

- parent/clone MAME como regra universal;
- tracks Redump como atributos de uma ROM;
- WHDLoad como cartucho;
- eXoDOS como simples ROM;
- RetroArch RDB como catálogo de preservação;
- LaunchBox como autoridade física.

Cada domínio conserva sua semântica.

## 24. Próximo documento

Este documento define o modelo conceitual. O próximo passo é transformar estas entidades em um **Data Model V2 detalhado**, com cardinalidades, chaves, estados, índices e regras de integridade. Só depois será escrito o schema SQLite/Alembic.
