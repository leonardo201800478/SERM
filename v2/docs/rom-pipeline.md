# Pipeline de ROMs — SERM V2

A V2 separa deliberadamente auditoria, seleção e materialização física.

```text
DAT/XML completo
      │
      ▼
1 — SCAN
      │  auditoria sem filtros
      ▼
SCAN FILE (SERM-SCAN-V1)
      │
      ▼
2 — FILTRAGEM
      │  somente sobre o snapshot persistido
      ▼
FILTERED FILE (SERM-FILTER-V1)
      │
      ▼
3 — RECONSTRUÇÃO
      │  plano + destino escolhido pelo usuário
      ▼
SET FÍSICO
```

## 1 — Scan

Cada família possui uma subguia própria: MAME, No-Intro, Redump, WHLoader e C64.

O scan não deve aplicar filtros de conteúdo. O DAT/ListXML selecionado é a fonte
completa da auditoria. O resultado contém as evidências encontradas, ausentes,
incorretas e duplicadas e é persistido como snapshot imutável.

No MAME existem exatamente três modos: `arcade`, `software` e `both`, apresentados
na interface como **Arcade**, **Software** e **Completa**.

Para No-Intro, cada DAT/variante é um catálogo independente. A seleção do DAT é
explícita; não se escolhe Headered/Headerless, endian ou encrypted/decrypted por
heurística.

## 2 — Filtragem

A fase recebe exclusivamente um scan concluído. Ela nunca revarre as fontes.

Cada sistema possui uma subguia. MAME utiliza as regras específicas de seleção
já existentes na V2. As demais famílias possuem uma camada genérica segura baseada
nas evidências persistidas enquanto suas regras de catálogo forem evoluídas.

O arquivo original de scan nunca é sobrescrito. Cada execução cria um novo
`SERM-FILTER-V1`, preservando referência ao `scan_id`, catálogo e hash do catálogo.

## 3 — Reconstrução

A reconstrução recebe somente um `SERM-FILTER-V1`, mostra seu contexto e exige que
o usuário escolha o diretório de destino.

O plano agrupa membros de arquivos ZIP e, quando possível, recria o ZIP contendo
somente os membros selecionados. Arquivos soltos e CHDs são copiados. Contêineres
não-ZIP, como LHA, são preservados como contêiner enquanto a reconstrução específica
do formato não estiver implementada.

A execução ocorre em worker separado, possui progresso/cancelamento e não executa
novo scan.

## Regra de integridade

Alterar filtros deve ser barato: muda apenas o `SERM-FILTER-V1`. O `SERM-SCAN-V1`
permanece a fotografia da auditoria original e pode ser reutilizado para quantos
perfis de filtragem forem necessários.
