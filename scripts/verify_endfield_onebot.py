"""独立模拟 OneBot 对端；不向 Postman/NapCat 注入消息，不会发到真实 QQ。"""
import asyncio
import json
import subprocess
import time
import tomllib
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus


async def main():
    config = tomllib.loads(Path("/Users/deseer/project/EndfieldBot/config.local.toml").read_text())
    token = config["bot"]["token"]
    url = "ws://127.0.0.1:8792/onebot/v11/ws"
    try:
        async with connect(url):
            raise AssertionError("Unauthenticated connection was accepted")
    except InvalidStatus as error:
        assert error.response.status_code == 403
    print("Unauthenticated WebSocket rejected", flush=True)
    async with connect(url, additional_headers={"Authorization": f"Bearer {token}"},
                       max_size=1_048_576) as ws:
        for index, (command, expected) in enumerate([
            ("/终末地 帮助", "text"),
            ("/终末地 武器 黯色火炬", "image"),
            ("/终末地 插图 莱万汀 1", "image"),
        ]):
            event = {"post_type": "message", "message_type": "group", "sub_type": "normal",
                     "self_id": 1, "user_id": 100 + index, "group_id": 2,
                     "message_id": time.time_ns(), "message": command, "raw_message": command}
            await ws.send(json.dumps(event))
            raw = await asyncio.wait_for(ws.recv(), timeout=120)
            packet = json.loads(raw)
            assert packet["action"] == "send_group_msg"
            assert packet["params"]["group_id"] == 2
            assert len(raw.encode()) < 1_048_576
            segments = packet["params"]["message"]
            assert any(segment["type"] == expected for segment in segments)
            for segment in segments:
                file = segment.get("data", {}).get("file", "")
                if file.startswith("http"):
                    # 从真实 Postman 容器验证签名图链的容器到宿主机路径，不输出签名。
                    result = subprocess.run([
                        "docker", "exec", "-i", "ws-dispatcher", "python", "-c",
                        "import sys,urllib.request; data=urllib.request.urlopen(sys.stdin.read(),timeout=15).read(); "
                        "assert data.startswith(bytes.fromhex('89504e47')); print(len(data))",
                    ], input=file, text=True, capture_output=True, timeout=20)
                    assert result.returncode == 0, "Signed image fetch from Postman failed"
                    print("Original PNG reachable from Postman container: bytes=" + result.stdout.strip(), flush=True)
            await ws.send(json.dumps({"status": "ok", "retcode": 0,
                                      "data": {"message_id": index}, "echo": packet["echo"]}))
            print(f"Verified {command}: {expected}, packet_bytes={len(raw.encode())}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
