# FreeRouter

FreeRouter 把多个平台的免费模型入口汇总成一个 OpenAI 兼容 API，供 Agent、编辑器和脚本调用。它基于 [LiteLLM Proxy](https://github.com/BerriAI/litellm) 构建，只增加免费模型发现、统一别名和本地部署配置，不复制 LiteLLM 源码。

## 能做什么

- `free-router`：在所有已启用的免费模型入口之间自动分流。
- `zenmux-free`：启动时读取 ZenMux 模型目录，只加入输入和输出价格都为 0 的文本模型。
- `openrouter-free`：使用 OpenRouter 官方的 `openrouter/free` 路由。
- 保留 LiteLLM Dashboard、虚拟 Key、用量日志、预算和 OpenAI 兼容接口。
- 每次启动时刷新免费模型池；账户侧的 0 额度限制可以作为额外保护。

## 快速开始

要求：Docker Desktop、Docker Compose、`openssl`。

```bash
git clone https://github.com/markwaveio/FreeRouter.git
cd FreeRouter
make setup
```

编辑 `.env`，至少填写一个平台 Key：

```dotenv
ZENMUX_API_KEY=
OPENROUTER_API_KEY=
```

启动并测试：

```bash
make up
make status
make test
```

默认地址：

- API：`http://127.0.0.1:4000/v1`
- Dashboard：`http://127.0.0.1:4000/ui`
- API Key：`.env` 中自动生成的 `LITELLM_MASTER_KEY`
- 推荐模型：`free-router`

Agent 配置示例：

```text
Base URL: http://127.0.0.1:4000/v1
API Key: <LITELLM_MASTER_KEY>
Model: free-router
```

## 免费保护机制

ZenMux 模型只有同时满足以下条件才会进入路由池：

1. 支持文本输入和文本输出；
2. `prompt` 的全部价格规则都为 0；
3. `completion` 的全部价格规则都为 0。

OpenRouter 使用其官方免费路由别名。平台规则可能变化，建议同时在平台控制台设置 0 额度或严格预算。FreeRouter 不会把“价格优先”模型自动视为免费模型。

## 配置其他模型

在 `.env` 填写对应平台 Key，然后把 LiteLLM 模型定义加入 `config/litellm-config.yaml`。启动脚本会保留你添加的模型，只重新生成 `free-router`、`zenmux-free` 和 `openrouter-free` 三个自动别名。

详细说明见项目自带 Skill：

```bash
make install-skill
```

安装后可以向支持 Agent Skills 的客户端提出：

```text
使用 $freerouter 帮我安装并配置 FreeRouter。
```

## 更新 LiteLLM

```bash
make update
```

项目默认直接使用 LiteLLM 官方 Docker 镜像。上游地址、版本固定方式和更新说明见 [UPSTREAM.md](UPSTREAM.md)。

## 常用命令

| 命令 | 用途 |
|---|---|
| `make setup` | 生成本地 `.env` 和随机密钥 |
| `make up` | 启动服务 |
| `make down` | 停止服务 |
| `make logs` | 查看网关日志 |
| `make status` | 查看容器健康状态 |
| `make test` | 发出一次真实 API 请求 |
| `make update` | 拉取并重启最新 LiteLLM 镜像 |
| `make check` | 运行项目检查 |
| `make install-skill` | 安装 FreeRouter Skill |

## 安全说明

- `.env` 已被 Git 忽略，禁止提交真实平台 Key、Master Key 或数据库密码。
- 默认只监听 `127.0.0.1`，不会直接暴露到局域网或公网。
- 若需要远程访问，请额外配置身份验证、TLS 和访问控制。
- Dashboard 与 API 共用 LiteLLM 的数据库，删除 Docker volume 会删除其本地记录。

## License

FreeRouter 使用 MIT License。LiteLLM 是独立上游项目，其源码和许可由 [BerriAI/litellm](https://github.com/BerriAI/litellm) 维护。
