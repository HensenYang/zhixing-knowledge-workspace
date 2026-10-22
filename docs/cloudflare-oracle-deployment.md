# Cloudflare Pages + Oracle Always Free

Oracle 注册失败时，可以改用 [Cloudflare Pages + Azure for Students](cloudflare-azure-deployment.md)，复用下方的 Docker 和 Pages 部署配置。

If Oracle signup fails, the Azure for Students alternative reuses the deployment configuration below.

这是新云环境的部署步骤，不会迁移或修改本机数据库。文中的 `app.example.com` 和 `origin.example.com` 需要换成你自己的两个子域名。

These steps create a new cloud installation. Local data is unchanged. Replace the example hostnames with your own.

```text
浏览器 / Browser → app.example.com (Cloudflare Pages)
                  /api/* → Pages Function (server-only secret)
                         → origin.example.com (Cloudflare Tunnel)
                         → Oracle: Python API → PostgreSQL + attachment volumes
```

Pages 保持现有 `/api` 路径和同源 Cookie；后端不开放跨域。前端静态文件免费额度与 Pages Functions 的 API 请求额度分开计算。

The proxy preserves same-origin sessions and streams files. Only `/api/*` invokes a Pages Function. No browser-visible API keys or CORS changes are required.

## 1. 注册 Oracle / Create an Oracle account

1. 打开 [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)，本人完成身份和银行卡验证。验证可能有临时预授权；不要在聊天中提供卡号或验证码。
2. 主区域影响 Always Free 可用性。先选择适合你的可选区域；选定后不能随意更换。若目标区域无容量，先记录错误，不要为了继续操作升级付费资源。
3. 当前 [官方 Always Free 文档](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)列出的 A1 配额为每月 1,500 OCPU 小时和 9,000 GB 小时，相当于合计 2 OCPU / 12 GB；块存储共 200 GB，包含启动盘。以你的控制台资格、现有用量及费用预估为准。

Sign up personally, choose the home region carefully, and check the Always Free eligibility and account-wide quota. Capacity is not guaranteed. Older 4 OCPU / 24 GB tutorials may not match current entitlements.

## 2. 创建实例 / Create the VM

- Compute → Instances → Create instance.
- 名称 / Name: `zhixing`.
- 镜像 / Image: Ubuntu 24.04 LTS，选择与 A1 ARM 架构匹配的镜像。
- Shape: `VM.Standard.A1.Flex`，2 OCPU、12 GB 内存；现有其他 A1 实例也计入额度。
- Boot volume: 50 GB，确认没有额外的付费性能设置。
- Public subnet + public IP，以便从本机 SSH；入口只需 SSH 22，限制为自己的 IP。无需开放 8001 或 5432。
- 保存 SSH 私钥到自己的电脑；不要上传到 Git 或聊天。实例状态为 Running 后记录公网 IP。

Use an Always Free-eligible A1 shape and ARM-compatible Ubuntu image. The Tunnel uses outbound connections, so application and database ports stay closed to the Internet.

Windows PowerShell 示例 / Example:

```powershell
ssh -i "C:\path\oracle-key.key" ubuntu@YOUR_SERVER_IP
```

## 3. 安装 Docker / Install Docker

以下命令在新 Oracle Ubuntu 服务器执行。先按 [Docker 官方 Ubuntu 指南](https://docs.docker.com/engine/install/ubuntu/)安装 Engine 和 Compose plugin。新机器可使用：

Run on the new Ubuntu VM; use Docker's official repository:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker compose version
```

## 4. 启动后端和数据库 / Start the backend and database

在本次部署文件已经推送到仓库后执行以下步骤。若尚未推送，先完成仓库同步。

Run after these deployment files have been pushed to the repository:

```bash
git clone https://github.com/HensenYang/zhixing-knowledge-workspace.git
cd zhixing-knowledge-workspace
python3 deploy/oracle/prepare.py
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml up -d --build --wait db api
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml ps
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml exec -T api python -m deploy.oracle.runtime health
```

`prepare.py` 只生成服务器的数据库密码和代理密钥，不输出值，且不会覆盖现有配置。`.env` 不进入 Git、镜像或前端。Bootstrap 使用数据库管理员创建普通 `knowledge_app` 角色和新数据库，再以普通角色执行 V001–V009 迁移；运行 API 不持有管理员密码。数据库和附件使用命名卷。API 只监听服务器回环端口；它还会校验来自 Pages 的代理密钥。

Configuration generation never overwrites an existing file. Bootstrap creates an unprivileged app role so PostgreSQL row-level security remains effective. Named volumes retain database and attachment data across container replacement. The API uses one process because background jobs are process-local.

本机开发环境与云端是两个独立安装。不要上传本机 `.env`、`storage/postgres-data` 或整个 `storage`。如要迁移内容，在云端完成登录后通过网站的备份/Artifact 导入功能操作。

Do not upload the personal development configuration or PostgreSQL data directory. Import selected content through the application after the new installation is ready.

## 5. 连接 Cloudflare Tunnel / Connect the origin tunnel

按 [Cloudflare Tunnel 官方步骤](https://developers.cloudflare.com/tunnel/get-started/)操作：

1. 登录 Cloudflare，确认域名已激活。
2. Networking → Tunnels（部分界面在 Zero Trust → Networks），创建 `zhixing-oracle`，选择 Docker connector。
3. 将安装命令中的 **token 值** 填入服务器 `deploy/oracle/.env` 的 `CLOUDFLARE_TUNNEL_TOKEN`。使用服务器编辑器，例如 `nano deploy/oracle/.env`；不要把 token 发到聊天或提交 Git。
4. Published application route：hostname `origin.example.com`，Service URL **`http://api:8001`**。这里用 Docker 服务名，不能填 `localhost`。
5. 在服务器启动连接器：

```bash
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml --profile tunnel up -d tunnel
```

Tunnel 显示 Healthy 后继续。直接浏览 `origin.example.com/api/health` 返回 404 是预期：公开源站没有正确代理密钥，只有 Pages 转发时才允许访问。

The connector needs outbound connectivity to Cloudflare. Direct origin requests are intentionally rejected; successful tunnel connectivity and authenticated API health are separate checks.

## 6. 部署 Pages / Deploy Pages

Workers & Pages → Create application → **Pages** → Connect Git repository，选择本项目：

| 设置 / Setting | 值 / Value |
| --- | --- |
| Production branch | 本次部署配置所在分支；合入后为 `main` |
| Root directory | `frontend_Web` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Build variable | `NODE_VERSION=22` |

在 Pages 项目的生产环境 Variables and Secrets 中设置：

- `API_ORIGIN=https://origin.example.com`：不要带 `/api` 或其他路径。
- `API_PROXY_SECRET`：复制服务器 `.env` 中同名值，保存为 **Secret**。这是运行时变量，不要命名为 `VITE_*`。

保存后部署/重新部署。`frontend_Web/functions/api/[[path]].js` 由 Pages Git 构建自动部署为 Function；`dist` 文件夹拖拽上传不会自动带上 Functions，不要使用这种上传方式。开发预览环境建议另配测试后端；不配置时会显示 API 未配置。

Set the origin URL and matching server-only proxy secret in the production environment, then redeploy. Use Git integration to include Functions. Do not expose these values as Vite variables. Deploying only the static build directory is insufficient.

先用 `*.pages.dev` 地址验证，再在 Pages → Custom domains 添加 `app.example.com`。前端域名与 Tunnel 源站域名必须不同。

Verify the Pages-generated URL, then attach the frontend custom domain. Keep frontend and origin hostnames distinct.

## 7. 上线验收 / Smoke checks

- `https://app.example.com/api/health` 应返回 JSON，`database` 为 `ready`、版本为 `V009`，不能返回前端 HTML。
- `/api/auth/me` 未登录时应返回 401 JSON。
- 首次在网站注册自己的账号；刷新后登录应保留。新建笔记、上传小 PDF、新建画布、编辑并分享路径。
- 匿名窗口打开分享链接；下载 JSON，再从“导入学习路径文件”预览。
- 检查文件下载、分页、后台任务。关闭网站再打开，数据应仍在。
- 可选 LLM：只在服务器 `.env` 设置供应商 Key 和模型，再重建 API 容器；不配置也可以使用笔记、图谱、画布等核心功能。

The final acceptance must cover the deployed domains, real cookies, uploads, downloads, and persistence. Local checks do not certify the cloud runtime.

## 8. 更新与备份 / Updates and backups

更新前保留网站导出的备份，并复制到服务器之外。停止服务不会删除命名卷；不要执行 `docker compose down -v`，它会删除云端数据。

Keep backups outside the VM. Oracle may reclaim idle Always Free instances, so a Docker volume on that VM is not an off-host backup.

```bash
# Back up through the website first, then run on the server:
git pull --ff-only
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml build
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml stop api
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml run --rm bootstrap
sudo docker compose --env-file deploy/oracle/.env -f deploy/oracle/compose.yaml up -d api
```

PostgreSQL 主版本升级不包含在普通更新内。当前卷路径对应 PostgreSQL 18；不要直接切换主版本标签。云端不能直接访问你电脑上的 Zotero，因而默认禁用本地 Zotero MCP；PDF、arXiv、DOI、GitHub 导入仍由服务器处理。

PostgreSQL major upgrades need their own migration procedure. Local desktop Zotero is not reachable from Oracle by default; it is disabled in this deployment.

## 免费范围与验证边界 / Free-tier and verification limits

- Pages 的 API 代理受 Workers Free 请求与 CPU 配额约束；超出额度需要等待重置或更换方案。静态资源由 `_routes.json` 排除 Functions。
- Cloudflare Free 的单次请求体上限为 100 MB，multipart 开销也计入；应用原本 128 MB 的恢复上限不代表云端可上传 128 MB。较大的备份先压缩/拆分为可单独导入的内容，不要开放数据库端口来绕过限制。
- Oracle 额度、区域容量、闲置回收及额外资源以账户控制台为准。可选的模型 API 使用供应商单独计费，不属于免费托管额度。
- 本地验证结果：17 项前端单元测试（含 5 项代理测试）、4 项部署后端测试、10 项双语浏览器场景通过，国际化检查和前端生产构建通过。初始化脚本还在全新隔离 PostgreSQL 中完成 V001–V009 迁移，重复运行、普通角色/RLS、入口校验、注册和笔记持久化检查均通过。
- 本机没有 Docker Engine。2026-10-23 已在 Azure Ubuntu 24.04 x64、2 vCPU / 4 GiB VM 上完成镜像构建、V001–V009 迁移和容器健康验证。Oracle ARM 环境仍需单独验证。

Sources: [Pages Functions routing](https://developers.cloudflare.com/pages/functions/routing/), [Workers limits](https://developers.cloudflare.com/workers/platform/limits/), [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [Oracle signup FAQ](https://www.oracle.com/cloud/free/faq/).
