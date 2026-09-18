# Data Foundation V2

## Modelo conceitual

A fundação de dados do SERM separa origem, catálogo, identidade, arquivo físico, scan e execução.

```text
Source
  ↓
CatalogVersion
  ↓
CatalogEntry / CanonicalIdentity
  ↓
File / Hash
  ↓
ScanResult
  ↓
Mapping / Transformation
  ↓
ExecutionProfile
```

## Source

Representa a origem do dado ou recurso: MAME, No-Intro, Redump, LaunchBox, RetroArch, WHDLoad, TOSEC ou outra fonte suportada.

## Catalog

Representa uma coleção versionada de definições. Uma mesma entidade pode aparecer em múltiplos catálogos.

## Identity

É a identidade canônica usada pelo SERM para relacionar representações externas. Nomes externos devem ser preservados como aliases/metadados quando relevantes.

## File

Representa um recurso físico observado no filesystem. Seu nome e localização são atributos; hashes e tamanho fornecem evidência mais forte para matching.

## Mapping

Relaciona identidades de fontes diferentes e deve preservar a evidência e a confiança da associação quando houver inferência.

## Scan

Scan registra o estado observado no filesystem em relação ao catálogo. Não modifica o catálogo authoritative.

## Configuration

Configurações administradas pelo SERM pertencem ao estado persistente V2. Arquivos de configuração externos são interoperabilidade e devem ser tratados por adapters/services específicos.

## Proveniência

Quando disponível, preservar:

- source;
- versão/data;
- identificador externo;
- regra usada na transformação;
- evidência do matching;
- timestamp do processamento.

## Regras de consistência

- não usar nome como única identidade física;
- não misturar entidades de fontes diferentes sem mapping;
- não apagar evidência física por divergência do catálogo;
- não transformar metadata provider em fonte de preservação por conveniência;
- manter compatibilidade entre catálogo, scan e reconstruction plan.
