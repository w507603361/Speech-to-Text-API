# 本地运行与人工验收

本项目不包含自动化测试套件。本文件和 Postman 集合用于逐条人工演示，开发过程中的一次性替身验收结果记录在 development-log.md。

## 从空环境启动

1. 安装并启动 Docker Desktop，选择 Linux 容器。执行 `docker version`、`docker compose version` 确认可用。
2. 克隆仓库，进入目录。将 `.env.example` 复制为 `.env`，已有 .env 则只补齐缺少字段。
3. 填入两个不同的随机数据库密码和自己的 DeepSeek Key；模型默认 deepseek-flash。没有 Key 也能启动，但转写成功后会失败为 LLM_NOT_CONFIGURED。
4. 执行 `docker compose up -d --build --wait --wait-timeout 120`。初次联网下载镜像和依赖可能较慢；120 秒用于服务启动等待，不代表镜像下载总时限。
5. 默认访问 http://localhost:8000/health 和 /docs。本项目开发电脑的 .env 使用 APP_PORT=18000，故实际访问 http://localhost:18000/health 。

Compose 在 MySQL 健康后启动应用。数据库空卷第一次自动运行 sql/001_init.sql，应用无需本机 Python 或 MySQL。镜像以非 root 用户运行，上传目录预先创建并授权，数据库和文件各有独立命名卷。

## Postman 演示

导入 [api.postman_collection.json](api.postman_collection.json)。集合变量 base_url 默认 http://localhost:18000，其他端口需要修改。不要额外创建同名环境变量覆盖集合中的 recording_id、task_id。

1. 发送健康检查，预期 200、status=ok、database=ok。
2. 在上传请求 Body 中选择仓库 samples/demo.wav，或自己的 wav/mp3/m4a/aac 文件。预期 202，返回 pending 与两个 UUID；集合会自动保存 ID，但不会自动轮询或再次上传。
3. 手动查询任务。Mock 随机等待 5～15 秒、约 20% 失败；成功后调用真实 DeepSeek。单次上传返回不等待这些处理完成。
4. done 时查询详情，检查 transcript 及三个摘要字段。示例 WAV 是短静音，Mock 输出固定会议文本，与音频无关。
5. failed 时检查错误。修正错误原因后手动重试，预期 202，同一 task_id、attempt 增加；执行中再次重试为 409。不要为了观察 Mock 失败而反复产生付费摘要。
6. 列表应包含此录音，按创建时间倒序；详情不包含存储路径。page=0 或 page_size=101 为 400，合法但不存在的 UUID 为 404。
7. 先核对当前录音 ID，再发送一次删除。done/failed 返回 204，随后详情、任务、再次删除都为 404；处理中删除返回 409。

集合中的 post-response 脚本只保存上传返回的 ID，不含测试断言、自动重试或批量删除。请逐条发送，不用 Collection Runner 连续执行删除。

## 重启与持久化

- `docker compose stop` 停止服务，`docker compose up -d --wait --wait-timeout 120` 再启动；不要删除卷。
- 已完成录音、摘要和文件保留；pending/transcribing/summarizing 会在应用启动前变为 failed / SERVICE_RESTARTED，不自动继续处理。
- 验证中断可以在转写期间执行 `docker compose restart api`，再查询该任务；若任务已在重启前完成，则保留 done，不能误判为恢复了任务。
- 任务失败后需显式重试，可能再次调用付费摘要。没有自动失败重试或自动恢复。

## 维护与常见问题

| 操作或问题 | 处理 |
| --- | --- |
| 查看服务状态 | docker compose ps |
| 查看最近日志 | docker compose logs --timestamps --tail 100 api |
| 更新代码 | git pull 后执行 docker compose up -d --build --wait --wait-timeout 120 |
| 端口被占用 | 在 .env 修改 APP_PORT，然后重新 up |
| 数据库密码变更后连接失败 | MYSQL_PASSWORD 初始化只在空卷生效；现有账号需在 MySQL 内修改密码并同步配置，不能仅改 .env，也不要删卷 |
| Docker 镜像拉取失败 | 检查网络和本机镜像源，可单独 docker pull python:3.12-slim 后再启动 |
| 应用健康检查失败 | 先看 db 状态及 api 日志，不输出或公开 docker compose config 中展开的密钥 |
| 摘要失败 | 根据 LLM_* 错误码核对 Key、额度、网络和模型；修复后手动 retry |
| 查看实际数据位置 | docker volume inspect speech-to-text-api_mysql_data 或 speech-to-text-api_uploads；自定义项目名时卷名使用对应前缀 |

停止容器不删除数据；本文不提供递归清空命令。需要批量清理文件时由用户自行处理。完整运行命令见 [本地运行文档](run-local.md)。
