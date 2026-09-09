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

O provider inicial é isolado em `ProgettoSnapsProvider`. Ele não deve espalhar URLs ou convenções de nomes pela aplicação.

Recursos de referência analisados para esta etapa:

| Recurso | Versão de referência | Papel | Armazenamento |
|---|---:|---|---|
| CatVer | 0.289 | classificação/filtros | SERM metadata |
| Series | 0.289 | série/títulos | SERM metadata |
| Languages | 0.289 | idioma | SERM metadata |
| GameInit | 0.289 | inicialização/metadados auxiliares | SERM metadata |
| BestGames | 0.280 | curadoria/seleção | SERM metadata, histórico |
| Command | 0.273 | comandos/controle auxiliar | SERM metadata, histórico |
| MAME Samples FullPack | 0.289 | áudio adicional | MAME source |

As versões históricas acima são preservadas como referência de proveniência. O SERM não deve assumir que um recurso antigo deve ser baixado novamente para uma versão MAME mais nova sem evidência de compatibilidade.

### Samples

O Progetto-SNAPS informa que os samples adicionais são ZIPs com o mesmo nome do conjunto de ROMs e devem ser colocados na pasta `samples` do MAME. A página atualizada em 08/02/2026 lista o `MAME Samples FullPack 0.289` com 75 ZIPs e alerta que alguns conjuntos contêm arquivos falsos para fins de demonstração. Esses arquivos devem ser tratados como conteúdo não confiável até validação física. 

Fonte: https://www.progettosnaps.net/samples/

## O que não deve ser duplicado

O MAME `-listxml` continua sendo a fonte primária para identidade de máquinas, ROMs, relações, BIOS, devices, CHDs e outros elementos estruturais do catálogo. Recursos externos de classificação não substituem o catálogo MAME.

Portanto:

- CatVer/Series/Languages/GameInit/BestGames/Command enriquecem o catálogo quando sua informação não está disponível no ListXML;
- ROMs, BIOS, devices e CHDs continuam sujeitos ao catálogo e às identidades físicas MAME;
- samples são dependências físicas separadas e entram no grafo de dependências;
- snapshots/artwork/cabinets são recursos de apresentação e não devem ser confundidos com conteúdo executável.

## Segurança

A extração deve rejeitar caminhos absolutos e `..`. Nenhum pacote externo pode sobrescrever um arquivo no destino final sem passar pela validação e política de materialização.
