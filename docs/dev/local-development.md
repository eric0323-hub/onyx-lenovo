# Onyx 本地开发环境

这份文档记录当前仓库的本地开发环境、端口配置、启动方式和常见问题。

## 环境概览

当前仓库路径：

```bash
/Users/yangsong/Documents/Lenovo/code/onyx-lenovo
```

主要技术栈：

- 后端：Python 3.11、FastAPI、SQLAlchemy、Celery
- 前端：Next.js、React、TypeScript、Tailwind CSS
- 依赖服务：PostgreSQL、Redis、OpenSearch、MinIO、model server、code-interpreter
- 可选观测服务：Langfuse web / worker、Langfuse PostgreSQL、ClickHouse、Redis、MinIO
- Python 依赖管理：`uv` + `.venv`
- 前端依赖管理：`bun`
- 本地开发服务编排：Docker Compose

## Python 环境

仓库使用 `uv` 管理 Python 依赖，根目录包含：

- `.python-version`：指定 Python `3.11`
- `pyproject.toml`：Python 依赖和工具配置
- `uv.lock`：锁定依赖版本

初始化 Python 虚拟环境：

```bash
uv venv .venv --python 3.11
source .venv/bin/activate
uv sync
uv run playwright install
```

之后可以直接用激活后的环境运行命令：

```bash
source .venv/bin/activate
pytest -xv backend/tests/unit
```

也可以用 `uv run`：

```bash
uv run pytest -xv backend/tests/unit
```

### PyPI 镜像问题

如果 `uv sync` 或 `uv run` 遇到清华 PyPI 镜像返回 `403 Forbidden`，通常是当前 shell 里设置了：

```bash
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

临时绕过镜像并使用官方 PyPI：

```bash
env -u UV_INDEX_URL -u UV_INDEX -u UV_EXTRA_INDEX_URL \
  UV_DEFAULT_INDEX=https://pypi.org/simple \
  uv sync
```

启动后端时也可以这样临时绕过：

```bash
cd backend
env -u UV_INDEX_URL -u UV_INDEX -u UV_EXTRA_INDEX_URL \
  UV_DEFAULT_INDEX=https://pypi.org/simple \
  uv run python -m dotenv -f ../.vscode/.env run -- uvicorn onyx.main:app --reload --port 8080
```

注意：`env -u UV_INDEX_URL ...` 必须和 `uv run ...` 写在同一条命令里。单独运行
`env -u UV_INDEX_URL -u UV_INDEX -u UV_EXTRA_INDEX_URL` 只会打印一个临时环境，不会修改当前 shell。
如果想修改当前终端，使用：

```bash
unset UV_INDEX_URL UV_INDEX UV_EXTRA_INDEX_URL
export UV_DEFAULT_INDEX=https://pypi.org/simple
```

`uv` 可以配置多个 index，但默认的 `first-index` 策略会在第一个包含该包名的 index 上停止。
如果该 index 返回 `403 Forbidden`，默认也会停止，不一定继续 fallback 到 PyPI。因此不要长期把有
artifact `403` 问题的镜像放在最高优先级。

如果 wheel 缓存已经损坏，可以先清理对应缓存：

```bash
uv cache clean agent-client-protocol aioboto3 types-oauthlib prometheus-client
env -u UV_INDEX_URL -u UV_INDEX -u UV_EXTRA_INDEX_URL \
  UV_DEFAULT_INDEX=https://pypi.org/simple \
  uv sync
```

## Docker Compose 开发端口

开发覆盖文件是：

```bash
deployment/docker_compose/docker-compose.dev.yml
```

当前开发环境故意避开常见默认端口，例如 `80`、`3000`、`5432`、`6379`、`8000`、`8080`、`9000`、`9200`。
这样可以把 Docker Compose 服务、本机后端和本机前端同时跑起来。

默认宿主机端口：

| 服务 | 宿主机地址 |
| --- | --- |
| Web / nginx | `http://localhost:18030` |
| nginx 备用入口 | `http://localhost:18081` |
| API server | `http://localhost:18082` |
| Code interpreter | `http://localhost:18083` |
| PostgreSQL | `localhost:15432` |
| Redis | `localhost:16379` |
| Model server | `http://localhost:19000` |
| MinIO API | `http://localhost:19004` |
| MinIO Console | `http://localhost:19005` |
| OpenSearch | `http://localhost:19200` |
| MCP server 可选端口 | `http://localhost:18090` |

可选 Langfuse profile 的默认宿主机端口：

| 服务 | 宿主机地址 |
| --- | --- |
| Langfuse UI | `http://localhost:3001` |
| Langfuse PostgreSQL | `localhost:15433` |
| Langfuse ClickHouse HTTP | `http://localhost:18123` |
| Langfuse ClickHouse native | `localhost:19010` |
| Langfuse Redis | `localhost:16380` |
| Langfuse MinIO API | `http://localhost:19090` |
| Langfuse MinIO Console | `http://localhost:19091` |

端口变量在 `deployment/docker_compose/env.template` 中有示例：

```bash
HOST_PORT=18030
HOST_PORT_80=18081
API_SERVER_HOST_PORT=18082
CODE_INTERPRETER_HOST_PORT=18083
MCP_SERVER_HOST_PORT=18090
POSTGRES_HOST_PORT=15432
REDIS_HOST_PORT=16379
MODEL_SERVER_HOST_PORT=19000
MINIO_API_HOST_PORT=19004
MINIO_CONSOLE_HOST_PORT=19005
OPENSEARCH_HOST_PORT=19200
LANGFUSE_HOST_PORT=3001
LANGFUSE_POSTGRES_HOST_PORT=15433
LANGFUSE_CLICKHOUSE_HTTP_HOST_PORT=18123
LANGFUSE_CLICKHOUSE_NATIVE_HOST_PORT=19010
LANGFUSE_REDIS_HOST_PORT=16380
LANGFUSE_MINIO_API_HOST_PORT=19090
LANGFUSE_MINIO_CONSOLE_HOST_PORT=19091
```

注意：容器内部服务仍然使用原始端口，例如 `api_server:8080`、`relational_db:5432`、
`cache:6379`、`langfuse-web:3000`。这些内部端口不要为了避开宿主机冲突而修改。

## 启动开发环境

本地开发固定拆成三部分启动，不再同时维护完整 Docker、Docker 后端、本机后端等多套路径：

- Docker：只跑 Onyx 依赖服务和 Langfuse，不跑 Onyx 的 API/Web/background。
- 后端：本机用 `uv` 启动 FastAPI，监听 `8080`。
- 前端：本机用 `bun` 启动 Next.js，监听 `3000`，通过 `INTERNAL_URL` 连接本机后端。

### 1. 启动其他 Docker 服务和 Langfuse

首次使用先准备 compose env：

```bash
cd deployment/docker_compose
cp env.template .env
```

确认 `deployment/docker_compose/.env` 至少包含这些本地 Langfuse 配置：

```bash
COMPOSE_PROFILES=s3-filestore,langfuse,code-interpreter
LANGFUSE_HOST_PORT=3001
LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-lf-local-onyx
LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-lf-local-onyx
LANGFUSE_INIT_USER_EMAIL=admin@example.com
LANGFUSE_INIT_USER_PASSWORD=LangfuseLocal123!
```

启动 Onyx 依赖 Docker 服务：

```bash
cd deployment/docker_compose
COMPOSE_PROFILES=s3-filestore,code-interpreter docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d \
  relational_db cache opensearch inference_model_server indexing_model_server minio code-interpreter
```

启动 Langfuse Docker 服务：

```bash
cd deployment/docker_compose
COMPOSE_PROFILES=langfuse docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d langfuse-web langfuse-worker
```

确认 `.vscode/.env` 里有本机后端连接 Docker 依赖和 Langfuse 的配置：

```bash
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=15432
REDIS_HOST=127.0.0.1
REDIS_PORT=16379
OPENSEARCH_HOST=127.0.0.1
OPENSEARCH_REST_API_PORT=19200
MODEL_SERVER_HOST=127.0.0.1
MODEL_SERVER_PORT=19000
S3_ENDPOINT_URL=http://localhost:19004
S3_FILE_STORE_BUCKET_NAME=onyx-file-store-bucket
S3_AWS_ACCESS_KEY_ID=minioadmin
S3_AWS_SECRET_ACCESS_KEY=minioadmin
CODE_INTERPRETER_BASE_URL=http://localhost:18083
LANGFUSE_HOST=http://127.0.0.1:3001
LANGFUSE_UI_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-local-onyx
LANGFUSE_SECRET_KEY=sk-lf-local-onyx
```

当前决策：Langfuse 本地栈暂时不共享 Onyx 的 PostgreSQL、Redis 或 MinIO。这样依赖边界更清楚，
Langfuse 数据和 volume 可以独立清理，也避免本地调试时互相污染。

Langfuse v3 本地会启动 ClickHouse，资源占用较高。启动后用下面命令检查状态：

```bash
cd deployment/docker_compose
COMPOSE_PROFILES=s3-filestore,langfuse,code-interpreter docker-compose -f docker-compose.yml -f docker-compose.dev.yml ps
curl http://localhost:3001
```

Langfuse UI：

```bash
http://localhost:3001
```

本地 Langfuse 登录：

```bash
admin@example.com
LangfuseLocal123!
```

### 2. 启动本机后端

```bash
cd backend
uv run python -m dotenv -f ../.vscode/.env run -- uvicorn onyx.main:app --reload --port 8080
```

后端监听：

```bash
http://127.0.0.1:8080
```

如果修改了 `.vscode/.env` 里的 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY` 或 `LANGFUSE_HOST`，必须重启
本机后端，tracing processor 才会重新初始化。

### 3. 启动本机前端

确认 `web/.env.local` 指向本机后端：

```bash
INTERNAL_URL=http://127.0.0.1:8080
PORT=3000
```

启动前端：

```bash
cd web
bun run dev
```

访问 Onyx：

```bash
http://localhost:3000
```

Langfuse 观测页面：

```bash
http://localhost:3000/admin/performance/observability
```

本地开发测试登录账号不要写入可提交文档。当前机器的测试登录信息记录在：

```bash
.vscode/.env.local-login
```

## 前端依赖

进入前端目录：

```bash
cd web
bun install
```

启动前端开发服务使用上面的 `cd web && bun run dev`。

## 数据库连接

从宿主机连接 PostgreSQL：

```bash
psql -h localhost -p 15432 -U postgres
```

默认用户和密码来自 `deployment/docker_compose/env.template`：

```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

通过容器执行 SQL：

```bash
docker exec -it onyx-relational_db-1 psql -U postgres -c "<SQL>"
```

项目约定：数据库操作代码放在 `backend/onyx/db` 或 `backend/ee/onyx/db` 下。

## 常用测试命令

先激活虚拟环境：

```bash
source .venv/bin/activate
```

单元测试：

```bash
pytest -xv backend/tests/unit
```

外部依赖单元测试：

```bash
python -m dotenv -f .vscode/.env run -- pytest backend/tests/external_dependency_unit
```

集成测试：

```bash
python -m dotenv -f .vscode/.env run -- pytest backend/tests/integration
```

Playwright E2E：

```bash
cd web
bunx playwright test <TEST_NAME>
```

## 日志

服务日志通常在：

```bash
backend/log/
```

例如：

- `api_server_debug.log`
- `web_server_debug.log`
- `celery_*_debug.log`

如果要确认服务是否在运行，可以先查看相关日志是否持续更新。

## 常见问题

### 端口被占用

检查端口：

```bash
lsof -nP -iTCP:<PORT> -sTCP:LISTEN
```

开发端口可以通过 `deployment/docker_compose/.env` 覆盖，例如：

```bash
HOST_PORT=18130
API_SERVER_HOST_PORT=18182
POSTGRES_HOST_PORT=15433
```

修改后重新启动 compose。

### 修改 Celery worker 后没有生效

Celery worker 没有自动热重载。修改 worker 代码后，需要重启对应 Celery worker 或相关容器。

### OpenSearch SSL EOF

如果本机后端启动时出现：

```bash
ssl.SSLEOFError: [SSL: UNEXPECTED_EOF_WHILE_READING]
```

先检查 OpenSearch 是否真正 ready：

```bash
curl -k -u admin:StrongPassword123! 'https://127.0.0.1:19200/_cluster/health?pretty'
```

当前 OpenSearch Docker 镜像默认启用 Security Plugin，本机后端默认也会用 HTTPS 连接它。不要因为这个
EOF 错误直接把 `OPENSEARCH_USE_SSL=false` 写进 `.vscode/.env`；如果 curl 也 connection reset，通常是
OpenSearch 还没启动完成、容器卡住，或 Docker/Podman VM 内存不足。先查看日志或重启 OpenSearch：

```bash
cd deployment/docker_compose
docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail 120 opensearch
docker-compose -f docker-compose.yml -f docker-compose.dev.yml restart opensearch
```

### 后端 API 调用路径

当前固定本地开发模式下，浏览器入口是本机前端：

```bash
http://localhost:3000
```

前端通过 `web/.env.local` 里的 `INTERNAL_URL` 代理到本机后端：

```bash
http://127.0.0.1:8080
```

### Docker Compose 展开配置检查

检查最终端口映射：

```bash
COMPOSE_PROFILES=s3-filestore docker-compose -f docker-compose.yml -f docker-compose.dev.yml config
```

只看 published 端口：

```bash
COMPOSE_PROFILES=s3-filestore docker-compose -f docker-compose.yml -f docker-compose.dev.yml config \
  | awk '/^[[:space:]]{2}/ {svc=$1; sub(":", "", svc)} /published:/ {print svc, $2}'
```
