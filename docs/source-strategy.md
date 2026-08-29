# Estratégia de Fontes de Dados — SERM

**Referência:** 29/08/2026  
**Status:** arquitetura consolidada; adapters ainda pendentes

## 1. Princípio

O SERM trabalhará com três classes principais de fontes:

```text
PRESERVAÇÃO / REFERÊNCIA
        ↓
identidade e integridade física

CONVENIÊNCIA
        ↓
representação operacional alternativa

METADATA / INTEGRAÇÃO
        ↓
nomes, IDs, plataformas, identificação e enriquecimento
```

A fonte oficial/nativa aplicável mantém a referência. Uma fonte conveniente nunca substitui silenciosamente a referência oficial.

## 2. Fontes prioritárias

### Consoles e portáteis

**No-Intro / Dat-o-MATIC** será a referência principal para cartuchos e mídias digitais suportadas. O adapter deverá preservar nome, parent/clone quando existente, nome de ROM, tamanho, CRC32, MD5, SHA1 e demais metadados relevantes.

### Discos

**Redump** será a referência para discos ópticos. O modelo será orientado a disco/faixas e não a uma extensão do modelo de cartucho. CHD poderá ser saída de reconstrução quando tecnicamente compatível.

### Arcade

**MAME/listxml** continua sendo a fonte de verdade já existente para máquinas MAME. Não criar uma segunda representação concorrente.

**FBNeo** terá adapter e semântica próprios.

### Softlists

MAME Softlists serão fonte estruturada para sistemas suportados pelo MAME quando aplicável, especialmente em sistemas como X68000 e outros que tenham software catalogado dessa forma.

## 3. Fontes convenientes

### Amiga

WHDLoad/Retroplay será tratado como fonte conveniente especializada. O SERM deve suportar pacotes `.lha` e, quando implementado, outros formatos relevantes, mantendo a identidade e o nome originais da fonte.

Objetivo operacional:

```text
WHDLoad/Retroplay
        ↓
identificação
        ↓
DE-PARA
        ↓
Canonical Game
        ↓
classificação por sistema/compatibilidade
        ↓
nome adequado para scraper
        ↓
pacote pronto para execução
```

O SERM não deve transformar WHDLoad em um catálogo No-Intro.

### MS-DOS

eXoDOS será tratado como fonte conveniente. O objetivo é permitir, quando compatível com o runtime escolhido, a execução direta de pacotes `.zip` pelo DOSBox-Pure, standalone ou core, evitando extração/reempacotamento desnecessários.

### C64 e outros

Coleções como C64 Dreams, EasyFlash e outras fontes convenientes poderão ser adapters específicos. A existência de uma fonte conveniente não altera a identidade canônica do SERM.

## 4. Fontes de metadata

### RetroArch RDB

Os arquivos `.rdb` da pasta `database` do RetroArch serão providers de metadata/identificação. Podem auxiliar matching por hash/nome e associação com sistemas, mas não substituem uma fonte de preservação aplicável.

### LaunchBox Metadata DB

O `LaunchBox.Metadata.db` será tratado como provider externo de metadata e referência arquitetural. A análise realizada identificou as estruturas:

```text
Games
Platforms
Emulators
EmulatorPlatforms
GameAlternateTitles
GameImages
```

O banco também utiliza SQLite e Entity Framework migrations.

O SERM não dependerá do LaunchBox e não usará seu banco como banco operacional.

### LaunchBox Platforms.xml

É uma fonte útil de classificação e metadata técnica de plataformas. Campos como `Category`, `Emulated` e `UseMameFiles` são relevantes para normalização. Registros marcados no próprio XML como obsoletos/duplicados não devem ser importados cegamente.

### Outros arquivos LaunchBox

`MAME.xml`, `Files.xml` e caches como `RetroAchievementsCache.json` poderão ser providers adicionais, depois de identificados os dados exclusivos que realmente agregam valor.

## 5. Identidade e DE-PARA

Uma entidade canônica do SERM pode possuir múltiplas identidades de fonte:

```text
Canonical Game
├── No-Intro identity
├── Redump identity
├── MAME identity
├── RetroArch identity
├── LaunchBox identity
├── WHDLoad identity
└── eXoDOS identity
```

O relacionamento será explícito em `source_entry_mappings` ou equivalente.

O mapping deve preservar origem, destino, evidência, confiança, regra e versão da fonte.

## 6. Nomes

O SERM deve distinguir:

```text
source_name
canonical_name
display_name
scraper_name
filename
normalized_name
```

Uma fonte conveniente pode possuir nomenclatura inadequada para scraper. O SERM pode gerar um nome canônico/operacional melhor sem perder o nome original registrado na proveniência.

## 7. Política de autoridade

A prioridade conceitual é:

```text
Fonte de preservação aplicável
        ↓
identidade física / hashes
        ↓
identidade canônica
        ↓
metadata providers
        ↓
conveniência / apresentação / execução
```

Quando fontes entrarem em conflito, o SERM não deve sobrescrever automaticamente a informação de maior autoridade. O conflito deve poder ser registrado.

## 8. Adapter Contract

Cada provider deverá implementar, conforme sua natureza:

```text
identify()
discover()
download()
validate()
parse()
normalize()
version()
import()
```

Nem todo provider precisa baixar dados. Um provider local, como RetroArch RDB ou LaunchBox, pode trabalhar diretamente sobre um arquivo existente e registrar sua versão/integridade.

## 9. Atualização

Toda atualização externa seguirá staging:

```text
Fonte
 ↓
download/cópia
 ↓
validação
 ↓
parse
 ↓
normalização
 ↓
transaction
 ↓
ativação da nova versão
```

Falha não destrói a versão válida anterior.

## 10. Ordem dos adapters

1. infraestrutura Source Registry;
2. LaunchBox/RetroArch como fontes locais de metadata para validar o modelo;
3. No-Intro;
4. Redump;
5. MAME/listxml integrado ao modelo já existente;
6. FBNeo;
7. WHDLoad/Retroplay;
8. eXoDOS;
9. Softlists e outras fontes específicas;
10. providers adicionais.

A ordem não transforma metadata providers em fontes de preservação; eles são usados cedo porque ajudam a validar a identidade, plataforma e execução do modelo.
