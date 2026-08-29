# Integração Datoso

## Objetivo

O SERM usa o Datoso como backend de aquisição dos DATs publicados por fontes externas. O SERM continua responsável por descoberta, roteamento, matching, frescor, manifesto e organização em `data/`.

A integração inicial é deliberadamente desacoplada das classes internas do Datoso: o adapter executa `python -m datoso` usando o mesmo interpretador Python do ambiente V2.

## Fontes

- `nointro`: aquisição No-Intro/DAT-o-MATIC.
- `redump`: reservado para a integração Redump futura; não deve ser tratado como No-Intro.

O projeto Datoso documenta seeds separados para No-Intro e Redump e suporta `--fetch` e `--filter`. A versão atualmente validada pelo projeto é `datoso 1.1.1` com `datoso-seed-nointro 1.1.1`.

## Instalação

No ambiente V2:

```powershell
python -m pip install -e ".[dev,sources]"
```

O plugin No-Intro depende de `geckodriver`. O SERM não tenta instalar navegador ou driver automaticamente.

## Diagnóstico

```powershell
python -m datoso doctor nointro
```

## Fluxo SERM

```text
LaunchBox
   |
   v
SystemSourceRouter
   |--------------------|
   v                    v
No-Intro              Redump
   |                    |
   v                    v
Datoso nointro        futuro adapter Redump
   |
   v
SERM data/sources/no_intro/dats
```

A implementação inicial está em `serm_v2.sources.acquisition.datoso.DatosoProvider`.

## Download seletivo

O adapter executa o equivalente a:

```text
datoso nointro --fetch --filter "<sistema>"
```

Depois identifica o DAT novo ou modificado na área temporária padrão do Datoso (`~/.datoso/dats/nointro/dats`) e copia o arquivo para o destino informado pelo SERM.

Isso evita que o SERM dependa do HTML, IDs internos ou fluxo Scene do DAT-o-MATIC.

## CAPTCHA e bloqueio

O Datoso documenta que o DAT-o-MATIC pode apresentar CAPTCHA. O SERM não deve tentar contornar CAPTCHA. Em caso de falha, o erro deve ser reportado ao usuário para intervenção manual.

## Estado da migração

- [x] Dependências opcionais do Datoso adicionadas ao V2.
- [x] Adapter No-Intro desacoplado criado.
- [x] Detecção de DAT novo/modificado criada.
- [x] Testes unitários iniciais criados.
- [ ] Validar `datoso doctor nointro` no ambiente Windows do usuário.
- [ ] Validar um download real de NES.
- [ ] Integrar o adapter ao botão de download da GUI.
- [ ] Integrar atualização seletiva da GUI.
- [ ] Criar adapter Redump separado.
