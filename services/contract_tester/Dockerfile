# syntax=docker/dockerfile:1.6
# ─────────────────────────────────────────────────────────────────────────
# Contract Tester — CLI image that validates any model service URL.
#
# IMPORTANT: build context must be the repository root so the
# contracts/schemas/ directory is included in the image.
#
#   docker build -f services/contract_tester/Dockerfile -t contract-tester .
#   docker run --rm --network=host contract-tester http://localhost:9000
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

# Bake the contract schemas into the image so the tester is self-contained.
COPY contracts /workspace/contracts

# Copy tester source
COPY services/contract_tester /workspace/services/contract_tester

RUN pip install -r /workspace/services/contract_tester/requirements.txt

ENTRYPOINT ["python", "/workspace/services/contract_tester/main.py"]
