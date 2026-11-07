# line-mx-roster · 机务排班日历

给航线机务（也可以是任何轮班岗位）用的排班日历：单文件前端 + 零依赖 Python 同步后端，一个仓库跑通「手机日历看班、多设备云同步、工时统计」。

> **如果你是 AI 助手 / 自动化代理**，收到「帮我把 line-mx-roster 部署起来」这类请求时，直接按下方[《部署》](#部署)一节逐步执行即可，所有命令都可以照抄，占位符只有 `<你的域名>` 和两个口令。

## 功能

- 📅 月历视图：农历、节气、法定节假日/调休（2026–2027 已内置，源自国务院放假安排）、班次彩色标签
- 🔄 一键排班（⚡）：选好班次顺序，从任意日期起按循环批量填充，默认跳过已有排班，可撤销
- ⏱ 工时统计：每个班次工时自己定义，月度实排 vs 标准工时（工作日×8h）对比，法定节假日三工单列
- 🛠 班次管理（⚙）：班次的名称/颜色/工时全部可改，可新增删除，改完自动同步到云端
- ☁️ 云同步：两级口令（查看=只读，编辑=可写），多设备共用一份数据
- 📱 PWA：手机浏览器「安装到桌面」，离线可开页面壳（数据始终走网络，不缓存）
- 🖥 响应式：≥900px 自动切双栏桌面布局

## 文件结构

```
line-mx-roster/
├── index.html                  # 前端全部（HTML+CSS+JS 单文件，含日历/农历/节假日/统计）
├── manifest.webmanifest        # PWA 清单
├── sw.js                       # Service Worker：缓存页面壳，/api/ 永不缓存
├── icon-*.png / favicon.ico    # 图标
└── server/
    ├── api.py                  # 同步 API，Python 3 标准库，零第三方依赖
    ├── env.example             # 口令配置模板 → 复制为 env
    ├── shift-api.service       # systemd 单元
    └── nginx-shift-schedule.conf  # nginx 站点配置（含 HTTPS）
```

## 部署

### 方式 A：只用前端（不部署后端）

1. 把 `index.html` 放到任意静态服务器（或直接双击打开也行）
2. 用编辑器改 `index.html` 顶部的 `VIEW_CODE`（默认 `8888`），这就是进门口令
3. 没有 API 时页面自动进入「仅本地」模式：数据存浏览器 localStorage，换设备不互通
4. 备份/迁移用「我的 → 导出备份 / 导入备份」

### 方式 B：完整部署（前端 + 云同步）

以下命令假设 Ubuntu/Debian + nginx，域名 `<你的域名>` 已解析到服务器。

**1. 后端**

```bash
sudo mkdir -p /opt/shift-api
sudo cp server/api.py /opt/shift-api/
sudo cp server/shift-api.service /etc/systemd/system/

# 生成口令配置（把两个口令改成你自己的，前者要与前端的 VIEW_CODE 一致）
sudo tee /opt/shift-api/env >/dev/null <<'EOF'
SHIFT_ACCESS_CODE=8888
SHIFT_EDIT_CODE=6666
EOF
sudo chmod 640 /opt/shift-api/env

sudo systemctl daemon-reload
sudo systemctl enable --now shift-api
curl -s http://127.0.0.1:8023/api/ping   # 应返回 {"ok": true}
```

**2. 前端 + nginx**

```bash
sudo mkdir -p /var/www/shift-schedule
sudo cp index.html manifest.webmanifest sw.js icon-*.png favicon.ico /var/www/shift-schedule/

# 把 server/nginx-shift-schedule.conf 里的 shift.example.com 换成你的域名，
# HTTPS 证书路径按实际情况改（certbot / acme.sh 均可），然后：
sudo cp server/nginx-shift-schedule.conf /etc/nginx/sites-available/shift-schedule
sudo ln -sf /etc/nginx/sites-available/shift-schedule /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**3. 验证**

```bash
curl -s https://<你的域名>/api/ping          # {"ok": true}
# 浏览器打开 https://<你的域名>/，输入查看口令进入，点「我的」输编辑口令开始排班
```

### 配置速查

| 配置 | 位置 | 说明 |
|---|---|---|
| 查看口令 | `index.html` 顶部 `VIEW_CODE` + `server/env` 的 `SHIFT_ACCESS_CODE` | 两处必须一致；登录后只读 |
| 编辑口令 | `server/env` 的 `SHIFT_EDIT_CODE` | 在网页「我的」里输入，可写 |
| 后端端口 | `server/shift-api.service`（默认 8023，仅监听 127.0.0.1） | 由 nginx 反代 `/api/` |
| 静态目录 | nginx 配置 `root`（默认 `/var/www/shift-schedule`） | |

### 数据与备份

- 数据在后端目录：`data.json`（排班 + 班次定义）、`tokens.json`（登录令牌）
- 格式：`{"shifts": {"2026-11-08": ["白班"], ...}, "defs": [{"key":"白班","color":"#66bb6a","hours":12.5}, ...], "updated": 1700000000}`
- 备份 = 复制这两个文件；恢复 = 放回原位重启 `shift-api`
- 换机器迁移：整个 `/opt/shift-api/` 打包带走即可

### 安全建议

- 两个口令务必改成自己的，别用仓库里的示例值
- 必须 HTTPS（口令是明文 POST 到 `/api/login`）
- nginx 配置已带「非本域名 444 断开」，建议保留
- `tokens.json` 里的令牌永久有效，怀疑泄露就删掉它重启服务（所有人重新登录）

## 已知取舍

- 编辑口令在前端只用于换取 token，真正的写权限校验在后端，改口令后旧 token 仍有效（删 tokens.json 可全部登出）
- 重命名班次只影响之后新排的日期，历史记录保持原名（颜色回退为灰色）
- Service Worker 会缓存页面壳，发新版后如遇客户端仍是旧界面，强刷一次即可

## License

[MIT](LICENSE)
