#!/usr/bin/env bash
# Apply or revert a single-file patch to NVIDIA CUDA Toolkit 12.9 files
set -euo pipefail

usage() {
  cat <<EOF
Usage:
  sudo $0 --patch /caminho/para/fix.patch --target relative/path/in/cuda [--cuda-root /usr/local/cuda-12.9] [--dry-run|--revert]
EOF
}

CUDA_ROOT="/usr/local/cuda-12.9"
PATCH_FILE=""
TARGET_REL=""
DRY_RUN=0
REVERT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --patch) PATCH_FILE="${2:-}"; shift 2 ;;
    --target) TARGET_REL="${2:-}"; shift 2 ;;
    --cuda-root) CUDA_ROOT="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --revert) REVERT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "arg desconhecido: $1"; usage; exit 2 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then echo "precisa de root"; exit 1; fi
[[ -n "$PATCH_FILE" && -f "$PATCH_FILE" ]] || { echo "patch inválido"; exit 1; }
[[ -n "$TARGET_REL" ]] || { echo "--target é obrigatório"; exit 2; }
[[ -d "$CUDA_ROOT" ]] || { echo "CUDA_ROOT não encontrado: $CUDA_ROOT"; exit 1; }

TARGET_ABS="${CUDA_ROOT%/}/${TARGET_REL#'/'}"
[[ -f "$TARGET_ABS" ]] || { echo "alvo não existe: $TARGET_ABS"; exit 1; }

P_LEVEL=0
grep -qE '^(---|\+\+\+) (a|b)/' "$PATCH_FILE" && P_LEVEL=1

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="/var/backups/cuda129_${TS}"
mkdir -p "$BACKUP_DIR"
cp -a --parents "$TARGET_ABS" "$BACKUP_DIR/"
echo "backup em: $BACKUP_DIR"

cd "$CUDA_ROOT"
CMD=(patch -p"$P_LEVEL" --verbose)
[[ $DRY_RUN -eq 1 ]] && CMD+=(--dry-run)
[[ $REVERT -eq 1 ]] && CMD+=(-R)
echo "Executando: (cd $CUDA_ROOT && ${CMD[*]} < $PATCH_FILE)"
"${CMD[@]}" < "$PATCH_FILE"

command -v restorecon >/dev/null 2>&1 && restorecon -Rv "$CUDA_ROOT" >/dev/null || true
echo "OK."
