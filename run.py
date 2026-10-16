"""本地启动入口：读取 .env 并运行 uvicorn。生产建议直接用 uvicorn/gunicorn 命令。"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
