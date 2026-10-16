FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# 构建上下文 = 后端目录内容（requirements.txt、app/、scripts/ 与本文件同级，无 backend/ 父目录）
# 镜像内还原为 backend/ 包路径，代码里的 backend.app 导入与本机运行保持一致
COPY requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.txt

COPY app backend/app
COPY scripts backend/scripts

EXPOSE 8000

# 先确保 admin 账号存在（幂等），再启动服务
CMD ["sh", "-c", "python -m backend.scripts.seed && exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
