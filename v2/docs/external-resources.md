# Recursos externos e aquisicao MAME

O Arcade Studio pode consumir recursos publicados por providers externos, mas a aquisicao nunca escreve diretamente na instalacao do emulador.

## Pipeline

```text
Provider
   ↓
Resource Catalog
   ↓
Download Cache
   ↓
Integrity validation
   ↓
Safe extraction
   ↓
SERM Source / MAME Source
   ↓
Physical Scan
   ↓
Dependency Resolution
   ↓
Reconstruction
   ↓
Destination validation
   ↓
MAME destination
```

A origem permanece somente leitura durante scan e reconstrução. O Download Manager prepara recursos em cache/source; a materialização continua sendo a única camada autorizada a publicar artefatos no destino.

## Resource Catalog

Cada recurso possui:

- provider;
- plataforma;
- nome lógico;
- versão;
- tipo funcional;
- URL de aquisição;
- política de armazenamento;
- política de extração;
- tamanho/hash esperado, quando fornecidos;
- obrigatoriedade;
- metadados do provider.

A chave de deduplicação é `provider + platform + name + version`. O hash de conteúdo pode demonstrar que duas versões carregam o mesmo conteúdo e evitar aquisição redundante.

## Progetto-SNAPS

O provider inicial é isolado em `ProgettoSnapsProvider`. Ele concentra URLs, versões e o mapeamento dos membros internos dos ZIPs.

Recursos de referência analisados para esta etapa:

| Recurso | Versão | Membros úteis | Destino |
|---|---:|---|---|
| CatVer | 0.289 | `catver.ini`; `catlist.ini`; `genre.ini`; complementos | SERM metadata / `folders` |
| Series | 0.289 | `series.ini` | `folders` |
| Languages | 0.289 | `languages.ini` | `folders` |
| GameInit | 0.289 | `gameinit.dat`; `gameinit.ini` | `dats` / `folders` |
| BestGames | 0.280 | `bestgames.ini` | `folders` |
| Command | 0.273 | `command.dat`; `command.ini` | `dats` / `folders` |
| MAME Samples FullPack | 0.289 | 75 ZIPs | `samples` |

As versões são independentes. O SERM não deve assumir que a versão de um recurso é igual à versão do MAME, porque alguns providers atualizam esses arquivos em cadências próprias.

### Conteúdo efetivamente verificado nos pacotes de referência

Os ZIPs fornecidos para esta etapa foram inspecionados diretamente. Eles contêm, entre outros arquivos de documentação, os seguintes membros:

```text
pS_CatVer_289.zip
  catver.ini
  UI_files/catlist.ini
  UI_files/genre.ini
  UI_files/genre_ows.ini
  UI_files/mature.ini
  UI_files/not_mature.ini

pS_BestGames_280.zip
  folders/bestgames.ini

pS_Series_289.zip
  folders/series.ini

pS_Languages_289.zip
  folders/languages.ini

pS_gameinit_289.zip
  dats/gameinit.dat
  folders/gameinit.ini

pS_Command_273.zip
  dats/command.dat
  folders/command.ini
```

O provider não deve copiar `readme.txt`, diretórios vazios ou arquivos auxiliares não mapeados para o destino.

### Semântica dos recursos

- `CatList` e `Genre` enriquecem classificação; `CatVer` é uma classificação voltada principalmente a frontends e não substitui o catálogo nativo do MAME.
- `Series` e `Languages` são dados de navegação/filtro.
- `BestGames` é uma avaliação pessoal do autor e não deve ser tratada como verdade oficial ou como critério automático de reconstrução.
- `GameInit` e `Command` são informações auxiliares de uso do MAME.
- Samples são conteúdo físico e entram no grafo de dependências somente quando o catálogo MAME exigir sua presença.

## Samples

O Progetto-SNAPS informa que os samples adicionais são ZIPs com o mesmo nome do conjunto de ROMs e devem ser colocados na pasta `samples` do MAME. A página atualizada em agosto de 2026 lista o `MAME Samples FullPack 0.289` com 75 ZIPs e alerta que alguns conjuntos contêm arquivos falsos para fins de demonstração. Esses arquivos devem ser tratados como conteúdo não confiável até validação física.

O provider usa o pacote FullPack como unidade de aquisição. A validação futura deve inspecionar os ZIPs internos contra as dependências do catálogo e impedir que conteúdo falso seja promovido para a origem física confiável.

## O que não deve ser duplicado

O MAME `-listxml` continua sendo a fonte primária para identidade de máquinas, ROMs, relações, BIOS, devices, CHDs e outros elementos estruturais do catálogo. Recursos externos de classificação não substituem o catálogo MAME.

Portanto:

- ROMs, BIOS, devices e CHDs continuam sujeitos ao catálogo e às identidades físicas MAME;
- samples são dependências físicas separadas;
- snapshots/artwork/cabinets são recursos de apresentação e não devem ser confundidos com conteúdo executável;
- recursos externos somente enriquecem o catálogo quando sua informação não estiver adequadamente disponível na fonte primária.

## Política de aquisição e destino

O Download Manager mantém o pacote no cache/source, valida quando houver hash/tamanho conhecido e extrai com proteção contra path traversal.

Na publicação dos membros mapeados:

- `CREATE`: arquivo não existe;
- `REUSE`: arquivo existente é byte a byte idêntico;
- `REPLACE`: arquivo diferente e a substituição foi explicitamente autorizada;
- `BLOCK`: arquivo diferente e nenhuma substituição foi autorizada.

Não existe sobrescrita silenciosa e não existe exclusão automática de arquivos desconhecidos no destino.

## Segurança

A extração deve rejeitar caminhos absolutos e `..`. Nenhum pacote externo pode sobrescrever um arquivo no destino final sem passar pela validação e política de materialização.
