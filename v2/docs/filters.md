# Filtros

Filtros reduzem um catálogo ou dataset segundo regras explícitas. Eles não alteram a fonte original.

## Pipeline

```text
Scan físico selecionado
  ↓
Machines presentes no scan
  ↓
SERM DB / ListXML normalizado
  ↓
Fontes auxiliares persistidas (folders/*.ini)
  ↓
Filtros fundamentais
  ↓
Filtros estruturais e avançados
  ↓
Resultado de machines
```

## MAME

O Arcade Studio V2 usa o banco relacional do SERM como fonte primária para os dados estruturais do MAME. O scan físico apenas define quais machines estão disponíveis no universo consultado.

O XML do MAME continua sendo a fonte de origem para dados como machine, clone, ano, fabricante, driver, vídeo, input, ROM, disco, samples, BIOS e devices. O filtro não deve depender de uma nova leitura dos ZIPs/CHDs durante a pesquisa.

### Fontes auxiliares `folders/*.ini`

Os arquivos `.ini` do diretório `folders` são ingeridos em lote para o banco do SERM antes da aplicação da semântica específica de cada filtro. Nesta primeira etapa, a ingestão é deliberadamente genérica e preserva:

- nome do arquivo;
- caminho original;
- SHA-256 e tamanho;
- data da importação;
- seção;
- nome da machine;
- linha original.

Isso permite importar rapidamente todo o conjunto de suporte e somente depois construir os filtros sem precisar reler os arquivos físicos a cada consulta.

Arquivos sem alteração são ignorados pelo hash. Uma nova revisão do mesmo arquivo substitui a revisão anterior. Arquivos diferentes com conteúdo idêntico continuam sendo fontes independentes.

A semântica específica deve ser construída posteriormente sobre esses dados persistidos. Exemplos incluem `Working Arcade.ini`, `Not Working Arcade.ini`, `Parents Arcade.ini`, `Clones Arcade.ini`, `genre.ini`, `series.ini`, `controls.ini`, `resolution.ini`, `players.ini`, `CPU.ini`, `Device.ini`, `Version.ini`, `Vsync.ini`, `CHD Working.ini` e os demais arquivos disponíveis no diretório.

### CATLIST

CATLIST permanece uma fonte de classificação própria e não deve ser substituído por `category.ini`, `catver.ini` ou heurísticas genéricas. O serviço de classificação procura primeiro `folders/catlist.ini` e utiliza `cat32en/catlist.ini` como fallback.

### Ano

Os anos expostos como faceta rápida e utilizados pela faixa de ano representam somente machines classificadas como **Arcade**. Machines de console, computer, handheld, BIOS, device ou outras classificações não devem criar anos adicionais nessa faceta.

## Persistência

Filtros podem ter estado de aplicação/sessão ou persistência própria quando implementada. Documentação deve distinguir claramente os dois casos.

## Regras

- filtro não modifica o catálogo authoritative;
- resultado deve ser reprodutível a partir do catálogo, fontes auxiliares persistidas e configuração;
- filtros devem ser testáveis sem GUI;
- novos critérios devem ter cobertura de teste;
- filtros usados no scan devem ser identificáveis junto ao resultado quando necessário para auditoria;
- a ingestão dos `.ini` deve ocorrer antes da construção da semântica específica dos filtros.
