# Wayback Recon

Mapa histórico de um domínio: consulta a [Wayback Machine](https://web.archive.org/) (CDX API), coleta as URLs arquivadas e destaca as superfícies de ataque interessantes (admin, login, API, backups, arquivos sensíveis, entre outros..)

> ⚠️ **Reconhecimento PASSIVO**: nunca toca no site alvo — apenas consulta o arquivo público da Wayback Machine. 

## O que faz (resumido)

- Busca as URLs históricas do domínio na Wayback Machine.
- Remove duplicadas, normaliza e classifica as interessantes (`ADMIN`, `LOGIN`, `API`, `ENV`, `SQL`, `BACKUP`, `ARCHIVE`, `JAVASCRIPT`, `CONFIG`, ...).
- Opcional: baixa cópias arquivadas e extrai os links **de dentro** delas (`--extract-links`) — descobre rotas que nunca foram capturadas como URL.
- Exporta tudo em JSON e mostra um resumo bonito no terminal (Rich).

## Instalação

Requisito: Python 3.12+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

## Uso

```bash
wayback-recon scan exemplo.com
wayback-recon scan exemplo.com --extract-links --max-pages 30
wayback-recon scan exemplo.com -o resultado.json
```

## Opções principais

| Opção | Descrição |
| --- | --- |
| `--interesting` | mostra só as URLs classificadas como interessantes |
| `--extract-links` | extrai links das páginas arquivadas |
| `--max-pages N` | nº de páginas arquivadas a analisar (padrão 20) |
| `--output`, `-o` | salva os resultados em JSON |
| `--limit N` | limita a quantidade de dados vindos da API |
| `--timeout S` / `--retries N` | tolerância à lentidão/instabilidade da Wayback |

## Exemplo de saída

```text
╭───────────────────────────── WAYBACK RECON ───────────────────────────────╮
│  Target              exemplo.com                                         │
│  URLs found          1250                                                │
│  Unique URLs         843                                                 │
│  Interesting URLs    27                                                  │
│  Pages analysed      23                                                  │
│  New links extracted 168                                                 │
╰───────────────────────────────────────────────────────────────────────────╯
LOGIN
https://exemplo.com/wp-login.php

API
https://exemplo.com/wp-json/wp/v2/users
```

## Importante

- As categorias são heurísticas — revise os resultados manualmente.
- Domínios grandes podem demorar; ajuste `--limit` / `--timeout`.

## Licença

MIT — veja [LICENSE](LICENSE).
