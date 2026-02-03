#!/bin/bash
# WebSocket 指令分配器 - 启动脚本
# 自动检查环境、安装依赖、启动服务

set -e

cd "$(dirname "$0")"

echo "╔════════════════════════════════════════════╗"
echo "║    🚀 WebSocket 指令分配器 启动脚本        ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ========== 检查 Python ==========
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON=python3
    elif command -v python &> /dev/null; then
        PYTHON=python
    else
        echo "❌ 错误: 找不到 Python，请先安装 Python 3.10+"
        echo "   下载地址: https://www.python.org/downloads/"
        exit 1
    fi
    
    # 检查 Python 版本
    PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "📦 Python 版本: $PY_VERSION"
    
    # 版本检查 (需要 3.10+)
    PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
    PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')
    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
        echo "❌ 错误: 需要 Python 3.10 或更高版本"
        exit 1
    fi
}

# ========== 创建/激活虚拟环境 ==========
setup_venv() {
    if [ ! -d ".venv" ]; then
        echo ""
        echo "📦 创建虚拟环境..."
        $PYTHON -m venv .venv
        echo "✅ 虚拟环境创建成功"
    fi
    
    echo "📦 激活虚拟环境..."
    source .venv/bin/activate
}

# ========== 安装 Python 依赖 ==========
install_python_deps() {
    # 检查是否需要安装依赖
    if [ ! -f ".venv/.deps_installed" ] || [ "requirements.txt" -nt ".venv/.deps_installed" ]; then
        echo ""
        echo "📦 安装 Python 依赖..."
        pip install -q --upgrade pip
        pip install -q -r requirements.txt
        touch .venv/.deps_installed
        echo "✅ Python 依赖安装完成"
    else
        echo "✅ Python 依赖已是最新"
    fi
}

# ========== 检查 Node.js 和构建前端 ==========
build_frontend() {
    # 检查是否需要构建前端
    if [ ! -d "static/assets" ]; then
        NEED_BUILD=true
    elif [ -d "webui/src" ]; then
        # 检查前端源码是否有更新
        WEBUI_MODIFIED=$(find webui/src -type f -name "*.vue" -o -name "*.js" -o -name "*.css" 2>/dev/null | xargs stat -f "%m" 2>/dev/null | sort -n | tail -1 || echo "0")
        STATIC_MODIFIED=$(stat -f "%m" static/assets 2>/dev/null || echo "0")
        if [ "$WEBUI_MODIFIED" -gt "$STATIC_MODIFIED" ]; then
            NEED_BUILD=true
        fi
    fi
    
    if [ "$NEED_BUILD" = true ]; then
        echo ""
        echo "🔨 检查前端构建环境..."
        
        if ! command -v node &> /dev/null; then
            echo "⚠️  未安装 Node.js，跳过前端构建"
            echo "   如需修改前端，请安装 Node.js: https://nodejs.org/"
            return
        fi
        
        if ! command -v npm &> /dev/null; then
            echo "⚠️  未安装 npm，跳过前端构建"
            return
        fi
        
        echo "📦 Node.js 版本: $(node -v)"
        
        cd webui
        
        if [ ! -d "node_modules" ]; then
            echo "📦 安装前端依赖..."
            npm install --silent
        fi
        
        echo "🔨 构建前端..."
        npm run build --silent
        
        cd ..
        echo "✅ 前端构建完成"
    else
        echo "✅ 前端已是最新"
    fi
}

# ========== 创建配置文件 ==========
init_config() {
    if [ ! -f "config/config.yaml" ]; then
        echo ""
        echo "📝 创建配置文件..."
        if [ -f "config/config.example.yaml" ]; then
            cp config/config.example.yaml config/config.yaml
            echo "✅ 已从示例创建配置文件"
        else
            # 创建默认配置
            mkdir -p config
            cat > config/config.yaml << 'EOF'
# WebSocket 指令分配器配置文件

logging:
  level: INFO
  file: ./logs/dispatcher.log

server:
  host: 0.0.0.0
  port: 8080
  ws_port: 8765

database:
  url: sqlite+aiosqlite:///./data/dispatcher.db

# 分类配置
categories: []

# 连接配置
connections: []

# 指令集配置  
command_sets: []

# 默认规则
final:
  action: reject
  message: 未知指令，请使用 /help 查看帮助
  send_message: true

# 管理员 QQ 号
admins: []
EOF
            echo "✅ 已创建默认配置文件"
        fi
        echo "   请编辑 config/config.yaml 配置你的连接"
    fi
}

# ========== 创建必要目录 ==========
init_dirs() {
    mkdir -p logs data config
}

# ========== 启动服务 ==========
start_server() {
    echo ""
    echo "════════════════════════════════════════════"
    echo "🔌 启动 WebSocket 指令分配器..."
    echo "   WebUI: http://localhost:8080"
    echo "   WS端口: 8765 (NapCat 连接此端口)"
    echo "   按 Ctrl+C 停止服务"
    echo "════════════════════════════════════════════"
    echo ""
    
    $PYTHON -m src.main
}

# ========== 主流程 ==========
main() {
    check_python
    setup_venv
    install_python_deps
    init_dirs
    init_config
    build_frontend
    start_server
}

# 处理命令行参数
case "${1:-}" in
    --install-only)
        check_python
        setup_venv
        install_python_deps
        init_dirs
        init_config
        build_frontend
        echo ""
        echo "✅ 安装完成！运行 ./start.sh 启动服务"
        ;;
    --help|-h)
        echo "用法: ./start.sh [选项]"
        echo ""
        echo "选项:"
        echo "  --install-only  仅安装依赖，不启动服务"
        echo "  --help, -h      显示此帮助信息"
        echo ""
        echo "示例:"
        echo "  ./start.sh              # 安装并启动服务"
        echo "  ./start.sh --install-only  # 仅安装依赖"
        ;;
    *)
        main
        ;;
esac
