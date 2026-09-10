# Projeto-SNAPS — guia da V2

## Estado

A integração inicial do projeto-SNAPS com o Arcade Studio está **concluída para esta etapa**. Esta guia é considerada estável por enquanto; novos recursos ou melhorias podem ser tratados em uma etapa futura sem reabrir as decisões já consolidadas.

## Objetivo

Disponibilizar na V2 uma interface para aquisição e atualização dos principais arquivos auxiliares do MAME publicados pelo projeto-SNAPS, mantendo separadas:

- descoberta da fonte;
- resolução da versão;
- download e cache;
- extração segura;
- publicação na instalação do MAME;
- detecção da versão efetivamente instalada.

O executável MAME continua sendo o único executável configurado em `emulator_paths.json` pela chave `mame_executable`. A integração do projeto-SNAPS não cria um segundo cadastro de executável.

## Interface

A página `ProgettoSnapsPage` apresenta:

| Coluna | Significado |
|---|---|
| Arquivo / recurso | Caminho lógico ou recurso externo |
| Tipo | DAT, INI ou SAMPLES |
| Descrição | Função do recurso |
| Versão detectada | Versão encontrada no arquivo instalado ou no fallback de cache |
| Status local | Presença do arquivo ou quantidade de ZIPs de Samples |

A página permite atualizar o suporte geral e os pacotes específicos de NPlayers, Category, Version, MESSINFO e Samples FullPack, além de abrir a pasta MAME e as páginas oficiais de referência.

## Recursos

A integração atual cobre:

- Support Files, com arquivos `dats/*.dat` e `folders/*.ini` mapeados pelo provider;
- NPlayers;
- Category;
- Version;
- MESSINFO;
- Samples FullPack.

O provider também mantém recursos complementares como CatVer, Series, Languages, GameInit, BestGames e Command. Cada recurso possui identidade e versão próprias; a versão do MAME não deve ser usada para fabricar a versão de um recurso externo.

## Resolução da versão

O SERM deve sempre preferir a versão mais recente que a fonte externa permita descobrir. A responsabilidade fica no `LatestResourceResolver`, antes da aquisição.

O fluxo é:

```text
catálogo do provider
        ↓
LatestResourceResolver
        ↓
versão publicada mais recente
        ↓
download
        ↓
cache
```

O provider de Samples usa a página dedicada de Samples do projeto-SNAPS e seu FullPack como unidade de aquisição.

## Detecção da versão instalada

A coluna **Versão detectada** utiliza o detector local `detect_local_version()`.

Prioridade:

```text
1. cabeçalho/conteúdo inicial do arquivo instalado
2. nome do arquivo/ZIP instalado
3. versão do pacote no cache do SERM
4. —
```

Para `.ini`, a versão normalmente está em comentários do cabeçalho. Para `.dat`, declarações explícitas como `MAME 0.289` têm prioridade. A leitura de arquivos de texto é limitada à região inicial para evitar varredura desnecessária.

Exemplo reconhecido:

```ini
;; MECHANICAL_ARCADE.ini 0.289 / 21-Aug-26 / MAME 0.289 ;;
```

Resultado na GUI: `0.289`.

### Samples

O FullPack é composto por vários ZIPs individuais. Um ZIP individual de sample pode não carregar a versão do FullPack no nome ou conteúdo. Por isso, quando a detecção local não é suficiente, a GUI usa a proveniência do pacote original no cache do SERM.

Não se deve atribuir uma versão ao FullPack examinando arbitrariamente um único sample.

## Destinos

Os arquivos publicados pelo provider são direcionados para a instalação do MAME:

```text
<MAME>/dats/
<MAME>/folders/
<MAME>/samples/
```

Arquivos de metadados que não pertencem ao diretório MAME permanecem no espaço de metadata definido pelo SERM.

O `DownloadManager` valida todos os membros antes da publicação e protege a extração contra path traversal.

## Segurança e integridade

A integração não possui sobrescrita silenciosa. Os estados de destino são:

- `CREATE` — arquivo inexistente;
- `REUSE` — arquivo existente idêntico;
- `REPLACE` — arquivo diferente, com substituição explicitamente autorizada;
- `BLOCK` — arquivo diferente, sem autorização para substituir.

O pacote é baixado primeiro para o cache e somente depois publicado.

## Fonte de autoridade

O projeto-SNAPS é uma fonte auxiliar. O MAME `-listxml` continua sendo a autoridade para identidade estrutural das máquinas, ROMs, BIOS, devices e CHDs.

Samples são dependências físicas separadas. Arquivos de classificação, navegação e apresentação não substituem o catálogo MAME.

## Critérios de conclusão desta etapa

Considera-se esta guia concluída porque a V2 possui:

- provider isolado para projeto-SNAPS;
- catálogo de recursos externos;
- resolução de versão mais recente;
- download/cache e extração segura;
- publicação controlada dos membros;
- suporte ao Samples FullPack;
- GUI dedicada;
- detecção de versão a partir dos arquivos instalados;
- fallback de versão pelo cache;
- testes unitários para o detector de versões.

## Fora do escopo desta etapa

Ficam para etapas futuras, se necessários:

- auditoria semântica completa dos 75 ZIPs de Samples contra o catálogo MAME;
- validação de dependências de Samples em nível de conjunto;
- histórico visual de versões instaladas;
- rollback de recursos externos;
- ampliação do catálogo para outros recursos do projeto-SNAPS.

Esses itens não devem ser interpretados como falhas da integração atual; são extensões futuras deliberadamente fora do escopo desta etapa.
