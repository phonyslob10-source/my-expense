# 我的记账 PWA（Windows 私有后端 / 无 Notion 导入版）

该版本移除了 Notion CSV 导入功能，适合历史数据迁移完成后的长期使用。

前端：React + TypeScript + Vite + PWA + IndexedDB；后端：FastAPI + SQLite。

## Windows

1. 双击 `scripts/install-and-build.bat`。
2. 构建成功后双击 `scripts/start.bat`。
3. Windows 本机访问 `http://127.0.0.1:3000`。
4. 同一局域网手机访问 `http://Windows电脑IP:3000`。

## iPhone

首次用 Safari 打开服务器地址，然后使用“分享 -> 添加到主屏幕”。建议通过 HTTPS 安装 PWA，这样离线缓存、Service Worker 与 Home Screen Web App 能力更稳定。

## 远程访问 / 不同 Wi-Fi

推荐使用 Tailscale：Windows 与 iPhone 安装 Tailscale、登录同一账号；Windows 启动本项目后，用 Tailscale 的 HTTPS 地址打开应用并重新添加到主屏幕。之后手机不需要与 Windows 处于同一个 Wi-Fi，在其他 Wi-Fi 或蜂窝网络下也可同步。

## 离线机制

记录、分类与成员会先写入 iPhone 本地 IndexedDB；网络不可用时仍可录入和查看已经缓存的数据，网络恢复后自动同步。真正的离线启动依赖 HTTPS 安全上下文和 Service Worker，因此推荐使用 Tailscale HTTPS 地址。

## 本次移动端修复

- 输入框统一使用 16px，避免 iPhone Safari 自动放大表单页面。
- 日期范围在窄屏下使用稳定的三列布局，避免“至”挤进日期框。
- 统计柱状图使用整数元显示，柱顶显示数值；X 轴标签保持居中。
- 饼图使用不同颜色，取消饼块上的拥挤文字，改为下方可读图例。
- 记录本地优先保存；网络恢复、切回应用或重新获得焦点时自动尝试同步，并显示待同步数量。


## Remote access without the same Wi-Fi

For access from other Wi-Fi networks or mobile data, use Tailscale Serve. Tailscale Serve keeps the service private to your Tailscale network and terminates HTTPS automatically. It can proxy this app with `tailscale serve 3000`.

1. Install Tailscale on Windows and sign in.
2. Install the Tailscale app on each iPhone/iPad that should use the app and sign in to the same tailnet.
3. Start this app with `scripts\start.bat`.
4. Run `scripts\setup-remote-access.bat`. It configures Tailscale Serve and prints the private HTTPS URL.
5. Open that HTTPS URL on the iPhone and add it to the Home Screen again.

Do not use Tailscale Funnel for this application: Funnel makes the service public on the internet.


## Cloudflare

The project now includes a Cloudflare Workers + D1 deployment path. The React/Vite/PWA frontend is served by Workers Static Assets, while the FastAPI backend runs as a Python Worker and stores server data in D1. Historical local SQLite data is intentionally not migrated.

See [CLOUDFLARE.md](CLOUDFLARE.md) for setup and deployment steps.

## 单条删除与字体设置

- 在首页点开一笔记录，进入“编辑记录”后可点击“删除这笔记录”；账单列表也保留逐笔删除按钮。确认框会显示项目、日期、账户及金额，取消不会删除。
- 删除沿用软删除标记，可离线操作；联网后进入原有同步流程。记录和待同步队列一起保存，同步途中新增的删除也会保留。
- “设置 → 字体与显示”提供“小号、适中、原字号”，默认适中（比原字号略小），选择保存在当前设备。正文使用设备系统字体；输入框保留手机友好的字号。
- 账单项目可以换行，金额和删除按钮不会被挤走；极窄屏幕会把金额放到下一行。

本地验证：`npm --prefix frontend ci`、`npm --prefix frontend test`、`npm --prefix frontend run build`。测试使用虚构记录和内存 IndexedDB，禁止请求线上 API。

Android APK 是加载部署网址的 WebView 外壳，不内置前端页面。新网页功能需要单独发布前端后生效；构建 APK 不会执行数据库迁移或删除记录。
