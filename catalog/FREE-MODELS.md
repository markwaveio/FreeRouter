# FreeRouter 免费模型目录

最后变更：2026-08-25（由 `.github/workflows/watch-free-models.yml` 自动生成，请勿手改）

| 平台 | 类型 | 区域 | 状态 | 已知限额 | 免费模型数 | 活动到期 | 注册 |
|---|---|---|---|---|---|---|---|
| [B.AI](https://docs.b.ai) | offer | global | active | 需要在账户中保留少量 Credits 用于身份校验；活动随时可能调整 | 2 | - | [官网](https://b.ai) · [邀请链接†](https://chat.b.ai/chat?invite_code=H82845) |
| [Cerebras](https://inference-docs.cerebras.ai/introduction) | free | global | active | 30 RPM / 每日约 100 万 Token。若探测返回 402 Payment required，说明该账号未开通免费层，去 https://cloud.cerebras.ai 的 billing 页确认套餐 | 0 | - | [官网](https://cloud.cerebras.ai/platform/apikeys) |
| [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) | free | global | active | 每天 10,000 Neurons 为账号共享额度 | 0 | - | [官网](https://dash.cloudflare.com/profile/api-tokens) |
| [Cohere](https://docs.cohere.com/docs/rate-limits) | free | global | active | 20 RPM / 33 RPD / 官方限额是约 1000 次/月，这里折算成每天约 33 次填进 rpd，便于探测预算体检 | 0 | - | [官网](https://dashboard.cohere.com/api-keys) |
| [百度文心快码 Comate](https://comate.baidu.com/) | offer | cn | watch | 见官方文档 | 0 | 2026-09-24 | - |
| [阿里云百炼 (DashScope)](https://help.aliyun.com/zh/model-studio/models) | trial | cn | active | 需要实名认证；赠送额度到期后模型会被探测判定为 exhausted | 3 | - | [官网](https://bailian.console.aliyun.com/?tab=model#/api-key) |
| [DeepSeek 开放平台](https://api-docs.deepseek.com/zh-cn/) | trial | cn | active | 赠送额度通常在注册后 30 天内有效 | 2 | - | [官网](https://platform.deepseek.com/api_keys) |
| [Google AI Studio (Gemini)](https://ai.google.dev/gemini-api/docs/rate-limits) | free | global | active | 15 RPM / 1500 RPD / 各模型限额不同；欧盟、英国、瑞士可能没有免费层，且免费层数据可能用于训练 | 0 | - | [官网](https://aistudio.google.com/apikey) |
| [GitHub Models](https://github.blog/changelog/2026-07-30-github-models-is-now-retired/) | free | global | retired | 见官方文档 | 0 | - | - |
| [Groq](https://console.groq.com/docs/models) | free | global | active | 30 RPM / 14400 RPD / 各模型 RPD 从 1000 到 14400 不等 | 0 | - | [官网](https://console.groq.com/keys) |
| [Hugging Face 推理](https://huggingface.co/docs/inference-providers/en/pricing) | trial | global | paused | 每月约 0.10 美元额度，超出后按量计费 | 0 | - | [官网](https://huggingface.co/settings/tokens) |
| [腾讯混元](https://cloud.tencent.com/document/product/1729) | trial | cn | active | 需要开通混元大模型服务 | 2 | - | [官网](https://console.cloud.tencent.com/hunyuan/api-key) |
| [Mistral AI](https://docs.mistral.ai/getting-started/models/models_overview/) | free | global | active | 60 RPM / 约 1 RPS，每月约 10 亿 Token | 0 | - | [官网](https://console.mistral.ai/api-keys) |
| [魔搭社区 ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | free | cn | active | 2000 RPD / 单模型约 500 次/日。**必须先绑定阿里云账号**，否则所有调用返回 401；绑定入口 https://modelscope.cn/my/settings/account | 25 | - | [官网](https://modelscope.cn/my/myaccesstoken) · [邀请链接†](https://modelscope.cn/register?inviteCode=MarkWave&invitorName=MarkWave) |
| [月之暗面 Kimi](https://platform.moonshot.cn/docs/intro) | trial | cn | active | 速率与并发按账户等级浮动 | 3 | - | [官网](https://platform.moonshot.cn/console/api-keys) |
| [NVIDIA NIM](https://build.nvidia.com/models) | free | global | active | 40 RPM / 需要邮箱注册并完成手机验证 | 25 | - | [官网](https://build.nvidia.com/settings/api-keys) |
| [OpenRouter](https://openrouter.ai/docs) | free | global | active | 20 RPM / 50 RPD / 累计充值满 10 美元后约升至 1000 RPD | 18 | - | [官网](https://openrouter.ai/settings/keys) |
| [百度千帆](https://cloud.baidu.com/doc/qianfan-api/index.html) | free | cn | active | 有 QPS 限制，需要完成实名认证 | 6 | - | [官网](https://console.bce.baidu.com/iam/#/iam/apikey/list) |
| [硅基流动 SiliconFlow](https://docs.siliconflow.cn/cn/userguide/quickstart) | free | cn | active | 免费模型有 RPM/TPM 限制，具体见控制台 | 0 | - | [官网](https://cloud.siliconflow.cn/account/ak) · [邀请链接†](https://cloud.siliconflow.cn/i/CuI9M5Ht) |
| [讯飞星火](https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html) | trial | cn | active | API Key 使用「APIPassword」形式，需要在控制台开通对应服务 | 2 | - | [官网](https://console.xfyun.cn/services/cbm) |
| [阶跃星辰 StepFun](https://platform.stepfun.com/docs/overview/concept) | trial | cn | active | 体验额度有效期较短 | 2 | - | [官网](https://platform.stepfun.com/interface-key) |
| [火山引擎 (豆包)](https://www.volcengine.com/docs/82379) | trial | cn | active | 若账号未开通模型或仍要求 endpoint id，探测会把该模型隔离并写入变更日志 | 4 | - | [官网](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey) |
| [ZenMux](https://zenmux.ai/docs) | free | global | active | 以控制台公布的并发与速率为准 | 7 | - | [官网](https://zenmux.ai/settings/keys) · [邀请链接†](https://zenmux.ai/invite/L4QDZW) |
| [智谱 AI (BigModel)](https://docs.bigmodel.cn/cn/guide/start/model-overview) | free | cn | active | 免费模型并发较低（部分为 1 并发），需要手机号注册 | 6 | - | [官网](https://bigmodel.cn/usercenter/apikeys) · [邀请链接†](https://www.bigmodel.cn/invite?icode=bkHx%2Fep6dDks7UF3yJZB4LC%2Fk7jQAKmT1mpEiZXXnFw%3D) |

### † 关于邀请链接

标了 † 的是邀请链接，通过它注册，你和本项目维护者双方都会获得平台奖励：

- **B.AI**：被邀请人注册可领 30 万积分（官方仅公布受邀方奖励，邀请方奖励未说明）
- **魔搭社区 ModelScope**：双方各得魔方（ModelScope 平台积分），注册即得无需充值
- **硅基流动 SiliconFlow**：双方各得 2000 万 tokens（约 ¥14 平台额度，不可提现）
- **ZenMux**：双方各得 $5 credit，被邀请人首次充值后额外获得 25% 奖励
- **智谱 AI (BigModel)**：好友实名注册后双方各得 Tokens 资源包，无需充值

旁边的「官网」是无返利的直达入口，两个都能用，注册流程完全一样。

**返利不影响任何技术判断。** 一个平台能不能进 `providers/`、
一个模型能不能进 `free-router` 池，只取决于该平台 `free_basis` 字段写明的免费依据
和真实探测结果；排序按平台 id 字母序，与有无返利无关。
这一点有测试守着（见 `tests/test_registry.py`）。

## 各平台当前免费模型

### B.AI (`b-ai`)

> 需要凭证，CI 未刷新

- `deepseek-v4-flash`
- `deepseek-v4-flash-vision-exp`

### Cerebras (`cerebras`)

> 需要凭证，CI 未刷新

_当前没有可路由的免费模型。_

### Cloudflare Workers AI (`cloudflare`)

> 需要凭证，CI 未刷新

_当前没有可路由的免费模型。_

### Cohere (`cohere`)

> 需要凭证，CI 未刷新

_当前没有可路由的免费模型。_

### 百度文心快码 Comate (`comate`)

> watch

_当前没有可路由的免费模型。_

### 阿里云百炼 (DashScope) (`dashscope`)

- `qwen-flash`
- `qwen-plus`
- `qwen-turbo`

### DeepSeek 开放平台 (`deepseek`)

- `deepseek-chat`
- `deepseek-reasoner`

### Google AI Studio (Gemini) (`gemini`)

> 需要凭证，CI 未刷新

_当前没有可路由的免费模型。_

### GitHub Models (`github-models`)

> GitHub Models 已于 2026-07-30 完全退役，playground、模型目录、推理 API 和 BYOK 全部关闭，官方引导迁移到 Azure AI Foundry。调研文档中这一条已过期。

_当前没有可路由的免费模型。_

### Groq (`groq`)

> 需要凭证，CI 未刷新

_当前没有可路由的免费模型。_

### Hugging Face 推理 (`huggingface`)

> paused

_当前没有可路由的免费模型。_

### 腾讯混元 (`hunyuan`)

- `hunyuan-lite`
- `hunyuan-turbos-latest`

### Mistral AI (`mistral`)

> 需要凭证，CI 未刷新

_当前没有可路由的免费模型。_

### 魔搭社区 ModelScope (`modelscope`)

- `MedAIBase/AntAngelMed`
- `MiniMax/MiniMax-M1-80k`
- `MiniMax/MiniMax-M3`
- `PaddlePaddle/ERNIE-4.5-0.3B-PT`
- `PaddlePaddle/ERNIE-4.5-21B-A3B-PT`
- `PaddlePaddle/ERNIE-4.5-300B-A47B-PT`
- `Qwen/Qwen3-14B`
- `Qwen/Qwen3-235B-A22B`
- `Qwen/Qwen3-235B-A22B-Instruct-2507`
- `Qwen/Qwen3-235B-A22B-Thinking-2507`
- `Qwen/Qwen3-30B-A3B`
- `Qwen/Qwen3-30B-A3B-Thinking-2507`
- `Qwen/Qwen3-4B`
- `Qwen/Qwen3-8B`
- `Qwen/Qwen3-Coder-30B-A3B-Instruct`
- `Qwen/Qwen3-Next-80B-A3B-Instruct`
- `Qwen/Qwen3-Next-80B-A3B-Thinking`
- `Qwen/Qwen3.5-122B-A10B`
- `Qwen/Qwen3.5-27B`
- `Qwen/Qwen3.5-35B-A3B`
- `Qwen/Qwen3.5-397B-A17B`
- `Qwen/Qwen3.8-27B`
- `Shanghai_AI_Laboratory/Intern-S1`
- `Shanghai_AI_Laboratory/Intern-S1-mini`
- `Shanghai_AI_Laboratory/Intern-S2-Preview`

### 月之暗面 Kimi (`moonshot`)

- `kimi-latest`
- `moonshot-v1-32k`
- `moonshot-v1-8k`

### NVIDIA NIM (`nvidia-nim`)

- `ai21labs/jamba-1.5-large-instruct`
- `aisingapore/sea-lion-7b-instruct`
- `databricks/dbrx-instruct`
- `deepseek-ai/deepseek-coder-6.7b-instruct`
- `google/gemma-3-12b-it`
- `google/gemma-3-4b-it`
- `google/gemma-4-31b-it`
- `ibm/granite-3.0-3b-a800m-instruct`
- `ibm/granite-3.0-8b-instruct`
- `ibm/granite-34b-code-instruct`
- `ibm/granite-8b-code-instruct`
- `meta/llama-3.1-70b-instruct`
- `meta/llama-3.1-8b-instruct`
- `meta/llama-3.2-1b-instruct`
- `meta/llama-3.2-3b-instruct`
- `meta/llama-3.3-70b-instruct`
- `microsoft/phi-3.5-moe-instruct`
- `mistralai/codestral-22b-instruct-v0.1`
- `mistralai/mistral-7b-instruct-v0.3`
- `mistralai/mistral-large-2-instruct`
- `nv-mistralai/mistral-nemo-12b-instruct`
- `nvidia/llama-3.1-nemotron-51b-instruct`
- `nvidia/llama-3.1-nemotron-70b-instruct`
- `nvidia/llama3-chatqa-1.5-70b`
- `nvidia/mistral-nemo-minitron-8b-8k-instruct`

### OpenRouter (`openrouter`)

- `cohere/north-mini-code:free`
- `dots-studio/dots-3-note-preview:free`
- `google/gemma-4-26b-a4b-it:free`
- `google/gemma-4-31b-it:free`
- `liquid/lfm-2.5-2.6b:free`
- `minimax/minimax-m2.7:free`
- `minimax/minimax-m3:free`
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- `nvidia/nemotron-3-super-120b-a12b:free`
- `nvidia/nemotron-3-ultra-550b-a55b:free`
- `nvidia/nemotron-3.5-lightning:free`
- `openrouter/free`
- `poolside/laguna-s-2.1:free`
- `poolside/laguna-xs-2.1:free`
- `stealth/ox-alpha`
- `thinkingmachines/inkling-small:free`
- `thinkingmachines/inkling:free`
- `z-ai/glm-5.2:free`

### 百度千帆 (`qianfan`)

- `ernie-lite-8k`
- `ernie-lite-pro-128k`
- `ernie-speed-128k`
- `ernie-speed-8k`
- `ernie-speed-pro-128k`
- `ernie-tiny-8k`

### 硅基流动 SiliconFlow (`siliconflow`)

> 需要凭证，CI 未刷新

_当前没有可路由的免费模型。_

### 讯飞星火 (`sparkdesk`)

- `generalv3.5`
- `lite`

### 阶跃星辰 StepFun (`stepfun`)

- `step-1-8k`
- `step-2-mini`

### 火山引擎 (豆包) (`volcengine`)

- `doubao-lite-32k`
- `doubao-lite-4k`
- `doubao-pro-32k`
- `doubao-seed-1-6-flash-250715`

### ZenMux (`zenmux`)

- `deepseek/deepseek-v4-flash-vision-exp-free`
- `dots-studio/dots3-note-prev`
- `inclusionai/ling-3.0-tiny`
- `sapiens-ai/agnes-2.0-flash`
- `sapiens-ai/agnes-2.5-flash`
- `z-ai/glm-4.6v-flash-free`
- `z-ai/glm-4.7-flash-free`

### 智谱 AI (BigModel) (`zhipu`)

- `glm-4-flash`
- `glm-4-flash-250414`
- `glm-4.5-flash`
- `glm-4.7-flash`
- `glm-4v-flash`
- `glm-z1-flash`

