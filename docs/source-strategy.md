# Estratégia de fontes

## Princípio

O SERM pode consumir várias fontes porque nenhum catálogo possui a mesma autoridade para todos os sistemas.

A autoridade é definida **por domínio e por tipo de informação**, não por conveniência de integração.

## Classes

### Fontes de preservação / referência

- MAME ListXML;
- No-Intro / Dat-o-MATIC;
- Redump;
- FBNeo;
- MAME Softlists;
- fontes confiáveis de BIOS.

### Fontes especializadas / conveniência

- WHDLoad / Retroplay;
- eXoDOS;
- C64 / TOSEC;
- outros datasets específicos.

### Providers de metadata

- LaunchBox;
- RetroArch RDB;
- caches e bancos auxiliares.

Providers de metadata não se tornam fonte física de verdade apenas por serem importados.

## Adapters

Cada fonte externa deve possuir um adapter que converta seu formato para contratos V2.

```text
Provider
   ↓
Adapter
   ↓
Canonical model
   ↓
SQLite
```

O restante do aplicativo não deve depender diretamente de XML/JSON/DAT ou do schema de um provider.

## Proveniência

Dados importados devem manter, quando tecnicamente possível:

- fonte;
- versão/data da fonte;
- identificador externo;
- regra de transformação;
- evidência usada no matching;
- confiança quando houver inferência.

## Identity mapping

Quando duas fontes representam a mesma obra/conteúdo de formas diferentes, o SERM deve criar um DE-PARA explícito em vez de alterar o nome original.

```text
Official identity
       ↕
Mapping / evidence
       ↕
Convenience identity
```

Isso permite reorganizar arquivos para execução sem perder a nomenclatura de origem.

## Regra de conflito

Em caso de conflito, o sistema deve preferir a fonte authoritative para o campo específico. Se não houver autoridade suficiente, preservar as duas evidências e marcar a resolução como não determinada, em vez de inventar um valor.

## Atualização

Atualizações de fontes devem ser idempotentes sempre que possível. Uma nova versão deve permitir distinguir dados atuais de dados importados anteriormente.
