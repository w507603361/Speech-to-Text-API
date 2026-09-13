# 本地运行文档

项目最终保留前六步功能，通过 Docker Compose 在本机启动 FastAPI 和 MySQL。无需在宿主机安装 Python 或 MySQL；真实摘要需要 DeepSeek API 网络访问和可用额度。

## 1. 准备环境

启动 Docker Desktop，使用 Linux 容器。在 PowerShell 检查：

```powershell
docker version
docker compose version
```

新电脑获取代码：

```powershell
git clone https://github.com/w507603361/Speech-to-Text-API.git
cd Speech-to-Text-API
```

当前开发电脑已有项目，请直接进入 C:\Users\50760\Desktop\后端开发实习生项目，不必再次克隆。

## 2. 配置（首次运行）

仅当没有 .env 时执行，避免覆盖已有密钥：

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

在编辑器中填写 .env：

| 配置 | 用途 |
| --- | --- |
| MYSQL_DATABASE / MYSQL_USER | 保持 speech_api 即可 |
| MYSQL_PASSWORD | 应用数据库密码，使用随机强密码 |
| MYSQL_ROOT_PASSWORD | 另一个不同的随机强密码 |
| APP_PORT | 默认 8000；当前开发电脑已经配置为 18000 |
| DEEPSEEK_API_KEY | 自己的 API Key；不要提交 Git 或公开 |
| DEEPSEEK_MODEL | 保留项目现有配置 deepseek-flash |
| DEEPSEEK_BASE_URL | https://api.deepseek.com |
| DEEPSEEK_TIMEOUT_SECONDS | 60 |

已有 .env 和数据卷请保持数据库密码一致。修改 .env 不会自动修改已初始化的 MySQL 账号密码。没有 DeepSeek Key 也可以启动，转写成功后的摘要阶段会报 LLM_NOT_CONFIGURED。

## 3. 一键启动

在含 compose.yaml 的项目目录执行：

```powershell
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
```

首次需要下载镜像和依赖。等待参数限制容器健康等待时间，不限制镜像下载和构建总时间。MySQL 空卷第一次自动执行 sql/001_init.sql，已有卷保留数据。

当前开发电脑（APP_PORT=18000）：

- 健康检查：http://localhost:18000/health
- Swagger 调试：http://localhost:18000/docs
- 录音列表：http://localhost:18000/v1/recordings

新环境采用默认 APP_PORT=8000 时，将地址中的 18000 改为 8000。健康检查应返回 HTTP 200 和 {"status":"ok","database":"ok"}。两个服务均应显示 healthy。MySQL 不对宿主机开放端口，API 仅绑定 127.0.0.1。

## 4. 演示核心功能

打开 /docs，选择 POST /v1/recordings，点击 Try it out，为 file 选择 samples/demo.wav，执行后保存 recording_id 和 task_id。

使用 GET /v1/tasks/{task_id} 手动查询状态。Mock 转写等待 5～15 秒，约 20% 概率失败；成功后才调用真实 DeepSeek。Mock 返回固定会议文本，不识别音频内容。

- done：通过 GET /v1/recordings/{id} 查看 transcript 和 summary_result（summary、key_points、todos）。
- failed：阅读 error_code 和 error_message，修复原因后手动 POST /v1/tasks/{task_id}/retry；重试可能产生额外 API 费用。
- GET /v1/recordings：查看分页列表。
- DELETE /v1/recordings/{id}：核对唯一录音 ID 后删除一条 done/failed 记录；活动任务不能删除。

也可导入 [Postman 文件](api.postman_collection.json)，将集合变量 base_url 设置为实际本机地址。逐条发送请求，不用集合运行器批量执行删除。详细边界和验收过程见 [人工验收指南](local-acceptance.md)。

## 5. 停止、重启和更新

停止服务（保留数据）：

```powershell
docker compose stop
```

重新启动：

```powershell
docker compose up -d --wait --wait-timeout 120
```

更新代码和应用镜像：

```powershell
git pull --ff-only origin main
docker compose up -d --build --wait --wait-timeout 120
```

更新前应等待活动任务结束。未完成任务在应用启动时会标记 failed / SERVICE_RESTARTED，不自动恢复；已完成的摘要、录音文件和数据库记录保留。仅运行一个应用实例、一个 worker。

数据卷为 speech-to-text-api_mysql_data 和 speech-to-text-api_uploads（自定义 Compose 项目名时前缀不同）。不要删除数据卷，不提供批量或递归清理命令。

## 6. 排查问题

```powershell
docker compose ps
docker compose logs --timestamps --tail 100 api
docker compose logs --timestamps --tail 100 db
```

- Docker 无法连接：确认 Docker Desktop 已启动且使用 Linux 容器。
- 端口占用：修改 APP_PORT 后重新执行一键启动命令。
- /health 返回 503：检查 db 是否 healthy，以及账号密码是否与已有数据卷一致。
- 镜像或依赖下载失败：检查网络后重试构建。
- 摘要失败：根据 LLM_* 错误码检查密钥、额度、模型及网络，不要盲目反复重试。
- 不要公开 .env 或输出展开后的完整 Compose 配置，其中可能包含密钥。

本项目无前端、无用户鉴权、无自动重试或自动恢复；本地 Docker 运行是最终交付方式。开发历史与验收证据见 [开发记录](development-log.md)。
