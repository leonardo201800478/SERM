# Download Manager

O Download Manager é responsável por aquisição de recursos externos e por separar download, extração e publicação.

## Pipeline

```text
Provider
   ↓
Resource Catalog
   ↓
Latest Resource Resolver
   ↓
Download
   ↓
Temporary file / cache
   ↓
Integrity check
   ↓
Safe extraction
   ↓
Explicit publication
   ↓
Scan / ingestion
```

O Download Manager não deve escrever cegamente na instalação do emulador.

## Provider

Providers encapsulam sites e formatos externos. O primeiro provider do Arcade Studio é `ProgettoSnapsProvider`.

O provider deve:

- descobrir recursos;
- identificar versão;
- informar tipo funcional;
- fornecer origem de aquisição;
- informar metadados de pacote;
- mapear somente membros úteis do pacote;
- evitar que URLs e convenções do site vazem para o domínio.

## Resolução da versão mais recente

Antes do download, o `LatestResourceResolver` pode substituir a versão declarada no catálogo pela versão mais recente descoberta pelo provider. As estratégias disponíveis incluem listagem, probe e extração de links publicados.

A regra operacional da V2 é: **quando a fonte permite descobrir uma versão mais recente, a aquisição deve utilizar essa versão; nunca criar uma versão por suposição a partir da versão do MAME.**

## Recursos Progetto-SNAPS integrados

O provider mantém atualmente referências para:

- CatVer 0.289;
- BestGames 0.280;
- Series 0.289;
- Languages 0.289;
- GameInit 0.289;
- Command 0.273;
- MAME Samples FullPack 0.289.

Essas versões são referências do catálogo e podem ser substituídas pelo resolver quando uma fonte publicar uma versão mais recente.

## Princípios

- downloads devem ocorrer em arquivo temporário;
- validar tamanho/hash quando a fonte fornecer referência;
- não considerar download concluído antes da validação mínima;
- permitir retry e falha explícita;
- registrar origem e versão quando possível;
- não executar conteúdo baixado durante a validação;
- impedir path traversal na extração;
- reutilizar cache quando a identidade do recurso já for conhecida;
- comparar hash para detectar conteúdo idêntico entre versões;
- manter aquisição fora do destino até que a publicação seja explicitamente autorizada.

## Publicação de arquivos auxiliares

Os pacotes de support files podem conter membros destinados a pastas diferentes. O provider informa essa relação, por exemplo:

```text
folders/*.ini → <MAME>/folders/
dats/*.dat    → <MAME>/dats/
samples/*.zip  → <MAME>/samples/
```

O `DownloadManager.install_members()` faz primeiro o **preflight de todos os conflitos** e somente depois executa as cópias. Isso impede publicação parcial de um pacote quando um membro posterior está em conflito.

Estados de destino:

- `CREATE`: não existe arquivo no destino;
- `REUSE`: o arquivo existente é byte a byte idêntico;
- `REPLACE`: o arquivo existente é diferente e a substituição foi autorizada explicitamente;
- `BLOCK`: o arquivo existente é diferente e a publicação é interrompida.

Não há exclusão automática de arquivos desconhecidos e não há sobrescrita silenciosa.

## Detecção de versão local

A GUI do projeto-SNAPS não considera a versão do cache como fonte primária para arquivos que já estejam instalados. O detector local procura primeiro a declaração no próprio arquivo e depois utiliza o nome do arquivo/ZIP. O cache é somente fallback.

Para `.ini` e `.dat`, somente uma região inicial do arquivo é lida. Isso permite reconhecer cabeçalhos do projeto-SNAPS sem varrer arquivos inteiros.

Para Samples, o FullPack é instalado como vários ZIPs individuais. Como esses ZIPs podem não declarar a versão do pacote individualmente, a proveniência do FullPack no cache é usada quando necessário.

## Separação

Download Manager transporta recursos. Providers interpretam a fonte remota. O `ExternalResourceCatalog` mantém identidade e proveniência. Services de catálogo decidem como persistir e normalizar. A publicação decide quando um artefato pode ser colocado no destino MAME.

## MAME / Progetto-SNAPS

Metadados como CatVer, Series e Languages podem enriquecer o catálogo do SERM, mas não substituem o MAME ListXML como autoridade para identidade e relações das máquinas. `GameInit` e `Command` são informações auxiliares; `BestGames` é curadoria pessoal; Samples são recursos físicos separados.
