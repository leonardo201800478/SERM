# Download Manager

O Download Manager é responsável por aquisição de recursos externos e por separar download de ingestão.

## Pipeline

```text
Provider
   ↓
Resource Catalog
   ↓
Download
   ↓
Temporary file / cache
   ↓
Integrity check
   ↓
Safe extraction
   ↓
Source repository
   ↓
Scan / ingestion
```

O Download Manager **não publica diretamente na instalação do emulador**. A publicação continua sob responsabilidade da reconstrução/materialização.

## Provider

Providers encapsulam sites e formatos externos. O primeiro provider do Arcade Studio é `ProgettoSnapsProvider`.

O provider deve:

- descobrir recursos;
- identificar versão;
- informar tipo funcional;
- fornecer origem de aquisição;
- informar metadados de pacote;
- evitar que URLs e convenções do site vazem para o domínio.

## Princípios

- downloads devem ocorrer em arquivo temporário;
- validar tamanho/hash quando a fonte fornecer referência;
- não considerar download concluído antes da validação mínima;
- permitir retry e falha explícita;
- registrar origem e versão quando possível;
- não executar conteúdo baixado durante a validação;
- impedir path traversal na extração;
- reutilizar cache quando a identidade do recurso já for conhecida;
- comparar hash para detectar conteúdo idêntico entre versões.

## Separação

Download Manager transporta recursos. Providers interpretam a fonte remota. O `ExternalResourceCatalog` mantém identidade e proveniência. Services de catálogo decidem como persistir e normalizar. O materializer decide quando um artefato pode ser publicado no destino.

## MAME / Progetto-SNAPS

Metadados como CatVer, Series e Languages podem enriquecer o catálogo do SERM, mas não substituem o MAME ListXML como autoridade para identidade e relações das máquinas. Samples são recursos físicos separados e devem entrar no source repository MAME, sendo validados antes da reconstrução.
