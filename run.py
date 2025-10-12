import os
import socket
import subprocess
import sys
from pathlib import Path

import uvicorn
from uvicorn.config import LOGGING_CONFIG

PYTHON312_EXE = Path(r"C:\Program Files\Python312\Scripts\python.exe")


def ensure_python312() -> None:
    if sys.version_info[:2] == (3, 12):
        return
    if not PYTHON312_EXE.exists():
        raise RuntimeError("未找到 C\\Program Files\\Python312\\Scripts\\python.exe，请确认已安装 Python 3.12")
    script_path = Path(__file__).resolve()
    result = subprocess.run([str(PYTHON312_EXE), str(script_path), *sys.argv[1:]])
    sys.exit(result.returncode)


if __name__ == "__main__":
    # ensure_python312()  # 暂时跳过版本检查，使用当前环境

    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    # 配置根日志器以显示应用日志
    LOGGING_CONFIG["loggers"][""] = {
        "handlers": ["default"],
        "level": "INFO",
        "propagate": False,
    }

    # 创建自定义 socket 配置以绕过端口 9999 的权限限制
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Windows 特定: 尝试设置额外的 socket 选项
        if sys.platform == "win32":
            try:
                # SO_EXCLUSIVEADDRUSE = -5 on Windows
                sock.setsockopt(socket.SOL_SOCKET, -5, 0)
            except (AttributeError, OSError):
                pass
        
        sock.bind(("0.0.0.0", 9999))
        
        # 使用预绑定的 socket 启动 uvicorn
        import asyncio
        config = uvicorn.Config(
            "app:app",
            host="0.0.0.0",
            port=9999,
            reload=True,
            log_config=LOGGING_CONFIG
        )
        server = uvicorn.Server(config)
        asyncio.run(server.serve(sockets=[sock]))
        
    except PermissionError as e:
        print(f"\n❌ 权限错误: {e}")
        print("\n端口 9999 被系统安全策略阻止。")
        print("请以管理员身份运行 PowerShell,或者联系系统管理员。")
        sys.exit(1)
    except OSError as e:
        if e.errno == 10013:
            print(f"\n❌ 权限错误: {e}")
            print("\n端口 9999 被系统安全策略阻止。")
            print("请以管理员身份运行 PowerShell,或者联系系统管理员。")
        else:
            print(f"\n❌ 系统错误: {e}")
        sys.exit(1)
