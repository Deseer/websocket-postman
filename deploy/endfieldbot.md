# EndfieldBot 接入

本地源码：`/Users/deseer/project/EndfieldBot`。单独使用 OrbStack Compose 项目
`postman-endfield`，端口 `127.0.0.1:8792`（8790 已由 Mizuki 画廊占用）。
素材目录只读挂载，限制 2 CPU / 2 GiB / 128 PIDs，镜像以非 root 用户运行。

```sh
docker compose -p postman-endfield -f deploy/endfieldbot.compose.yaml up -d --build
uv run --with-requirements requirements.txt python scripts/verify_endfield_onebot.py
uv run --with-requirements requirements.txt python scripts/sync_endfield_bot.py
```

同步前先运行验证：直接模拟 OneBot 对端，检查鉴权、帮助、武器图片、潜能原图
及回执；不向真实 QQ 发消息。此验证加上连接在线不等同于真实 QQ 发图成功。

同步脚本只修改 `endfieldbot` 连接/指令集，不触碰 HrK、Mizuki、ArkBot、8823。
从本地当前 `commands.py` 的 `ALIASES` 安全解析最新清单，不导入执行上游模块。
若握手失败则禁用 EndfieldBot 的重连且不发布新指令。部署成功后使用 Postman
热更新，无须重启 Postman 或 NapCat。源码更新后需重新构建并重新同步。

私密 token 只从原有 `config.local.toml` 读取，通过只读挂载提供给容器；不写入
仓库或镜像。EndfieldBot 源目录的 `.dockerignore` 限定只复制 `src`、`pyproject.toml`。
原图签名链接使用 `http://host.docker.internal:8792`，供 NapCat 从 Docker 内取图。

## 群聊指令

- `ef/help` / `ef/帮助`
- `ef/干员 莱万汀 9` / `ef/角色 女管理员`
- `ef/武器 黯色火炬`
- `ef/敌人 潜地虬兽 60`
- `ef/基质 黯色火炬`（另有 `/基质规划`、`/武器基质` 别名）
- `ef/干员列表` / `ef/武器列表` / `ef/敌人列表 虬兽`
- `ef/地图 枢纽区 宝箱`
- `ef/插图 莱万汀 1`

群聊必须带 `ef`，也接受 `ef /干员`、`ef:/干员`。短指令自动转成上游原生
`/终末地 干员 …`，不要求开启 EndfieldBot 的全局 `short_commands`。
Postman 内部命令仍只有 `pm/`，不会抢 `ef/help`。

## 暂停与恢复

在 Postman 连接页断开 `endfieldbot` 会持久化禁用、停止重连。
仅需关闭 Bot 进程时使用：

```sh
docker compose -p postman-endfield -f deploy/endfieldbot.compose.yaml stop endfieldbot
```

要恢复运行并启用路由，执行上面的启动、验证、同步命令即可。
