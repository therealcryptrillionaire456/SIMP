FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PROJECTX_HOST=0.0.0.0
ENV PROJECTX_PORT=5555

COPY . /app

RUN pip install --no-cache-dir --upgrade pip

EXPOSE 5555

CMD ["python3", "-m", "simp.projectx.runtime_server"]
