#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Local CUDA 12.9 build helper for ollama-grid-cuda12.
#
# This script is intentionally meant for local/specialized builds, not COPR.
# It can enable NVIDIA's Fedora CUDA repository, install CUDA Toolkit 12.9,
# verify that nvcc is available, and then run rpmbuild with --with cuda12.
#
# The actual CUDA header patch is applied by packaging/ollama-grid.spec during
# %prep/%build by copying headers into the RPM build directory and patching the
# copy. This script does not modify files under /usr/local/cuda-*.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_FILE="${SPEC_FILE:-${PROJECT_ROOT}/packaging/ollama-grid.spec}"
CUDA_VERSION_DASH="${CUDA_VERSION_DASH:-12-9}"
CUDA_VERSION_DOT="${CUDA_VERSION_DOT:-12.9}"
CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-${CUDA_VERSION_DOT}}"
FEDORA_CUDA_REPO="${FEDORA_CUDA_REPO:-fedora42}"
ENABLE_NVIDIA_REPO=0
INSTALL_TOOLKIT=0
EXTRA_RPMBUILD_ARGS=()

usage() {
    cat <<'EOF'
Usage: scripts/build-cuda12-local.sh [options]

Options:
  --enable-nvidia-repo      Add NVIDIA CUDA network repo for Fedora.
  --install-toolkit         Install cuda-toolkit-12-9 using dnf.
  --fedora-repo NAME        NVIDIA repo distro name, e.g. fedora42.
                            Default: FEDORA_CUDA_REPO or fedora42.
  --cuda-home PATH          CUDA toolkit root. Default: /usr/local/cuda-12.9.
  --spec PATH               RPM spec path. Default: packaging/ollama-grid.spec.
  --                        Pass remaining arguments to rpmbuild.
  -h, --help                Show this help.

Examples:
  # Use an already installed CUDA 12.9 toolkit:
  scripts/build-cuda12-local.sh

  # Enable NVIDIA repo, install toolkit, then build:
  scripts/build-cuda12-local.sh --enable-nvidia-repo --install-toolkit

  # Fedora 42 repo explicitly:
  scripts/build-cuda12-local.sh --fedora-repo fedora42 --enable-nvidia-repo --install-toolkit

Environment variables:
  FEDORA_CUDA_REPO   Default NVIDIA repo distro name. Example: fedora42.
  CUDA_HOME          CUDA toolkit root. Example: /usr/local/cuda-12.9.
  SPEC_FILE          RPM spec path.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --enable-nvidia-repo)
            ENABLE_NVIDIA_REPO=1
            shift
            ;;
        --install-toolkit)
            INSTALL_TOOLKIT=1
            shift
            ;;
        --fedora-repo)
            FEDORA_CUDA_REPO="${2:?missing value for --fedora-repo}"
            shift 2
            ;;
        --cuda-home)
            CUDA_HOME="${2:?missing value for --cuda-home}"
            shift 2
            ;;
        --spec)
            SPEC_FILE="${2:?missing value for --spec}"
            shift 2
            ;;
        --)
            shift
            EXTRA_RPMBUILD_ARGS+=("$@")
            break
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing command: $1" >&2
        return 1
    fi
}

require_cmd sudo
require_cmd dnf
require_cmd rpm

if [[ ${ENABLE_NVIDIA_REPO} -eq 1 ]]; then
    echo "==> Enabling NVIDIA CUDA repository: ${FEDORA_CUDA_REPO}"
    sudo dnf -y install dnf-plugins-core
    sudo dnf config-manager --add-repo \
        "https://developer.download.nvidia.com/compute/cuda/repos/${FEDORA_CUDA_REPO}/x86_64/cuda-${FEDORA_CUDA_REPO}.repo"
fi

if [[ ${INSTALL_TOOLKIT} -eq 1 ]]; then
    echo "==> Installing CUDA Toolkit ${CUDA_VERSION_DOT}"
    sudo dnf -y install "cuda-toolkit-${CUDA_VERSION_DASH}"
fi

NVCC="${CUDA_HOME}/bin/nvcc"
if [[ ! -x "${NVCC}" ]]; then
    cat >&2 <<EOF
CUDA nvcc was not found at:
  ${NVCC}

Install CUDA Toolkit ${CUDA_VERSION_DOT}, or pass --cuda-home PATH.
For NVIDIA's Fedora network repository, try:
  $0 --enable-nvidia-repo --install-toolkit --fedora-repo ${FEDORA_CUDA_REPO}
EOF
    exit 1
fi

if [[ ! -f "${SPEC_FILE}" ]]; then
    echo "Spec file not found: ${SPEC_FILE}" >&2
    exit 1
fi

if [[ ! -f "${PROJECT_ROOT}/scripts/cuda12-math-functions.h.patch" ]]; then
    echo "Expected patch not found: scripts/cuda12-math-functions.h.patch" >&2
    exit 1
fi

if [[ ! -d "${HOME}/rpmbuild" ]]; then
    echo "==> Creating ~/rpmbuild tree"
    mkdir -p "${HOME}/rpmbuild"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
fi

echo "==> CUDA nvcc detected"
"${NVCC}" --version

echo "==> Building ollama-grid with CUDA 12.9 legacy backend"
echo "    Spec: ${SPEC_FILE}"
echo "    CUDA_HOME: ${CUDA_HOME}"

# The spec currently expects /usr/local/cuda-12.9. CUDA_HOME is validated here
# for user feedback, but the spec itself controls the exact build path.
rpmbuild -ba "${SPEC_FILE}" --with cuda12 "${EXTRA_RPMBUILD_ARGS[@]}"

echo "==> Build finished. Check ~/rpmbuild/RPMS and ~/rpmbuild/SRPMS."
