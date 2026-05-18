# Lab #28 Submission — Student ID 2A202600023

Full Platform Integration Sprint — AI platform demo từ data ingestion đến model serving với full observability.

## Cấu trúc

```
lab28_submission_2A202600023/
├── README.md                       # File này
├── ANSWERS.md                      # Trả lời 5 câu hỏi
├── smoke_tests_results.txt         # Kết quả pytest (8/8 passed)
├── production_readiness.txt        # Production readiness 10/10 (100%)
└── screenshots/
    ├── prefect_ui.png
    ├── api_gateway.png
    ├── grafana_dashboard.png
    ├── smoke_tests_results.png
    └── production_readiness.png
```

Source code lab nằm ở thư mục cha (cùng repo): `docker-compose.yml`, `prefect/flows/`, `scripts/`, `api-gateway/`, `monitoring/`, `smoke-tests/`.

## Kết quả

- **Smoke tests**: 8/8 passed — xem `smoke_tests_results.txt`
- **Production readiness**: 10/10 = 100% (READY) — xem `production_readiness.txt`
- **5 câu hỏi**: xem `ANSWERS.md`

## Cách reproduce

### 1. Start local stack

```bash
docker compose up -d
docker compose ps   # đảm bảo tất cả services Up
```

Services:
- Prefect UI: http://localhost:4200
- Grafana: http://localhost:3000 (admin/admin)
- Qdrant: http://localhost:6333/dashboard
- Prometheus: http://localhost:9090
- API Gateway: http://localhost:8000

### 2. Start local GPU services (thay cho Kaggle)

```bash
# Embedding service (sentence-transformers all-MiniLM-L6-v2, port 8002)
.venv/bin/uvicorn scripts.embed_service:app --host 0.0.0.0 --port 8002 &

# vLLM (Qwen2.5-1.5B-Instruct, port 8001) — cần GPU
PATH="$PWD/.venv/bin:$PATH" .venv/bin/vllm serve Qwen/Qwen2.5-1.5B-Instruct \
  --host 0.0.0.0 --port 8001 --gpu-memory-utilization 0.7 --max-model-len 4096 &
```

`.env` đã trỏ tới các local endpoint này:
```
VLLM_NGROK_URL=http://host.docker.internal:8001
EMBED_NGROK_URL=http://localhost:8002
```

### 3. Deploy Prefect flow

```bash
.venv/bin/python prefect/flows/kafka_to_delta.py
```

Flow `kafka-to-delta` chạy theo cron `*/5 * * * *`.

### 4. Run pipeline (seed data)

```bash
.venv/bin/python scripts/01_ingest_to_kafka.py
.venv/bin/python scripts/03_delta_to_feast.py
.venv/bin/python scripts/05_embed_to_qdrant.py
```

### 5. Run smoke tests

```bash
.venv/bin/pytest smoke-tests/ -v
# 8/8 passed
```

### 6. Production readiness

```bash
.venv/bin/python scripts/production_readiness_check.py
# Score 10/10 = 100% READY
```

## Screenshots cần chụp (chưa có)

Chụp các màn hình sau và lưu vào `screenshots/`:

1. **`prefect_ui.png`** — http://localhost:4200, tab Flow Runs hiển thị `kafka-to-delta` đang chạy / scheduled
2. **`api_gateway.png`** — terminal output `curl http://localhost:8000/health` trả `{"status":"ok"}` và `curl -X POST http://localhost:8000/api/v1/chat -d '{"query":"...","embedding":[...]}'`
3. **`grafana_dashboard.png`** — http://localhost:3000 (admin/admin), dashboard hiển thị metrics từ API Gateway
4. **`smoke_tests_results.png`** — terminal output `pytest smoke-tests/ -v` (8 passed)
5. **`production_readiness.png`** — terminal output `python scripts/production_readiness_check.py` (10/10)

## Notes

- Kiến trúc hybrid: local Docker stack + GPU services (Kaggle hoặc local). Trong submission này tôi chạy GPU services local thay cho Kaggle (Qwen2.5-1.5B thay cho Qwen2.5-7B-GPTQ-Int4).
- Lý do swap: lab gốc yêu cầu Kaggle T4×2 cho 7B-GPTQ; local GPU nhỏ hơn nên dùng 1.5B với `gpu-memory-utilization=0.7`.
- Không sửa `scripts/05_embed_to_qdrant.py` — thay vào đó viết `scripts/embed_service.py` (FastAPI adapter) match đúng contract `/embed` và đổi `EMBED_NGROK_URL` trong `.env`.
