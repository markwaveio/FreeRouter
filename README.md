# FreeRouter

FreeRouter 把多个平台的免费模型入口汇总成一个 OpenAI 兼容 API，供 Agent、编辑器和脚本调用。它基于 [LiteLLM Proxy](https://github.com/BerriAI/litellm) 构建，只增加免费模型发现、健康探测、自动增删和本地部署配置，不复制 LiteLLM 源码。

**一句话**：免费模型天天挂，FreeRouter 让你的 Agent 感觉不到，免去多Agent手动配置、自动轮询可用模型。

## 它做什么

- **一个 API 挂所有免费模型**。`free-router` 这一个模型名，背后是所有已验证可用的免费模型，自动分流。
- **失效自动下线**。后台每 6 小时拿真实请求探测一遍；连续失败的模型被移出池子，恢复了自动放回。
- **新模型自动上线**。平台上新的免费模型会被自动发现、探测、接入，不需要重启也不需要你改配置。
- **活动变化自动跟踪**。限时活动到期前会提醒，平台目录里模型的增减会写进变更日志并推到你的 webhook。
- **本地部署**。Docker Compose 三个容器，只监听 `127.0.0.1`。

## 先领一批免费 Key



<!-- BEGIN GENERATED: signup — 由 make docs 生成，请勿手改 -->

**填任意一个平台的 Key 就能跑起来。** 下面几家注册即用、不要信用卡：

| 平台 | 免费什么 | 限额 | 奖励 | |
|---|---|---|---|---|
| **B.AI** | DeepSeek-V4-Flash 系列限时 0 Credits 不限量 | 见官网 | 注册即得 | [**立即注册 →**†](https://chat.b.ai/chat?invite_code=H82845) |
| **魔搭社区 ModelScope** | Qwen3、DeepSeek、GLM 等 25 个开源模型免费推理 | 2000 次/天 | 注册即得 | [**立即注册 →**†](https://modelscope.cn/register?inviteCode=MarkWave&invitorName=MarkWave) |
| **硅基流动 SiliconFlow** | Qwen3-8B、GLM-4-9B 等 9B 以下开源模型永久免费 | 见官网 | 注册即得 | [**立即注册 →**†](https://cloud.siliconflow.cn/i/CuI9M5Ht) |
| **智谱 AI (BigModel)** | GLM-4.7-Flash 等 Flash 系列长期免费 | 见官网 | 注册即得 | [**立即注册 →**†](https://www.bigmodel.cn/invite?icode=bkHx%2Fep6dDks7UF3yJZB4LC%2Fk7jQAKmT1mpEiZXXnFw%3D) |
| **ZenMux** | 自动发现平台上所有 0 价模型 | 见官网 | 奖励需首充 | [**立即注册 →**†](https://zenmux.ai/invite/L4QDZW) |

> † **这些是邀请链接**，通过它注册会产生平台奖励：
>
> - **B.AI**：被邀请人注册可领 30 万积分（官方仅公布受邀方奖励，邀请方奖励未说明）
> - **魔搭社区 ModelScope**：双方各得魔方（ModelScope 平台积分），注册即得无需充值
> - **硅基流动 SiliconFlow**：双方各得 2000 万 tokens（约 ¥14 平台额度，不可提现）
> - **智谱 AI (BigModel)**：好友实名注册后双方各得 Tokens 资源包，无需充值
> - **ZenMux**：双方各得 $5 credit，被邀请人首次充值后额外获得 25% 奖励
>
> 不想走返利就用[官网直达入口](#已接入的平台)，注册流程完全一样；那张表里还有另外 16 家不带邀请链接的平台。返利不影响任何技术判断，见[说明](#挂自己的邀请链接)。

<!-- END GENERATED: signup -->

## 快速开始

要求：Docker Desktop、Docker Compose、`openssl`。

```bash
git clone https://github.com/markwaveio/FreeRouter.git
cd FreeRouter
make setup
```

把上面领到的 Key 填进 `.env`（`.env.example` 里每个变量上方都写了去哪注册），然后启动：

```bash
make up        # 启动网关 + 刷新器
make verify    # 一条命令确认全链路可用，并打印客户端该填什么
```

Agent 配置：

```text
Base URL: http://127.0.0.1:4000/v1
API Key:  <.env 里的 LITELLM_MASTER_KEY>
Model:    free-router
```

## 三种模型名

| 模型名               | 含义                                                             |
| -------------------- | ---------------------------------------------------------------- |
| `free-router`      | 所有**已探测通过**的免费模型，跨平台自动分流与故障转移     |
| `<平台>-free`      | 只用某个平台，例如`groq-free`、`zenmux-free`、`zhipu-free` |
| `fr/<平台>/<模型>` | 精确指定一个模型，例如`fr/openrouter/z-ai/glm-5.2:free`        |

被隔离的模型会从前两种里移除，但保留 `fr/…` 这个入口——方便你自己确认它到底怎么挂的。

## 自动更新是怎么做的

两层，各管一件事。

**运行时自愈（refresher 容器，默认每 6 小时）**

```
读 providers/*.yaml
  → 拉平台目录，按规则筛出免费模型
  → 新模型先只挂 fr/… 入口
  → 读 LiteLLM 调用日志：真实流量已经验证过的模型，直接采信，不再探测
  → 只对「没人验证过的新模型」和「隔离中该重试的」发探测请求
  → 通过才进 free-router 池；失败的按原因分级处理
  → 通过 LiteLLM 的 /model/new 和 /model/delete 热增删，全程不重启
  → 变化写进 state/changelog.jsonl，并推送到 webhook
```

**探测不花冤枉额度**：真实调用的成功和失败，LiteLLM 都记了 `error_code` 和 `error_message`，跟主动探测能拿到的信息一模一样。所以只要你的 Agent 在用这个网关，健康模型就一直在被免费验证，探测只花在三种情况上：

| 情况                   | 为什么必须探测                                                |
| ---------------------- | ------------------------------------------------------------- |
| 新发现的模型           | 还没进`free-router`，收不到真实流量，需要一次探测才敢放进池 |
| 隔离中的模型           | 已被移出池子收不到流量，靠退避重试才能恢复                    |
| 长时间零流量的健康模型 | 超过`FREEROUTER_RECHECK_HOURS` 没有成功记录，需要确认还活着 |

退避最长会等到 12 小时。如果你已经把根因修好了（补了 Key、绑定了账号、改了平台参数），不用干等——`make recheck` 清掉隔离状态，下一轮立刻重新探测。

稳态下（模型池不变、Agent 正常调用）**每轮探测次数是 0**：

```
real traffic verified 26 models; no probe needed for them
cycle complete: healthy=20 traffic-verified=26 probed=0 added=0 deleted=0
```

探测结果分五类，处理方式不同：

| 结果                  | 判定             | 处理                               |
| --------------------- | ---------------- | ---------------------------------- |
| 429 / 限流            | 模型活着，只是挤 | **不计失败**                 |
| 404 / model not found | 模型下架了       | 立刻隔离                           |
| 402 / 余额不足        | 额度用尽         | 隔离，1 小时后重试（日额度会重置） |
| 401 / 403             | Key 有问题       | 计入失败                           |
| 5xx / 超时            | 临时抖动         | 计入失败，连续 3 次才隔离          |

隔离后按指数退避重试（30 分钟起，最长 12 小时），恢复了自动放回池子并记一条 `revived`。

**平台侧变化跟踪（GitHub Actions，每天一次）**

`.github/workflows/watch-free-models.yml` 每天拉一遍各平台的公开模型目录，跟 `catalog/snapshot.json` 比对；有新增、下架、状态变化就自动开 PR，同时刷新 [catalog/FREE-MODELS.md](catalog/FREE-MODELS.md)。没有变化就不开 PR。

需要 Key 才能拉目录的平台，在仓库 Secrets 里配置同名变量后 CI 也会一起刷新。

## 免费的判定标准

FreeRouter 不会因为「便宜」就把模型当免费。三种发现方式各有各的依据：

| 方式               | 判定依据                                                                                                                            | 用在哪些平台                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `priced_catalog` | 目录返回的 prompt 与 completion 价格**全部为 0**，输入输出都含 text，且输出模态不含 audio/image/video                         | ZenMux、OpenRouter                                                                          |
| `listing`        | 模型出现在平台的实时模型列表里，且**必须**二选一给出免费依据：写 `allow` 白名单，或显式声明 `whole_catalog_is_free: true` | Groq、Cerebras、Gemini、NVIDIA NIM、ModelScope、Mistral、Cohere、Cloudflare、硅基流动、B.AI |
| `static`         | 官方文档明确写了永久免费或赠送额度的模型清单                                                                                        | 智谱、千帆、百炼、DeepSeek、火山、Kimi、混元、星火、阶跃                                    |

> 这两条守卫都是被真实数据逼出来的，不是想象出来的风险：
>
> - **输出模态**：OpenRouter 上有 token 价格为 0、但按生成秒数计费的音乐模型（`google/lyria-3-*`），纯看价格会被误判成免费。
> - **listing 必须给依据**：B.AI 是聚合转售平台，同一个 `/models` 目录里既有活动免费的 DeepSeek-V4-Flash，也有 GPT-5.6 和 Claude Opus 5。`listing` 模式如果默认信任整个目录，就会把 Claude Opus 5 当免费模型接进 `free-router`。现在缺依据的 provider 文件**直接加载失败**，不会带着隐患跑起来。

每个平台的判定依据写在 `providers/<id>.yaml` 的 `free_basis` 字段里，附带核对日期。**静态清单可以写得宽松**——写错的、下架的会在第一次探测时被隔离，不会污染 `free-router`。

## 已接入的平台

**填任意一个平台的 Key 就能跑起来**，留空的自动跳过。每个平台当前有哪些免费模型见自动生成的 [catalog/FREE-MODELS.md](catalog/FREE-MODELS.md)。

<!-- BEGIN GENERATED: platforms — 由 make docs 生成，请勿手改 -->

### 永久免费层（长期可用）

| 平台 | 区域 | 免费什么 | 限额 | |
|---|---|---|---|---|
| [Cerebras](https://inference-docs.cerebras.ai/introduction) | 国际 | Llama、Qwen 等高速推理 | 30 RPM | [**注册**](https://cloud.cerebras.ai/platform/apikeys) |
| [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) | 国际 | Llama、Qwen、Mistral 等 50+ 模型 | 每天 10,000 Neurons 为账号共享额 | [**注册**](https://dash.cloudflare.com/profile/api-tokens) |
| [Cohere](https://docs.cohere.com/docs/rate-limits) | 国际 | Command 系列（仅限非商业用途） | 20 RPM、33 次/天 | [**注册**](https://dashboard.cohere.com/api-keys) |
| [Google AI Studio (Gemini)](https://ai.google.dev/gemini-api/docs/rate-limits) | 国际 | Gemini Flash 与 Gemma 系列 | 15 RPM、1500 次/天 | [**注册**](https://aistudio.google.com/apikey) |
| [Groq](https://console.groq.com/docs/models) | 国际 | Llama、Qwen 等全系模型，LPU 超高速推理 | 30 RPM、14400 次/天 | [**注册**](https://console.groq.com/keys) |
| [Mistral AI](https://docs.mistral.ai/getting-started/models/models_overview/) | 国际 | Mistral Small/Large、Codestral 等全系文本模型 | 60 RPM | [**注册**](https://console.mistral.ai/api-keys) |
| [魔搭社区 ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | 国内 | Qwen3、DeepSeek、GLM 等 25 个开源模型免费推理 | 2000 次/天 | [**注册**†](https://modelscope.cn/register?inviteCode=MarkWave&invitorName=MarkWave) · [官网](https://modelscope.cn/my/myaccesstoken) |
| [NVIDIA NIM](https://build.nvidia.com/models) | 国际 | Llama、Gemma、Mistral 等 100+ 开源模型 | 40 RPM | [**注册**](https://build.nvidia.com/settings/api-keys) |
| [OpenRouter](https://openrouter.ai/docs) | 国际 | 20+ 个 :free 后缀模型，DeepSeek/Gemma/Nemotron 等 | 20 RPM、50 次/天 | [**注册**](https://openrouter.ai/settings/keys) |
| [百度千帆](https://cloud.baidu.com/doc/qianfan-api/index.html) | 国内 | ERNIE Speed / Lite / Tiny 永久免费不限量 | 有 QPS 限制，需要完成实名认证 | [**注册**](https://console.bce.baidu.com/iam/#/iam/apikey/list) |
| [硅基流动 SiliconFlow](https://docs.siliconflow.cn/cn/userguide/quickstart) | 国内 | Qwen3-8B、GLM-4-9B 等 9B 以下开源模型永久免费 | 免费模型有 RPM/TPM 限制，具体见控制台 | [**注册**†](https://cloud.siliconflow.cn/i/CuI9M5Ht) · [官网](https://cloud.siliconflow.cn/account/ak) |
| [ZenMux](https://zenmux.ai/docs) | 国际 | 自动发现平台上所有 0 价模型 | 以控制台公布的并发与速率为准 | [**注册**†](https://zenmux.ai/invite/L4QDZW) · [官网](https://zenmux.ai/settings/keys) |
| [智谱 AI (BigModel)](https://docs.bigmodel.cn/cn/guide/start/model-overview) | 国内 | GLM-4.7-Flash 等 Flash 系列长期免费 | 免费模型并发较低（部分为 1 并发），需要手机号 | [**注册**†](https://www.bigmodel.cn/invite?icode=bkHx%2Fep6dDks7UF3yJZB4LC%2Fk7jQAKmT1mpEiZXXnFw%3D) · [官网](https://bigmodel.cn/usercenter/apikeys) |

### 新用户赠送额度（有有效期）

| 平台 | 区域 | 免费什么 | 限额 | |
|---|---|---|---|---|
| [阿里云百炼 (DashScope)](https://help.aliyun.com/zh/model-studio/models) | 国内 | 通义千问 Qwen-Turbo / Plus / Flash | 需要实名认证；赠送额度到期后模型会被探测判定为  | [**注册**](https://bailian.console.aliyun.com/?tab=model#/api-key) |
| [DeepSeek 开放平台](https://api-docs.deepseek.com/zh-cn/) | 国内 | DeepSeek-V3 与 R1 推理模型 | 赠送额度通常在注册后 30 天内有效 | [**注册**](https://platform.deepseek.com/api_keys) |
| [腾讯混元](https://cloud.tencent.com/document/product/1729) | 国内 | 腾讯混元 Lite / Turbo | 需要开通混元大模型服务 | [**注册**](https://console.cloud.tencent.com/hunyuan/api-key) |
| [月之暗面 Kimi](https://platform.moonshot.cn/docs/intro) | 国内 | Kimi 长文本模型 | 速率与并发按账户等级浮动 | [**注册**](https://platform.moonshot.cn/console/api-keys) |
| [讯飞星火](https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html) | 国内 | 讯飞星火 Lite 与 V3.5 | API Key 使用「APIPassword」形 | [**注册**](https://console.xfyun.cn/services/cbm) |
| [阶跃星辰 StepFun](https://platform.stepfun.com/docs/overview/concept) | 国内 | 阶跃 Step-1 / Step-2 系列 | 体验额度有效期较短 | [**注册**](https://platform.stepfun.com/interface-key) |
| [火山引擎 (豆包)](https://www.volcengine.com/docs/82379) | 国内 | 豆包 Doubao 系列 | 若账号未开通模型或仍要求 endpoint id | [**注册**](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey) |

### 限时活动（随时可能调整）

| 平台 | 区域 | 免费什么 | 限额 | |
|---|---|---|---|---|
| [B.AI](https://docs.b.ai) | 国际 | DeepSeek-V4-Flash 系列限时 0 Credits 不限量 | 需要在账户中保留少量 Credits 用于身份校 | [**注册**†](https://chat.b.ai/chat?invite_code=H82845) · [官网](https://b.ai) |

### 已跟踪但不路由

- **百度文心快码 Comate**（`watch`）：测试版活动提供不限量 Token，但只在 Comate Auto 邀测版客户端内可用，没有公开的 OpenAI 兼容 API，因此只跟踪活动到期、不接入路由
- **GitHub Models**（`retired`）：GitHub Models 已于 2026-07-30 完全退役，playground、模型目录、推理 API 和 BYOK 全部关闭，官方引导迁移到 Azure AI Foundry。调研文档中这一条已过期。
- **Hugging Face 推理**（`paused`）：每月少量免费额度；Inference Providers 的模型标识需要带上具体的 provider 段（例如 together/…），无法用统一规则自动发现

> † 标记的是邀请链接，通过它注册**你和维护者双方都会拿到平台奖励**：
>
> - **B.AI**：被邀请人注册可领 30 万积分（官方仅公布受邀方奖励，邀请方奖励未说明）
> - **魔搭社区 ModelScope**：双方各得魔方（ModelScope 平台积分），注册即得无需充值
> - **硅基流动 SiliconFlow**：双方各得 2000 万 tokens（约 ¥14 平台额度，不可提现）
> - **ZenMux**：双方各得 $5 credit，被邀请人首次充值后额外获得 25% 奖励
> - **智谱 AI (BigModel)**：好友实名注册后双方各得 Tokens 资源包，无需充值
>
> 旁边的「官网」是无返利直达入口，两个都能用，注册流程一样。返利不影响任何技术判断，见[下方说明](#挂自己的邀请链接)。

<!-- END GENERATED: platforms -->

## 查看调用了什么

```bash
make calls
```

```
时间      结果  耗时      tokens   来源
05:30:27  OK    3223ms    87+32    调用
          free-router  →  openai/deepseek/deepseek-v4-flash-vision-exp-free
05:32:41  FAIL  -         0+0      探测
          fr/openrouter/google/gemma-4-26b-a4b-it:free  →  openrouter/google/gemma-4-26b-a4b-it:free
```

「来源」区分你自己的调用和刷新器的健康探测（探测请求带 `freerouter-probe` 标签）。只想看自己的流量：

```bash
docker compose exec refresher python -m freerouter calls 30 --no-probe
```

更完整的视图在 LiteLLM Dashboard：`http://127.0.0.1:4000/ui` 的 Logs 页，能看到每次请求的完整 messages、response、延迟、重试链路，并支持按模型和时间筛选。底层数据在 Postgres 的 `LiteLLM_SpendLogs` 表，也可以直接查 `GET /spend/logs`。

三个命令各看一层：

| 命令             | 回答什么问题                               |
| ---------------- | ------------------------------------------ |
| `make calls`   | 刚才那次请求到底走了谁？多久？多少 token？ |
| `make pool`    | 现在有哪些模型可用？挂掉的是为什么挂的？   |
| `make changes` | 这几天模型池发生过什么增删？               |

## 挂自己的邀请链接

### 各平台邀请计划调研（2026-08-25 核查）

| 平台                                      | 邀请计划                     | 奖励                                     | 是否需要充值               |
| ----------------------------------------- | ---------------------------- | ---------------------------------------- | -------------------------- |
| **硅基流动**                        | 有，已接入                   | 双方各得 2000 万 tokens（约 ¥14 额度）  | **否，注册即得**     |
| **智谱 BigModel**                   | 有，已接入                   | 好友实名注册后双方各得 Tokens 资源包     | **否，注册即得**     |
| **魔搭 ModelScope**                 | 有，已接入                   | 双方各得魔方（平台积分）                 | **否，注册即得**     |
| **ZenMux**                          | 有，已接入                   | 双方各得 $5 credit，被邀请人首充额外 25% | **是，奖励绑定首充** |
| OpenRouter                                | 仅内部推荐，无公开 affiliate | 双方各得 $5 credits                      | **是，需消费 $10+**  |
| 阿里云百炼 / DeepSeek / Kimi / 火山引擎   | 公开渠道未发现               | —                                       | —                         |
| 百度千帆 / 腾讯混元 / 阶跃星辰 / 讯飞星火 | 公开渠道未发现               | —                                       | —                         |
| Groq / Cerebras / Gemini / NVIDIA NIM     | 公开渠道未发现               | —                                       | —                         |
| Mistral / Cohere / Cloudflare / B.AI      | 公开渠道未发现               | —                                       | —                         |

> 「公开渠道未发现」只代表搜索和官方文档里没查到，**不代表一定没有**。ZenMux 和 ModelScope 起初都归在这一类，登录账户后台后都找到了邀请入口。想确认某家有没有，最快的办法是登进自己的控制台翻「邀请/推荐/Referral」。

前四家的奖励性质不同，值得分开看：硅基流动、智谱、ModelScope 是**注册即得**，跟本项目「用免费模型」的定位一致；ZenMux 的 $5 credit 要被邀请人**首次充值后**才发放，所以它的 `referral_note` 里明确写了这个门槛。OpenRouter 门槛更高（需累计消费 $10），暂未接入。

### 怎么加

在对应的 `providers/<id>.yaml` 里填两行：

```yaml
console_url: https://cloud.siliconflow.cn/account/ak          # 必须保留：无返利的直达入口
referral_url: https://cloud.siliconflow.cn/i/你的邀请码
referral_note: 双方各得 2000 万 tokens（约 ¥14 平台额度，不可提现）
```

然后跑一次 `make docs`，链接会**同时出现在三个用户真正会看的地方**：

| 位置                                   | 效果                                                 |
| -------------------------------------- | ---------------------------------------------------- |
| README 上方的平台表格                  | 「注册†」按钮直接指向你的链接，旁边保留「官网」直达 |
| `.env.example` 里对应 Key 的上方注释 | 用户填 Key 时正好看到「注册领 Key: 你的链接」        |
| `make keys` 终端输出                 | 列出所有没配置的平台和注册地址                       |

这三处都是从 `providers/*.yaml` 生成的，中间用 `<!-- BEGIN GENERATED -->` 标记圈起来，手写内容不受影响。改了注册表忘了跑 `make docs`，CI 会失败（`test_generated_blocks_in_the_repo_are_up_to_date`）。

`make catalog` 会同时刷新 [catalog/FREE-MODELS.md](catalog/FREE-MODELS.md) 和这三处。

三条规矩是**代码强制**的，不是自觉：

| 规矩                                                             | 怎么强制的                                                                                                                              |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 填了`referral_url` 就必须填 `referral_note` 说明双方各得什么 | 缺了直接加载失败（`ReferralWithoutDisclosureError`）                                                                                  |
| 必须同时保留`console_url` 无返利入口，读者可以二选一           | `test_shipped_referral_links_all_state_the_benefit`                                                                                   |
| 返利不得参与任何路由决策                                         | `test_referral_links_cannot_influence_routing`：`discovery/planning/probe/refresh/traffic` 五个模块一旦出现 `referral` 字样就失败 |

最后一条最要紧。这个项目卖的是「诚实判定免费模型」，一旦让人怀疑「是不是因为有返利才把这家排前面」，公信力就没了。所以哪个平台进 `providers/`、哪个模型进 `free-router` 池，只看 `free_basis` 写明的免费依据和真实探测结果，排序按平台 id 字母序——这条用测试锁死，改不动。

如果你 fork 这个项目，把 `referral_url` 换成自己的就行，其余不用动。

## 变更通知

在 `.env` 里填一个 webhook 就行，格式自动适配：

```dotenv
FREEROUTER_NOTIFY_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
```

支持飞书、企业微信、钉钉、Slack、Discord，以及任何接收 `{"text": "..."}` 的通用端点。不填就只写本地日志，用 `make changes` 查看。

## 平台的怪脾气怎么处理

有些平台有自己的规矩，比如 **ModelScope 的思考模型在非流式调用下会返回 `choices: null`**（Qwen3 和 ERNIE 都会），必须显式关掉思考模式。这类平台级参数写在 `extra_params` 里，会合并进该平台每个 deployment 的 `litellm_params`，**对探测和真实流量同时生效**：

```yaml
extra_params:
  enable_thinking: false
```

不要只在探测里绕过这种问题——探测通过但真实调用返回空，比探测直接失败更糟。

## 加一个新平台

在 `providers/` 下新建一个 YAML 就行，不用改代码：

```yaml
id: newplatform
name: New Platform
name_zh: 新平台
tier: free                    # free 永久免费 / trial 新用户额度 / offer 限时活动
region: cn
credential: NEWPLATFORM_API_KEY
litellm_prefix: openai        # LiteLLM 原生前缀，或 openai + api_base
api_base: https://api.newplatform.com/v1
docs_url: https://docs.newplatform.com
free_basis: 官方文档写明 xxx 系列永久免费
free_basis_checked: 2026-08-25
limits:
  rpm: 30
discovery:
  mode: listing
  url: https://api.newplatform.com/v1/models
  auth: bearer
  deny: ["*embed*"]
```

然后把 `NEWPLATFORM_API_KEY` 加进 `.env.example` 和 `.env`，`make refresh` 立刻生效。

## 常用命令

| 命令                        | 用途                                                                                                                 |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `make verify`             | 一条命令自检：网关、模型名、池健康度、刷新器、真实请求。`make verify MODEL=zenmux-free` 只测一个平台               |
| `make setup`              | 生成`.env`；已存在时补齐新增的配置项，不动已有值                                                                   |
| `make up` / `make down` | 启动 / 停止                                                                                                          |
| `make pool`               | 查看当前模型池，每个模型的健康状态和失败原因                                                                         |
| `make calls`              | 查看最近的调用记录：请求名 → 实际命中哪个平台的哪个模型、耗时、tokens。`make calls N=50` 调条数                   |
| `make changes`            | 查看最近的模型池变更记录                                                                                             |
| `make refresh`            | 立刻跑一轮发现 + 探测 + 热更新                                                                                       |
| `make recheck`            | 修好根因（补了 Key、绑了账号、改了配置）后清掉隔离与退避，立刻重新探测。`make recheck P=modelscope` 只重检一个平台 |
| `make keys`               | 列出所有平台：哪些已配置、没配的去哪注册领 Key                                                                       |
| `make docs`               | 把平台表格同步进 README 和`.env.example` 的生成块                                                                  |
| `make catalog`            | 刷新`catalog/` 快照，并同步 README 与 `.env.example`                                                             |
| `make logs`               | 网关与刷新器日志                                                                                                     |
| `make test`               | 发一次真实 API 请求                                                                                                  |
| `make update`             | 拉取并重启最新 LiteLLM 镜像                                                                                          |
| `make check`              | 跑测试、lint、类型检查和 compose 校验                                                                                |
| `make install-skill`      | 安装 FreeRouter Skill                                                                                                |

## 调优

全部在 `.env` 里：

| 变量                             | 默认      | 说明                                                                       |
| -------------------------------- | --------- | -------------------------------------------------------------------------- |
| `FREEROUTER_REFRESH_INTERVAL`  | `21600` | 刷新间隔（秒），最小 300                                                   |
| `FREEROUTER_RECHECK_HOURS`     | `24`    | 健康模型多久**没有成功记录**才需要主动探测（有真实流量就一直不触发） |
| `FREEROUTER_FAILURE_THRESHOLD` | `3`     | 连续失败几次移出池子                                                       |
| `FREEROUTER_OFFER_WARN_DAYS`   | `14`    | 限时活动到期前几天提醒                                                     |
| `FREEROUTER_NOTIFY_WEBHOOK`    | 空        | 变更推送地址                                                               |

每个平台的 `max_models` 和 `probe.max_per_cycle` 在各自的 YAML 里调。

`probe.max_per_cycle` 是**每轮探测的上限**，不是固定开销——有真实流量时实际探测数通常是 0。它的作用是兜住最坏情况：`最坏每天探测次数 = max_per_cycle × (86400 ÷ FREEROUTER_REFRESH_INTERVAL)`。默认 6 小时一轮即每天 4 轮。

对有明确额度上限的平台这个天花板要压住。OpenRouter 免费层只有 **50 次/天**，所以给它 `max_per_cycle: 2`（最坏 8 次/天，占 16%）；Cohere 是月额度 1000，折算成 `rpd: 33` 后给 `max_per_cycle: 1`。这条约束有 CI 测试守着（`test_no_provider_spends_its_daily_quota_on_health_probes`），谁调大了会直接失败。

额度打满后探测会返回 `throttled`——**不算故障、不会踢出池**，因为日额度第二天会重置，但期间路由到该平台的请求需要靠重试转到别的平台。

## 自己的付费模型

FreeRouter 只托管 `free-router`、`<平台>-free`、`fr/…` 这三类别名（在 LiteLLM 里带 `fr-` 前缀的 deployment id）。你自己写进 `config/litellm-config.yaml` 的模型不会被碰：

```yaml
model_list:
  - model_name: my-gpt
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
```

## 安全说明

- `.env` 已被 Git 忽略，禁止提交真实平台 Key、Master Key 或数据库密码。
- 默认只监听 `127.0.0.1`，不会直接暴露到局域网或公网。
- 若需要远程访问，请额外配置身份验证、TLS 和访问控制。
- `state/` 是运行期状态，已被 Git 忽略；`catalog/` 是自动生成的公开目录，会入库。
- Dashboard 与 API 共用 LiteLLM 的数据库，删除 Docker volume 会同时删掉已托管的模型和用量记录。

## 更新 LiteLLM

```bash
make update
```

项目默认直接使用 LiteLLM 官方 Docker 镜像。上游地址、版本固定方式和更新说明见 [UPSTREAM.md](UPSTREAM.md)。

## License

FreeRouter 使用 MIT License。LiteLLM 是独立上游项目，其源码和许可由 [BerriAI/litellm](https://github.com/BerriAI/litellm) 维护。
