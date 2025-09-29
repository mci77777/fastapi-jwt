import os
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
    ensure_python312()

    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    uvicorn.run("app:app", host="0.0.0.0", port=9999, reload=True, log_config=LOGGING_CONFIG)
