# Ambiente de desenvolvimento

## Requisitos

O `pyproject.toml` define:

- Python `>=3.12,<3.15`;
- PySide6 `>=6.8,<7`;
- SQLAlchemy `>=2.0,<3`;
- Alembic `>=1.16,<2`.

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

Ruff usa target Python 3.12, line length de 100 caracteres e regras E4/E7/E9/F/I/B/UP.

## Banco de dados

A inicialização é feita pelos componentes em `serm_v2/database`. Migrations são SQL versionados em `serm_v2/database/migrations`.

Ao alterar o schema:

1. adicionar a migration correspondente;
2. atualizar os modelos afetados;
3. cobrir o comportamento com testes;
4. validar bootstrap e upgrade em banco limpo;
5. nunca editar silenciosamente uma migration já aplicada.

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
