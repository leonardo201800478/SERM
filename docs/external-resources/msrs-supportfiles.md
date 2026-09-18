# Fonte de INIs — AntoPISA/MAME_SupportFiles

O SERM V2 reconhece `https://github.com/AntoPISA/MAME_SupportFiles` como fonte externa de suporte para metadados e listas auxiliares MAME.

O repositório declara suporte ao ciclo MAME v0.289 e informa quais pacotes foram atualizados no ciclo, incluindo Category, CatVer, `languages.ini`, `series.ini` e version pack. Também informa que alguns pacotes, como `bestgames.ini` e CHD-Info, não foram atualizados nesse ciclo. Isso torna a revisão/versão da fonte um dado importante para auditoria e compatibilidade. 

## Política de ingestão

- ListXML do MAME permanece authoritative para estrutura de machines, ROMs, discos e relações técnicas.
- INIs do AntoPISA entram como fontes auxiliares, sempre com `source_type` e `source_path` preservados.
- O SERM deve persistir revisão/hash/data de ingestão e evitar republicar silenciosamente dados de uma versão antiga sobre uma nova.
- `CATLIST` continua com proveniência própria e não deve ser substituído por outro INI semanticamente parecido.
- Arquivos não atualizados no ciclo corrente devem continuar utilizáveis, mas sua revisão deve ficar registrada para permitir auditoria.

## Pacotes de interesse para o SERM

### Alta prioridade

- `catver.ini/catver.ini`
- `catver.ini/catlist.ini`
- `catver.ini/genre.ini`
- `category.ini/category.ini`
- `category.ini/Working Arcade.ini`
- `category.ini/Working Arcade Clean.ini`
- `category.ini/Not Working Arcade.ini`
- `category.ini/ArcadeWorkingParents.ini`
- `category.ini/Parents Arcade.ini`
- `category.ini/Clones Arcade.ini`
- `category.ini/Bootlegs.ini`
- `category.ini/Non Bootlegs.ini`
- `category.ini/Prototype.ini`
- `category.ini/Mechanical Arcade.ini`
- `category.ini/Non Mechanical Arcade.ini`
- `category.ini/players.ini`
- `category.ini/resolution.ini`
- `category.ini/monochrome.ini`
- `category.ini/driver.ini`
- `category.ini/mess.ini`
- `category.ini/mame.ini`
- `category.ini/mame_NOBIOS.ini`
- `category.ini/mame_BIOS.ini`
- `category.ini/CHD Working.ini`
- `category.ini/CHD (no BIOS).ini`
- `category.ini/artwork_necessary.ini`
- `category.ini/screenless.ini`
- `bestgames.ini/bestgames.ini`

### Outras fontes úteis

O repositório também contém conjuntos auxiliares relacionados a idiomas, séries, versões, alterações de MAME e outros metadados. A ingestão deve ser descoberta a partir da árvore do repositório, em vez de manter uma lista fechada que dependa de uma revisão específica.

## Atualização

A fonte deve ser tratada como um snapshot versionado. Para uma sincronização:

1. consultar a árvore da branch configurada;
2. detectar novos/alterados arquivos;
3. calcular SHA-256 do conteúdo recebido;
4. persistir nova revisão sem apagar o histórico;
5. executar normalização semântica somente depois da persistência;
6. registrar conflitos ou fontes ausentes como estado auditável.

A versão do snapshot exibida no README da fonte deve ser registrada como metadado de aquisição, não como substituto do SHA do conteúdo.
