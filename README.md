# NBA Data Pipeline

Pipeline local de estatísticas da NBA desenvolvido com **Python e PostgreSQL**, com carga incremental de partidas, importação histórica e views para análise no Power BI.

Projeto de estudo e portfólio que reúne coleta via API, modelagem relacional, transformação de dados, SQL e verificações de integridade. Um dos usos da base é analisar a evolução do desempenho de jogadores ao longo das temporadas.

> A coleta é automatizada pelo código, mas a execução é manual. Baixar este repositório não cria, preenche nem atualiza um banco automaticamente. Nenhum agendamento está incluído.

## Funcionamento

1. Consulta os jogos encerrados da temporada solicitada.
2. Identifica partidas que ainda não possuem box score carregado.
3. Busca estatísticas de times e jogadores usando `nba_api`.
4. Padroniza campos, converte minutos e valida os placares.
5. Grava cada partida em uma transação no PostgreSQL.
6. Disponibiliza tabelas e views para consultas SQL e ferramentas de BI.

O banco e as credenciais não são distribuídos com o código. A biblioteca `nba_api` é comunitária; este projeto não é um produto oficial da NBA.

## Recursos implementados

- Carga de jogos encerrados de temporada regular, playoffs e play-in.
- Estatísticas por jogador e por time em cada partida.
- Atualização incremental baseada em box scores já carregados.
- Opção de reconsulta para incorporar correções da fonte.
- Importação histórica em lotes por temporada e tipo de competição.
- Chaves primárias e estrangeiras, atualizações com `ON CONFLICT` e transações.
- Validação da soma dos pontos individuais contra o placar do time.
- Registro de execuções, falhas e respostas originais em JSONB.
- Views com médias por temporada, eFG% e TS%.

## Tecnologias

| Tecnologia | Uso |
|---|---|
| Python | Coleta, transformação e coordenação da carga |
| `nba_api` | Acesso aos endpoints de dados da NBA |
| pandas | Manipulação dos resultados tabulares |
| PostgreSQL / psycopg | Armazenamento e acesso ao banco |
| python-dotenv | Configuração local por variáveis de ambiente |
| Power BI | Consumo das tabelas e views para visualização |

Ambiente utilizado no desenvolvimento: Windows, PowerShell, Python 3.14 e PostgreSQL 18. As dependências estão em `requirements.txt`, ainda sem versões fixadas; outras combinações de versões não foram certificadas.

## Estrutura

```text
src/
  db.py                # Conexão ao PostgreSQL e leitura do .env
  init_db.py           # Criação da estrutura inicial
  pipeline.py          # Placar do dia e funções compartilhadas de gravação
  season.py            # Atualização incremental de box scores
  history.py           # Importação histórica em lote e views por temporada
  status.py            # Consulta do estado da base
  verify_season.py     # Verificações e teste de regravação
  audit_history.py     # Auditoria de cobertura e integridade histórica
sql/
  schema.sql           # Estrutura inicial
  statistics.sql       # Tabelas de estatísticas e views básicas
  history.sql          # Estrutura histórica e views analíticas
  analysis_examples.sql
  historical_examples.sql
.env.example           # Modelo de configuração, sem credenciais reais
.gitignore
requirements.txt
COMO_ANALISAR.txt
HISTORICO.txt
```

## Instalação local — Windows / PowerShell

### 1. Obter o projeto e instalar as dependências

```powershell
git clone https://github.com/diegol447/nba_data_pipeline.git
cd nba_data_pipeline
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Execute a cópia do exemplo apenas na primeira configuração: não sobrescreva um `.env` já preenchido. Os comandos usam diretamente o Python do ambiente virtual, sem precisar ativá-lo.

### 2. Criar e configurar o banco

Com o PostgreSQL instalado e em execução, crie um banco vazio chamado `nba` pelo pgAdmin. Alternativamente, conectado a outro banco com um usuário autorizado, execute separadamente:

```sql
CREATE DATABASE nba;
```

Preencha seu `.env` local:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nba
DB_USER=seu_usuario
DB_PASSWORD=sua_senha_local
```

O usuário precisa de permissão para criar e atualizar a estrutura do projeto. Não publique esse arquivo e não use credenciais administrativas para compartilhar acesso de leitura com terceiros.

### 3. Preparar a estrutura

Na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m src.init_db
```

Depois, no Query Tool do pgAdmin conectado ao banco **nba**, abra e execute os arquivos nesta ordem:

1. `sql/statistics.sql`
2. `sql/history.sql`

Essa ordem prepara também a importação histórica. `init_db` sozinho cria apenas a estrutura inicial; `history.sql` depende das tabelas de estatísticas.

## Atualizar uma temporada

```powershell
.\.venv\Scripts\python.exe -m src.season --season 2026-27
```

Substitua o argumento pela temporada desejada. O programa consulta jogos encerrados, ignora os box scores já carregados e registra o resultado em `pipeline_runs`.

Para reconsultar todos os jogos encontrados nessa temporada, inclusive os já carregados:

```powershell
.\.venv\Scripts\python.exe -m src.season --season 2026-27 --refresh
```

Essa opção pode gerar muitas requisições. Uma atualização comum não revisa automaticamente partidas já carregadas. Os registros de estatísticas não são duplicados, mas novos snapshots de auditoria podem ser armazenados.

O comando carrega estatísticas da liga, não apenas de um jogador. Filtros por atleta ou time são aplicados nas consultas e visualizações.

## Importar o histórico

Para uma temporada encerrada:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m src.history --seasons 2023-24
```

Para a seleção histórica padrão do código, de 2017–18 a 2025–26:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m src.history
```

Lotes concluídos são registrados em `historical_imports` e ignorados nas execuções seguintes. Use `season.py` para temporadas em andamento: o importador histórico verifica contagens esperadas de temporadas completas.

Os checkpoints históricos e os snapshots de box score são controles distintos. Executar `season.py` sobre uma temporada importada somente por `history.py` pode voltar a buscar seus jogos; as chaves impedem duplicação das estatísticas.

## Organização do banco

| Schema | Conteúdo |
|---|---|
| `public` | Tabelas físicas de times, jogadores, jogos, estatísticas e auditoria |
| `analytics` | Views de partidas de jogadores e médias por temporada |
| `season_YYYY_YY` | Views filtradas por temporada, criadas pelo importador histórico |

As tabelas principais são `teams`, `players`, `games`, `team_game_stats` e `player_game_stats`. Cada estatística individual relaciona jogador, partida e time naquela partida; não representa um cadastro de contratos ou elenco atual.

Os schemas por temporada **não duplicam os dados**. Novas temporadas podem ser armazenadas nas tabelas centrais sem um schema específico; `season.py` não cria esses schemas automaticamente.

Exemplo de consulta após a preparação da estrutura e carga:

```sql
SELECT season, games_played, points_per_game,
       assists_per_game, efg_pct, ts_pct
FROM analytics.player_season_averages
WHERE player_name = 'Jayson Tatum'
  AND season_type = 'Regular Season'
ORDER BY season;
```

## Validação e acompanhamento

```powershell
.\.venv\Scripts\python.exe -m src.status
.\.venv\Scripts\python.exe -X utf8 -m src.audit_history
```

As auditorias verificam contagens e consistência dos dados presentes; não garantem que a fonte nunca terá erros ou correções.

O comando abaixo requer pelo menos um box score carregado e **regrava uma partida a partir do JSON salvo**, incluindo um novo snapshot. Não é um teste somente de leitura; prefira executá-lo em uma base de desenvolvimento:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m src.verify_season
```

## Power BI e interpretação das métricas

Conecte o Power BI ao PostgreSQL e selecione as tabelas ou views desejadas. Em modo **Importar**, após atualizar a pipeline é necessário atualizar também o relatório. Views criadas manualmente no pgAdmin e o arquivo do dashboard não são necessariamente reproduzidos pelos scripts deste repositório.

- eFG% = `(FGM + 0,5 × 3PM) / FGA`.
- TS% = `PTS / (2 × (FGA + 0,44 × FTA))`.
- Nas views SQL, os percentuais são apresentados na escala **0 a 100**. Para formatá-los como porcentagem no Power BI, converta para a escala de proporção ou crie medidas a partir dos totais.
- Para combinar partidas, calcule percentuais pelos totais de acertos e tentativas, não pela média simples dos percentuais individuais.
- Minutos são decimais: 33 minutos e 15 segundos correspondem a `33.25`.
- No histórico, utilize `game_date`; o horário exato pode estar ausente.

## Limitações e segurança

- Acesso à internet e PostgreSQL em execução são necessários para a carga.
- Endpoints externos podem falhar, limitar requisições ou mudar de formato. O código inclui pausas e tentativas, mas não garante disponibilidade.
- Não inclui pré-temporada, All-Star ou finais da NBA Cup que não contam para a temporada regular na importação histórica.
- No histórico, titularidade, posição e horário exato podem permanecer nulos. Não são inventados registros de jogadores que não atuaram.
- Não inclui histórico estruturado de lesões, modelos preditivos ou agendamento de execução.
- Regras de contagem de temporadas completas e a seleção histórica padrão estão no código e podem exigir manutenção para formatos futuros.
- `.env`, ambientes virtuais, dados locais, backups e relatórios Power BI são ignorados pelo Git. O `.gitignore` não remove segredos já publicados, não detecta senhas dentro do código e não controla sincronização por OneDrive.
- Guarde dumps SQL em `backups/` ou `dumps/`, não em `sql/`, que contém scripts versionados.
- Respeite as condições de uso da fonte antes de redistribuir dados. A publicação do código não implica autorização para redistribuir conteúdo da NBA.

## Próximas melhorias

- Fixar versões das dependências e ampliar testes automatizados.
- Criar uma inicialização única para todos os scripts SQL.
- Revisar automaticamente uma janela de jogos recentes para captar correções.
- Documentar e versionar as views específicas do dashboard.
- Estruturar datas de lesão e retorno, com fontes, para análises comparáveis.

Esses itens são propostas de evolução, não funcionalidades já implementadas.
