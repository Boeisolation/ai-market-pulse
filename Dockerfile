FROM python:3.11-slim

# Override for faster installs behind regional mirrors, e.g.
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple .
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY prompts ./prompts

RUN python -m pip install --upgrade pip -i "$PIP_INDEX_URL" && \
    pip install --no-cache-dir -i "$PIP_INDEX_URL" -e ".[cn,excel,tushare]"

EXPOSE 8766

CMD ["market-pulse", "serve", "--host", "0.0.0.0", "--port", "8766", "--root", "/workspace"]
