# Reconstrução de CHDs

## Regra fundamental

O MAME Set Builder **não reconstrói CHDs**.

Um CHD encontrado é apenas:

1. identificado como candidato exigido pelo `ScanResult`;
2. validado pelo `chdman info`;
3. comparado pelo content SHA1 com o digest esperado pelo LISTXML;
4. validado por `chdman verify` somente quando o SHA1 corresponde;
5. copiado byte a byte para o diretório da machine.

Não são executadas operações `create`, `extract`, `merge`, recompressão ou conversão de CHD.

## Regra de rejeição

Se o arquivo existir, mas o content SHA1 não corresponder:

- não copiar;
- não tentar reparar;
- não substituir por outro CHD automaticamente;
- registrar o motivo exato;
- tratar o requisito como `MISSING` para fins da reconstrução.

Se `chdman verify` falhar depois de o SHA1 corresponder:

- não copiar;
- registrar o erro;
- tratar o requisito como `MISSING`/bloqueador quando obrigatório.

## Tamanho

O tamanho físico do arquivo `.chd` não é utilizado para determinar identidade.
Ele depende da compressão. O `listxml` não fornece um tamanho físico confiável para essa finalidade.

O tamanho lógico retornado por `chdman info` é apenas informativo nesta etapa e não é usado como critério de aceitação.

## Destino

O CHD válido é colocado diretamente em:

```text
<destination>/<machine>/<disk>.chd
```

O nome do arquivo é o nome esperado pelo LISTXML. A pasta usa o shortname da machine.

## Origem

O serviço de reconstrução de CHD não faz uma varredura genérica do HDD. Ele usa exclusivamente a evidência física já produzida pelo scanner (`RomScanResult.path`/`location`).

Isso evita que o botão de reconstrução passe novamente por todo o conjunto procurando CHDs irrelevantes.

## Estados

| Situação | Ação | Máquina |
|---|---|---|
| CHD ausente | MISSING | bloqueia se obrigatório |
| SHA1 divergente | IGNORE | MISSING/bloqueia |
| SHA1 correto + verify OK | COPY | disponível |
| SHA1 correto + verify falha | IGNORE | MISSING/bloqueia |
| erro ao copiar | ERROR | bloqueia |

## Delta CHD

O projeto não gera delta CHDs. Se um delta CHD já existente for validado pelo digest esperado e `chdman verify`, ele pode ser copiado. Se a dependência de parent necessária não estiver disponível, a dependência deverá permanecer como bloqueadora no plano MAME.
