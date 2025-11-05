#!/usr/bin/env bash
set -e
which ollama || { echo "ollama não encontrado no PATH"; exit 1; }
echo "ollama version:"
ollama --version || true
# Tentativa de checar backends (se serviços estiverem no ar)
for p in 11434 11435 11436 11437 11438; do
  curl -sSf "http://127.0.0.1:${p}/api/version" || true
done
