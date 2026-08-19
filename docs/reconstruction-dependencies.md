# Resolução de dependências na reconstrução MAME

## Objetivo

A reconstrução não trata uma machine como um ZIP isolado. O LISTXML define uma
grafo de dependências que pode envolver parent/clone, `merge`, BIOS, devices e
samples. O projeto resolve esse grafo antes da escrita física.

## Estados da ROM

A decisão de uma ROM mantém duas dimensões:

- estado físico: `valid`, `missing`, `invalid`, `error`;
- estado documental MAME: `good`, `baddump`, `nodump`.

Uma ROM `baddump` que corresponde ao dump conhecido é utilizável. Uma ROM
`nodump` ausente não deve ser procurada indefinidamente, pois o MAME não
conhece um dump funcional para ela.

## Parent/clone

`cloneof` e `romof` formam a dependência estrutural. A resolução percorre a
cadeia até a raiz e detecta ciclos ou parents inexistentes.

## `merge`

Uma ROM com `merge="X"` é fornecida pelo set `X`. O arquivo não deve ser
copiado novamente no clone em Split. Em Non-Merged a ROM fornecida deve ser
materializada no set do clone. Em Merged ela pertence ao ZIP do parent raiz,
junto com os dados dos clones selecionados.

## Modos de armazenamento

### Split

```text
parent.zip -> ROMs do parent
clone.zip  -> somente ROMs exclusivas do clone
```

O parent continua sendo uma dependência necessária para executar o clone.

### Non-Merged

```text
clone.zip -> ROMs próprias + ROMs herdadas do parent/merge
```

Cada set deve ser autocontido quanto às ROMs de sistema que pertencem à cadeia
parent/clone.

### Merged

```text
parent.zip -> ROMs do parent + ROMs dos clones selecionados
```

O clone não recebe um ZIP próprio para as ROMs que foram incorporadas ao
merged set.

## BIOS

BIOS não é tratada como uma ROM arbitrária a ser jogada dentro de qualquer ZIP.
O resolver identifica a BIOS selecionada e a machine BIOS correspondente pelo
`biosset`. O BIOS set permanece um artefato externo (`biosname.zip`).

Se `include_bios=false`, a dependência é deliberadamente excluída e a decisão
fica registrada; isso não deve ser confundido com uma BIOS inexistente.

## Devices

`device_ref` gera uma dependência explícita. O device possui seu próprio set e
pode ter parent/clone próprio. Ele não é incorporado arbitrariamente ao ZIP do
jogo. O plano expõe o arquivo externo esperado, por exemplo `device.zip`.

## Samples

Samples são dependências externas a `samples/<name>.zip`. A opção
`include_samples` controla se entram no plano de construção.

## Segurança

O resolver nunca cria uma ROM virtual como válida. A definição do LISTXML só
diz o que deveria existir; a evidência física continua vindo exclusivamente do
scan. Se uma dependência necessária não foi escaneada, a reconstrução deve
registrar isso como bloqueador, nunca assumir que o arquivo existe.

## Componentes

- `app/core/services/mame_dependency_resolver.py`: grafo de dependências;
- `app/core/services/mame_archive_layout.py`: localização lógica das ROMs;
- `app/core/services/mame_build_planner.py`: plano unificado;
- `app/core/services/dependency_aware_reconstruction.py`: ponte entre scan e
  plano de reconstrução.

O motor físico existente continua responsável por streaming, hash, staging,
retry e publicação atômica. A camada MAME-aware decide **o que** precisa ser
construído; o motor físico decide **como** copiar e validar os bytes.
