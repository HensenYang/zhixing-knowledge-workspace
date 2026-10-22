# Cloudflare Pages + Azure for Students

这是 Oracle 注册失败后的替代部署入口。前端仍使用 Cloudflare Pages；后端、PostgreSQL 和附件运行在 Azure Ubuntu VM 上。

This alternative keeps the Pages frontend and runs the API, PostgreSQL, and attachment volumes on an Azure Ubuntu VM.

## 第一步：激活学生订阅 / Activate the student subscription

1. 打开 [Azure for Students](https://azure.microsoft.com/en-us/free/students/)，点击 Start free。
2. 按官网流程完成学生身份认证，选择完整的 **Azure for Students** 权益。Students Starter 的可用服务不同，不能当作同一套餐。
3. 激活后登录 [Azure Portal](https://portal.azure.com/)，打开 Subscriptions，确认学生订阅为 Active，并在学生权益/余额页面确认可用额度及到期日。
4. 当前官网列出 US$100 额度、12 个月使用期限且无需信用卡。具体资格和地区限制以你的账户为准。先保留学生订阅及费用限制。

Use the full Azure for Students offer, complete eligibility verification, and check that the subscription is active before creating resources. The current offer provides US$100 credit valid for 12 months without a credit card; eligibility and regional availability still apply.

学生额度不是无限期免费服务器。根据 [Microsoft 的说明](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/azurestudents-subscription-disabled)，额度用尽或到期可能停用服务；转按量付费会改变计费方式。虚拟机、磁盘及网络资源都应在创建前核对费用。

Credit is finite. Exhausted or expired student credit can disable services. Check the resource estimate before provisioning and keep backups outside the VM.

## 第二步：创建 Ubuntu VM / Create the VM

激活成功后再做这一节。配置建议：

- Subscription: Azure for Students。
- Resource group: 新建专用于本项目的 `zhixing-demo`。
- Image: Ubuntu Server 24.04 LTS，选择与 VM 架构匹配的镜像。
- Region: 从学生订阅允许且有容量的区域选择；优先考虑靠近团队的区域。
- Size: 按控制台的免费资格、内存和费用预估选择。Python PDF 处理与 PostgreSQL 同机运行，建议至少 2 GB 内存，4 GB 留有更多余量；某些免费小规格未必够用。
- Authentication: SSH public key，用户名可用 `azureuser`，私钥只保存在自己的电脑上。
- OS disk: 先用小容量 Standard SSD；核对磁盘和 IP 等配套资源费用。暂不加额外数据盘、Bastion、付费监控或其他附加服务。
- 入站只开放自己的 IP 到 SSH 22。Cloudflare Tunnel 使用出站连接，不需要向公网开放 8001、5432、80 或 443。

Choose a size only after reviewing eligibility, memory, quota, and the full estimate in the portal. The application uses outbound Cloudflare Tunnel connectivity, so only restricted SSH ingress is needed.

创建流程可参考 [Microsoft Linux VM 快速入门](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/quick-create-portal?tabs=ubuntu)。不要照抄示例中为 Nginx 开放 HTTP 80 的设置，本方案的入口是 Pages 和 Tunnel。

SSH 示例 / Example:

```powershell
ssh -i "C:\path\azure-key.pem" azureuser@YOUR_SERVER_IP
```

## 第三步起：复用已有部署配置 / Reuse the deployment configuration

当前 `deploy/oracle/` 中的 Docker、数据库初始化和代理入口是通用 Linux 配置，在 Azure Ubuntu 上同样适用。

The existing files under `deploy/oracle/` also work on an Azure Ubuntu VM; they do not call Oracle-specific APIs.

VM 准备好后，从 [部署指南第 3 节](cloudflare-oracle-deployment.md#3-安装-docker--install-docker) 继续：

1. 在 VM 上安装 Docker 和 Compose。
2. 同步已包含部署配置的代码，生成服务器 `.env`。
3. 启动数据库和后端；确认迁移和容器健康。
4. 创建 Cloudflare Tunnel，源站子域名指向 `http://api:8001`。
5. Pages 连接 GitHub，Root directory 为 `frontend_Web`，构建为 `npm run build`，输出为 `dist`。协作者仓库未授权给 Cloudflare 时，执行 `npm run build:pages-upload`，直接上传包含 `_worker.js` 的 `dist` 文件夹或 ZIP。
6. 配置 Pages 的 `API_ORIGIN` 和 Secret `API_PROXY_SECRET`，绑定前端域名，再验证登录、附件和数据持久化。

Skip that guide's Oracle account and instance steps. Its Oracle Always Free quotas and reclamation rules do not describe Azure. The container image, V001–V009 migration, and API/database health were verified on an Azure Ubuntu 24.04 x64 VM with 2 vCPUs and 4 GiB RAM on 2026-10-23. ARM still requires separate verification.

## 区域与规格限制 / Region and size restrictions

`NotAvailableForSubscription` 表示该区域/规格组合受限；即使规格可选，最终校验仍可能因 `RequestDisallowedByAzure` 拒绝区域。先在 Policy → Assignments 中读取 Allowed resource deployment regions 的参数，不要假定新加坡或澳洲可用。若策略页面加载失败，可在无需存储帐户的临时 Cloud Shell 中只读查询：

```bash
az policy assignment list --query "[].{name:displayName,parameters:parameters}" -o json
```

Check the subscription’s allowed deployment regions before choosing a VM size. The visible size picker alone does not prove a region is allowed. Keep database and API ingress closed, and verify the full configuration before accepting creation terms.
