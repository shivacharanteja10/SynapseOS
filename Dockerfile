FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system synapseos && adduser --system --ingroup synapseos synapseos

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install -r requirements.txt

USER synapseos

EXPOSE 8000

CMD ["uvicorn", "synapseos.main:app", "--host", "0.0.0.0", "--port", "8000"]
