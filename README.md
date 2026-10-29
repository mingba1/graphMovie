# graphMovie

LangGraph 制作规划服务：输入题材、时长、预算和风格，并行准备素材证据，再并行产出 `fast_social` / `balanced` / `cinematic` 三套分镜，按可解释分数择优，并在人工确认处暂停续跑。

设计说明见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## Quick start

```bash
cd /Users/mingba/Documents/trunk/github/graphMovie
# 若 shell 里还残留旧路径，先退出旧虚拟环境
deactivate 2>/dev/null || true
unset VIRTUAL_ENV

uv venv .venv
source .venv/bin/activate
uv sync

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

可选 PostgreSQL 检查点：

```bash
docker compose up -d
export DATABASE_URL=postgresql://graphmovie:graphmovie@localhost:5432/graphmovie
uv sync --extra postgres
```

`uv sync` 会默认带上开发依赖（pytest）。只要运行时依赖可用 `uv sync --no-dev`。
Postgres / LLM 仍是可选 extra：`uv sync --extra postgres`、`uv sync --extra llm`。

## What LangGraph is doing here

- `Send()`：主管按需派发研究 Agent；`generated` 不启动 `footage_agent`
- Checkpoint：`review_agent` 的 `interrupt()` 暂停；默认 `MemorySaver`，配置 `DATABASE_URL` 后用 `PostgresSaver`
- `MovieState`：共享需求、证据、分镜、预算、审计和分数
- 条件边：审计失败只回滚当前策略；人工修订可只重跑分镜，或按意见重派研究 Agent

## Tests

```bash
pytest
```
