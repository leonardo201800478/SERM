# Ambiente de desenvolvimento

## Estrutura do workspace

A raiz do repositório contém `pyproject.toml`, `serm_v2/`, `tests/` e `docs/`. Execute comandos de desenvolvimento a partir dessa raiz. Um ambiente virtual local pode ser criado em `.venv/`; arquivos de configuração do editor são opcionais e não definem outro diretório-base.

## Requisitos

O `pyproject.toml` define:

- Python `>=3.12,<3.15`;
- PySide6 `>=6.8,<7`;
- SQLAlchemy `>=2.0,<3`.

Outras dependências de runtime definidas no pacote:

- PySDL3 `>=0.9.12b1,<1`;
- hidapi `>=0.15,<1`.

Dependências de desenvolvimento:

- pytest `>=9,<10`;
- pytest-cov `>=7,<8`;
- Ruff `>=0.12,<1`.

## Ambiente virtual

No Windows/PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

No VS Code, abra a raiz do repositório e selecione o interpretador `.venv` criado acima. Extensões Python, Pylance e Ruff podem ser instaladas para suporte de linguagem e qualidade; são auxiliares, não dependências do SERM.

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

Configurações de ferramentas externas versionadas devem ficar em `config/<ferramenta>/`. O `config/mame/ui.ini` é um template/configuração do MAME e não faz parte do pacote Python.

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
