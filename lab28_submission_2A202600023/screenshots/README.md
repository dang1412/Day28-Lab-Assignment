# Screenshots cần chụp

| File | URL / Command | Nội dung cần chụp |
|---|---|---|
| `prefect_ui.png` | http://localhost:4200 | Flow `kafka-to-delta` ở tab Flow Runs / Deployments |
| `api_gateway.png` | terminal | `curl http://localhost:8000/health` + `/api/v1/chat` response |
| `grafana_dashboard.png` | http://localhost:3000 (admin/admin) | Dashboard hiển thị metrics từ api-gateway |
| `smoke_tests_results.png` | terminal | `pytest smoke-tests/ -v` → 8 passed |
| `production_readiness.png` | terminal | `python scripts/production_readiness_check.py` → 10/10 READY |
