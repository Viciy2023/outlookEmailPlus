---
title: OutLookEmailPlus-Manager
emoji: 📧
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 5000
---

## 中文说明

### 运行方式

- 当前 Space 固定为 ``
- 默认使用当前项目已发布镜像：`ghcr.io/zeropointsix/outlook-email-plus:latest`
- 构建阶段会额外 clone 源仓库 `https://github.com/ZeroPointSix/outlookEmailPlus.git` 作为兜底启动路径
- 默认运行模式是 `APP_SOURCE=image`
- 只有你明确需要从源码目录启动时，才设置 `APP_SOURCE=git`
- 持久化数据目录是 `/data`，应由 HF bucket 挂载并保持 `Read & Write`

### GitHub Repository Secrets

这些是 GitHub 仓库里的 Secrets，不是 HF Space 里的 Variables/Secrets，用于 `.github/workflows/sync-hf-space.yml` 同步 Space：

- `HF_TOKEN`：必填，用于同步 `EmilyReed96989/OutLookEmailPlus-Manager`
- `HF_BUCKET`：当前 workflow 不依赖它推导 Space 名，但建议保留，方便你以后切回 bucket 推导方案

### HF Space Secrets

- `SECRET_KEY`：必填。Flask 启动所需密钥，不设置会直接启动失败
- `LOGIN_PASSWORD`：强烈建议配置。后台登录密码；不设置时会回退到项目默认值 `admin123`
- `OAUTH_CLIENT_ID`：可选。仅在你启用 Outlook OAuth 时配置
- `GPTMAIL_API_KEY`：可选。仅在你启用 GPTMail/正式临时邮箱上游时配置
- `EMAIL_NOTIFICATION_SMTP_PASSWORD`：可选。仅在你启用邮件通知 SMTP 时配置
- `CF_WORKER_ADMIN_KEY`：可选。Cloudflare Temp Email Worker 的 Admin Key，建议放在 Secret

### HF Space Variables

建议至少配置：

- `APP_SOURCE=image`
- `DATABASE_PATH=/data/outlook_accounts.db`
- `PORT=5000`
- `GUNICORN_THREADS=4`
- `GUNICORN_TIMEOUT=300`
- `ALLOW_LOGIN_PASSWORD_CHANGE=false`
- `SCHEDULER_AUTOSTART=true`
- `PROXY_FIX_ENABLED=true`
- `TRUSTED_PROXIES=`

按需配置：

- `OAUTH_REDIRECT_URI`
- `GPTMAIL_BASE_URL`
- `CF_WORKER_BASE_URL`
- `EMAIL_NOTIFICATION_SMTP_HOST`
- `EMAIL_NOTIFICATION_SMTP_PORT`
- `EMAIL_NOTIFICATION_FROM`
- `EMAIL_NOTIFICATION_SMTP_USERNAME`
- `EMAIL_NOTIFICATION_SMTP_USE_TLS`
- `EMAIL_NOTIFICATION_SMTP_USE_SSL`
- `EMAIL_NOTIFICATION_SMTP_TIMEOUT`

### 重要说明

- 当前方案下，容器内不再执行 bucket 双向同步，HF bucket 直接挂载到 `/data`
- `HF_TOKEN` 和 `HF_BUCKET` 只用于 GitHub Action 同步 Space 仓库，不是应用运行期环境变量
- `PROXY_FIX_ENABLED` / `TRUSTED_PROXIES` 才是代码真实识别的代理相关变量，不要再使用旧的 `TRUST_PROXY_HEADERS`
- Telegram 推送、`cf_worker_base_url`、`cf_worker_admin_key`、`email_notification_recipient`、`telegram_bot_token`、`telegram_chat_id`、`telegram_poll_interval` 等，主要是应用启动后保存在数据库设置中，不是必须通过 HF 环境变量预置

## English Notes

### Runtime

- This Space is fixed to ``
- The default runtime image is `ghcr.io/zeropointsix/outlook-email-plus:latest`
- The build also clones `https://github.com/ZeroPointSix/outlookEmailPlus.git` as a fallback source path
- Default runtime mode is `APP_SOURCE=image`
- Set `APP_SOURCE=git` only when you explicitly want to boot from the cloned source tree
- Persistent application data lives in `/data`, backed by the mounted HF bucket

### GitHub Repository Secrets

- `HF_TOKEN`: required for syncing the Space repository from GitHub Actions
- `HF_BUCKET`: currently not required by the workflow for Space name resolution, but kept for future bucket-derived workflows

### HF Space Secrets

- `SECRET_KEY`: required
- `LOGIN_PASSWORD`: strongly recommended; otherwise the app falls back to `admin123`
- `OAUTH_CLIENT_ID`: optional, only for Outlook OAuth
- `GPTMAIL_API_KEY`: optional, only for GPTMail/upstream temp mail
- `EMAIL_NOTIFICATION_SMTP_PASSWORD`: optional, only for SMTP email notifications
- `CF_WORKER_ADMIN_KEY`: optional, recommended as a Secret

### HF Space Variables

Recommended baseline values:

- `APP_SOURCE=image`
- `DATABASE_PATH=/data/outlook_accounts.db`
- `PORT=5000`
- `GUNICORN_THREADS=4`
- `GUNICORN_TIMEOUT=300`
- `ALLOW_LOGIN_PASSWORD_CHANGE=false`
- `SCHEDULER_AUTOSTART=true`
- `PROXY_FIX_ENABLED=true`
- `TRUSTED_PROXIES=`

Optional values when needed:

- `OAUTH_REDIRECT_URI`
- `GPTMAIL_BASE_URL`
- `CF_WORKER_BASE_URL`
- `EMAIL_NOTIFICATION_SMTP_HOST`
- `EMAIL_NOTIFICATION_SMTP_PORT`
- `EMAIL_NOTIFICATION_FROM`
- `EMAIL_NOTIFICATION_SMTP_USERNAME`
- `EMAIL_NOTIFICATION_SMTP_USE_TLS`
- `EMAIL_NOTIFICATION_SMTP_USE_SSL`
- `EMAIL_NOTIFICATION_SMTP_TIMEOUT`

### Important Notes

- In the current deployment mode, the container does not perform bucket sync; HF mounts the bucket directly to `/data`
- `HF_TOKEN` and `HF_BUCKET` are for GitHub Actions only, not runtime application configuration
- The code recognizes `PROXY_FIX_ENABLED` and `TRUSTED_PROXIES`; do not use the outdated `TRUST_PROXY_HEADERS`
- Telegram push settings and several provider settings are primarily stored in the application's database-backed settings after startup, not required as HF environment variables
