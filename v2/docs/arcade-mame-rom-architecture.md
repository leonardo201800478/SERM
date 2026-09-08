# Arquitetura de ROMs MAME no SERM V2

## Objetivo

Este documento descreve, em profundidade, como o SERM V2 representa, resolve e materializa ROMs MAME no Arcade Studio. A arquitetura separa quatro conceitos que não podem ser confundidos:

1. **machine set**: a máquina MAME identificada por `machine_name`;
2. **ROM catalogada**: um elemento `<rom>` do ListXML, identificado pelo seu `display_name`/nome XML;
3. **origem lógica**: a máquina e ROM que devem fornecer o conteúdo (`merge`, `romof`, `cloneof`/parent ou a própria máquina);
4. **identidade física**: SHA1, MD5 ou CRC+size usados para localizar o arquivo existente.

A separação é fundamental porque o nome da máquina e o nome da ROM são domínios diferentes. O código do SERM não deve inferir um a partir do outro.

## 1. Modelo conceitual do MAME

O MAME organiza dados de hardware em **sets**. Uma ROM image representa os dados de um chip; um jogo arcade normalmente precisa de várias ROMs para reconstruir o hardware. O MAME usa relações parent/clone para representar variantes que compartilham grande parte dos dados. Sets podem ser armazenados como **non-merged**, **split** ou **merged**. BIOS e device sets são dependências adicionais e não devem ser tratados como simples clones.

A documentação oficial do MAME descreve:

- non-merged: cada ZIP contém tudo o que uma variante precisa;
- split: o parent contém os componentes comuns e o clone contém apenas o que mudou;
- merged: parent e clones são armazenados no arquivo do parent.

Fonte primária: documentação oficial do MAME, seção *About ROMs and Sets*.

## 2. ListXML e identidade lógica

O `-listxml` oficial do MAME é a fonte estrutural usada pelo SERM para compreender máquinas e seus componentes. No XML, atributos como `cloneof` e `romof` pertencem à máquina, enquanto `name`, `merge`, `crc`, `sha1` e `size` pertencem ao elemento ROM.

Portanto:

```text
machine.name     -> identifica o machine set
rom.name         -> identifica a ROM dentro daquele machine set
rom.merge        -> identifica o nome da ROM que deve ser obtida de outra definição
rom.sha1/crc/size -> identificam o conteúdo físico esperado
```

O SERM mantém essa separação em `ArcadeGame` e `ArcadeRom`.

## 3. Representação no SERM

`ArcadeGame.machine_name` representa o short name técnico da máquina.

`ArcadeGame.parent_name` representa a relação parent/clone normalizada.

Cada `ArcadeRom` possui:

- `machine_name`: máquina que declara a ROM;
- `display_name`: nome da ROM no catálogo/XML;
- `metadata`: atributos técnicos e de auditoria.

O campo `display_name` é a chave correta para identificar uma ROM dentro de uma máquina. Uma máquina possui normalmente várias ROMs, portanto usar apenas `machine_name` como identidade da ROM produz colisões.

## 4. Origem lógica antes da identidade física

A reconstrução do SERM ocorre em duas fases.

### Fase A — plano lógico

`ArcadeRomReconstructionPlanner` determina de onde a ROM deve vir.

A prioridade atual é:

1. `merge` explícito;
2. `romof`, quando aplicável e resolvível;
3. parent;
4. própria máquina (`SELF`).

Para `merge`, o valor é interpretado como **nome de ROM**, não como nome de máquina. A busca considera a máquina atual e as máquinas explicitamente relacionadas. Uma correspondência global arbitrária é rejeitada para evitar dependências inventadas.

O resultado é um `RomReconstructionPlan` contendo:

```text
machine_name
rom_name
source_machine
source_rom_name
source_kind
reason
```

### Fase B — resolução física

Somente depois do plano lógico o `ArcadeRomReconstructionEngine` procura o arquivo físico no inventário.

A prioridade de identidade é:

```text
SHA1
  ↓
MD5
  ↓
CRC + size
```

Uma identidade que encontra vários arquivos físicos é marcada como `AMBIGUOUS`; o SERM não escolhe arbitrariamente.

## 5. Duplicatas no catálogo

O ListXML/catálogo pode conter registros com o mesmo nome lógico dentro de uma máquina. Isso não significa necessariamente que existam duas ROMs físicas diferentes.

O planner distingue:

### Duplicatas fisicamente idênticas

Se SHA1, CRC e size normalizados são iguais, os registros são considerados a mesma identidade física e podem ser resolvidos deterministicamente.

### Duplicatas fisicamente conflitantes

Se os registros possuem identidades físicas diferentes, a resolução permanece ambígua. O SERM não deve escolher uma das duas por ordem de inserção.

Essa regra evita transformar uma duplicação representacional em falso `MISSING` sem, ao mesmo tempo, esconder uma ambiguidade real.

## 6. `SELF`, `MERGED`, `PARENT`, `ROMOF` e `MISSING`

### SELF

A ROM pertence ao próprio machine set e pode ser obtida localmente.

### MERGED

O `merge` foi resolvido para uma ROM de outra máquina relacionada. O `source_rom_name` continua sendo o nome da ROM, não o nome da máquina.

### PARENT

Não há `merge` explícito, mas a ROM de mesmo nome está disponível no parent.

### ROMOF

A ROM é herdada da máquina indicada por `romof` quando a relação é explicitamente resolvível.

### MISSING

A origem lógica solicitada não foi localizada. No catálogo real auditado pelo SERM, após a correção das duplicatas fisicamente idênticas, as 179.667 relações `merge` foram classificadas como:

```text
SELF     167.637
MERGED    12.030
PARENT         0
ROMOF          0
MISSING        0
```

Essa classificação foi validada diretamente contra o catálogo real importado no SERM.

## 7. Parent/clone não é a mesma coisa que `merge`

`cloneof` descreve uma relação entre **máquinas**. `merge` descreve a origem de uma **ROM**.

Consequentemente:

```text
cloneof = relação máquina → máquina
romof   = relação máquina → máquina
merge   = relação ROM → ROM
```

Essa distinção é uma das regras centrais da arquitetura do SERM.

## 8. Layout físico

O `ArcadeSetLayoutPlanner` traduz a estrutura lógica para três layouts.

### SPLIT

Cada máquina possui seu próprio archive. Dependências encontradas no parent permanecem no archive de origem e não são duplicadas no clone.

### NON_MERGED

Cada máquina recebe todos os componentes necessários, incluindo os compartilhados.

### FULL_MERGED

A família parent/clone é materializada no archive da raiz da família. Componentes fisicamente idênticos compartilhados são deduplicados no destino.

A documentação oficial do MAME define o comportamento conceitual desses três formatos; o SERM implementa a materialização determinística desses conceitos no seu manifesto.

## 9. Manifesto de materialização

`ArcadeReconstructionManifestBuilder` é a fronteira entre reconstrução lógica e escrita física.

Ele recebe os resultados de ROM e CHD, aplica o layout e produz `MaterializationEntry`.

Para ROMs, a chave do resultado é:

```text
(machine_name, rom_name)
```

onde `rom_name` corresponde ao `display_name` da ROM.

Essa regra é obrigatória: usar `ArcadeRom.machine_name` como segunda dimensão faria todas as ROMs da mesma máquina colidirem.

Antes da escrita, o manifesto detecta:

- dependências não resolvidas;
- identidades físicas ausentes;
- destinos duplicados com a mesma origem;
- destinos em conflito com origens físicas diferentes.

## 10. CHD é outra classe de componente

CHD não deve ser tratado como ROM ZIP.

O MAME documenta CHD como formato para meios de armazenamento de maior capacidade, como discos rígidos, CD-ROMs e LaserDiscs. O SERM mantém `ArcadeDisk`, `PhysicalChd` e `ArcadeChdReconstructionEngine` separados da cadeia de ROMs.

A identidade lógica de um CHD usa os hashes disponíveis no catálogo, com prioridade SHA1 e depois MD5. O arquivo `.chd` não deve ser colocado dentro de ZIP de ROM.

O MAME também suporta delta CHDs em relações de clone; essa possibilidade deve ser preservada como semântica própria de CHD, não reduzida ao algoritmo de ROM `merge`.

## 11. BIOS e devices

BIOS e device sets são dependências reais do hardware MAME. A documentação oficial diferencia esses conjuntos de parent/clone comuns.

No SERM, `is_bios` e `is_device` são atributos semânticos da ROM/máquina e não devem ser filtrados simplesmente como se fossem ROMs opcionais comuns.

Em particular, uma dependência obrigatória de BIOS/device não pode ser descartada pelo Set Builder apenas porque o próprio machine set está desabilitado.

## 12. Evidência física versus reconstrução lógica

Uma ROM pode ter uma identidade conhecida no catálogo sem existir no inventário físico. Portanto, estas duas perguntas são diferentes:

```text
O catálogo sabe qual conteúdo deveria existir?
        ≠
O SERM encontrou esse conteúdo no disco?
```

O planner responde à primeira dimensão lógica. O reconstruction engine responde à segunda dimensão física.

`NOT FOUND`, `nodump` ou ausência de inventário não devem ser convertidos automaticamente em uma afirmação sobre a validade histórica ou emulação do componente.

## 13. Contratos de segurança

A arquitetura considera erro melhor que uma reconstrução silenciosamente incorreta.

São falhas explícitas:

- escolher uma ROM entre identidades físicas conflitantes;
- resolver `merge` por um nome global não relacionado;
- confundir nome da máquina com nome da ROM;
- duplicar uma dependência compartilhada em SPLIT;
- materializar duas origens diferentes no mesmo destino;
- tratar CHD como ROM ZIP;
- ignorar BIOS/device obrigatório.

## 14. Validação realizada

A implementação foi validada em camadas:

- casos semânticos de planner;
- auditoria do catálogo MAME real;
- reconstrução física por SHA1/MD5/CRC+size;
- integração planner → reconstruction;
- manifestação de SPLIT/NON_MERGED/FULL_MERGED;
- CHD;
- prevenção de colisões de múltiplas ROMs por máquina.

A auditoria real do planner validou 179.667 relações `merge` com zero divergências.

## 15. Referências primárias

- MAME Documentation — *About ROMs and Sets*.
- MAME Documentation — *Common Issues*.
- Código-fonte MAME `scripts/minimaws/lib/lxparse.py`, que demonstra a leitura de `cloneof`, `romof`, `<rom>` e `<disk>` do ListXML.

Para a arquitetura específica do SERM, a fonte normativa é o código V2 e seus testes. A documentação deste artigo explica o contrato implementado; não substitui os testes executáveis.
