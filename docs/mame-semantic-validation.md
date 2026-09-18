# SERM V2 — Validação Semântica do Catálogo MAME

Este documento registra as validações semânticas e relacionais usadas para preservar a correção do pipeline MAME da V2. Ele existe para permitir regressões futuras, correções de código e novas importações sem depender da memória de uma auditoria anterior.

## 1. Regra de autoridade

O **ListXML MAME importado** é a fonte estrutural para máquinas, ROMs, discos e relações de herança. As classificações provenientes de INIs devem respeitar sua proveniência: uma classificação não deve ser tratada como `CATLIST` apenas porque possui o mesmo texto em outra fonte.

A cadeia conceitual é:

```text
ListXML / CATLIST / outras fontes
        ↓
catálogo normalizado
        ↓
identidade lógica
        ↓
relação de herança
        ↓
evidência física (SHA1/MD5/CRC+size)
        ↓
reconstrução
```

Nenhuma etapa posterior deve substituir uma relação explícita anterior por uma inferência apenas baseada em nome.

## 2. Auditorias existentes

| Auditoria | Objetivo | Regra principal |
|---|---|---|
| `tests/test_database_xml_audit.py` | integridade estrutural geral | detectar inconsistências do banco/catálogo |
| `tests/test_mame_filter_semantic_audit.py` | cardinalidade e proveniência | agregar relações 1:N independentemente e validar CATLIST |
| `tests/test_mame_folder_semantic_audit.py` | semântica dos filtros de pasta | distinguir polaridades reais de facetas independentes |
| `tests/test_mame_rom_semantic_audit.py` | estrutura de ROM/disco | medir herança, identidade, merge e referências |
| `tests/test_mame_rom_dependency_audit.py` | dependências lógicas | resolver merge/romof/cloneof antes da reconstrução |
| `tests/test_mame_rom_catalog_semantics.py` | invariantes do catálogo | impedir inferências globais não autorizadas |
| `tests/test_mame_rom_reconstruction_plan.py` | regras do planejador | testar SELF/PARENT/ROMOF/MERGED/MISSING |
| `tests/test_mame_rom_merge_relation_audit.py` | relação real do `merge` | classificar destino por relação e comparar identidade |

As auditorias são predominantemente **read-only**. Uma auditoria não deve alterar o banco para corrigir o que encontrou.

## 3. Proveniência de classificação

A consulta de classificação do filtro MAME deve restringir a origem à fonte `source_type='catlist'` quando o contrato for especificamente CATLIST.

Isso evita misturar classificações equivalentes vindas de outros INIs ou fontes externas.

Validação registrada:

- classificações existentes em qualquer fonte: `37.995`;
- classificações somente CATLIST: `37.995`;
- classificações CATLIST múltiplas: `0`.

O fato de esses números coincidirem é evidência da base auditada, não uma autorização para remover a restrição de proveniência.

## 4. Cardinalidade relacional

MAME possui várias relações 1:N, especialmente ROMs, discos, samples, BIOS, devices, chips, controles e displays. Fazer vários `JOIN`s 1:N diretamente na mesma consulta pode produzir multiplicação cartesiana:

```text
ROM × CHIP × DISPLAY × INPUT × ...
```

A regra implementada no filtro é:

1. selecionar a população-base de máquinas;
2. agregar cada relação 1:N separadamente por `machine_id`;
3. juntar somente os resultados agregados à população-base.

A auditoria deve continuar reportando a cardinalidade real das relações, mas o serviço não pode multiplicá-la durante a aplicação dos filtros.

Baseline da auditoria:

- máquinas: `50.368`;
- relações 1:N potencialmente ambíguas: `105.721`.

## 5. Semântica dos filtros de pasta

Somente os pares abaixo foram considerados polaridades semânticas reais na base auditada:

- `working` × `not_working`;
- `mechanical` × `non_mechanical`;
- `mature` × `not_mature`;
- `bootleg` × `non_bootleg`.

Nenhum desses pares apresentou sobreposição na auditoria.

Por outro lado, **artwork** e **artwork_necessary** são facetas diferentes e podem coexistir. Da mesma forma, `CHD Working` e `CHD (no BIOS)` não são complementos lógicos.

Portanto, não implementar genericamente `A = not B` apenas porque dois nomes parecem opostos.

Baseline:

```text
WORKING       + 13.420 / - 292 / overlap 0
MECHANICAL    + 15.839 / - 21.053 / overlap 0
MATURE        + 811 / - 37.184 / overlap 0
BOOTLEG       + 2.038 / - 41.027 / overlap 0
ARTWORK       + 2.230 / - 15.474 / overlap 446
CHD           + 365 / - 1.262 / overlap 365
```

Os dois últimos números de overlap são esperados porque os pares não representam polaridades.

## 6. Identidade de ROM

Nome de máquina ou nome de ROM **não é identidade física suficiente**.

A evidência disponível no catálogo auditado inclui:

- SHA1: `365.142` registros;
- CRC: `365.142` registros;
- MD5: `0` registros;
- `merge` definido: `179.667` registros;
- `optional` explícito: `0` registros;
- BIOS associado: `64.934` registros;
- SHA1 compartilhado entre máquinas: `41.008` identidades.

O SHA1 compartilhado entre máquinas é particularmente importante: a mesma identidade física pode participar de mais de uma máquina lógica.

Para evidência física, a ordem usada pela reconstrução é:

1. SHA1;
2. MD5;
3. CRC + tamanho.

Uma correspondência somente por nome deve ser tratada como insuficiente.

## 7. Herança: cloneof, romof e merge

As relações possuem responsabilidades diferentes:

- `cloneof`: linhagem entre máquinas;
- `romof`: autoridade de herança de ROM;
- `merge`: nome da ROM que deve ser obtida de outra relação/catálogo;
- identidade criptográfica: confirma se o conteúdo corresponde.

Baseline estrutural:

- `cloneof`: `27.730` referências;
- `romof`: `29.425` referências;
- `sampleof`: `1.891` referências;
- referências `cloneof` inexistentes: `0`;
- referências `romof` inexistentes: `0`;
- referências `sampleof` inexistentes: `1.575`.

Todos os `27.730` clones auditados possuíam `romof`. Isso é uma propriedade observada da importação auditada e não deve ser transformada em regra universal sem nova evidência.

## 8. Semântica de `merge`

O valor de `merge` identifica **uma ROM**, não uma máquina. Portanto, não se deve procurar uma máquina globalmente pelo valor de `merge` e assumir que ela é a origem correta.

A resolução autorizada deve priorizar relações explícitas:

1. própria máquina (`SELF`), quando o catálogo registra um self-merge;
2. `romof`;
3. `cloneof`/parent quando aplicável;
4. somente então classificar como ausente ou ambígua, sem adivinhar uma máquina global.

A implementação do planejador usa máquinas preferenciais explícitas e não faz fallback global arbitrário.

A auditoria `test_mame_rom_merge_relation_audit.py` classifica os destinos como:

- `SELF`;
- `ROMOF`;
- `CLONEOF/PARENT`;
- `OTHER`;
- `UNRESOLVED`;
- `AMBIGUOUS`.

Ela também compara identidade por SHA1 ou, na ausência dele, por CRC + tamanho.

### Importante sobre os 12.030 merges

A auditoria de dependências encontrou `12.030` merges que não apontavam diretamente para um alvo local pela primeira relação testada, mas que eram **resolvíveis por nome dentro das relações catalogadas**. Isso não significa que os `12.030` sejam dependências válidas para reconstrução.

Eles somente podem ser considerados resolvidos após a confirmação conjunta de:

```text
relação de herança explícita
        +
ROM alvo correta
        +
identidade/hash compatível
```

## 9. Self-merge

Uma ROM cujo `merge` seja igual ao seu próprio nome não deve automaticamente gerar dependência externa.

Em sets completos, esse registro pode representar a própria ROM como origem lógica. O planejador deve classificá-lo como `SELF` quando a máquina atual for o alvo preferencial.

Há exemplos reais de self-merge na auditoria de samples/ROMs. Portanto, a presença de `merge == name` não é, por si só, erro.

## 10. Reconstrução lógica versus física

A reconstrução deve ocorrer em duas camadas:

### Camada A — plano lógico

Determina de onde a ROM deveria vir:

```text
SELF
PARENT
ROMOF
MERGED
MISSING
```

Essa camada usa relações do catálogo e não deve declarar uma ROM fisicamente presente.

### Camada B — evidência física

Procura o conteúdo real no inventário do usuário por identidade:

```text
SHA1 → MD5 → CRC + size
```

Uma dependência lógica resolvida não implica que o arquivo exista fisicamente. Da mesma forma, uma correspondência física por hash não autoriza inventar uma relação de herança que o catálogo não declarou.

## 11. Status do catálogo versus presença física

`nodump`, `not found` e estados equivalentes são metadados de disponibilidade/conhecimento do catálogo. Eles não devem ser confundidos automaticamente com resultado do scan físico do usuário.

A auditoria de dependências registrou:

- status `NOT FOUND`: `6.610`;
- `optional` explícito: `0`;
- `dispose`: `0`.

Esses números descrevem o catálogo auditado e não o conteúdo físico do usuário.

## 12. CHD

CHD é uma identidade de conteúdo de disco. O SHA1 lógico registrado no catálogo representa o conteúdo esperado do disco, e não deve ser confundido com o SHA1 do arquivo `.chd` comprimido como arquivo genérico.

Qualquer futura validação física de CHD deve preservar essa distinção.

## 13. Testes de reconstrução que devem permanecer

`test_mame_rom_reconstruction_plan.py` deve proteger pelo menos estes casos:

1. `merge` resolvido pelo parent;
2. `romof` resolvido pela máquina `romof`;
3. self-merge não cria dependência externa;
4. merge sem alvo explícito é `MISSING`;
5. nome de merge globalmente ambíguo não é escolhido por adivinhação;
6. nome globalmente único, mas sem relação explícita, também não é inferido como dependência.

O fixture deve fornecer explicitamente `platform='mame'`, pois `ArcadeRom` exige esse campo.

## 14. Ordem segura para futuras correções

Quando uma nova inconsistência for encontrada, seguir esta ordem:

1. **Fonte/proveniência** — confirmar de onde veio o dado.
2. **Cardinalidade** — confirmar se a consulta não multiplica relações 1:N.
3. **Semântica de pasta/faceta** — confirmar se filtros positivos e negativos realmente são complementares.
4. **Relação de máquina** — separar `cloneof`, `romof` e parent.
5. **Relação de ROM** — interpretar `merge` como identidade de ROM, não como nome de máquina.
6. **Identidade** — validar SHA1/MD5/CRC+size.
7. **Evidência física** — confirmar a existência real do arquivo.
8. **Reconstrução** — somente então gerar operações de cópia, merge ou publicação.

Não pular diretamente de um nome de ROM para uma operação física.

## 15. Procedimento operacional

Antes de alterar o comportamento de filtros ou reconstrução:

```powershell
cd v2
git pull
python tests/test_database_xml_audit.py
python tests/test_mame_filter_semantic_audit.py
python tests/test_mame_folder_semantic_audit.py
python tests/test_mame_rom_semantic_audit.py
python tests/test_mame_rom_dependency_audit.py
python tests/test_mame_rom_catalog_semantics.py
python tests/test_mame_rom_merge_relation_audit.py
python -m pytest tests/test_mame_rom_reconstruction_plan.py -q
```

As auditorias longas devem ser executadas separadamente quando necessário. Seus resultados devem ser registrados antes de modificar a regra de produção.

## 16. Regra de manutenção

Se uma correção alterar qualquer uma destas premissas, atualize este documento e a auditoria correspondente na **mesma mudança**.

Uma nova regra de produção só deve ser considerada segura quando:

- existe uma evidência de catálogo que a justifique;
- existe teste que proteja a regra;
- a mudança não confunde identidade lógica com evidência física;
- as relações 1:N continuam sem multiplicação;
- a proveniência da fonte permanece explícita.
