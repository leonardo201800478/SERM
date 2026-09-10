# Roadmap da V2

Este documento é a fonte de planejamento macro da V2. O status deve refletir o código existente e os testes executados; auditorias antigas não são tratadas como funcionalidades concluídas.

## Estado atual — setembro de 2026

A V2 possui uma fundação funcional e uma base MAME significativamente validada, mas **ainda não é uma versão de produção**. A prioridade atual é fechar o ciclo completo **catálogo → scan → matching → reconstrução → materialização → execução** antes de ampliar integrações ou otimizações.

## Concluído e validado

### Fundação

- estrutura independente da V2;
- empacotamento e entry points;
- configuração/runtime paths;
- SQLite + SQLAlchemy;
- infraestrutura de migrations;
- testes e tooling de qualidade.

### Catálogo MAME

- ingestão e normalização de ListXML;
- classificação e filtros MAME;
- proveniência de fontes de classificação;
- dados de resolução/display/VSync;
- auditorias estruturais do catálogo;
- auditorias de relações parent/clone/romof;
- auditoria de identidade física;
- auditoria de dependências;
- auditoria de duplicatas representacionais.

A base auditada contém 50.368 máquinas e 179.667 relações `merge`. A auditoria do planner real foi fechada com 0 divergências:

```text
SELF       167.637
MERGED      12.030
PARENT           0
ROMOF            0
MISSING          0
DIVERGÊNCIAS     0
```

### Reconstrução MAME — camada lógica

- `ArcadeRomReconstructionPlanner`;
- distinção entre nome de máquina e nome de ROM;
- `merge` tratado como nome de ROM;
- resolução restrita a machine set atual e relações explicitamente relacionadas;
- resolução determinística de duplicatas com identidade física idêntica;
- preservação de ambiguidade quando a identidade física conflita;
- `ArcadeRomReconstructionEngine`;
- matching físico SHA1 → MD5 → CRC+size;
- manifesto de materialização;
- proteção contra colisão de múltiplas ROMs por máquina;
- reconstrução CHD em pipeline separado;
- planejamento SPLIT/NON_MERGED/FULL_MERGED.

### Testes de reconstrução

As suítes executadas no ambiente-alvo nesta etapa confirmaram:

- 1 teste de manifesto com múltiplas ROMs;
- 31 testes da suíte integrada de reconstrução/materialização;
- planner real MAME: 1 passed, 14,00 s;
- casos semânticos de `merge`: 10 passed;
- amostra dirigida do catálogo real: 1 passed, 17,44 s.

## Em desenvolvimento — ordem obrigatória

### Meta 1 — Fechar o contrato do scan MAME

**Objetivo:** garantir que a evidência física produzida pelo scanner seja suficiente para alimentar a reconstrução sem heurísticas.

Entregáveis:

- validar todos os estados físicos (`valid`, `missing`, `invalid`, `error`);
- separar explicitamente estado físico de estado documental MAME (`good`, `baddump`, `nodump`);
- validar matching por identidade em catálogo real;
- validar persistência e retomada do scan;
- fechar auditoria de candidatos ambíguos;
- documentar o contrato scan → reconstruction.

**Critério de saída:** um scan MAME completo pode produzir evidência determinística para o planner sem depender da GUI.

### Meta 2 — Fechar dependências MAME

**Objetivo:** transformar parent/clone, `romof`, `merge`, BIOS, devices e samples em um grafo de dependências auditável.

Entregáveis:

- consolidar resolução de BIOS;
- consolidar resolução de device sets;
- definir tratamento de samples;
- validar cadeias parent/clone profundas;
- detectar ciclos e referências inexistentes;
- impedir dependências implícitas não suportadas.

**Critério de saída:** qualquer dependência necessária tem origem explícita, estado e motivo de resolução.

### Meta 2.1 — Aquisição controlada de recursos externos

Esta meta é **subordinada às metas 1 e 2** e não altera a ordem de autoridade do catálogo MAME. O objetivo é eliminar a aquisição manual de recursos auxiliares sem permitir que um provider externo contorne scan, dependências ou reconstrução.

Implementação iniciada:

- `ExternalResource` para identidade/versionamento de pacotes externos;
- `ExternalResourceCatalog` para deduplicação por provider/plataforma/nome/versão;
- `ProgettoSnapsProvider` isolando URLs e layout do site;
- `DownloadManager` com cache, download atômico e extração protegida contra path traversal;
- mapeamento dos pacotes selecionados `CatVer`, `BestGames`, `Series`, `Languages`, `GameInit` e `Command`;
- mapeamento do `MAME Samples FullPack 0.289`;
- separação entre `dats/`, `folders/`, `samples/` e metadados do SERM;
- instalação conservadora: `CREATE`, `REUSE`, `REPLACE` explícito ou `BLOCK` em conflito;
- testes automatizados do catálogo, extração e conflitos de destino.

Ainda pendente nesta meta:

- descoberta automática da versão mais recente publicada pelo provider;
- validação do conteúdo real do FullPack e de seus membros;
- persistência do catálogo adquirido;
- integração com os diretórios configurados pelo usuário;
- ligação entre aquisição e grafo de dependências MAME;
- atualização incremental baseada em conteúdo, e não apenas em versão;
- integração com a GUI do Download Manager.

**Critério de saída:** o SERM consegue adquirir um recurso externo, validá-lo, extrair somente o conteúdo mapeado e publicar no destino MAME sem sobrescrever silenciosamente um arquivo existente.

### Meta 3 — Fechar materialização física

**Objetivo:** transformar o manifesto em arquivos reais sem corromper a origem.

Entregáveis:

- integração definitiva do `Materializer` com `ReconstructionManifest`;
- ZIP/arquivo por layout;
- staging temporário;
- validação antes da publicação;
- publicação atômica;
- retry seguro;
- prevenção de path traversal;
- verificação pós-publicação;
- logs e relatório de materialização.

**Critério de saída:** um conjunto selecionado pode ser reconstruído em diretório de destino e validado novamente pelo SERM.

### Meta 4 — Validar layouts contra MAME real

**Objetivo:** provar que SPLIT, NON_MERGED e FULL_MERGED produzem exatamente os componentes esperados.

Entregáveis:

- fixtures de famílias parent/clone reais;
- comparação do manifesto entre os três layouts;
- cobertura de ROM compartilhada;
- cobertura de ROM exclusiva;
- cobertura de CHD;
- cobertura de BIOS/device;
- auditoria de deduplicação e conflitos.

**Critério de saída:** nenhuma dependência compartilhada é duplicada em SPLIT e nenhuma dependência necessária é perdida nos demais layouts.

### Meta 5 — Integração do Arcade Studio

**Objetivo:** ligar catálogo, filtros, scan, reconstrução e manifesto à GUI sem mover regras de negócio para a apresentação.

Entregáveis:

- seleção de máquinas após filtros;
- resumo de dependências;
- prévia do manifesto;
- indicadores de `SELF`, `MERGED`, `PARENT`, `ROMOF`, `MISSING`;
- indicadores de evidência física;
- ação explícita de reconstrução;
- histórico de execuções;
- tratamento de erro sem bloquear a interface.

**Critério de saída:** o usuário consegue selecionar um conjunto, revisar o plano e iniciar uma reconstrução sem acesso manual ao banco.

### Meta 6 — Execução e perfis

**Objetivo:** somente depois da reconstrução estar confiável, integrar os artefatos aos emuladores.

Entregáveis:

- perfis de execução;
- associação set → emulador;
- caminhos gerados;
- argumentos e configurações;
- validação de executável;
- execução controlada e logs.

### Meta 7 — Consolidação e performance

**Objetivo:** otimizar somente após os contratos estarem estáveis.

Entregáveis:

- benchmarks de scan;
- benchmarks de matching;
- profiling de SQLite;
- paralelismo onde não comprometer I/O;
- cache seguro;
- redução de trabalho redundante.

## Fora da prioridade imediata

- novos adapters de sistemas externos, além do provider Progetto-SNAPS já iniciado como infraestrutura controlada;
- refinamentos cosméticos da GUI;
- aceleração por GPU sem gargalo comprovado;
- otimizações prematuras do scanner;
- funcionalidades periféricas de aquisição além da Meta 2.1.

## Critério de conclusão da V2

Uma capacidade só pode sair de desenvolvimento quando:

1. existe implementação V2 real;
2. existe teste automatizado apropriado;
3. caminhos de erro relevantes são cobertos;
4. persistência e estado são consistentes;
5. a GUI apenas coordena/apresenta;
6. a documentação corresponde ao código;
7. quando aplicável, a capacidade é validada contra dados reais e no ambiente-alvo.

## Sequência técnica oficial

```text
CATÁLOGO E IDENTIDADE
        ↓
SCAN FÍSICO CONFIÁVEL
        ↓
DEPENDÊNCIAS MAME
        ↓
PLANO DE RECONSTRUÇÃO
        ↓
MANIFESTO
        ↓
MATERIALIZAÇÃO ATÔMICA
        ↓
VALIDAÇÃO DO DESTINO
        ↓
EXECUÇÃO
        ↓
OTIMIZAÇÃO
```

**Próxima meta imediata: Meta 1 — fechar o contrato do scan MAME.**
