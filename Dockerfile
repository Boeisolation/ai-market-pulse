FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY prompts ./prompts

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -e ".[cn,excel,tushare]"

CMD ["market-pulse", "--help"]
