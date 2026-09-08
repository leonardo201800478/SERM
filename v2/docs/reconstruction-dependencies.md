# Resolução de dependências na reconstrução MAME

## Objetivo

A reconstrução não trata uma machine como um ZIP isolado. O ListXML define um grafo de dependências que pode envolver parent/clone, `romof`, `merge`, BIOS, devices, samples e CHDs. O SERM resolve essas dimensões em etapas distintas antes da materialização física.

A implementação atual deve ser entendida em três camadas:

```text
ArcadeGame / ArcadeRom / ArcadeDisk
            ↓
ArcadeRomReconstructionPlanner
            ↓
ArcadeRomReconstructionEngine
            ↓
ArcadeReconstructionManifestBuilder
            ↓
Materializer
```

O planner MAME-aware decide a origem lógica; o engine resolve a evidência física; o manifesto consolida o destino. A escrita física permanece separada dessa decisão.

## ROM: duas dimensões de estado

A decisão de uma ROM mantém separadas:

- **estado documental MAME:** por exemplo `good`, `baddump`, `nodump`;
- **evidência física do scan:** arquivo encontrado, ausente, inválido ou erro.

O catálogo informa o conteúdo esperado; somente o scan informa se o conteúdo foi encontrado no filesystem.

## Parent/clone e `romof`

`cloneof` e `romof` são relações entre machine sets. Não devem ser confundidas com `merge`, que referencia uma ROM.

A cadeia parent/clone deve ser percorrida explicitamente e ciclos devem ser rejeitados. Uma relação `romof` só deve ser usada quando a máquina de origem estiver presente no catálogo e a ROM correspondente puder ser resolvida.

## `merge`

`merge="X"` representa o nome da ROM de origem. O planner procura primeiro a própria máquina e depois as máquinas explicitamente relacionadas por `romof` e parent.

Uma correspondência global em uma máquina não relacionada é rejeitada. Isso evita transformar coincidência de nomes em dependência falsa.

Duplicatas do mesmo nome dentro de uma máquina são resolvidas deterministicamente somente quando SHA1/CRC/size identificam o mesmo conteúdo físico. Identidades conflitantes permanecem ambíguas.

A auditoria do catálogo real do SERM validou 179.667 relações `merge` com:

```text
SELF       167.637
MERGED      12.030
PARENT           0
ROMOF            0
MISSING          0
DIVERGÊNCIAS     0
```

## Modos de armazenamento

### SPLIT

```text
parent.zip -> ROMs pertencentes ao parent
clone.zip  -> ROMs exclusivas do clone
```

Uma ROM resolvida em outro machine set não é duplicada no clone.

### NON_MERGED

```text
clone.zip -> ROMs próprias + componentes compartilhados necessários
```

Cada set deve ser autocontido quanto às dependências que o catálogo determina como necessárias.

### FULL_MERGED

```text
parent.zip -> ROMs do parent + ROMs dos clones selecionados
```

A família utiliza o archive da raiz. A deduplicação ocorre pela origem física, e não por nomes coincidentes.

## BIOS

BIOS é dependência de sistema e possui semântica própria. Não deve ser incorporada arbitrariamente ao ZIP de uma máquina apenas porque seu conteúdo é uma ROM.

O tratamento definitivo de seleção, inclusão/exclusão e materialização de BIOS é uma etapa ainda pendente da Meta 2 do roadmap. Até sua conclusão, a documentação não deve afirmar que todo o grafo de BIOS já está materializado pelo pipeline V2.

## Devices

Device sets também são dependências externas ao archive comum do jogo. O tratamento completo de device graph é parte da Meta 2.

## Samples

Samples devem permanecer como dependência externa quando exigidos pelo catálogo. O tratamento completo de samples é parte da Meta 2.

## CHD

CHDs são tratados por `ArcadeChdReconstructionEngine` e `ArcadeDisk`, em pipeline separado de ROM ZIP. O manifesto mantém `MaterializationKind.CHD` distinto de `ROM`.

O tratamento completo de delta CHD e sua materialização física deve ser validado contra famílias reais antes de ser considerado concluído.

## Segurança

O resolver não cria uma ROM virtual como válida. A definição do ListXML só informa o que deveria existir; a evidência física continua vindo do scan.

A materialização deve obedecer:

```text
source → staging → validate → atomic publish
```

A origem permanece somente leitura. Conflitos de destino, identidade física ambígua, dependências não resolvidas e arquivos ausentes devem bloquear a publicação em vez de produzir uma reconstrução silenciosamente incorreta.

## Componentes V2 atuais

- `serm_v2/models/arcade.py` — modelo lógico de games, ROMs e discos;
- `serm_v2/services/arcade/rom_reconstruction_plan.py` — plano de origem lógica;
- `serm_v2/services/arcade/rom_reconstruction.py` — resolução da evidência física;
- `serm_v2/services/arcade/set_layout.py` — planejamento SPLIT/NON_MERGED/FULL_MERGED;
- `serm_v2/services/arcade/reconstruction_manifest.py` — manifesto unificado;
- `serm_v2/services/arcade/chd_reconstruction.py` — reconstrução CHD;
- `serm_v2/services/arcade/materializer.py` — materialização física.

Não utilizar caminhos históricos `app/core/services/...` como referência da arquitetura V2.

## Estado

A resolução de ROM e o manifesto possuem cobertura automatizada e foram confrontados com o catálogo real. A execução física completa e a validação abrangente de BIOS/devices/samples ainda pertencem às próximas metas do roadmap.
