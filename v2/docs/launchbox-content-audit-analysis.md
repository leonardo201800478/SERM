# SERM V2 — Análise Quantitativa do LaunchBox

**Fonte analisada:** `G:\LaunchBox\Metadata\LaunchBox.Metadata.db` e `G:\LaunchBox\Metadata\Platforms.xml`  
**Relatório:** `launchbox-audit.json` gerado em 29/08/2026  
**Estado:** análise estrutural concluída; análise de preenchimento detalhado limitada pelo relatório atual.

## 1. Inventário observado

| Tabela | Registros | Papel potencial no SERM |
|---|---:|---|
| `Games` | 187.564 | metadata de jogos/releases; não copiar 1:1 |
| `GameImages` | 1.322.505 | metadata visual e associação com jogos |
| `GameAlternateTitles` | 69.802 | aliases/títulos alternativos |
| `Platforms` | 190 | catálogo de plataformas |
| `PlatformAlternateNames` | 431 | aliases de plataforma |
| `Emulators` | 35 | catálogo de runtimes/emuladores |
| `EmulatorPlatforms` | 98 | associação emulador ↔ plataforma |
| `__EFMigrationsHistory` | 1 | infraestrutura exclusiva do LaunchBox; não importar |
| `__EFMigrationsLock` | 0 | infraestrutura exclusiva do LaunchBox; não importar |

O relatório também informa 190 plataformas no XML, das quais 183 estão marcadas como emuladas. Os registros exemplares de `Games` mostram que a base mistura Windows, Nintendo 64, NES, Arcade, Xbox 360 e outros sistemas. fileciteturn120file0

## 2. Decisão sobre `Games`

`Games` não deve virar uma tabela única equivalente no SERM.

O LaunchBox usa `DatabaseID` como identidade interna da própria aplicação e mantém `Platform` como texto. O SERM precisa separar:

```text
Canonical Identity
        ↓
Release
        ↓
Platform
        ↓
physical representation
```

Campos de metadata como descrição, desenvolvedor, publisher e gêneros são candidatos ao domínio canônico, mas não devem permanecer como um bloco denormalizado quando houver necessidade de consulta/relacionamento independente.

## 3. Títulos alternativos

Os 69.802 registros de `GameAlternateTitles` justificam uma entidade própria de nomes/aliases no SERM.

A informação de região deve permanecer preservada. O modelo V2 proposto em `identity_names` suporta tipos de nome, idioma, região e fonte.

Não importar `AltNameCompareValue` como coluna canônica; ele é tratado como mecanismo de comparação específico do provider, salvo evidência futura de utilidade independente.

## 4. Imagens

`GameImages` possui 1.322.505 registros e portanto não deve ser reproduzida como uma simples coluna ou lista JSON em `canonical_identities`.

A tabela evidencia que imagens são uma relação de alto volume entre jogo, arquivo/nome, tipo e região. No SERM, a representação final deverá distinguir:

```text
asset/image metadata
        ↓
source provenance
        ↓
canonical identity/release
```

Os arquivos de imagem não devem ser tratados como parte do banco principal; o banco guarda identidade, proveniência, tipo e localização/hash conforme necessário.

## 5. Plataformas

`Platforms` contém 190 registros e possui metadados técnicos úteis: fabricante, CPU, memória, gráficos, som, display, mídia, controladores e categoria.

Esses dados justificam a entidade `platforms` do SERM, mas não justificam o campo `Emulated` como propriedade primária do conceito de plataforma. Emulação é uma capacidade/configuração do ambiente, não a identidade histórica da plataforma.

`UseMameFiles` também deve permanecer específico de integração/compatibilidade com LaunchBox/MAME, não como atributo universal de plataforma.

`PlatformAlternateNames` justifica `platform_aliases` no SERM.

## 6. Emuladores e associações

`Emulators` tem 35 registros e `EmulatorPlatforms` 98 associações. São uma boa referência para o domínio de execução.

Não copiar cegamente os campos `NoQuotes`, `NoSpace`, `HideConsole`, `FileNameOnly` e `AutoExtract`. Eles representam detalhes de construção de comando do LaunchBox e devem ser avaliados como propriedades de um perfil de lançamento/provider.

O modelo V2 deve separar:

```text
Runtime
Emulator / Backend
Core
ExecutionProfile
Platform association
```

## 7. O que já pode ser descartado do domínio canônico

Os seguintes elementos são explicitamente específicos da implementação do LaunchBox e não devem entrar no núcleo SERM:

- `__EFMigrationsHistory`;
- `__EFMigrationsLock`;
- `GameImages.FileName` como identidade global;
- `Games.DatabaseID` como PK do SERM;
- `Games.CompareName` como dado canônico;
- `Platforms.PlatformKey` como identidade do SERM;
- `Platforms.UseMameFiles` como atributo universal;
- flags de command line como propriedades universais de emuladores.

## 8. Limite da análise atual

O relatório atual contém contagens, estrutura das colunas e dez registros exemplares de `Games`, mas ainda não contém estatísticas de preenchimento por coluna, distribuição de valores, tipos de imagens e cardinalidades detalhadas.

Portanto, não é correto afirmar, com base somente neste relatório, qual percentual de cada campo está preenchido.

## 9. Próxima evolução da auditoria

Antes da migration V2 definitiva, devemos ampliar o auditor para produzir:

- `COUNT(*)` por coluna não nula;
- quantidade de strings vazias;
- `COUNT(DISTINCT ...)`;
- top valores categóricos;
- distribuição de imagens por `Type` e `Region`;
- distribuição de jogos por plataforma;
- relações `EmulatorPlatforms` com extensões e BIOS;
- contagem de aliases por plataforma/jogo;
- índices e constraints reais;
- detecção de inconsistências entre `Platforms` e `Platforms.xml`.

Somente depois dessa segunda rodada a modelagem física V2 deve ser congelada.
