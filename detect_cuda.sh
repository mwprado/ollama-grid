#!/usr/bin/env bash
set -euo pipefail
CUDA_VERSION=""
if command -v nvcc >/dev/null 2>&1; then
  CUDA_VERSION=$(nvcc --version | awk '/release/{print $6}' | sed 's/,//')
fi
CUDA_HOME="/usr/local/cuda-${CUDA_VERSION:-12.9}"
cat <<EOF
%%global cuda_version ${CUDA_VERSION:-12.9}
%%global cuda_home ${CUDA_HOME}
EOF
