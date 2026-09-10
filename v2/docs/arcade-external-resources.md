# Arcade Studio — Recursos externos MAME

## Objetivo

O SERM V2 pode adquirir recursos auxiliares publicados por providers externos sem obrigar o usuário a baixar ZIPs manualmente, descobrir seu conteúdo ou copiar arquivos para pastas do MAME.

A aquisição não substitui o catálogo MAME, o scan físico ou a reconstrução. O fluxo é:

```text
Provider
   ↓
Resource Catalog
   ↓
Download / Cache
   ↓
Extraction + validation
   ↓
Source
   ↓
Scan / Dependencies / Reconstruction
   ↓
Destination MAME
```

A origem permanece separada do destino. Um provider externo nunca deve escrever diretamente no destino sem passar pela política de publicação.

## Provider atual

O primeiro provider é o **Progetto-SNAPS**.

O site publica vários tipos de recursos MAME e informa que os support files são divididos entre arquivos `.dat`, destinados a `dats/`, e arquivos `.ini`, destinados a `folders/`. A página também distingue recursos de classificação, suporte e Samples. O SERM mantém essa distinção no catálogo e não presume que todo arquivo publicado seja necessário para reconstrução.

## Pacotes selecionados

| Recurso | Versão | Conteúdo útil | Destino | Papel no SERM |
|---|---|---|---|---|
| CatVer | 0.289 | `catver.ini`, CatList, Genre e complementos | SERM metadata / `folders` | classificação e filtros |
| BestGames | 0.280 | `bestgames.ini` | `folders` | ranking opcional |
| Series | 0.289 | `series.ini` | `folders` | agrupamento de séries |
| Languages | 0.289 | `languages.ini` | `folders` | filtro por idioma |
| GameInit | 0.289 | `gameinit.dat`, `gameinit.ini` | `dats` / `folders` | informações de inicialização |
| Command | 0.273 | `command.dat`, `command.ini` | `dats` / `folders` | informações de comandos |
| MAME Samples FullPack | 0.289 | 75 pacotes de Samples | `samples` | dependência física opcional |

As versões são independentes. O SERM não deve transformar automaticamente a versão do MAME na versão de todos os recursos, porque alguns providers atualizam esses arquivos em cadências próprias.

## Observação sobre o catálogo MAME

O MAME/ListXML continua sendo a fonte primária para identidade, relações, ROMs, disks, BIOS, devices, software lists e demais semânticas estruturais do emulador.

Os arquivos externos são complementares. Em particular:

- `CatList`/`Genre`, `Series` e `Languages` podem enriquecer filtros e navegação;
- `BestGames` é uma avaliação pessoal e não deve ser tratado como verdade oficial;
- `GameInit` e `Command` são informações auxiliares para a experiência do usuário;
- Samples são conteúdo físico e entram no grafo de dependências somente quando o catálogo MAME exigir sua presença;
- CatVer não deve ser usado como substituto da semântica nativa do MAME.

## Política de download

Cada pacote possui uma identidade estável baseada em provider, plataforma, nome e versão. O conteúdo pode ainda receber SHA-256 e tamanho esperado quando a fonte fornecer evidência confiável.

O Download Manager:

1. verifica o cache;
2. baixa atomicamente quando necessário;
3. valida tamanho/hash quando disponíveis;
4. extrai com proteção contra path traversal;
5. mantém o resultado fora do destino MAME;
6. só publica membros explicitamente mapeados pelo provider.

## Política de destino

Para cada arquivo destinado ao MAME:

- `CREATE`: arquivo não existe;
- `REUSE`: arquivo existente é byte a byte idêntico;
- `REPLACE`: arquivo diferente e a substituição foi explicitamente autorizada;
- `BLOCK`: arquivo diferente e nenhuma substituição foi autorizada.

Não existe sobrescrita silenciosa e não existe exclusão automática de arquivos desconhecidos no destino.

## Samples

A página de Samples do Progetto-SNAPS publica o **MAME Samples FullPack 0.289** com 75 ZIPs e alerta explicitamente que alguns recursos individuais contêm arquivos falsos usados apenas para fazer ferramentas de verificação apresentarem um conjunto completo. Por isso o SERM deve tratar o FullPack como recurso a ser validado, e não como evidência automática de que todos os arquivos são físicos e válidos.

O próximo passo da Meta 2.1 é validar os membros reais do FullPack contra a evidência do catálogo MAME e impedir que recursos falsos sejam promovidos para a origem física confiável.

## Princípios

- provider é adapter, não regra de negócio;
- MAME é autoridade para semântica do catálogo;
- recurso externo é complemento, não substituto;
- source e destination são distintos;
- download não é reconstrução;
- extração não é publicação;
- conflitos devem ser explicitados;
- atualização deve ser incremental;
- GUI apenas coordena o fluxo.
