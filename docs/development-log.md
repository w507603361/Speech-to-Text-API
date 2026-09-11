# 开发记录

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

代码提交主题：`feat: add async transcription and query APIs`，推送后补记提交标识。

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
