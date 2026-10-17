# Política geral de SCAN, REFRESH e reconstrução

## Regra normativa

Todo fluxo do SERM que trabalha com um conjunto físico que possui **origem** e **destino** deve separar obrigatoriamente a observação dessas duas pastas.

```text
CATÁLOGO / PERFIL
       ↓
     SCAN
       ↓
  pasta de ORIGEM
       ↓
  evidência física
       ↓
    REFRESH
       ↓
  pasta de DESTINO
       ↓
 diferença do conjunto
       ↓
 RECONSTRUÇÃO
       ↓
 materialização no destino
       ↓
   REFRESH final
       ↓
 EXPORTAR NÃO VALIDADOS
```

Essa separação é uma regra de arquitetura, não apenas uma convenção da GUI.

## 1. Catálogo / atualização

A atualização do catálogo obtém e normaliza a definição do conjunto. Ela não deve ser confundida com um scan físico e não deve afirmar que um arquivo existe apenas porque está catalogado.

Quando houver uma fonte de identidade mais autoritativa que um agregador externo, a fonte autoritativa prevalece. Por exemplo, no ARES, os hashes declarados pelo código-fonte do próprio emulador são a identidade primária; RetroBIOS complementa disponibilidade e metadados.

## 2. SCAN — somente origem

`SCAN` significa **examinar a pasta de origem**.

O SCAN:
- percorre somente a origem configurada;
- identifica arquivos soltos e, quando suportado, membros de arquivos compactados;
- calcula somente as identidades necessárias ao catálogo;
- compara o conteúdo físico com as identidades catalogadas;
- produz a evidência que pode ser usada pela reconstrução;
- não usa a pasta de destino para decidir o que existe na origem;
- não gera a lista final de ausentes do destino.

A origem é tratada como fonte de material para reconstrução e deve permanecer somente leitura durante o processo.

## 3. REFRESH — somente destino

`REFRESH` significa **reexaminar a pasta de destino**.

O REFRESH:
- percorre somente o destino;
- valida os arquivos já materializados para uso pelo emulador;
- aplica os hashes/identidades do catálogo;
- distingue válido, ausente e inválido;
- calcula a diferença entre o conjunto esperado e o conjunto físico existente;
- prepara o estado usado para reconstrução e exportação.

O REFRESH não deve depender de executar novamente o SCAN da origem.

## 4. Reconstrução

A reconstrução usa dois estados independentes:

```text
origem reconhecida
       −
destino validado
       =
trabalho necessário
```

Quando o fluxo define reconstrução automática de ausentes, não deve existir seleção manual de cada ROM. O sistema deve descobrir automaticamente o que falta e usar todo o material disponível na origem para formar o conjunto esperado.

Dependendo do formato, a reconstrução pode copiar, renomear, extrair membros, criar diretórios, criar/atualizar arquivos compactados e resolver múltiplas fontes físicas para um único conjunto lógico.

Um arquivo existente no destino com identidade incorreta não é válido. Ele deve ser classificado como `invalid` e, quando houver fonte válida, pode ser substituído pela reconstrução.

Arquivos desconhecidos no destino não devem ser apagados apenas por não pertencerem ao catálogo, salvo quando uma política específica de reconstrução autorizar explicitamente essa limpeza.

## 5. REFRESH final

Depois de uma reconstrução bem-sucedida, o destino deve ser revalidado. A presença física de um arquivo recém-criado não é suficiente: o mesmo mecanismo de validação usado pelo REFRESH deve confirmar sua identidade.

Assim, o estado pós-reconstrução deve ser obtido por um novo REFRESH, e não por uma suposição baseada no resultado da operação de cópia.

## 6. EXPORTAR NÃO VALIDADOS

A exportação para pesquisa externa deve representar somente o que **continua ausente do destino após a validação física**.

Portanto:
- `missing` → pode entrar no arquivo de busca;
- `invalid` → não entra como ausente; é um arquivo existente que precisa ser corrigido/substituído;
- `valid` → não entra;
- arquivo desconhecido → não entra automaticamente;
- item que existe na origem e ainda não está no destino → entra como ausente.

O relatório deve usar as identidades do catálogo, preferencialmente hashes, como termos de busca quando disponíveis.

## 7. Identidade física

Nome de arquivo nunca deve superar uma identidade verificável fornecida pelo catálogo.

Quando o catálogo fornece hash:

```text
hash compatível          → VALID
hash incompatível        → INVALID
nome igual + hash errado → NÃO VALIDADO
```

O fallback por nome só pode ser usado quando a entrada não possuir identidade verificável suficiente.

Isso evita que um arquivo com nome correto e conteúdo incorreto seja apresentado como uma ROM pronta para uso.

## 8. Contrato entre estados

| Etapa | Pasta observada | Resultado principal |
|---|---|---|
| Atualizar catálogo | fonte externa/metadados | definição esperada |
| SCAN | origem | material físico disponível |
| REFRESH | destino | material físico válido/ausente/inválido |
| Reconstruir | origem → destino | materialização do conjunto |
| REFRESH final | destino | confirmação física |
| Exportar não validados | resultado do REFRESH | somente ausentes |

Nenhuma etapa deve substituir silenciosamente a responsabilidade da outra.

## 9. GUI

Quando uma tela oferecer essas ações, a ordem visual deve refletir o fluxo lógico:

```text
ATUALIZAR
SCAN
RECONSTRUIR AUSENTES
EXPORTAR NÃO VALIDADOS
REFRESH
```

O REFRESH permanece como a etapa de validação física do destino. Após reconstrução, ele pode ser acionado automaticamente como pós-validação.

## 10. Escopo

Esta política é geral para fluxos de BIOS, firmware, ROMs, arquivos compactados e demais conjuntos em que o SERM possui origem e destino físicos. Pipelines especializados que não possuem uma segunda pasta física devem manter sua semântica própria, mas não devem chamar uma operação de origem de REFRESH nem misturar evidência de origem com estado do destino.
