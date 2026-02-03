# WebSocket 指令分配器

面向 QQBot (NapCat/Matcha/LLOneBot) 的 WebSocket 指令分配器，支持多 Bot 指令路由、风格切换、权限控制和可视化管理。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

## ✨ 功能特性

- 🔌 **多连接支持** - 同时连接多个上游 Bot 服务
- 📦 **指令集管理** - 定义指令集、别名、时间限制、群聊限制
- 🎨 **风格切换** - 用户可在互斥指令集间自由切换
- 🔒 **权限控制** - 支持用户/群组黑白名单、特权指令
- 🎯 **默认规则** - 未匹配指令的处理策略（拒绝/放行/转发）
- 🌐 **WebUI** - 可视化管理所有配置，实时日志查看

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourname/websocket-postman.git
cd websocket-postman
```

### 2. 一键启动

```bash
chmod +x start.sh
./start.sh
```

首次运行会自动：
- 创建 Python 虚拟环境
- 安装所有依赖
- 创建默认配置文件
- 构建前端（如已安装 Node.js）

### 3. 访问管理界面

打开浏览器访问: **http://localhost:8080**

## 📦 手动安装

如果自动安装失败，可以手动安装：

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp config/config.example.yaml config/config.yaml

# 启动服务
python -m src.main
```

### 构建前端（可选）

```bash
cd webui
npm install
npm run build
cd ..
```

## ⚙️ 配置说明

配置文件位于 `config/config.yaml`，主要配置项：

```yaml
# 服务器配置
server:
  host: 0.0.0.0
  port: 8080      # WebUI 端口
  ws_port: 8765   # NapCat 连接端口

# 连接配置 - 上游 Bot 服务
connections:
  - id: mybot
    name: 我的Bot
    url: ws://localhost:3001/onebot/v11/ws
    token: ""  # OneBot v11 Token（如有）
    auto_reconnect: true

# 分类配置
categories:
  - id: pjsk
    name: pjsk
    display_name: Project Sekai
    allow_user_switch: true  # 允许用户自行切换

# 指令集配置
command_sets:
  - id: bot1
    name: Bot1
    category: pjsk
    target_ws: mybot
    is_public: true
    commands:
      - name: /个人信息
        aliases: [/info, /查询]
      - name: /抽卡
        is_privileged: true  # 特权指令

# 默认规则
final:
  action: reject  # reject / allow / forward
  message: 未知指令
  send_message: true  # 是否发送拒绝消息
```

## 📱 用户指令

| 指令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/status` | 显示系统状态 |
| `/list` | 列出所有分类 |
| `/list <分类>` | 列出分类下的指令集 |
| `/style list` | 列出可选风格 |
| `/style select <分类> <风格>` | 选择风格 |
| `/style current` | 查看当前选择 |

### 强制指令集调用

```
<指令集名称> <指令>
```

例如：`bot1 /个人信息` 强制使用 bot1 指令集

## 🔗 NapCat 对接

1. 在 WebUI 的「连接管理」添加上游 Bot 连接
2. 配置 NapCat 的 `onebot11.json`：

```json
{
  "network": {
    "websocketClients": [
      {
        "enable": true,
        "url": "ws://127.0.0.1:8765",
        "messagePostFormat": "string"
      }
    ]
  }
}
```

3. NapCat 将主动连接到分配器的 8765 端口

## 📁 项目结构

```
websocket-postman/
├── src/                    # 后端源码
│   ├── main.py             # 应用入口
│   ├── config.py           # 配置管理
│   ├── core/               # 核心逻辑
│   │   ├── router.py       # 指令路由引擎
│   │   ├── ws_server.py    # WS 服务端 (接收 NapCat)
│   │   └── ws_client.py    # WS 客户端 (连接上游 Bot)
│   ├── api/                # REST API
│   └── models/             # 数据模型
├── webui/                  # 前端源码 (Vue 3)
├── static/                 # 前端构建产物
├── config/                 # 配置文件
├── logs/                   # 日志文件
├── data/                   # 数据库文件
└── start.sh                # 启动脚本
```

## 🛠️ 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest

# 前端开发 (热重载)
cd webui
npm run dev
```

## 📄 License

MIT License
