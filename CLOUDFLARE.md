# Cloudflare 部署

这个版本把“记账”的中央后端从 Windows 本机迁移到 Cloudflare Workers + D1；前端继续使用现有 React/Vite/PWA，手机仍然通过 IndexedDB 离线优先并通过 `/api/sync` 同步。

## 当前方案

- Cloudflare Worker：Python + FastAPI
- 数据库：Cloudflare D1
- 前端：Workers Static Assets
- 地址：先使用 `workers.dev`，不需要购买域名
- 历史 SQLite 数据：不迁移；D1 从空库开始
- Android APK：继续使用 WebView，只需把服务器地址切换到最终 Worker URL

Cloudflare 官方目前支持 Python Workers、FastAPI、D1 Python bindings 和 Workers Static Assets。urlFastAPI on Python Workershttps://developers.cloudflare.com/workers/languages/python/packages/fastapi/ urlD1 from Python Workershttps://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/

## 一次性设置

### 1. 创建 D1

在 Cloudflare Dashboard -> Workers & Pages -> D1 创建：

`my-expense-db`

然后把数据库 ID 填入根目录的 `wrangler.jsonc`：

`database_id: "你的 D1 database id"`

### 2. 配置管理员密码

不要把密码写进 Git。

运行：

```bash
npx wrangler secret put ADMIN_PASSWORD
npx wrangler secret put ADMIN_TOKEN_SECRET
```

输入两个不同的随机秘密值。

### 3. 初始化空数据库

```bash
npx wrangler d1 migrations apply my-expense-db --remote
```

这只建立表和默认分类/成员，不导入旧数据。

### 4. 构建前端

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

### 5. 本地预览

安装 Python Worker 环境后：

```bash
uv run pywrangler dev
```

### 6. 部署

```bash
uv run pywrangler deploy
```

部署后会获得：

`https://<worker-name>.<your-subdomain>.workers.dev`

## 安全

在实际使用前，建议在 Cloudflare Zero Trust / Access 中保护整个 Worker。Cloudflare 现在支持直接对 Worker 启用 Access；也可以用一次性 PIN 登录。

不要为了这个项目购买流量包。首先使用 Free 方案测试即可。

## Android

当前 Android 工程已经把服务器地址抽成 `BuildConfig.SERVER_URL`。部署得到最终 Worker URL 后，将 `android/app/build.gradle` 中的 `SERVER_URL` 改成 HTTPS Worker URL，再重新构建 APK。
