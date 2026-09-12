# 开发记录

## 第 6 步：本地交付与完整人工验收

- 日期：2026-09-12。未修改业务行为，应用接口版本保持 0.5.0。
- 新增 Postman Collection（健康检查和六个业务接口）、0.1 秒静音 WAV 样例、本地启动与人工验收指南。
- README 补齐完整架构图、表字段和索引、技术取舍、数据维护和已知限制；Compose 增加数据卷用途注释。保留原有生命周期与业务日志，使用 `docker compose logs --timestamps` 查看时间。
- 一键命令补充 --wait --wait-timeout 120，确保命令成功结束时两个服务健康。

| 本轮实际验收 | 结果 |
| --- | --- |
| 隔离项目 speech-step6，从全新 MySQL/上传卷启动 | 一条 up --build --wait 命令成功，两个服务 healthy |
| 隔离环境 /docs | HTTP 200，端口 18001 |
| 一次性独立 ASGI 进程 + 真实 MySQL + 本地摘要替身 | 上传 → Mock 失败 → 手动重试 → done → 任务、详情、分页查询通过 |
| 实际重启隔离 API | pending、transcribing、summarizing 三个样例均 failed / SERVICE_RESTARTED，不自动续跑 |
| 完成态持久化 | done 状态、摘要和文件跨重启保留 |
| 实际 HTTP 删除唯一指定完成态样例 | 204 空响应，单个文件清理成功 |
| Postman JSON 与脚本 | 七个请求解析成功；独立执行变量保存脚本可正确捕获两个 ID |
| samples/demo.wav | 单声道、8000Hz、800 帧，合法 0.1 秒静音 WAV |
| 原有 18000 服务 | /health 返回 200、database=ok，未停止 |

未在 Postman 桌面界面中实际执行导入；通过 JSON 结构、请求内容与 ID 脚本检查，提供用户导入步骤。不增加测试套件、自动轮询或自动重试。真实 DeepSeek 调用为 0 次；第四步的一次真实成功记录仍保留。

隔离环境使用 .env.step6（Git 忽略、空 API Key、随机数据库密码），本轮结束时已停止两个容器，保留 speech-step6_mysql_data 与 speech-step6_uploads 两个卷及三个小型中断样例，不批量删除。原有业务卷没有修改。恢复隔离环境可使用 `docker compose -p speech-step6 --env-file .env.step6 up -d --wait`。

本次通过 HTTP 删除的唯一验收录音为 bd9ed8fe-a53f-48a3-865d-44326427ef9e。其他验收是一次性命令，没有写入仓库测试文件。

尚未完成第 7 步 Azure 公网部署，需要届时提供 Azure 订阅、资源/VM、地区预算及 SSH 信息；本轮未创建或操作 Azure 资源。

代码/交付提交主题：`docs: add local setup and API acceptance guide`，提交后补记远程核对结果。

## 第 5 步：失败重试、删除与并发保护

- 日期：2026-09-12，版本 0.5.0。
- 新增 POST /v1/tasks/{task_id}/retry 和 DELETE /v1/recordings/{id}，补充行锁、状态检查、注释与阶段日志；不改变表结构。
- 重试复用 task_id，attempt 递增，清空错误/时间/旧摘要并保留 transcript；后台复用成功转写，无转写才执行 Mock。
- 删除只允许终态，与重试统一锁定任务行；单文件清理失败回滚数据库，缺失文件可继续清理。

| 人工验收（真实 MySQL + 独立 ASGI 进程、本地摘要替身） | 结果 |
| --- | --- |
| 两个并发重试请求 | 分别 202、409；attempt=2，摘要替身仅调用一次 |
| 已有 transcript | 跳过 Mock，旧错误与结束时间清空，最终 done |
| 删除活动任务、重试 done 任务 | 409 |
| 注入单文件删除权限错误 | 500 FILE_DELETE_FAILED，文件与数据库记录保留 |
| 删除终态样例 | 204 空响应，单文件不存在，关联任务 404 |
| 再次删除、重试已删除任务 | 404 |
| 无 transcript 的 Mock 失败后重试 | 重新 Mock 成功，attempt=2，使用本地摘要后 done |

第一条验收录音 ac1090c7-90d6-469d-a3c8-273f31caf071 对应文件 69952136-e021-464b-81d8-653a5fde1f50.wav，通过 DELETE 接口单独删除。第二条验收录音 a1ad83b7-8295-4346-8746-2ff0d0c3d85b 也仅删除自己的单个文件及关联数据。没有批量删除，保留前三、四步的原有演示记录。

本轮没有真实 DeepSeek 请求（0 次），没有新增自动化测试套件；替身不影响运行中的真实服务。文件系统和数据库不能原子提交的限制已写入 README。第 6 步交付材料与第 7 步 Azure 部署仍待完成。

代码提交主题：`feat: support safe retry and recording deletion`。

- 代码提交：`6ff5585a1b7962f80528ed2a658778d811ba01df`。
- 链接：https://github.com/w507603361/Speech-to-Text-API/commit/6ff5585a1b7962f80528ed2a658778d811ba01df 。
- 已推送 origin/main 并通过 ls-remote 核对；本条记录以独立文档提交追加。
- 最终 /health 返回 200，database=ok；本机继续使用 18000 端口。

## 第 4 步：真实 DeepSeek 摘要

- 日期：2026-09-11；版本 0.4.0；新增 deepseek.py 与 HTTPX 依赖。
- 根据 DeepSeek 2026-09-10 官方发布说明，V4.1-Flash 的 API ID 为 deepseek-flash；Compose 使用该默认值，无需修改现有密钥。
- 生命周期内共享 HTTP 客户端，使用 JSON Output、关闭思考、512 输出 token 上限、60 秒总超时，不自动重试。
- Pydantic 严格校验摘要结构；任务失败保存业务错误码并保留 transcript；结果与 done/finished_at 同事务保存。
- 注释明确 JSON 结构校验、总超时、密钥保护和事务边界；日志关联 task_id/recording_id/attempt，记录模型、阶段、耗时与错误码。

| 验收 | 结果 |
| --- | --- |
| 本地 HTTP 替身：合法 JSON、空待办数组 | 通过 |
| 本地替身：空内容、非法 JSON、缺字段、错误类型、截断 | LLM_INVALID_OUTPUT |
| 本地替身：401 / 402 / 429 / 503 | 对应认证、余额不足、限流、上游错误码 |
| 本地替身：读取超时 | LLM_TIMEOUT |
| 本地替身：总等待超时 + 完整任务执行 | failed / LLM_TIMEOUT，transcript 保留、结果仍为空 |
| HTTP 上传 + 默认随机 Mock + 真实 DeepSeek | 202 → transcribing → summarizing → done，详情含三字段摘要 |
| 真实摘要请求数 | 1 次，无自动重试；约 1.02 秒完成，不估算未经计量的费用 |

真实成功样例：recording_id=884f12d1-5483-4b9f-b49c-08bf6bcacffa，task_id=cd1f177a-c403-4b44-86e8-5022118efa31，文件 stage4.wav 为 7 字节演示数据。固定 Mock 文本没有敏感内容。保留该 done 样例供查看，不删除文件。

旧 stage3 样例用于零费用错误验收，最终状态为 failed / LLM_TIMEOUT。本轮替身只运行在独立验收进程，没有替换正在运行的真实客户端，也未添加自动化测试套件。

密钥仅从 .env 注入应用容器，不进入镜像或 Git。第 5 步的重试与删除、第 7 步 Azure 部署尚未实现。

代码提交主题：`feat: generate validated summaries with DeepSeek`。

- 代码提交：`a1a9425cf4fcfbfac5f1c322afdaac7195cf088f`。
- 链接：https://github.com/w507603361/Speech-to-Text-API/commit/a1a9425cf4fcfbfac5f1c322afdaac7195cf088f 。
- 已推送 origin/main 并以 ls-remote 核对；本条记录作为独立文档提交追加。
- pip check 通过；暂存内容与 .env 敏感变量比对通过，未包含真实密钥。

## 第 3 步：异步 Mock 转写与查询

- 日期：2026-09-11；版本 0.3.0；新增 routes.py 与 tasks.py。
- 开放 POST /v1/recordings、GET /v1/tasks/{task_id}、GET /v1/recordings、GET /v1/recordings/{id}。
- 增加 multipart 解析依赖、统一参数/HTTP/数据库错误处理、UTC 时间序列化。
- 上传事务完成后注册 asyncio 任务，保留引用、结束释放；启动前将遗留任务标记失败，关闭时取消后台协程。
- 注释说明了状态领取、生命周期、事务快照和 Mock 中间态；日志记录转写耗时、任务阶段、失败原因与重启中断。

| 人工验收 | 实际结果 |
| --- | --- |
| HTTP multipart 上传 | 202、pending；约 0.031 秒返回，未等待转写 |
| 真实随机 Mock 成功 | 约 6 秒后 summarizing；固定 transcript 已持久化，summary_result=null |
| 任务、详情、分页列表 | 均 200，状态一致，详情不暴露 storage_path，时间含 UTC 时区 |
| page=0、非法 UUID | 统一 400 INVALID_REQUEST |
| 不存在的任务 UUID | 404 TASK_NOT_FOUND |
| 实际重启 API | summarizing 变为 failed / SERVICE_RESTARTED，未自动续跑 |
| 一次性验收进程固定随机值 | failed / ASR_FAILED；再次调用同一任务不会执行，条件领取生效 |
| 重启后健康检查 | 200，database=ok |

本轮保留一条 7 字节非敏感样例 stage3.wav，录音 ID 为 c35ca08d-88f7-4f5a-b50b-b01d42fa9cd5，任务 ID 为 800e43e3-2b48-4e7b-9823-efb1ad3816eb；最终为定向验收的 ASR_FAILED。没有删除文件、没有添加自动化测试套件，DeepSeek 请求为 0 次。

成功停在 summarizing 是第 3 步的明确中间态；第 4 步实现摘要，第 5 步实现手动重试和删除。未实现任何额外加分项。

代码提交主题：`feat: add async transcription and query APIs`。

- 代码提交：`de8ea53efd553d987485a1997e6ec7190468bd83`。
- 链接：https://github.com/w507603361/Speech-to-Text-API/commit/de8ea53efd553d987485a1997e6ec7190468bd83 。
- 已推送 origin/main 并通过 ls-remote 核对；本条记录以独立文档提交追加。

## 第 2 步：文件与录音持久化

- 日期：2026-09-11；沿用 main 分支。
- 新增 storage.py、recordings.py 和 errors.py；增加必要中文注释，说明路径隔离、分块读写、事务和单文件补偿清理。
- 应用版本 0.2.0；增加 uploads 持久卷；SQL 无变更，不清空已有数据库。
- 日志记录 upload_started、upload_saved、task_created、upload_failed 和 upload_cleaned，关联 recording_id、task_id、attempt；失败日志包含错误类别，不输出凭据或文件内容。
- 按阶段计划不开放上传路由、不调度后台任务；本轮以一次性容器内调用验收，没有提交自动化测试套件，DeepSeek 调用 0 次。

| 人工验收 | 结果 |
| --- | --- |
| 缺少文件、空内容、非法扩展名 | APIError 400，未留下文件或数据库记录 |
| 50MB + 1 字节 | APIError 413，部分文件已清理 |
| 恰好 50MB、WAV 大写扩展名、原始路径 ../../acceptance.WAV | 成功；展示名 acceptance.WAV，磁盘名为 UUID.wav |
| 成功事务 | recordings 与 tasks 各增加一条，status=pending、attempt=1，磁盘字节数正确 |
| 在第二条 INSERT 前由 MySQL SIGNAL 注入错误 | APIError 500；第一条 INSERT 回滚，文件清理，两表计数不变 |
| 验收清理 | 仅删除样例文件 13d919aa-432a-433e-bde4-d1c86350f7eb.wav，以及录音 998f7f93-ed61-4b95-856d-9330b300092a 的关联数据 |

这是服务层验收，未将异常断言冒充已开放 HTTP 上传接口的验收。极端进程退出和提交结果不确定时的跨文件系统/数据库一致性限制见 README。

提交主题：`feat: persist uploaded recordings and pending tasks`。

- 代码提交：`f9612ef0160aabea83f38d287d089948c9895c78`。
- 链接：https://github.com/w507603361/Speech-to-Text-API/commit/f9612ef0160aabea83f38d287d089948c9895c78 。
- 已推送 origin/main，并通过 ls-remote 核对该代码提交；本条推送记录随后以独立文档提交追加。
- 最终重建后 /health 返回 status=ok、database=ok；本地服务继续使用 18000 端口。

## 第 1 步：FastAPI 与 MySQL 基础

- 日期：2026-09-11。
- 仓库：git@github.com:w507603361/Speech-to-Text-API.git。
- 主分支：main；本阶段通过验收后提交，不生成后续业务代码。
- 完成内容：FastAPI 入口、环境变量配置、SQLAlchemy 异步 MySQL 连接、数据库健康检查、初始化 SQL、Dockerfile、Compose、README 和忽略规则。
- 配置：保留原有 .env，补齐独立应用账号和随机数据库密码；MySQL 数据使用命名卷，不开放 3306 宿主机端口。
- 密钥：.env 不提交、不复制进 Docker 镜像；本阶段不调用 DeepSeek。
- 实施边界：不实现录音上传、转写、摘要或 Azure 部署，不编写自动化测试套件。
- 环境处理：Docker 镜像源首次返回 502，单独重试拉取官方 Python 镜像后成功；未修改全局镜像源。本机 8000 已占用，项目 .env 改用 18000，没有停止其他服务。
- 依赖：从 PyPI 核对并固定 FastAPI 0.141.1、Uvicorn 0.52.4、SQLAlchemy 2.0.52、asyncmy 0.2.14 和 cryptography 50.0.1。

### 验收结果

| 检查 | 结果 |
| --- | --- |
| Compose 配置与镜像构建 | 通过 |
| api / db 容器健康检查 | 均 healthy |
| GET http://localhost:18000/health | 200，status=ok，database=ok |
| GET http://localhost:18000/docs | 200 |
| MySQL 实际版本 | 8.4.11 |
| SQL 初始化 | recordings、tasks 两张表存在，唯一约束和外键存在 |
| 停止项目数据库 | /health 返回 503，error.code=DATABASE_UNAVAILABLE |
| 恢复项目数据库 | /health 返回 200，表仍存在 |
| pip check | No broken requirements found |
| DeepSeek 请求 | 0 次 |

本次只进行上述人工验收，没有创建自动化测试套件。首次启动的镜像下载问题和端口冲突均已解决。

### GitHub 提交记录

- 代码提交：`fd092d868bdeff2024beaba4538519b3d3fa8cf6`。
- 提交主题：`chore: initialize FastAPI and MySQL foundation`。
- 提交链接：https://github.com/w507603361/Speech-to-Text-API/commit/fd092d868bdeff2024beaba4538519b3d3fa8cf6 。
- 已推送至 `origin/main`，并通过 `git ls-remote` 确认远程 main 对应上述代码提交。
- 本条记录通过独立文档提交追加，保留代码提交原始历史；最终 main 因此包含代码提交和记录提交。
- 提交前核对 `.env` 已忽略，并将其敏感变量值与暂存 diff 比对，未发现泄漏。
