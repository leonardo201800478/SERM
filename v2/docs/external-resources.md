# Recursos externos e aquisição MAME

O Arcade Studio pode consumir recursos publicados por providers externos, mas a aquisição é separada da instalação física até a etapa explícita de publicação.

## Pipeline

```text
Provider
   ↓
Resource Catalog
   ↓
Latest Resource Resolver
   ↓
Download Cache
   ↓
Integrity validation
   ↓
Safe extraction
   ↓
Explicit publication
   ↓
Physical Scan
   ↓
Dependency Resolution
   ↓
Reconstruction
```

O Download Manager prepara recursos em cache/source. A publicação utiliza validação de destino e não deve sobrescrever arquivos diferentes silenciosamente.

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

A chave de deduplicação é `provider + platform + name + version`. O `LatestResourceResolver` deve ser consultado antes da aquisição quando o provider disponibilizar uma estratégia de descoberta de versão.

## Progetto-SNAPS

O provider `ProgettoSnapsProvider` isola as URLs, convenções de publicação e o mapeamento dos membros internos dos ZIPs. A V2 não deve espalhar regras específicas do site pela GUI ou pelo domínio.

Recursos atualmente integrados:

| Recurso | Versão de referência | Membros úteis | Destino |
|---|---:|---|---|
| CatVer | 0.289 | `catver.ini`; `catlist.ini`; `genre.ini`; complementos | SERM metadata / `folders` |
| Series | 0.289 | `series.ini` | `folders` |
| Languages | 0.289 | `languages.ini` | `folders` |
| GameInit | 0.289 | `gameinit.dat`; `gameinit.ini` | `dats` / `folders` |
| BestGames | 0.280 | `bestgames.ini` | `folders` |
| Command | 0.273 | `command.dat`; `command.ini` | `dats` / `folders` |
| MAME Samples FullPack | 0.289 | 75 ZIPs | `samples` |

As versões são independentes. O SERM não deve assumir que a versão de um recurso é igual à versão do MAME.

### Descoberta e atualização

Quando o provider tiver uma fonte de listagem, probe ou link, o `LatestResourceResolver` pode descobrir a versão mais recente publicada antes do download. O pacote efetivamente adquirido é então identificado pelo nome lógico e pela versão resolvida.

O provider de Samples utiliza a página dedicada de Samples do Progetto-SNAPS como origem de descoberta. O FullPack publicado nessa fonte é a unidade de aquisição; não se deve inferir sua versão a partir de um ZIP individual de sample.

## Validação da versão instalada

A GUI do projeto-SNAPS apresenta uma coluna **Versão detectada**. A versão exibida não depende exclusivamente do catálogo/cache do SERM: o arquivo instalado é a autoridade primária quando contém uma declaração de versão.

A ordem de detecção é:

```text
arquivo instalado
   ↓
 cabeçalho/conteúdo inicial
   ↓
nome do arquivo/ZIP
   ↓
cache do SERM
   ↓
—
```

O detector `detect_local_version()` limita a leitura de arquivos de texto ao início do arquivo. Ele reconhece, entre outros, versões explícitas como `MAME 0.289`, versões genéricas `0.289` e convenções publicadas nos nomes dos ZIPs, como `pS_category_289.zip`, `nplayers0278.zip` e `MAME_samples_289.zip`.

Essa abordagem é especialmente importante para os `.ini` do projeto-SNAPS, que normalmente carregam a versão em comentários de cabeçalho. Para DATs, a declaração de versão no cabeçalho tem precedência sobre uma versão genérica encontrada posteriormente.

### Samples

O FullPack de Samples é extraído em vários ZIPs individuais dentro de `<MAME>/samples`. Como os arquivos individuais podem não carregar a versão do FullPack no próprio nome ou conteúdo, a GUI utiliza a proveniência do pacote no cache como fallback. Um sample individual não deve ser interpretado como se fosse, por si só, o manifesto de versão do FullPack.

## Semântica dos recursos

- `CatList` e `Genre` enriquecem classificação; `CatVer` é voltado principalmente a frontends e não substitui o catálogo nativo do MAME.
- `Series` e `Languages` são dados de navegação/filtro.
- `BestGames` é curadoria pessoal e não deve ser tratada como verdade oficial nem como critério automático de reconstrução.
- `GameInit` e `Command` são informações auxiliares de uso do MAME.
- Samples são conteúdo físico e entram no grafo de dependências somente quando o catálogo MAME exigir sua presença.

## O que não deve ser duplicado

O MAME `-listxml` continua sendo a fonte primária para identidade de máquinas, ROMs, relações, BIOS, devices, CHDs e outros elementos estruturais do catálogo. Recursos externos de classificação não substituem o catálogo MAME.

Portanto:

- ROMs, BIOS, devices e CHDs continuam sujeitos ao catálogo e às identidades físicas MAME;
- samples são dependências físicas separadas;
- snapshots/artwork/cabinets são recursos de apresentação e não devem ser confundidos com conteúdo executável;
- recursos externos enriquecem o catálogo quando sua informação não estiver adequadamente disponível na fonte primária.

## Política de aquisição e destino

O Download Manager mantém o pacote no cache/source, valida quando houver hash/tamanho conhecido e extrai com proteção contra path traversal.

Na publicação dos membros mapeados:

- `CREATE`: arquivo não existe;
- `REUSE`: arquivo existente é byte a byte idêntico;
- `REPLACE`: arquivo diferente e a substituição foi explicitamente autorizada;
- `BLOCK`: arquivo diferente e nenhuma substituição foi autorizada.

Não existe sobrescrita silenciosa e não existe exclusão automática de arquivos desconhecidos no destino.

## Segurança

A extração rejeita caminhos absolutos e `..`. Nenhum pacote externo pode sobrescrever um arquivo no destino final sem passar pela validação e política de publicação.
