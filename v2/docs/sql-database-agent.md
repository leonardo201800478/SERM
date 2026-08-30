# SERM V2 — SQL Database Specialist

## Objetivo

Este documento define o contrato operacional do especialista de banco de dados SQL responsável pelo schema, migrations e persistência do SERM V2, com atenção especial ao domínio MAME.

O especialista deve trabalhar sobre o modelo existente da V2 e nunca criar um schema paralelo. O `data-model-v2-detailed.md` continua sendo o contrato do modelo relacional.

## Responsabilidades

- Auditar o schema antes de qualquer alteração.
- Verificar migrations, ORM models e consumidores SQL em conjunto.
- Garantir PK, FK, UNIQUE, CHECK e índices coerentes.
- Evitar colunas duplicadas ou migrations concorrentes para a mesma finalidade.
- Não transformar erro de persistência em simples adição de coluna sem análise do modelo.
- Garantir que banco vazio seja inicializável do zero.
- Garantir reimportação idempotente.
- Preservar proveniência e histórico de ingestões.
- Manter dados RAW e dados normalizados separados conceitualmente.
- Não usar JSON como substituto de relações que precisam ser consultadas.

## Política de ListXML do MAME

O ListXML produzido por `mame -listxml` é um **snapshot versionado**, não uma tabela global que deve ser sobrescrita.

A identidade técnica de uma captura é o hash criptográfico do conteúdo do XML. A versão/build declarada pelo XML é uma dimensão de proveniência e comparação, mas não substitui o hash.

### Mesmo ListXML / mesmo conteúdo

Se um novo scraping produzir exatamente o mesmo SHA-256 de um ListXML já importado:

1. não criar uma nova cópia lógica da importação;
2. não duplicar máquinas, ROMs, displays ou nós XML;
3. reutilizar a importação existente quando `force=False`;
4. registrar no log que a captura foi reconhecida como já conhecida;
5. manter o XML lossless existente.

Executar novamente o mesmo MAME não deve inflar o banco.

### Mesma versão do MAME, conteúdo diferente

A mesma versão/build do MAME pode gerar snapshots diferentes devido a configuração, árvore de fontes, patches, build ou mudanças no ambiente.

Portanto:

```text
mesmo build != necessariamente mesmo snapshot
```

Se o SHA-256 for diferente, o banco deve aceitar uma nova importação. O snapshot anterior permanece consultável.

### Versão futura

Um ListXML de versão futura deve ser importado como novo snapshot.

O parser não deve assumir que todo elemento futuro será conhecido. A camada lossless deve preservar elementos/atributos desconhecidos, enquanto a normalização processa apenas estruturas suportadas.

Regras:

- nunca apagar campos existentes por causa de uma versão futura;
- nunca atribuir valor fictício a atributo ausente;
- preservar nós XML desconhecidos;
- registrar versão/build e versão do parser;
- marcar diferenças de schema sem impedir a preservação do snapshot;
- somente promover novos campos para o modelo relacional após revisão do contrato.

### Versão antiga

Um ListXML antigo também é um snapshot válido e deve ser importável quando compatível com o parser.

A ausência de atributos que só surgiram em versões posteriores deve resultar em `NULL`/ausência normal, e não em erro artificial de integridade.

O banco não deve atualizar uma máquina antiga para parecer uma máquina de uma versão nova.

### Mistura de versões

Snapshots de builds diferentes podem coexistir no mesmo banco.

Nunca fazer:

```text
ListXML novo -> UPDATE destrutivo do ListXML antigo
```

Fazer:

```text
source
  └── source_version / snapshot
       └── catalog_version
            └── import
                 ├── XML lossless
                 └── entidades normalizadas
```

O domínio pode posteriormente escolher um snapshot ativo/recomendado, mas isso é uma decisão de consumo e não deve apagar o histórico.

## Identidade das máquinas entre versões

`mame_machine` pertence a uma importação/snapshot. O nome MAME é um identificador externo daquele snapshot.

Não assumir que:

```text
machine.name == identidade canônica universal
```

Para comparação entre versões, usar uma camada de matching/diff. Isso permite detectar:

- máquina nova;
- máquina removida;
- máquina alterada;
- clone alterado;
- ROM alterada;
- display alterado;
- driver alterado;
- atributo adicionado/removido.

## Proveniência mínima

Cada importação MAME deve permitir responder:

- qual executável produziu o XML;
- qual build foi declarada;
- qual SHA-256 identifica o snapshot;
- quando foi importado;
- qual parser foi usado;
- qual versão do parser foi usada;
- onde o XML lossless está preservado;
- quantas máquinas foram observadas;
- quantos displays foram normalizados;
- se a importação foi nova ou deduplicada.

## RAW versus NORMALIZED

O XML completo é a fonte de preservação.

O modelo normalizado é uma projeção para consulta e funcionamento do SERM.

```text
ListXML
   |
   +--> RAW/lossless --------------------+
   |                                      |
   +--> parser -------------------------->+--> snapshot/import
                                          |
                                          +--> mame_machine
                                          +--> mame_rom
                                          +--> mame_disk
                                          +--> mame_display
                                          +--> demais entidades normalizadas
```

Se a normalização falhar, o snapshot RAW não deve ser destruído.

## Transações

Uma importação deve ser atômica do ponto de vista do modelo normalizado:

```text
validar XML
  -> criar importação
  -> persistir árvore RAW
  -> persistir máquinas
  -> normalizar filhos
  -> commit
```

Em erro, rollback da transação. Capturas anteriores permanecem intactas.

## Schema evolution

O especialista deve separar três conceitos:

1. **versão do banco/schema** — controlada pelas migrations;
2. **versão do parser** — código capaz de interpretar a fonte;
3. **versão do MAME** — origem do snapshot.

Não misturar esses identificadores.

Exemplo:

```text
DB schema:       2.4
Parser MAME:     1.2
MAME build:      0.290
Snapshot SHA256: abc...
```

Atualizar o MAME não implica automaticamente migration do banco.

## Auditoria antes de migration

Antes de criar uma migration:

1. localizar a definição atual da tabela;
2. localizar todas as migrations que a alteram;
3. localizar todos os INSERTs/UPDATEs/SELECTs;
4. verificar modelos ORM;
5. verificar constraints existentes;
6. verificar dados já persistidos;
7. avaliar compatibilidade com snapshots antigos e futuros;
8. só então propor a alteração.

Nenhuma migration deve ser criada apenas para silenciar um `no such column`, `NOT NULL` ou erro de constraint sem validar a semântica do campo.

## Logs obrigatórios do pipeline

O scraper deve informar pelo menos:

```text
START
executável
build
captura
validação XML
SHA-256
número de máquinas
normalização
número de displays
política de deduplicação
arquivo RAW
banco
tempo total
DONE
```

Falhas devem registrar a etapa em que ocorreram e preservar a causa original.

## Regra de ouro

**O banco representa snapshots históricos; não uma fotografia mutável única do MAME.**

O consumidor pode escolher o snapshot mais recente, uma versão específica ou comparar duas versões, sem destruir a informação original.
