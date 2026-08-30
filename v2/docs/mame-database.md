# Catálogo MAME persistido — documentação viva

## Objetivo

O SERM V2 preserva o `ListXML` bruto do MAME e normaliza as entidades conhecidas em tabelas relacionais. O normalizador documenta explicitamente as entidades persistidas: máquinas, ROMs, discos, displays, samples, chips, dispositivos, referências de dispositivos, inputs, controles, BIOS, dipswitches, valores de DIP, configurações, opções de configuração, portas, adjusters, drivers, features, slots, opções de slot, software lists e opções de RAM.

A fonte de verdade continua sendo o XML bruto. A camada relacional deve ser usada pelas funções futuras para consultas e filtros, enquanto campos não representados no modelo relacional devem ser recuperados do documento XML lossless.

## Auditoria do banco real

Para gerar uma fotografia do que efetivamente foi coletado no banco local:

```powershell
$env:SERM_MAME_DB = "C:\caminho\para\serm.db"
python -m serm_v2.tools.audit_mame_database --output docs/mame-database-audit.md
```

A auditoria:

- enumera todas as tabelas `mame_*` existentes;
- informa a quantidade real de registros de cada tabela;
- lista as colunas reais do SQLite;
- coleta até 3 registros de amostra por tabela;
- não altera o banco (`PRAGMA query_only=ON`);
- não inventa dados ausentes;
- pode ser repetida após cada nova importação do MAME.

## Teste de inventário

O teste live usa o mesmo banco informado em `SERM_MAME_DB`:

```powershell
$env:SERM_MAME_DB = "C:\caminho\para\serm.db"
pytest -q tests/test_mame_database_inventory.py -s
```

Sem `SERM_MAME_DB`, os testes live são marcados como `skip`, evitando que o CI dependa de um banco de dados local.

## Contrato para funções futuras

Ao criar uma função que dependa do catálogo MAME:

1. consulte primeiro as tabelas relacionais correspondentes;
2. use `mame_machine.id` como chave relacional da máquina;
3. respeite as relações filho → máquina (`mame_rom`, `mame_disk`, `mame_display`, etc.);
4. não trate ausência de uma linha filha como evidência de que o XML original não possuía o elemento sem verificar o XML quando essa distinção for relevante;
5. para informação não normalizada, consulte o `ListXML` lossless associado ao `mame_listxml_import`;
6. não sobrescreva dados coletados para gerar perfis ou decisões de configuração — essas são camadas posteriores.

## O que o normalizador coleta atualmente

| Entidade | Tabela | Origem principal no ListXML |
|---|---|---|
| Máquina | `mame_machine` | `<machine>` + atributos/textos básicos |
| Metadados de driver | `mame_machine_metadata` | `<driver>` |
| ROM | `mame_rom` | `<rom>` |
| Disco | `mame_disk` | `<disk>` |
| BIOS | `mame_biosset` | `<biosset>` |
| Sample | `mame_sample` | `<sample>` |
| Chip | `mame_chip` | `<chip>` |
| Display | `mame_display` | `<display>` |
| Input | `mame_input` | `<input>` |
| Controle | `mame_control` | `<input><control>` |
| DIP switch | `mame_dipswitch` | `<dipswitch>` |
| Valor de DIP | `mame_dipvalue` | `<dipswitch><dipvalue>` |
| Configuração | `mame_configuration` | `<configuration>` |
| Configuração/opção | `mame_confsetting` | `<configuration><confsetting>` |
| Porta | `mame_port` | `<port>` |
| Adjuster | `mame_adjuster` | `<adjuster>` |
| Driver | `mame_driver` | `<driver>` |
| Feature | `mame_feature` | `<feature>` |
| Device | `mame_device` | `<device>` |
| Device reference | `mame_device_ref` | `<device_ref>` |
| Slot | `mame_slot` | `<slot>` |
| Slot option | `mame_slot_option` | `<slot><slotoption>` |
| Software list | `mame_softwarelist` | `<softwarelist>` |
| RAM option | `mame_ramoption` | `<ramoption>` |

Esta tabela descreve o contrato do código atual; a auditoria live é a autoridade para saber quais dessas tabelas existem e quantos registros foram efetivamente coletados em uma instalação específica.
