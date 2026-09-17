# SERM V2 — Integração de lógica do MAME Smart ROM Sorter

Este documento registra regras conceitualmente inspiradas no projeto **Cyborgbob/MAME-Smart-ROM-Sorter** e reimplementadas para os contratos do SERM V2. Não copia a arquitetura da aplicação de origem e não introduz dependência de código externo.

## Objetivos incorporados

O SERM V2 passa a considerar, como regras de seleção reutilizáveis:

- curadoria 1G1R orientada por família parent/clone;
- preferência configurável de região e idioma;
- filtragem por controles, vias/direções, jogadores e botões;
- filtragem por orientação do display;
- filtragem por status de emulação/driver;
- exclusão explícita de categorias não-jogáveis;
- uso de pontuação de qualidade quando existir fonte persistida;
- preferência por dados auxiliares persistidos em vez de releitura dos INIs durante a consulta;
- registro de motivos de exclusão para auditoria;
- operações de materialização com hard link somente quando forem seguras e compatíveis com o filesystem.

## Regras que não são copiadas literalmente

O SERM não deve reproduzir a heurística de detecção de tipo de set baseada em poucos clones nem transformar a presença/ausência de ZIP em verdade estrutural. O tipo SPLIT/NON-MERGED/FULL-MERGED deve continuar sendo derivado do catálogo e das evidências do scan.

Da mesma forma, a regra de controles é adaptada ao modelo normalizado do SERM. Ausência de informação de controle não deve ser automaticamente interpretada como incompatibilidade.

## 1G1R

A seleção 1G1R ocorre depois dos filtros fundamentais e usa a família lógica do catálogo:

```text
machine
  ↓ cloneof/parent
root family
  ↓
ranking de variantes
  ↓
1 representante
```

O ranking é determinístico. A configuração define a ordem de preferência de regiões e idiomas. Em caso de empate, entram critérios estáveis do catálogo, incluindo preferência pelo parent quando apropriado e penalização de bootleg quando essa opção estiver desabilitada.

A decisão 1G1R deve preservar a distinção entre `cloneof` (máquina) e `merge` (ROM), conforme a arquitetura de reconstrução do SERM.

## Controles

Os controles devem ser tratados como um conjunto de capacidades da máquina. O filtro configurável deve permitir modo permissivo e estrito:

- permissivo: máquinas sem metadado de controle não são eliminadas somente por ausência de informação;
- estrito: máquinas com metadado conhecido incompatível são eliminadas;
- capacidades como joystick, twin stick, wheel, pedal, analog, buttons-only e vias 4/8/2 devem permanecer normalizadas, não armazenadas como texto dependente da GUI.

A origem pode ser ListXML ou fonte auxiliar persistida, desde que a proveniência seja preservada.

## Orientação e display

A orientação deve derivar dos nós de display do ListXML e suportar horizontal, vertical ou ambos. Dados auxiliares podem complementar a classificação, mas não devem sobrescrever silenciosamente o valor estrutural do XML.

## Qualidade e status

Quando uma fonte de classificação de qualidade existir, sua pontuação pode ser usada como filtro opcional. Isso não transforma score em fonte authoritative do catálogo.

Status de driver deve ser interpretado de forma ordenada e configurável, permitindo por exemplo `Working`, `Working + Imperfect` e inclusão de estados preliminares.

## Exclusão de não-jogáveis

Categorias como system/device/BIOS, hardware não executável, calculadoras, computadores, handhelds, consoles, slots, casino, electromechanical e outros conjuntos explicitamente não arcades podem ser descartados por uma política de classificação persistida.

Essa política não deve depender de uma lista de palavras em descrição como autoridade primária; heurísticas textuais são somente fallback com proveniência explícita.

## Dependências

A lógica de curadoria não pode quebrar uma família de ROMs. Depois da seleção de games, o SERM deve resolver dependências de ROM, BIOS, devices, samples e CHDs pelo pipeline de reconstrução já existente.

Assim, remover um clone da seleção 1G1R não significa descartar automaticamente todos os componentes físicos compartilhados que outro game selecionado ainda necessita.

## Materialização eficiente

Uma etapa de publicação pode usar hard links quando:

1. origem e destino estão no mesmo volume/filesystem;
2. a operação não atravessa fronteira de dispositivo incompatível;
3. o usuário selecionou explicitamente o modo de deduplicação;
4. o arquivo origem é somente leitura do ponto de vista lógico do SERM;
5. a falha do hard link gera fallback seguro para cópia normal.

Hard link não deve ser usado como identidade lógica nem para inferir validade do conteúdo.

## Auditoria

Cada regra aplicada deve ser representável no resultado do filtro, idealmente como:

```text
machine_name
selected
rule
reason
source/provenance
```

Isso permite explicar por que uma máquina foi incluída ou removida e evita transformar o Set Builder em uma caixa-preta.

## Referência externa estudada

Projeto estudado: `Cyborgbob/MAME-Smart-ROM-Sorter`.

As ideias incorporadas são as de curadoria por objetivo, 1G1R, preferência regional/linguística, controles, orientação, status e materialização eficiente. A implementação permanece nativa do SERM V2, respeitando suas regras de separação entre catálogo, identidade física, scan e reconstrução.
