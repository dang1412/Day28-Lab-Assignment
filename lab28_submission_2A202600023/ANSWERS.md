# Lab #28 — 5 Câu Hỏi Nộp Bài

## 1. Trade-offs trong thiết kế kiến trúc AI platform

Kiến trúc cân bằng giữa **performance**, **reliability**, và **maintainability** như sau:

- **Performance**: vLLM dùng cho LLM inference (continuous batching, paged attention) thay vì gọi API ngoài → giảm latency. API Gateway giới hạn `max_tokens=80` để response ≤ 2s theo SLO của smoke test. Vector search dùng Qdrant (Rust, HNSW) cho p99 < 50ms.
- **Reliability**: Mỗi component (Kafka, Qdrant, Redis, Prefect, vLLM) chạy độc lập trong container/process riêng — fail isolation. Prefect orchestration với cron retry `*/5 * * * *`. Prometheus + Grafana cho early-warning. API Gateway có timeout + Pydantic validation tại biên.
- **Maintainability**: GitOps config (docker-compose.yml + prefect/flows). Tách rõ tầng: ingestion (Kafka) → transform (Prefect/Delta) → serving (Qdrant/Redis) → gateway (FastAPI) → observability (Prom/Grafana). Env vars (`VLLM_NGROK_URL`, `EMBED_NGROK_URL`) cho phép swap provider mà không động vào code.

**Trade-off chính**: chọn **nhiều service nhỏ** thay vì monolith → maintainability + reliability cao hơn, nhưng tốn RAM/CPU local và operational complexity (phải biết debug Kafka/Prefect/Qdrant riêng).

## 2. Xử lý ngắt kết nối Local ↔ Kaggle (hybrid)

- **Adapter pattern qua env var**: `VLLM_NGROK_URL` và `EMBED_NGROK_URL` trỏ đến endpoint Kaggle qua ngrok. Khi Kaggle disconnect, chỉ cần đổi env var sang local service tương thích cùng API contract (OpenAI `/v1/chat/completions` cho vLLM, `/embed` cho embedding) — không sửa code.
- **Local fallback đã chứng minh**: Trong lab này tôi đã chạy `vllm serve Qwen2.5-1.5B-Instruct` + `scripts/embed_service.py` (sentence-transformers `all-MiniLM-L6-v2`) trên local thay cho Kaggle, chỉ cần update `.env`.
- **Graceful degradation**: API Gateway dùng `httpx.AsyncClient(timeout=30)` để không treo. Nếu vLLM down, request fail nhanh và Prometheus alert (`up{job='vllm'} == 0`).
- **Hạn chế**: chưa có circuit breaker hay retry với exponential backoff tại tầng gateway — production cần thêm `tenacity` hoặc `httpx-retries`.

## 3. Event-driven với Kafka giúp decouple components

- **Producer/Consumer tách biệt**: `scripts/01_ingest_to_kafka.py` push events `data.raw` vào Kafka. `prefect/flows/kafka_to_delta.py` consume độc lập theo cron `*/5 * * * *`. Producer không quan tâm ai đọc, consumer không quan tâm ai gửi.
- **Buffer + backpressure**: Khi Prefect/Delta chậm, Kafka giữ message trong topic — không mất data. Spike traffic không sập downstream.
- **Replay & multi-consumer**: Nhiều consumer group có thể đọc cùng topic → một stream Kafka phục vụ Delta Lake, Qdrant ingest, monitoring, audit cùng lúc.
- **Schema evolution**: Producer có thể thêm field JSON mới mà consumer cũ vẫn parse được (forward compatibility).
- **Trong lab**: Kafka đóng vai trò "single source of truth" cho raw events; downstream (Delta → Feast → Qdrant) đều build từ topic này.

## 4. Observability — Logs, Metrics, Traces

- **Metrics**: `prometheus_fastapi_instrumentator` expose `/metrics` trên API Gateway (latency histogram, request count, in-flight). Prometheus scrape config trong `monitoring/prometheus.yml`. Grafana (port 3000, admin/admin) visualize: request rate, p50/p95/p99 latency, error rate, container up/down.
- **Logs**: Mỗi container log stdout → `docker compose logs <service>`. Prefect UI (port 4200) hiển thị log của từng flow run + task state.
- **Traces**: LangSmith integration qua `LANGCHAIN_API_KEY` + `LANGCHAIN_PROJECT=lab28-platform` trong `.env` — trace LLM call chain (retrieval → prompt → LLM response).
- **Alerts**: Prometheus rules (placeholder) cho `up == 0`, p99 > 2000ms, error rate > 5%.
- **Verified**: `production_readiness_check.py` đạt 10/10, gồm 3 check observability (Prometheus, Grafana, /metrics).

## 5. Service crash — Graceful degradation

| Service | Hậu quả | Cách xử lý |
|---|---|---|
| **Qdrant** crash | Vector search fail → API Gateway trả lỗi 500 | Gateway nên catch exception, trả response "no context" và vẫn gọi LLM (degraded mode). Cần thêm health check + retry. |
| **Kafka** crash | Producer block / consumer idle → no new data flowing | Prefect flow retry theo cron; producer dùng `acks=1` + buffer local. Restart Kafka qua `docker compose up -d kafka` (đã test, container `lab28-kafka-1`). |
| **vLLM** crash | LLM call fail | Gateway timeout 30s, trả 502/503. Có thể fallback sang model nhỏ hơn hoặc cached response. Trong lab đã chứng minh swap qua env var. |
| **Redis (Feast)** crash | Online feature lookup fail | Fallback sang Delta Lake (offline store) — chậm hơn nhưng vẫn serve được. |
| **Prefect** crash | Pipeline ngừng chạy | Data tích trong Kafka (không mất). Restart Prefect là pipeline resume. |
| **Prometheus/Grafana** crash | Mất observability — không ảnh hưởng serving path | Restart độc lập, không downtime. |

**Nguyên tắc chung**: tách hard dependency (LLM, Vector store) khỏi soft dependency (observability, feature store). Soft dep down → degraded mode; hard dep down → fail fast với error code rõ ràng để client retry.
