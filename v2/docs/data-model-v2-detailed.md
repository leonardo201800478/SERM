# SERM V2 — Data Model Detalhado

**Status:** especificação para implementação da primeira migration.  
**Escopo:** modelo relacional SQLite + SQLAlchemy 2.x.  
**Regra:** este documento é o contrato entre o domínio e o schema físico; nenhuma tabela deve ser criada fora destas regras sem atualização desta especificação.

## 1. Princípios físicos

- SQLite é o banco local de referência do SERM.
- Foreign keys devem permanecer habilitadas em toda conexão.
- IDs internos são inteiros autoincrementais quando a entidade não possui uma chave natural estável.
- Identificadores externos de providers são armazenados separadamente e nunca substituem a identidade interna.
- Textos de origem são preservados; normalização produz campos adicionais.
- Datas armazenadas em UTC e representadas como valores temporais consistentes.
- Booleanos são armazenados como INTEGER/BOOLEAN conforme suporte do SQLAlchemy/SQLite.
- Constraints e índices recebem nomes explícitos.
- Não haverá JSON genérico como substituto de relações que precisam ser consultadas.
- JSON poderá ser usado para payload original ou metadados específicos quando uma estrutura relacional não for necessária.
- Arquivos físicos não são armazenados no banco.

A abordagem usa o estilo declarativo moderno do SQLAlchemy 2.x, com `DeclarativeBase`/`Mapped`/`mapped_column`, e constraints e índices declarados no metadata. A documentação atual do SQLAlchemy 2.0 recomenda o estilo declarativo como o padrão de mapeamento ORM. citeturn0search2turn0search4

## 2. Convenções de nomes

Tabelas: `snake_case`, plural.

Colunas PK: `id`.

FK: `<entidade>_id`.

Datas: `created_at`, `updated_at`, `imported_at`, `observed_at` conforme significado.

Identificadores externos: `external_id`.

Slugs: `slug`.

Hashes: `algorithm`, `value`.

Constraints:

```text
pk_<table>
uq_<table>_<columns>
ix_<table>_<columns>
ck_<table>_<name>
```

## 3. Auditoria comum

Não criar uma tabela de auditoria genérica nesta primeira versão.

Entidades mutáveis relevantes possuem:

- `created_at` NOT NULL;
- `updated_at` NOT NULL.

Histórico de importação, scan e transformação será preservado nas entidades próprias. Isso evita duplicar um sistema de auditoria genérico difícil de consultar.

---

# 4. Núcleo de fontes

## 4.1 `sources`

Representa um provider de dados/conteúdo.

| Coluna | Tipo | Null | Regra |
|---|---|---:|---|
| id | INTEGER | não | PK |
| slug | TEXT | não | UNIQUE |
| name | TEXT | não | UNIQUE |
| source_type | TEXT | não | CHECK |
| authority_level | INTEGER | não | 0..100 |
| description | TEXT | sim | |
| homepage_url | TEXT | sim | |
| active | BOOLEAN | não | default true |
| created_at | DATETIME | não | |
| updated_at | DATETIME | não | |

`source_type` inicial:

```text
preservation
metadata
emulator
convenience
community
user
```

Não usar `authority_level` como verdade absoluta; ele participa da resolução de conflitos.

## 4.2 `source_versions`

Representa uma versão concreta de uma fonte.

| Coluna | Tipo | Null | Regra |
|---|---|---:|---|
| id | INTEGER | não | PK |
| source_id | INTEGER | não | FK sources |
| version | TEXT | sim | |
| external_id | TEXT | sim | identificador da publicação |
| source_date | DATETIME | sim | data declarada pela fonte |
| retrieved_at | DATETIME | não | |
| source_url | TEXT | sim | |
| content_hash | TEXT | sim | hash do artefato fonte |
| parser_key | TEXT | sim | parser utilizado |
| parser_version | TEXT | sim | versão do parser |
| status | TEXT | não | CHECK |
| created_at | DATETIME | não | |

UNIQUE recomendado: `(source_id, external_id)` quando `external_id` existir. Para versões sem identificador externo, permitir múltiplas capturas, diferenciadas por hash.

Status:

```text
imported
validated
superseded
failed
```

## 4.3 `catalogs`

Representa uma coleção lógica dentro de uma fonte.

| Coluna | Tipo | Null | Regra |
|---|---|---:|---|
| id | INTEGER | não | PK |
| source_id | INTEGER | não | FK |
| slug | TEXT | não | |
| name | TEXT | não | |
| description | TEXT | sim | |
| catalog_type | TEXT | não | CHECK |
| created_at | DATETIME | não | |
| updated_at | DATETIME | não | |

UNIQUE `(source_id, slug)`.

Exemplos: `no-intro/nes`, `redump/playstation`, `mame/machines`, `retroarch/nes`.

## 4.4 `catalog_versions`

Liga um catálogo a uma versão específica da fonte.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| catalog_id | INTEGER | não |
| source_version_id | INTEGER | não |
| entry_count | INTEGER | não |
| imported_at | DATETIME | não |
| status | TEXT | não |

UNIQUE `(catalog_id, source_version_id)`.

## 4.5 `catalog_entries`

Registro bruto normalizado de uma fonte.

| Coluna | Tipo | Null | Regra |
|---|---|---:|---|
| id | INTEGER | não | PK |
| catalog_version_id | INTEGER | não | FK |
| external_id | TEXT | sim | ID do provider |
| source_name | TEXT | sim | nome original |
| normalized_name | TEXT | sim | normalização do provider |
| payload_json | TEXT | sim | dados não generalizados |
| status | TEXT | não | CHECK |
| created_at | DATETIME | não | |

UNIQUE `(catalog_version_id, external_id)` quando aplicável.

`payload_json` não deve ser usado para campos que o SERM precisa pesquisar ou relacionar frequentemente.

---

# 5. Identidade

## 5.1 `canonical_identities`

É a identidade interna e independente de provider.

| Coluna | Tipo | Null | Regra |
|---|---|---:|---|
| id | INTEGER | não | PK |
| identity_type | TEXT | não | CHECK |
| canonical_name | TEXT | não | |
| normalized_name | TEXT | não | |
| description | TEXT | sim | |
| created_at | DATETIME | não | |
| updated_at | DATETIME | não | |

`identity_type` inicial:

```text
game
software
machine
application
utility
other
```

Não associar plataforma diretamente à identidade se a mesma obra puder ter releases em plataformas distintas.

## 5.2 `source_identities`

Representa a identidade que uma fonte atribui ao conteúdo.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| source_id | INTEGER | não |
| catalog_entry_id | INTEGER | não |
| external_id | TEXT | sim |
| source_name | TEXT | não |
| normalized_name | TEXT | não |
| canonical_identity_id | INTEGER | sim |
| confidence | REAL | sim |
| resolution_status | TEXT | não |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

UNIQUE `(source_id, catalog_entry_id)`.

`canonical_identity_id` pode ser NULL enquanto o matching não estiver resolvido.

`resolution_status`:

```text
unresolved
matched
ambiguous
rejected
manual
```

## 5.3 `releases`

Representa uma publicação/edição concreta da identidade.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| canonical_identity_id | INTEGER | não |
| platform_id | INTEGER | não |
| release_name | TEXT | sim |
| normalized_name | TEXT | sim |
| region | TEXT | sim |
| languages | TEXT | sim |
| version | TEXT | sim |
| revision | TEXT | sim |
| serial | TEXT | sim |
| release_date | DATE | sim |
| release_type | TEXT | sim |
| parent_release_id | INTEGER | sim |
| metadata_json | TEXT | sim |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

`parent_release_id` é opcional e **não significa parent/clone universal**. Só deve ser usado quando a relação de release for semanticamente válida.

UNIQUE recomendado: `(canonical_identity_id, platform_id, region, version, revision, serial)` usando normalização explícita antes da persistência.

---

# 6. Nomes

## 6.1 `identity_names`

Não sobrescrever nomes.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| canonical_identity_id | INTEGER | não |
| name_type | TEXT | não |
| value | TEXT | não |
| language | TEXT | sim |
| region | TEXT | sim |
| source_id | INTEGER | sim |
| normalized_value | TEXT | não |

`name_type`:

```text
canonical
display
alternate
localized
scraper
source
```

UNIQUE `(canonical_identity_id, name_type, value, language, region, source_id)`.

---

# 7. Plataformas e sistemas

## 7.1 `platforms`

Representa o alvo de execução/catalogação.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| manufacturer | TEXT | sim |
| release_date | DATE | sim |
| category | TEXT | não |
| media_type | TEXT | sim |
| cpu | TEXT | sim |
| memory | TEXT | sim |
| graphics | TEXT | sim |
| sound | TEXT | sim |
| display | TEXT | sim |
| max_controllers | INTEGER | sim |
| notes | TEXT | sim |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

UNIQUE `slug` e `name`.

## 7.2 `platform_aliases`

| Coluna | Tipo | Null |
|---|---|---:|
| platform_id | INTEGER | não |
| alias | TEXT | não |
| source_id | INTEGER | sim |

PK `(platform_id, alias)`.

Essa tabela absorve os múltiplos nomes encontrados em LaunchBox, RetroArch, No-Intro etc.

## 7.3 `systems`

Opcionalmente classifica famílias técnicas.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| description | TEXT | sim |

## 7.4 `platform_systems`

Tabela de relação N:N entre plataforma e família técnica.

PK `(platform_id, system_id)`.

---

# 8. Arquivos e hashes

## 8.1 `files`

Representa um arquivo observado/conhecido, sem assumir que o caminho seja identidade.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| file_name | TEXT | não |
| extension | TEXT | sim |
| size_bytes | INTEGER | não |
| media_type | TEXT | sim |
| relative_path | TEXT | sim |
| availability_status | TEXT | não |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

Não armazenar caminho absoluto como chave.

Status:

```text
available
missing
unverified
invalid
```

## 8.2 `file_hashes`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| file_id | INTEGER | não |
| algorithm | TEXT | não |
| value | TEXT | não |
| source | TEXT | sim |
| computed_at | DATETIME | não |

UNIQUE `(file_id, algorithm)` e índice `(algorithm, value)`.

Algoritmos iniciais:

```text
crc32
md5
sha1
sha256
```

Não calcular todos os hashes obrigatoriamente em todo scan; o scanner deve respeitar a necessidade da operação.

## 8.3 `release_files`

Relaciona releases com arquivos.

| Coluna | Tipo | Null |
|---|---|---:|
| release_id | INTEGER | não |
| file_id | INTEGER | não |
| role | TEXT | não |
| required | BOOLEAN | não |
| ordinal | INTEGER | sim |

PK `(release_id, file_id, role)`.

Roles iniciais:

```text
rom
bios
disc
disk
archive
support
metadata
```

---

# 9. Arquivos compactados

## 9.1 `archives`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| file_id | INTEGER | não |
| format | TEXT | não |
| member_count | INTEGER | não |
| verified | BOOLEAN | não |

UNIQUE `file_id`.

## 9.2 `archive_members`

| Coluna | Tipo | Null |
|---|---|---:|
| archive_id | INTEGER | não |
| member_name | TEXT | não |
| size_bytes | INTEGER | não |
| crc32 | TEXT | sim |
| file_id | INTEGER | sim |
| ordinal | INTEGER | sim |

PK `(archive_id, member_name)`.

Isso permite representar:

```text
foo.zip
 ├── foo.bin
 ├── foo.cfg
 └── readme.txt
```

sem tratar o ZIP como se fosse o conteúdo lógico.

---

# 10. Discos e trilhas

## 10.1 `discs`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| release_id | INTEGER | não |
| disc_number | INTEGER | não |
| disc_type | TEXT | sim |
| serial | TEXT | sim |
| size_bytes | INTEGER | sim |
| metadata_json | TEXT | sim |

UNIQUE `(release_id, disc_number)`.

## 10.2 `disc_tracks`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| disc_id | INTEGER | não |
| track_number | INTEGER | não |
| track_type | TEXT | não |
| sector_size | INTEGER | sim |
| sector_count | INTEGER | sim |
| file_id | INTEGER | sim |

UNIQUE `(disc_id, track_number)`.

## 10.3 `disc_track_hashes`

| Coluna | Tipo | Null |
|---|---|---:|
| track_id | INTEGER | não |
| algorithm | TEXT | não |
| value | TEXT | não |

PK `(track_id, algorithm)`.

Esse modelo suporta fontes como Redump sem reduzir uma mídia óptica a um único arquivo/hash.

---

# 11. BIOS

## 11.1 `bios_sets`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| description | TEXT | sim |
| created_at | DATETIME | não |

## 11.2 `bios_files`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| bios_set_id | INTEGER | não |
| file_id | INTEGER | não |
| required | BOOLEAN | não |
| role | TEXT | sim |

## 11.3 `platform_bios_sets`

PK `(platform_id, bios_set_id)`.

Permite que uma BIOS seja reutilizada por múltiplas plataformas sem duplicação.

---

# 12. Runtime e emulação

## 12.1 `runtimes`

Representa o ambiente de execução.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| runtime_type | TEXT | não |
| version | TEXT | sim |
| executable_name | TEXT | sim |
| homepage_url | TEXT | sim |
| installed_path | TEXT | sim |
| active | BOOLEAN | não |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

Tipos:

```text
standalone
frontend
libretro_host
compatibility_layer
other
```

## 12.2 `emulators`

Um runtime pode expor um ou mais backends/emuladores.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| runtime_id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| version | TEXT | sim |
| executable_name | TEXT | sim |
| command_template | TEXT | sim |
| active | BOOLEAN | não |

UNIQUE `(runtime_id, slug)`.

## 12.3 `cores`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| emulator_id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| version | TEXT | sim |
| library_file | TEXT | sim |
| active | BOOLEAN | não |

UNIQUE `(emulator_id, slug)`.

Um emulador standalone pode simplesmente não possuir cores.

---

# 13. Configuração de execução

## 13.1 `execution_profiles`

É a entidade que substitui a dependência direta em XML para configuração operacional.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| emulator_id | INTEGER | não |
| core_id | INTEGER | sim |
| command_template | TEXT | sim |
| working_directory | TEXT | sim |
| environment_json | TEXT | sim |
| settings_json | TEXT | sim |
| active | BOOLEAN | não |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

`core_id` deve pertencer ao mesmo `emulator_id` quando informado.

## 13.2 `execution_profile_platforms`

PK `(execution_profile_id, platform_id)`.

Campos adicionais:

- `priority`;
- `recommended`;
- `file_extensions`;
- `bios_set_id` opcional.

## 13.3 `execution_profile_overrides`

Permite configuração específica por plataforma/release quando necessário, sem criar centenas de colunas no perfil principal.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| execution_profile_id | INTEGER | não |
| platform_id | INTEGER | sim |
| release_id | INTEGER | sim |
| key | TEXT | não |
| value | TEXT | sim |

Exatamente um entre `platform_id` e `release_id` deve ser informado.

---

# 14. Paths

## 14.1 `path_locations`

Não armazenar caminhos de sistema diretamente nas entidades de domínio.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| key | TEXT | não |
| category | TEXT | não |
| path | TEXT | não |
| enabled | BOOLEAN | não |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

Categorias:

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

O `path` pode ser absoluto no Windows, mas não deve participar da identidade do conteúdo.

---

# 15. Scan

## 15.1 `scan_runs`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| path_location_id | INTEGER | não |
| started_at | DATETIME | não |
| finished_at | DATETIME | sim |
| status | TEXT | não |
| files_seen | INTEGER | não |
| files_hashed | INTEGER | não |
| matches_found | INTEGER | não |
| errors | INTEGER | não |

## 15.2 `scan_files`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| scan_run_id | INTEGER | não |
| file_id | INTEGER | sim |
| observed_path | TEXT | não |
| file_name | TEXT | não |
| size_bytes | INTEGER | não |
| modified_at | DATETIME | sim |
| status | TEXT | não |
| error_message | TEXT | sim |

## 15.3 `scan_matches`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| scan_file_id | INTEGER | não |
| catalog_entry_id | INTEGER | sim |
| release_id | INTEGER | sim |
| match_type | TEXT | não |
| confidence | REAL | sim |
| evidence_json | TEXT | sim |
| status | TEXT | não |

Match types:

```text
hash
name
archive_member
metadata
manual
composite
```

Status:

```text
candidate
accepted
rejected
ambiguous
```

---

# 16. Transformações e reconstrução

## 16.1 `transformation_rules`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| slug | TEXT | não |
| name | TEXT | não |
| transformation_type | TEXT | não |
| description | TEXT | sim |
| configuration_json | TEXT | sim |
| active | BOOLEAN | não |

Tipos iniciais:

```text
rename
move
extract
repack
merge
split
reconstruct
convert
```

## 16.2 `transformation_jobs`

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| rule_id | INTEGER | não |
| started_at | DATETIME | não |
| finished_at | DATETIME | sim |
| status | TEXT | não |
| dry_run | BOOLEAN | não |
| error_message | TEXT | sim |

## 16.3 `transformation_inputs`

PK `(job_id, file_id)`.

## 16.4 `transformation_outputs`

PK `(job_id, file_id)`.

Campos adicionais:

- `created_new_file`;
- `replaced_existing`;
- `verified`.

Nenhuma transformação deve apagar o original automaticamente sem uma política explícita de segurança.

---

# 17. Source Mapping detalhado

## 17.1 `source_mappings`

Relaciona uma entrada de fonte com uma identidade ou release interna.

| Coluna | Tipo | Null |
|---|---|---:|
| id | INTEGER | não |
| source_identity_id | INTEGER | não |
| canonical_identity_id | INTEGER | sim |
| release_id | INTEGER | sim |
| mapping_type | TEXT | não |
| confidence | REAL | não |
| evidence_json | TEXT | sim |
| resolver | TEXT | sim |
| resolver_version | TEXT | sim |
| status | TEXT | não |
| created_at | DATETIME | não |
| updated_at | DATETIME | não |

Exatamente um destino principal deve ser preenchido: `canonical_identity_id` ou `release_id`.

Tipos:

```text
exact
hash
metadata
alias
manual
inferred
```

---

# 18. Relacionamentos principais

```text
sources 1 ─── N source_versions
sources 1 ─── N catalogs
source_versions 1 ─── N catalog_versions
catalogs 1 ─── N catalog_versions
catalog_versions 1 ─── N catalog_entries

catalog_entries 1 ─── 0..1 source_identities
source_identities N ─── 0..1 canonical_identities
canonical_identities 1 ─── N releases
platforms 1 ─── N releases

canonical_identities 1 ─── N identity_names
platforms 1 ─── N platform_aliases

releases N ─── N files       via release_files
files 1 ─── N file_hashes
files 1 ─── 0..1 archives
archives 1 ─── N archive_members

releases 1 ─── N discs
discs 1 ─── N disc_tracks
disc_tracks 1 ─── N disc_track_hashes

runtimes 1 ─── N emulators
emulators 1 ─── N cores
emulators 1 ─── N execution_profiles
execution_profiles N ─── N platforms

path_locations 1 ─── N scan_runs
scan_runs 1 ─── N scan_files
scan_files 1 ─── N scan_matches

transformation_rules 1 ─── N transformation_jobs
transformation_jobs N ─── N files via inputs/outputs
```

---

# 19. Índices obrigatórios

Além das PK/UNIQUE, o schema deverá criar índices para os caminhos de consulta principais:

```text
sources(slug)
sources(name)
source_versions(source_id, source_date)
catalogs(source_id, slug)
catalog_versions(catalog_id, source_version_id)
catalog_entries(catalog_version_id, external_id)
canonical_identities(normalized_name)
source_identities(source_id, external_id)
releases(canonical_identity_id, platform_id)
releases(platform_id, normalized_name)
identity_names(normalized_value)
platforms(slug)
platform_aliases(alias)
files(file_name)
files(size_bytes)
file_hashes(algorithm, value)
release_files(file_id)
archives(file_id)
archive_members(file_id)
discs(release_id, disc_number)
disc_tracks(disc_id, track_number)
runtimes(slug)
emulators(runtime_id, slug)
cores(emulator_id, slug)
execution_profiles(emulator_id, active)
scan_runs(path_location_id, started_at)
scan_files(scan_run_id, status)
scan_matches(scan_file_id, status)
source_mappings(source_identity_id, status)
```

Índices só serão adicionados quando justificáveis por consulta ou integridade; não indexar indiscriminadamente todas as colunas.

---

# 20. Foreign keys e cascades

Regra padrão: **não usar cascade delete destrutivo em entidades de catálogo, identidade ou conteúdo**.

Preferências:

- relação puramente associativa: `ON DELETE CASCADE` pode ser usada;
- entidade histórica: `RESTRICT`/proteção;
- entidade opcional derivada: `SET NULL` quando semanticamente correto.

Exemplo:

```text
canonical_identity
    ↓
release
```

Não permitir apagar uma identidade com releases sem operação explícita de limpeza.

Já:

```text
execution_profile
    ↓
execution_profile_platforms
```

pode utilizar cascade na relação associativa.

---

# 21. Estados

Estados não devem ser strings livres quando o conjunto é fechado.

Na camada Python usar `Enum`/Literal; no banco, usar CHECK constraints compatíveis com SQLite quando a enumeração for estável.

Para estados que podem evoluir rapidamente, considerar tabela de domínio ou validação de aplicação em vez de alterar schema constantemente.

---

# 22. JSON

JSON é permitido para:

- payload original de provider;
- evidência de matching;
- parâmetros de execução variáveis;
- configuração específica de transformação;
- metadados raros e provider-specific.

JSON não deve substituir:

- FK;
- nomes pesquisáveis;
- hashes;
- relações N:N;
- estados essenciais;
- plataforma;
- release;
- identidade.

---

# 23. Provider-specific data

Quando uma fonte tiver estrutura impossível de representar sem perda, haverá três níveis:

```text
provider raw data
        ↓
provider normalized model
        ↓
common SERM domain
```

A V2 não deve criar dezenas de colunas vazias apenas para acomodar um provider.

Para casos realmente específicos, usar tabelas especializadas ligadas por FK ao domínio comum.

Exemplo futuro:

```text
mame_machine
mame_rom_entry
mame_disk_entry
mame_softwarelist_entry
```

Essas tabelas **não entram na primeira migration** até que o adapter MAME exija seus campos.

---

# 24. SQLite e Alembic

A primeira migration deve criar o schema completo do núcleo, mas não precisa popular catálogos externos.

Alembic será a autoridade de versionamento do schema. A documentação oficial descreve Alembic como ferramenta de migração para SQLAlchemy. Para SQLite, alterações estruturais futuras podem exigir o modo batch, pois SQLite possui suporte limitado a ALTER TABLE; Alembic fornece `batch_alter_table()` para esse cenário. citeturn0search0turn0search15

Dados de catálogo inicial não devem ser misturados indiscriminadamente às migrations de schema. Para cargas maiores, usar importadores/seeders separados; a própria documentação do Alembic recomenda tratar migrações de dados de maneira distinta das migrações estruturais em muitos cenários. citeturn0search14

---

# 25. Ordem da primeira implementação

A implementação física será feita nesta ordem:

```text
01. database foundation
02. source registry
03. catalog/version/entry
04. canonical identity
05. platform/system
06. release
07. file/hash
08. archive
09. disc/track
10. BIOS
11. runtime/emulator/core
12. execution profiles
13. paths
14. source mapping
15. scan
16. transformation/reconstruction
```

Não implementar scanner, scraper, reconstrução ou importadores antes de o núcleo de identidade e proveniência estar funcional.

---

# 26. Critério para considerar o Data Foundation pronto

Antes de iniciar adapters reais, todos os seguintes testes devem existir:

1. criar banco vazio;
2. executar migrations do zero;
3. abrir banco com foreign keys habilitadas;
4. inserir source e source version;
5. inserir catalog/version/entry;
6. criar canonical identity;
7. criar source mapping;
8. criar platform e release;
9. registrar file e hashes;
10. associar release/file;
11. registrar archive/member;
12. registrar disc/track;
13. criar runtime/emulator/core/profile;
14. executar scan fictício;
15. registrar transformation dry-run;
16. executar rollback de migration de teste quando suportado;
17. verificar constraints e índices;
18. executar `pytest` e `ruff` sem erro.

Somente após isso o primeiro adapter real deve ser conectado.

---

# 27. Fontes que orientarão os adapters

A arquitetura deve permitir, sem alterar o núcleo:

- No-Intro / Dat-o-Matic;
- Redump;
- MAME;
- FBNeo;
- RetroArch `.rdb`;
- LaunchBox Metadata DB/XML;
- WHDLoad/Retroplay;
- eXoDOS;
- MAME Softlists;
- demais fontes futuras.

Essas fontes não são equivalentes. Cada uma terá adapter próprio e preservará sua proveniência.

---

# 28. Decisão arquitetural final desta etapa

O SERM V2 terá uma **base canônica própria**, e as fontes externas serão tratadas como dados de proveniência/mapeamento.

```text
               ┌──────────── No-Intro
               │
               ├──────────── Redump
               │
               ├──────────── MAME
               │
               ├──────────── FBNeo
               │
               ├──────────── RetroArch
               │
               ├──────────── LaunchBox
               │
               ├──────────── WHDLoad
               │
               └──────────── eXoDOS
                              │
                              ▼
                    ┌─────────────────┐
                    │ SOURCE ADAPTERS │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ PROVENANCE      │
                    │ + SOURCE MODEL  │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ CANONICAL DOMAIN│
                    └────────┬────────┘
                             ▼
               ┌────────────┼────────────┐
               ▼            ▼            ▼
            CATALOG       SCAN       EXECUTION
               │            │            │
               └────────────┼────────────┘
                            ▼
                    TRANSFORMATION /
                    RECONSTRUCTION
```

Este é o contrato estrutural da V2. O schema SQL/Alembic deve ser derivado dele, e não o contrário.
