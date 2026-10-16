# Photo Count

实验室图片计数系统：Vue 3 前端 + FastAPI 后端，第一版使用 OpenCV 分水岭算法。

## 本机运行

后端依赖由 `uv` 管理：

```powershell
uv sync
uv run python -m backend.app.main
```

后端地址为 `http://localhost:8000`，接口文档为 `http://localhost:8000/docs`。

首次运行会自动创建 SQLite 数据库。默认管理员账号为 `admin` / `admin123`，账号只有用户名和密码。

前端：

```powershell
cd frontend
pnpm install
pnpm dev
```

## 部署（Docker）

对外只开放 **20010** 端口：nginx（前端容器）提供静态资源并反代 `/api/`、`/files/` 到后端容器，后端不直接对外暴露。

```powershell
cp .env.example .env   # 修改 JWT_SECRET 为随机值
docker compose up -d --build
```

浏览器访问 `http://<服务器IP>:20010`，默认管理员 `admin` / `admin123`（容器启动时自动执行 `backend/scripts/seed.py`，幂等）。数据库与图片持久化在 `./data` 目录。云服务器需在安全组放行 20010 端口。

生产切换 PostgreSQL：`.env` 中设置 `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/photocount` 并自行添加 db 服务即可。

单独部署后端（无 nginx，API 与图片直接走 20010）：

```powershell
docker compose -f docker-compose.backend.yml up -d --build
```

此时接口为 `http://<服务器IP>:20010/api`、图片为 `http://<服务器IP>:20010/files`；前端若部署在其他域名，需在 `.env` 的 `FRONTEND_ORIGIN` 中填写该地址以放开跨域。

### 前端深链接 404（服务器必需配置）

SPA 的 `/count`、`/history/<task_id>` 在服务器上并没有对应文件，必须由 Web 服务器回退到 `index.html`，否则会返回 nginx 自己的 404 页面（`<hr><center>nginx</center>`）。前端容器（`frontend/nginx.conf`）已经包含这段回退：

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

若前端静态资源由宿主机上的 openresty/nginx 单独提供，需要在该 server 块里补上同样的 `try_files`，完整示例见 `deploy/openresty.frontend.example.conf`。

自检：`curl -I https://<域名>:<端口>/count` 返回 `200` 即正常，返回 `404` 说明回退缺失。注意 Vue Router 里的兜底路由（`/:pathMatch(.*)*`）只处理 index.html 加载之后的未知路径，修不了服务器层的 404。

### 文件访问范围

后端只把 `data/uploads` 和 `data/results` 挂成静态目录（`/files/uploads/*`、`/files/results/*`）。不要改回挂载 `data/` 根目录：SQLite 数据库就在 `data/app.db`，挂根目录会让 `/files/app.db` 把整个库（含 bcrypt 密码哈希）下载走。

> 安全提醒：收窄挂载范围之前上线的实例，`/files/app.db` 是可以公开下载的。升级后请通过管理接口重置用户密码——旧库里的哈希应当视为已泄露。

## 示例图片

将测试图片放入 `examples/`。该目录不强制包含示例文件，系统也支持直接上传手机或电脑图片。

## 识别准确率评估

`examples/` 里的文件名本身就是真值（`soy53.JPG` 表示应为 53 个，`soy69_1.jpg` 表示 69 个），可直接当评估集用。调参或改算法后跑一遍这个常驻脚本，用数字说话：

```powershell
uv run python scripts/eval_accuracy.py                     # 默认 mode=beans
uv run python scripts/eval_accuracy.py --mode pills
uv run python scripts/eval_accuracy.py --param fg_ratio=0.65
uv run python scripts/eval_accuracy.py --sweep-resolution   # 比较不同处理分辨率
uv run python scripts/eval_accuracy.py --dump-worst out/    # 导出误差最大的标注图，便于肉眼定位
uv run python scripts/eval_accuracy.py --max-mae 1.5        # MAE 超阈值时退出码 1，可挂 CI
```

脚本自动读取后端 `settings.default_max_side`（改了配置就会反映到评估里），输出 MAE（整体精度）、bias（系统性多算/少算）、exact（完全正确的张数）、max_error（最坏情况）和耗时。

当前基线（14 张，`mode=beans`，`min_area=500`，长边 2200）：**exact 7/14，MAE 1.29，bias −1.14（偏少算），max_error 5（soy70 −5）**。提分辨率主要修好了之前最差的 soy53（−6 → −1），但不是每张都变好：soy69 由 −3 变 −4、soy100 由 0 变 +1。已实测的对照，避免以后重复试：

| 改动 | MAE | bias | exact | max_error |
| --- | --- | --- | --- | --- |
| **基线**（长边 2200，样本原图 1920） | **1.29** | −1.14 | 7/14 | 5 |
| 长边压到 1600（改动前的旧默认值） | 1.64 | −1.36 | 6/14 | 6 |
| `fg_ratio` 0.35 / 0.5 / 0.7 / 0.8 | 12.29 / 3.14 / 2.93 / 8.07 | −11 ~ −2 | 2 / 4 / 2 / 1 | 67 ~ 21 |
| 全局平场光照归一化 | 9.57 | −9.29 | 3/14 | 47 |
| h-maxima 分水岭（按颗粒半径自校准 h） | 24.5 ~ 29.0 | +12 ~ +29 | 0/14 | 281 |

- **下采样是当前唯一的精度损失来源**：评估样本长边都是 1920，1600 属于纯下采样；1920 / 2200 / 2600 / 3200 结果完全相同（`load_image` 只会缩小、不会放大）。所以 2200 的取值是为了覆盖常见 1080×1920 竖拍图并给 iPhone 原图（4032 长边）留余量，而不是"越大越好"。
- `fg_ratio` 默认 0.6 在两端都比邻值更好，不用调。
- **不要再试全局平场归一化和 h-maxima 分水岭**：两者都明显更差。前者破坏 `yellow > median + 25` 这个基于 Lab b\* 的固定阈值关系；后者对 h 极敏感，单一全局 h 无法同时适配大颗粒和阴影里的小颗粒。
- 长边 1600 时最差的是 soy53（少 6 个），已定位在阴影密集堆叠处：那里**不是**粘连未拆分（最大连通域面积 3180 vs 中位 2349，没有巨型连通域），而是全局 `yellow > median + 25` 把阴影里的豆子判成了背景。提到 2200 后 soy53 降到 −1，印证了下采样就是主因。当前剩余最差的是 soy70（−5）、soy104（−4）、soy69（−4），**尚未逐张定位**——用 `--dump-worst` 导出标注图肉眼看清是最快的下手方式。要整体再提升，方向仍是**局部**化二值化阈值，而不是上面两个全局方案。

## 实现决策

- 开发环境使用 SQLite，启动时通过 SQLAlchemy 自动建表；生产可通过 `DATABASE_URL` 切换 PostgreSQL。
- 登录失败固定等待 1 秒后返回错误，不引入 Redis 限流。
- 刷新令牌使用内存存储，服务重启后失效，便于本机调试。
- 人工修正接口保留，前端第一版提供重新计数，交互式点位编辑暂不展开。CSV 导出功能按需求移除（前后端一并删除）。
- `uv run python -m backend.app.main` 是后端本机启动入口，`frontend` 是独立的 Vite 应用。
- 时间统一使用北京时间（UTC+8）：`backend/app/core/clock.py` 提供 `beijing_now()` / `beijing_today()`，数据库 `DateTime` 列按北京时间（naive）写入，不用 `datetime.utcnow()`。前端 `frontend/src/utils/format.js` 只做展示格式化、不做时区换算，因此任何设备时区下显示的都是同一个北京时间。例外：JWT 的 `iat`/`exp` 按规范仍使用 UTC（`backend/app/core/security.py`）。`docker-compose.yml` 为两个服务设置 `TZ=Asia/Shanghai`，容器日志同样是北京时间。
- 旧数据修正：`backend/scripts/fix_timezone.py` 把 2026-10-10 之前按 UTC 落库的 `created_at` / `last_login_at` 统一 +8 小时，默认只预演，加 `--apply` 才写入，且不可重复执行。本机 `data/app.db` 已执行，执行前的备份在 `backups/`。线上库需在服务器上执行同一条命令。
- 标注图描边：豆子（`mode=beans`）的标注圆圈线宽为 2，其他模式为 1。豆子颗粒大、数量多，稍粗的描边在手机小屏上更容易分辨（`backend/app/services/counting.py`）。
- 处理分辨率：前端 `MAX_SIDE` 与后端 `default_max_side` 统一为 2200，**两者必须同步修改**（`frontend/src/utils/image.js`、`backend/app/config.py`），只改后端无效——前端上传前就已经缩放。存库与返回的原图、标注图都按处理后的尺寸，接口结构不变。取值依据见「识别准确率评估」。

## 移动端适配

- `index.html` 提供 `viewport` 与 `theme-color`；窄屏（≤720px）隐藏侧边栏，改为顶部栏 + 固定底部标签栏，底部适配 iPhone 安全区（`env(safe-area-inset-bottom)`）。
- 历史任务在窄屏显示为卡片列表，管理/统计表格改为横向滚动，弹窗宽度自适应（92vw），输入框移动端字号 16px 防止 iOS 聚焦自动放大。
- 上传前用 Canvas 将图片压缩到长边 2200、JPEG 质量 0.8（`frontend/src/utils/image.js` 的 `MAX_SIDE`）：手机相机原图很大，且 iPhone 的 HEIC 不在后端扩展名白名单内，统一转 JPEG 再上传；解码失败时回退原文件由后端校验。这个值直接影响识别精度，必须与后端 `settings.default_max_side` 保持一致，取值依据见「识别准确率评估」。
- 上传区提供两个入口：「拍照」用 `capture="environment"` 直接调起后置摄像头，「从相册选择」不带 `capture`，交给系统选择相册或文件；触摸设备显示两个按钮，桌面端只显示「选择图片」（`capture` 在桌面端本就被忽略）。直接点上传区在手机上等同于「拍照」，保留原来的快捷路径。
- 结果图查看器为自研组件 `frontend/src/components/ImageViewer.vue`：Element Plus 2.x 的 `el-image-viewer` 在触摸时遇到多指会直接返回（`touches.length !== 1`），只有单指拖动，无法双指放大。自研版本用 Pointer Events 实现双指捏合缩放（以两指中点为锚点）、单指/鼠标拖动、双击或双指轻点放大、滚轮缩放，并限制平移范围、锁定页面滚动。
- 路由增加兜底 `{ path: '/:pathMatch(.*)*', redirect: '/count' }`：刷新到失效或拼错的地址时直接回到计数页，不再出现 404 页面。
- 不引用 Google Fonts，改用系统字体栈，避免移动端（尤其国内网络）字体请求阻塞渲染。
- `vite.config.js` 开启 `server.host`，手机可通过局域网地址访问 `pnpm dev` 开发服务进行真机联调。
