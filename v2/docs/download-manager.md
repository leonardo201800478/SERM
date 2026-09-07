# Download Manager

O Download Manager é responsável por aquisição de recursos externos e por separar download de ingestão.

## Pipeline

```text
Remote source
   ↓
Download
   ↓
Temporary file
   ↓
Integrity check
   ↓
Source adapter
   ↓
Catalog / resource store
```

## Princípios

- downloads devem ocorrer em arquivo temporário;
- validar tamanho/hash quando a fonte fornecer referência;
- não considerar download concluído antes da validação mínima;
- permitir retry e falha explícita;
- registrar origem e versão quando possível;
- não executar conteúdo baixado durante a validação.

## Separação

Download Manager transporta recursos. Adapters interpretam o conteúdo. Services de catálogo decidem como persistir e normalizar.
