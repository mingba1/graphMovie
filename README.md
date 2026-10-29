# graphMovie

LangGraph **制片规划**服务：输入题材、时长、预算和风格，并行准备素材证据，再并行产出 `fast_social` / `balanced` / `cinematic` 三套分镜，按可解释分数择优，并在人工确认处暂停续跑。

输出是分镜方案、预算与评审结果（Markdown/JSON），**不是渲染成片**。成片生成属于后续产品能力，不在本仓库范围。

设计说明见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## Quick start

```bash
cd /Users/mingba/Documents/trunk/github/graphMovie
deactivate 2>/dev/null || true
unset VIRTUAL_ENV

uv venv .venv
source .venv/bin/activate
uv sync --extra worker

python -m graphmovie plan \
  --title 雨夜霓虹 --genre 科幻 --style cinematic \
  --duration 60 --budget 8000 --pace balanced \
  --footage generated --decision approve
```

API:

```bash
uvicorn graphmovie.api:app --reload
```

```bash
curl -s localhost:8000/projects -H 'content-type: application/json' -d '{
  "title":"雨夜霓虹","genre":"科幻","style":"cinematic",
  "duration_sec":60,"budget_cny":8000,"footage_source":"generated"
}'
```

生产建议打开鉴权：

```bash
export GRAPHMOVIE_API_KEYS=dev-secret
curl -s localhost:8000/projects -H 'content-type: application/json' \
  -H 'X-API-Key: dev-secret' -d '{...}'
```

可选 PostgreSQL 检查点：

```bash
docker compose up -d redis postgres
export DATABASE_URL=postgresql://graphmovie:graphmovie@localhost:5432/graphmovie
uv sync --extra postgres --extra worker
```

`uv sync` 默认带开发依赖（pytest）。可选 extra：`postgres`、`llm`、`worker`。

## 工程化

| 能力 | 做法 |
|---|---|
| 鉴权 | `GRAPHMOVIE_API_KEYS`，请求头 `X-API-Key`；未配置则本地关闭鉴权 |
| 限流 | `GRAPHMOVIE_RATE_LIMIT_PER_MINUTE`（默认 60） |
| 超时 | API `GRAPHMOVIE_REQUEST_TIMEOUT_SEC`；Celery `CELERY_SOFT_TIME_LIMIT` / `CELERY_TIME_LIMIT` |
| 共享检查点 | 非 eager 的 `resume` 未配置 `DATABASE_URL` 时直接拒绝入队 |
| CI | `.github/workflows/ci.yml`，push/PR 自动 `pytest` |

## Celery 异步任务

同步 API（`/projects`）适合本地调试。生产流量用 Jobs API：

```bash
docker compose up -d redis postgres
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
export DATABASE_URL=postgresql://graphmovie:graphmovie@localhost:5432/graphmovie
uvicorn graphmovie.api:app --reload
celery -A graphmovie.celery_app.celery_app worker -Q graphmovie -l info
```

```bash
curl -s localhost:8000/jobs/plan -H 'content-type: application/json' -H 'X-API-Key: dev-secret' -d '{
  "title":"雨夜霓虹","genre":"科幻","style":"cinematic",
  "duration_sec":60,"budget_cny":8000,"footage_source":"generated"
}'
curl -s localhost:8000/jobs/<task_id> -H 'X-API-Key: dev-secret'
curl -s localhost:8000/jobs/<project_id>/resume -H 'content-type: application/json' \
  -H 'X-API-Key: dev-secret' -d '{"decision":"approve"}'
```

跨进程 `resume` 必须配置 `DATABASE_URL`。本地可用 `CELERY_TASK_ALWAYS_EAGER=1`。

## What LangGraph is doing here

- `Send()`：主管按需派发研究 Agent；`generated` 不启动 `footage_agent`
- Checkpoint：`review_agent` 的 `interrupt()` 暂停；默认 `MemorySaver`，配置 `DATABASE_URL` 后用 `PostgresSaver`
- `MovieState`：共享需求、证据、分镜、预算、审计和分数
- 条件边：审计失败只回滚当前策略；人工修订可只重跑分镜，或按意见重派研究 Agent

## Tests

```bash
CELERY_TASK_ALWAYS_EAGER=1 pytest
```
