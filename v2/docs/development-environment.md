# Ambiente de desenvolvimento

## Estrutura do workspace

O arquivo `SERM.code-workspace` abre `v2/` como a pasta do workspace. Portanto, dentro do VS Code:

- `${workspaceFolder}` = diretório `v2/`;
- o interpretador padrão é `v2/.venv/Scripts/python.exe` no Windows;
- `pytest`, Ruff e `python -m serm_v2` são executados a partir de `v2/`;
- a configuração específica do editor fica em `v2/.vscode/`.

Isso evita que configurações específicas da V2 dependam de caminhos relativos à raiz histórica do repositório.

## Requisitos

O `pyproject.toml` define:

- Python `>=3.12,<3.15`;
- PySide6 `>=6.8,<7`;
- SQLAlchemy `>=2.0,<3`.

Dependências de desenvolvimento:

- pytest `>=9,<10`;
- pytest-cov `>=7,<8`;
- Ruff `>=0.12,<1`.

## Ambiente virtual

No Windows/PowerShell:

```powershell
cd v2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

No VS Code, abra `SERM.code-workspace` depois de criar o ambiente. A configuração do workspace aponta automaticamente para o interpretador da V2.

## Extensões recomendadas

`v2/.vscode/extensions.json` recomenda:

- Microsoft Python;
- Microsoft Pylance;
- Ruff;
- Material Icon Theme;
- SQLite Viewer.

Python e Pylance fornecem linguagem, testes e debug; Ruff fornece lint/format; SQLite Viewer é apenas uma ferramenta de inspeção local.

As extensões são auxiliares do desenvolvimento e não são dependências de runtime do SERM.

## Execução

```powershell
python -m serm_v2
```

Após a instalação do pacote:

```powershell
serm
```

## Testes

```powershell
pytest
```

Para uma execução específica:

```powershell
pytest tests/mame/test_listxml_catalog_integrity.py
```

## Qualidade

```powershell
ruff check serm_v2 tests
ruff format --check serm_v2 tests
```

Ou pela task `V2: quality` do VS Code, que executa lint, verificação de formatação e testes em sequência.

Para cobertura:

```powershell
pytest --cov=serm_v2 --cov-report=term-missing
```

## Banco de dados

A inicialização é feita pelos componentes em `serm_v2/database`. Migrations são SQL versionados em `serm_v2/database/migrations`; o mecanismo atual não usa Alembic.

Ao alterar o schema:

1. adicionar a migration correspondente;
2. usar o próximo número de migration disponível;
3. atualizar os modelos/serviços afetados;
4. cobrir o comportamento com testes;
5. validar bootstrap e upgrade em banco limpo;
6. nunca editar silenciosamente uma migration já publicada.

## Configurações externas

Configurações de ferramentas externas versionadas devem ficar em `v2/config/<ferramenta>/`. O `v2/config/mame/ui.ini` é um template/configuração do MAME e não faz parte do pacote Python.

Dados de usuário, bancos locais, logs, caches, staging, exports e backups permanecem fora da árvore versionada.

## Ferramentas externas

Alguns workflows dependem de executáveis ou dados externos, principalmente MAME e ferramentas de arquivo/CHD. O caminho dessas ferramentas deve ser configurável e validado antes da execução.

## Práticas de desenvolvimento

- manter a V2 independente da V1;
- preferir funções pequenas e serviços testáveis;
- não colocar SQL, hash ou traversal de filesystem em widgets;
- registrar falhas com contexto suficiente para reprodução;
- evitar estado global mutável;
- documentar decisões arquiteturais que alterem contratos;
- atualizar a documentação junto com mudanças funcionais relevantes.
