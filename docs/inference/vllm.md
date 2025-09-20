# Self-Hosted vLLM Deployment Guide

This walkthrough shows how to stand up vLLM locally (or on a GPU host), configure it as the RLaaS inference backend, and verify the gateway integration.

## Prerequisites
- CUDA-capable GPU (for realistic workloads) or CPU (for tiny models/testing).
- Docker (recommended) or Python environment with CUDA drivers.
- RLaaS stack running from this repo (`make up` brings up collector/gateway/stub). We'll replace the stub with vLLM.

## 1. Launch vLLM (Docker)
Pick a model that fits your hardware. Example with Llama-3.1 8B (requires ~16GB GPU memory):

```bash
MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
PORT=8081

docker run --gpus all \
  -p ${PORT}:8000 \
  -e VLLM_OPENAI_API_KEY=stub-key \
  vllm/vllm-openai:latest \
  --model $MODEL \
  --tensor-parallel-size 1 \
  --max-model-len 4096
```

Key flags:
- `--gpus all`: expose host GPUs.
- `-p PORT:8000`: map container port 8000 (vLLM REST API) to host.
- `VLLM_OPENAI_API_KEY`: optional; vLLM emulates OpenAI API. We'll use this pseudo key in the gateway.

For CPU-only testing (very slow): add `--device cpu`.

### Health check
Wait for the logs to show “Uvicorn running on … port 8000”, then:
```bash
curl http://localhost:${PORT}/healthz
```
Expect `{"status": "ok"}`.

## 2. Update RLaaS gateway configuration
Edit `.env` in this repo:
```ini
INFERENCE_BASE_URL=http://host.docker.internal:${PORT}
INFERENCE_API_KEY=stub-key
GATEWAY_USE_STUB_BACKEND=false
```
- `host.docker.internal` lets the gateway container call the host (works on Docker Desktop). On Linux, use the host IP or run vLLM on the same Docker network.
- `INFERENCE_API_KEY` should match `VLLM_OPENAI_API_KEY` you set above.

Restart the stack:
```bash
docker compose down
make up
```
Gateway logs should include `backend_ok=True` during startup.

## 3. Verify `/v1/infer`
```bash
curl -X POST http://localhost:8000/v1/infer \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "acme-support",
    "input": {"text": "Need a refund policy response."}
  }'
```
You should see vLLM’s response text (not the stub). Collector will log the output event; shadow candidates (if any) will also show in `/debug/shadow-log`.

## 4. Performance tuning
- Set `tensor_parallel` or `gpu_memory_utilization` flags if you have multiple GPUs.
- Gateways is asynchronous: configure `UVICORN_WORKERS` env var in `apps/gateway/Dockerfile` or `.env` only if CPU-bound.
- For production, put vLLM behind TLS and authentication; the gateway’s `INFERENCE_API_KEY` header can be used for shared-secret auth.

## 5. Cleanup
```bash
docker stop vllm-container
```

## 6. Troubleshooting
- **Connection refused**: ensure gateway can reach vLLM. On Linux, run vLLM in the same docker-compose network (`network_mode: "service:inference"`) or use IP.
- **GPU OOM**: choose a smaller model or limit sequence length (`--max-model-len`).
- **Slow responses**: enable token streaming in the gateway (future work) or allocate more GPUs.

## Next steps
- Replace the stub inference service in docker-compose with a vLLM service container (optional).
- Add load testing to validate latency before going live.
- Automate deployment (Kubernetes, ECS, etc.) with the same env vars (`INFERENCE_BASE_URL`, `INFERENCE_API_KEY`).
