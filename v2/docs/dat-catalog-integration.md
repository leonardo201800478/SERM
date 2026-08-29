# Aquisição de DATs via Public DAT Catalog

## Objetivo

O SERM V2 usa o **Public DAT Catalog** como fonte principal de aquisição de DATs No-Intro. O catálogo mantém um snapshot público dos DATs em uma estrutura navegável e fornece um `index.csv` com nome, URL, CRC e tamanho de cada arquivo.

Fonte usada pelo SERM:

```text
https://raw.githubusercontent.com/videogame-archive/dat-catalog/main/root/basic/No-Intro/index.csv
```

A fonte é consumida por HTTP direto. Não há Selenium, Firefox, GeckoDriver, CAPTCHA ou dependência da interface HTML do DAT-o-MATIC.

## Arquitetura

```text
LaunchBox
   |
   v
plataformas
   |
   v
Public DAT Catalog
   |
   +--> index.csv
   |       |
   |       +--> nome
   |       +--> URL
   |       +--> CRC32
   |       +--> tamanho
   |
   v
matching LaunchBox x No-Intro
   |
   v
SERM data/sources/no_intro/dats
```

A implementação está em:

```text
serm_v2.sources.acquisition.dat_catalog.PublicDatCatalogProvider
```

## Categorias

O provider considera somente arquivos localizados dentro da seção `No-Intro` do índice. Categorias como `Source Code`, `Non-Redump`, `Unofficial` e outras não são incorporadas ao fluxo principal.

**Redump permanece um backend separado.** Um DAT marcado como `Non-Redump` não é encaminhado para o fluxo Redump nem tratado como equivalente a Redump.

## Matching

O SERM cruza os nomes das plataformas LaunchBox com os nomes dos DATs. A normalização remove diferenças de caixa, acentuação e pontuação. Também existem aliases explícitos para plataformas comuns, como NES, SNES, Genesis e Master System.

## Integridade e atualização

Cada entrada contém `CRC` e `Size`. Antes de considerar um DAT atual, o SERM valida:

1. existência do arquivo;
2. tamanho exato;
3. CRC32 exato.

Estados locais:

- `current`: arquivo corresponde ao catálogo;
- `outdated`: arquivo existe, mas tamanho/CRC divergem;
- `missing`: arquivo ainda não existe.

O botão **Atualizar desatualizados** baixa somente os DATs em `missing` ou `outdated`.

Após um download válido, o SERM grava `manifest.json` com URL, CRC, tamanho e SHA-256.

## Fluxo de download

O download é feito diretamente pela URL publicada no índice:

```text
GET index.csv
    |
    v
match LaunchBox
    |
    v
GET URL do DAT
    |
    v
validar tamanho
    |
    v
validar CRC32
    |
    v
substituição atômica do arquivo
    |
    v
manifest.json
```

Arquivos parciais usam a extensão `.part` e somente são promovidos para `.dat` depois da validação.

## Limpeza da arquitetura anterior

O fluxo antigo baseado em DAT-o-MATIC/Selenium foi removido do V2. Não fazem mais parte do caminho operacional:

- `datoso`;
- `datoso-seed-nointro`;
- Firefox/GeckoDriver;
- scraper HTML do DAT-o-MATIC;
- Scene IDs;
- downloader No-Intro baseado em URLs do DAT-o-MATIC;
- manifesto baseado na revisão HTML do DAT-o-MATIC.

O fork `leonardo201800478/datoso_seed_nointro` permanece independente e pode ser mantido para experimentação, mas não é dependência do SERM.
