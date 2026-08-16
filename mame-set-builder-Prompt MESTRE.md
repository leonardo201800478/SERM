# MAME SET BUILDER

## PROMPT MESTRE v3

### Estado real do projeto, objetivos e regras de desenvolvimento

**Data de referência:** 16/08/2026

---

# 1. IDENTIDADE DO PROJETO

O **MAME Set Builder** é uma aplicação desktop desenvolvida em Python para gerenciamento inteligente de conjuntos de ROMs do MAME.

O objetivo principal não é simplesmente filtrar nomes de máquinas.

O sistema deve:

* interpretar os dados oficiais fornecidos pelo MAME;
* manter um banco de dados estruturado das máquinas e seus componentes;
* classificar máquinas;
* permitir criação de perfis de filtragem;
* identificar quais máquinas pertencem ao conjunto desejado;
* localizar e auditar os arquivos físicos correspondentes;
* identificar ROMs, BIOS, devices, samples, disks e CHDs necessários;
* verificar a integridade dos arquivos;
* permitir reconstrução de um conjunto selecionado a partir de um FULLSET;
* futuramente integrar downloads via qBittorrent;
* futuramente permitir reconstrução de diferentes formatos de set.

O projeto deve ser tratado como um **gerenciador de datasets, auditor e construtor de conjuntos MAME orientado a dependências**.

---

# 2. FONTE DE VERDADE

A regra mais importante do projeto é:

**O código existente no GitHub é a fonte de verdade da implementação atual.**

Repositório:

https://github.com/leonardo201800478/mame-set-builder

Antes de propor alterações estruturais:

1. consultar o código atual;
2. verificar os arquivos realmente existentes;
3. verificar os modelos atuais;
4. verificar o schema atual;
5. verificar as relações entre os módulos;
6. verificar os commits recentes;
7. somente então propor ou implementar alterações.

Documentos antigos nunca devem ser considerados superiores ao código atual.

Documentação pode estar desatualizada.

---

# 3. ARQUITETURA REAL ATUAL

A estrutura atual do projeto é baseada em:

```text
mame-set-builder/
│
├── app/
│   ├── config/
│   ├── core/
│   ├── database/
│   ├── gui/
│   ├── mame/
│   └── main.py
│
├── data/
├── docs/
├── tests/
├── pyproject.toml
└── README.md
```

A arquitetura deve evoluir incrementalmente a partir dessa estrutura.

Não migrar automaticamente para arquiteturas hipotéticas como:

```text
src/mame_set_builder/
```

ou outras estruturas somente porque aparecem em documentação antiga.

---

# 4. OBJETIVO ATUAL DO PROJETO

O objetivo imediato é construir uma aplicação funcional capaz de:

```text
MAME
  ↓
detecção da instalação
  ↓
versão do MAME
  ↓
listxml
  ↓
parser
  ↓
dataset SQLite
  ↓
classificação
  ↓
perfil de filtro
  ↓
seleção de máquinas
  ↓
scan do FULLSET
  ↓
associação Machine ↔ Arquivos
  ↓
auditoria
  ↓
identificação de arquivos necessários
  ↓
construção do conjunto selecionado
```

A prioridade atual NÃO é implementar todo o sistema futuro de uma única vez.

A prioridade é tornar cada etapa existente correta, integrada e testável.

---

# 5. PRINCÍPIO FUNDAMENTAL

O projeto trabalha com duas entidades diferentes:

## Machine

Representa a entidade lógica do MAME.

Exemplos:

```text
sf2
sf2ce
mk
mk2
outrun
daytona
```

## Arquivo

Representa o artefato físico encontrado no armazenamento.

Exemplos:

```text
sf2.zip
sf2ce.zip
mk.zip
neogeo.zip
daytona.chd
```

Nunca assumir:

```text
machine == arquivo
```

Uma machine pode depender de:

* ROMs;
* BIOS;
* devices;
* samples;
* disks;
* CHDs;
* arquivos compartilhados;
* arquivos pertencentes ao parent;
* arquivos pertencentes a outras máquinas.

---

# 6. DATASET MAME

O executável do MAME é a autoridade sobre a versão do dataset.

Fluxo:

```text
MAME.EXE
   ↓
detecção da versão
   ↓
-listxml
   ↓
XML
   ↓
parser
   ↓
SQLite
```

Datasets de versões diferentes do MAME não devem ser misturados.

Sempre que possível, registrar:

* versão;
* build;
* origem;
* caminho do executável;
* fingerprint/hash do dataset;
* data de geração.

---

# 7. LISTXML

O `listxml` é a principal fonte estrutural de informações do MAME.

O parser deve preservar os dados necessários para:

* machines;
* descrição;
* ano;
* fabricante;
* sourcefile;
* parent/clone;
* romof;
* sampleof;
* BIOS;
* device;
* mechanical;
* runnable;
* ROMs;
* disks;
* samples;
* device references;
* drivers;
* displays;
* inputs;
* controls;
* chips;
* sound;
* slots;
* features;
* software lists;
* demais informações relevantes disponibilizadas pelo XML.

O parser deve ser eficiente e não deve introduzir dependências artificiais entre GUI e parsing.

---

# 8. FOLDERS / INI

Os arquivos `folders/*.ini` são fontes complementares.

Eles podem ser usados para:

* classificação;
* agrupamento;
* enriquecimento;
* informações que não estejam adequadamente representadas no listxml.

Nunca substituir indiscriminadamente informações estruturais do listxml por dados de INI.

---

# 9. CLASSIFICAÇÃO

A classificação deve ser separada do filtro.

Conceito:

```text
DADOS MAME
   ↓
CLASSIFICAÇÃO
   ↓
PERFIL DE FILTRO
   ↓
SELEÇÃO
```

Categorias podem incluir:

* Arcade;
* Console;
* Computer;
* Portable;
* Mechanical;
* Pinball;
* Pachinko;
* Fruit Machine;
* Quiz;
* Tabletop;
* BIOS;
* Device;
* outras categorias necessárias.

A classificação não deve depender apenas do nome da máquina.

Sempre que possível utilizar dados estruturais do MAME.

---

# 10. ARCADE

O projeto possui como um dos objetivos principais a construção de sets Arcade.

O filtro Arcade deve excluir categorias que não fazem parte do objetivo do usuário.

Entre elas podem estar:

* casino;
* quiz;
* tabletop;
* fruit machines;
* máquinas mecânicas;
* pinball;
* computadores;
* consoles;
* portáteis;
* pachinko;
* outras categorias não Arcade.

Entretanto:

**não usar exclusões textuais frágeis como única regra.**

A classificação estrutural deve ser priorizada.

---

# 11. STATUS DE EMULAÇÃO

O MAME possui estados de emulação.

O projeto deve suportar pelo menos:

```text
GOOD
IMPERFECT
PRELIMINARY
ALL
```

A seleção deve possuir semântica cumulativa quando apropriado.

Exemplo:

```text
GOOD
→ somente GOOD

IMPERFECT
→ GOOD + IMPERFECT

PRELIMINARY
→ GOOD + IMPERFECT + PRELIMINARY

ALL
→ todos
```

O status do MAME não deve ser tratado isoladamente como sinônimo de "jogo inválido".

Máquinas como:

* Sega Model 2;
* Sega Model 3;
* Naomi;
* Naomi 2;

podem ser importantes para o objetivo Arcade mesmo quando o status de emulação não for GOOD.

---

# 12. FILTROS

Filtros devem ser representados por um modelo de perfil.

A GUI não deve conter regras de negócio espalhadas em callbacks.

A GUI deve coletar as opções do usuário e produzir uma configuração de filtro.

Exemplo conceitual:

```text
FilterProfile
├── categories
├── emulation_status
├── include_clones
├── include_bios
├── include_devices
├── include_samples
├── include_disks
├── include_chds
└── outras opções
```

O filtro deve ser executado pela camada responsável pela regra de negócio.

---

# 13. GUI

A GUI atual possui diferentes áreas funcionais, incluindo:

* diretórios;
* filtros;
* filtros em tempo real;
* home;
* scan de ROMs.

A GUI deve ser tratada como camada de apresentação.

Ela:

* coleta entradas;
* exibe resultados;
* apresenta progresso;
* apresenta erros;
* dispara operações;
* não deve duplicar regras do domínio.

---

# 14. SCAN DE ROMS

O scanner é uma parte central da implementação atual.

O objetivo do scan é analisar o armazenamento físico e criar uma representação confiável dos arquivos encontrados.

O scanner deve:

* localizar arquivos;
* reconhecer formatos;
* registrar tamanho;
* registrar extensão;
* identificar ZIP;
* identificar 7Z;
* identificar CHD;
* analisar membros de arquivos compactados quando aplicável;
* coletar CRC quando disponível;
* coletar SHA1 quando necessário;
* identificar possíveis correspondências com ROMs do dataset;
* produzir resultados estruturados;
* informar progresso;
* permitir cancelamento;
* evitar bloquear a interface.

O resultado do scanner deve ser representado por modelos próprios.

O `ScanResult` é parte da arquitetura atual e não deve ser substituído por estruturas improvisadas dentro da GUI.

---

# 15. SCAN E DATABASE

O scanner não deve possuir regras SQL espalhadas pela GUI.

A responsabilidade deve ser separada:

```text
GUI
 ↓
Scanner
 ↓
Modelos
 ↓
Database / Repository
```

Quando uma operação precisar persistir dados, utilizar a camada de banco apropriada.

Não criar SQL duplicado em múltiplos arquivos.

---

# 16. DATABASE

SQLite é o banco principal da aplicação.

O schema atual do projeto é a autoridade para a implementação do banco.

Antes de alterar qualquer tabela:

1. consultar o schema atual;
2. consultar repositories;
3. consultar modelos;
4. consultar consumidores;
5. identificar impacto;
6. somente então alterar.

Não assumir que o schema descrito em documentação antiga ainda corresponde ao banco atual.

---

# 17. MODELOS

Os modelos atuais incluem, entre outros:

```text
category.py
disk.py
filter_profile.py
ini_models.py
machine.py
mame_installation.py
rom.py
scan_result.py
```

Os modelos devem representar entidades reais do domínio.

Não criar estruturas paralelas para representar a mesma entidade.

Se existir um modelo consolidado, reutilizá-lo.

---

# 18. ROMS

Uma ROM deve ser tratada como um artefato com identidade própria.

Informações importantes podem incluir:

* nome;
* tamanho;
* CRC;
* SHA1;
* merge;
* região;
* offset;
* status;
* optional;
* BIOS;
* machine relacionada.

A existência de um arquivo ZIP não significa automaticamente que todas as ROMs necessárias para determinada machine estão presentes.

---

# 19. DEPENDÊNCIAS

O projeto deve evoluir para um sistema de resolução de dependências.

Uma seleção:

```text
Machine
```

pode resultar em:

```text
ROM
BIOS
Device
Sample
Disk
CHD
Shared dependency
Parent
Clone
```

A seleção lógica deve ser separada da resolução física dos arquivos.

---

# 20. FULLSET

O FULLSET é a fonte física principal para auditoria e construção.

Regra absoluta:

**O FULLSET é somente leitura.**

O software nunca deve:

* apagar;
* mover;
* renomear;
* sobrescrever;
* modificar;
* reconstruir diretamente no FULLSET.

---

# 21. MEU SET

O "Meu Set" é o conjunto de destino.

Ele deve ser:

* independente;
* reconstruível;
* descartável;
* gerado a partir de uma seleção;
* gerado a partir das dependências resolvidas.

Fluxo:

```text
FULLSET
   ↓
SELEÇÃO
   ↓
DEPENDÊNCIAS
   ↓
MANIFEST
   ↓
MEU SET
```

---

# 22. AUDITORIA

A auditoria deve responder perguntas como:

* arquivo existe?
* tamanho está correto?
* CRC está correto?
* SHA1 está correto?
* ROM esperada existe?
* ROM está dentro do arquivo correto?
* arquivo está corrompido?
* arquivo está sobrando?
* dependência está ausente?
* CHD está presente?
* BIOS necessária está presente?

Estados possíveis:

```text
PRESENT
MISSING
WRONG
CORRUPTED
EXTRA
```

---

# 23. ZIP / 7Z / CHD

O projeto deve suportar:

```text
ZIP
7Z
CHD
```

A lógica de domínio não deve depender diretamente de uma implementação específica de biblioteca quando isso puder ser evitado.

A implementação atual deve ser preservada e evoluída incrementalmente.

---

# 24. Merged / Split / Non-Merged

O projeto deve reconhecer os três modelos:

```text
NON-MERGED
SPLIT
MERGED
```

A política de clones depende do tipo de set.

No modo MERGED, não assumir que um clone pode ser simplesmente removido como se fosse um arquivo independente.

A lógica deve considerar a composição física real do conjunto.

---

# 25. GERAÇÃO DE XML

A geração de XML filtrado é uma funcionalidade importante.

O XML gerado deve ser consequência de:

```text
Dataset
 ↓
Filter Profile
 ↓
Selected Machines
 ↓
XML Export
```

Não reconstruir o dataset diretamente na GUI.

O exportador deve utilizar os dados persistidos e/ou modelos apropriados.

---

# 26. PERFIL DE FILTRO

O usuário deve conseguir criar uma configuração que represente algo como:

```text
Nome:
Meu Arcade

Categorias:
Arcade

Emulação:
Preliminary

Clones:
Excluir

BIOS:
Incluir

Devices:
Incluir

Samples:
Configuração definida pelo usuário

CHDs:
Incluir
```

O perfil deve ser persistível e reutilizável.

---

# 27. PERFORMANCE

A prioridade de otimização é:

1. evitar trabalho desnecessário;
2. operações eficientes no SQLite;
3. parsing eficiente;
4. processamento em lote;
5. cache;
6. paralelização quando comprovadamente vantajosa.

Não paralelizar apenas por existir CPU multicore.

Não utilizar GPU como requisito.

Sempre que houver otimização relevante:

**medir antes e depois.**

---

# 28. THREADS E GUI

Operações pesadas não devem bloquear a interface.

Especialmente:

* geração de listxml;
* parsing;
* scan de arquivos;
* análise de arquivos compactados;
* SHA1;
* auditoria;
* operações de banco em grande escala.

A GUI deve permanecer responsiva.

Progresso e cancelamento devem ser tratados de maneira segura.

---

# 29. REGRAS DE COMPATIBILIDADE

Ao modificar um arquivo:

* preservar funções existentes;
* preservar funcionalidades ativas;
* preservar APIs internas utilizadas por outros módulos;
* preservar comportamento válido;
* atualizar consumidores quando uma assinatura precisar mudar.

Não remover uma função apenas porque ela parece redundante sem verificar todos os usos.

Uma função pode ser:

* usada diretamente;
* usada por callback;
* usada por testes;
* usada por outro módulo;
* necessária para compatibilidade.

---

# 30. REGRA PARA FUNÇÕES LEGADAS

Uma função somente deve ser removida quando houver evidência de que:

* está realmente inativa;
* está quebrada;
* é substituída por outra implementação;
* não possui consumidores;
* sua remoção não quebra compatibilidade.

Quando houver dúvida:

**preservar e documentar.**

---

# 31. DEBUG E CORREÇÕES

Ao corrigir um erro:

1. reproduzir ou analisar o erro;
2. localizar a origem;
3. consultar os consumidores;
4. verificar o modelo/database envolvido;
5. corrigir a causa;
6. verificar efeitos colaterais;
7. atualizar testes quando aplicável.

Não corrigir apenas o sintoma na GUI.

---

# 32. DOCUMENTAÇÃO

A documentação deve acompanhar a implementação.

Quando uma alteração arquitetural significativa ocorrer, atualizar:

* README;
* documentação técnica correspondente;
* modelos;
* schema;
* fluxo;
* instruções para IA, quando necessário.

Documentação antiga não deve permanecer descrevendo uma arquitetura inexistente.

---

# 33. WEB E DOCUMENTAÇÃO EXTERNA

Para bibliotecas ou APIs externas:

* consultar documentação oficial atual;
* verificar mudanças de versão;
* verificar APIs depreciadas;
* verificar compatibilidade com a versão instalada.

Para MAME:

* priorizar documentação oficial;
* considerar o comportamento real da versão do MAME usada pelo usuário.

---

# 34. REPOSITÓRIO GITHUB

Para qualquer tarefa relevante:

```text
1. Consultar GitHub
2. Identificar estado atual
3. Identificar arquivos envolvidos
4. Identificar dependências
5. Alterar somente o necessário
6. Testar
7. Atualizar documentação
```

Nunca desenvolver uma solução assumindo que o código é igual ao de uma conversa anterior.

---

# 35. FASE ATUAL DO DESENVOLVIMENTO

A prioridade atual é:

## FASE A — CONSOLIDAÇÃO

Consolidar:

* database;
* models;
* listxml parser;
* ROM scanner;
* ScanResult;
* GUI de Scan;
* integração entre scanner e banco;
* filtros;
* geração de XML.

## FASE B — SCAN FUNCIONAL

Garantir:

```text
FULLSET
 ↓
SCAN
 ↓
INDEXAÇÃO
 ↓
DATABASE
 ↓
RESULTADOS
```

com:

* progresso;
* cancelamento;
* tratamento de erros;
* resultados confiáveis;
* persistência correta.

## FASE C — AUDITORIA

Depois:

```text
DATABASE
 ↓
EXPECTED FILES
 ↓
LOCAL SCAN
 ↓
AUDIT
 ↓
MISSING / WRONG / CORRUPTED / EXTRA
```

## FASE D — DEPENDENCY RESOLUTION

Depois:

```text
SELECTED MACHINES
 ↓
DEPENDENCY RESOLUTION
 ↓
REQUIRED FILES
```

## FASE E — SET BUILDER

Depois:

```text
REQUIRED FILES
 ↓
SET MANIFEST
 ↓
MEU SET
```

## FASE F — QBITTORRENT

Somente após o fluxo local estar confiável:

```text
MISSING FILES
 ↓
TORRENT METADATA
 ↓
MATCHING
 ↓
DOWNLOAD
```

## FASE G — FUNCIONALIDADES FUTURAS

Posteriormente:

* rebuild;
* Merged/Split/Non-Merged avançado;
* criação de torrents subset;
* Software Lists;
* funcionalidades avançadas de automação.

---

# 36. O QUE NÃO FAZER AGORA

Não implementar prematuramente:

* arquitetura `src/` completamente nova;
* Software Lists completos;
* Torrent Builder;
* reconstrução avançada de sets;
* qBittorrent complexo;
* funcionalidades que ainda não possuem base no banco;
* abstrações gigantescas sem necessidade.

Primeiro consolidar o que já existe.

---

# 37. PRINCÍPIO DE DESENVOLVIMENTO INCREMENTAL

Cada alteração deve ser pequena o suficiente para ser validada.

Fluxo recomendado:

```text
AUDITAR
 ↓
PLANEJAR
 ↓
ALTERAR
 ↓
TESTAR
 ↓
VALIDAR
 ↓
DOCUMENTAR
 ↓
COMMIT
```

Não alterar dezenas de arquivos sem necessidade.

---

# 38. TESTES

Testes devem existir progressivamente para:

* parser;
* models;
* database;
* filtros;
* classificação;
* scanner;
* auditoria;
* geração de XML;
* integração.

Testes de integração são especialmente importantes para garantir que mudanças no database não quebrem:

```text
parser → database → filtro → GUI → exportação
```

---

# 39. REGRA ESPECIAL PARA DATABASE

Sempre que o schema mudar:

auditar obrigatoriamente:

```text
models
repositories
parsers
scanners
filters
GUI
exportadores
testes
```

Nenhuma alteração de schema deve ser considerada isolada.

---

# 40. REGRA ESPECIAL PARA SCAN

O scanner deve ser tratado como serviço de domínio/aplicação.

A GUI não deve implementar:

* cálculo de SHA1;
* leitura de ZIP;
* interpretação de CHD;
* descoberta de ROM;
* regras de matching;
* SQL de persistência.

A GUI somente coordena e apresenta.

---

# 41. REGRA ESPECIAL PARA ScanResult

`ScanResult` representa o resultado estruturado de uma operação de scan.

Ele deve permitir que:

* scanner;
* worker;
* GUI;
* banco;
* testes;

compartilhem uma representação consistente do resultado.

Evitar retornar dicionários anônimos diferentes entre funções.

---

# 42. REGRA ESPECIAL PARA MAME

Nunca assumir que:

```text
nome.zip
```

é suficiente para representar uma machine.

O MAME possui relações de:

* parent;
* clone;
* ROM merge;
* BIOS;
* device;
* sample;
* disk;
* CHD;
* dependências compartilhadas.

Essas relações precisam ser respeitadas.

---

# 43. REGRA ESPECIAL PARA CLONES

Clone é entidade lógica própria.

Não apagar clones simplesmente porque o usuário selecionou "somente parent" sem considerar:

* tipo de set;
* merge;
* dependências;
* arquivos compartilhados.

---

# 44. REGRA ESPECIAL PARA BIOS E DEVICES

BIOS e devices não são jogos.

Porém podem ser obrigatórios.

Portanto:

```text
não selecionado como jogo
≠
desnecessário
```

A seleção de jogos e a resolução das dependências são etapas diferentes.

---

# 45. REGRA ESPECIAL PARA CHD

CHD não deve ser tratado simplesmente como ZIP ou ROM.

Modelar separadamente:

```text
ROM
DISK
CHD
```

e preservar a relação com a machine correspondente.

---

# 46. CRITÉRIO DE QUALIDADE

Uma implementação só deve ser considerada concluída quando:

* funciona;
* está integrada ao restante do projeto;
* não quebra funcionalidades existentes;
* utiliza o modelo atual;
* utiliza o schema atual;
* possui tratamento de erros;
* possui logs adequados;
* possui testes quando aplicável;
* está documentada.

---

# 47. COMO A IA DEVE TRABALHAR NO PROJETO

Ao receber uma solicitação:

## Primeiro

Consultar o GitHub atual.

## Segundo

Identificar:

* arquivo;
* função;
* dependências;
* modelo;
* tabela;
* consumidor;
* impacto.

## Terceiro

Explicar brevemente o que será alterado.

## Quarto

Implementar.

## Quinto

Verificar compatibilidade.

## Sexto

Informar quais arquivos foram alterados e por quê.

---

# 48. REGRA CONTRA ALUCINAÇÃO DE ARQUITETURA

Nunca criar:

* tabelas inexistentes;
* modelos inexistentes;
* funções inexistentes;
* APIs inexistentes;
* módulos inexistentes;

como se já fizessem parte do projeto.

Se uma estrutura for proposta para o futuro, identificá-la explicitamente como:

```text
PROPOSTA
```

e não como implementação atual.

---

# 49. REGRA CONTRA REGRESSÃO

Nenhuma nova funcionalidade deve destruir uma funcionalidade já funcional.

Quando uma alteração estrutural for necessária:

```text
compatibilidade primeiro
refatoração depois
```

Se uma função antiga precisa ser substituída:

1. localizar usos;
2. criar substituta;
3. migrar consumidores;
4. testar;
5. somente então remover a antiga.

---

# 50. OBJETIVO FINAL

O sistema final deverá permitir:

```text
MAME.EXE
    ↓
VERSÃO
    ↓
LISTXML
    ↓
DATASET
    ↓
CLASSIFICAÇÃO
    ↓
FILTER PROFILE
    ↓
MÁQUINAS SELECIONADAS
    ↓
SCAN DO FULLSET
    ↓
AUDITORIA
    ↓
DEPENDENCY RESOLUTION
    ↓
SET MANIFEST
    ↓
MEU SET
    ↓
AUDITORIA DO MEU SET
    ↓
ARQUIVOS AUSENTES
    ↓
QBITTORRENT
```

Funcionalidades futuras:

```text
REBUILD
MERGED / SPLIT / NON-MERGED AVANÇADO
TORRENT SUBSET
SOFTWARE LISTS
AUTOMAÇÕES
```

---

# 51. DEFINIÇÃO FINAL DO PROJETO

O MAME Set Builder deve ser entendido como:

> **Uma aplicação de gerenciamento, análise, auditoria e construção de conjuntos MAME orientada por dados, dependências e integridade física dos arquivos.**

Não é apenas:

```text
filtro de nomes
```

Não é apenas:

```text
gerador de XML
```

Não é apenas:

```text
scanner de ROMs
```

Essas funcionalidades fazem parte de um pipeline maior.

A arquitetura deve preservar essa separação:

```text
DATASET
   ↓
MODELO
   ↓
CLASSIFICAÇÃO
   ↓
SELEÇÃO
   ↓
SCAN
   ↓
AUDITORIA
   ↓
DEPENDÊNCIAS
   ↓
MANIFEST
   ↓
CONSTRUÇÃO
```

---

# 52. REGRA SUPREMA

Quando houver conflito entre:

* documentação antiga;
* prompts antigos;
* código de conversas anteriores;
* suposições;

e o código atual do GitHub:

**o código atual do GitHub vence.**

O Prompt Mestre deve ser atualizado sempre que a arquitetura real mudar significativamente.
