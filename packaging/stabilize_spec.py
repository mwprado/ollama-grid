#!/usr/bin/env python3
"""Apply conservative, idempotent cleanups to packaging/ollama-grid.spec.

This helper intentionally performs small exact substitutions instead of applying
an invasive patch to the full spec file. It is meant for local review:

    python3 packaging/stabilize_spec.py
    git diff packaging/ollama-grid.spec
    rpmbuild -ba packaging/ollama-grid.spec

The script fails only when the spec file is missing. Missing substitutions are
reported as warnings so the script remains safe to rerun after partial edits.
"""

from __future__ import annotations

from pathlib import Path

SPEC = Path("packaging/ollama-grid.spec")

REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "License:        Apache-2.0 AND MIT",
        "License:        MIT",
    ),
    (
        "URL:            https://github.com/ollama/ollama",
        "URL:            https://github.com/mwprado/ollama-grid",
    ),
    (
        "# ====== SOURCE0: OLLAMA-GRID (seus assets: scripts/patch/nginx/…) =====",
        "# ====== SOURCE0: OLLAMA-GRID (assets: scripts/patch/nginx/systemd/tmpfiles/sysusers) =====",
    ),
    (
        "# ====== SOURCE1: OLLAMA (upstream) via Forge macros ======",
        "# ====== SOURCE1: OLLAMA upstream ======",
    ),
    (
        "%global cpp_compler g++",
        "%global cpp_compiler g++",
    ),
    (
        "Instale pelo menos um backend (Vulkan/ROCm/CUDA).",
        "Instale pelo menos um backend (CPU/Vulkan/ROCm/CUDA).",
    ),
    (
        "Bibliotecas Vulkan e wrapper /usr/bin/ollama-grid-cpu.",
        "Bibliotecas CPU e wrapper /usr/bin/ollama-grid-cpu.",
    ),
    (
        "  mkdir -p %{bdir}/build\n  cmake --fresh   --preset \"CUDA 12\"",
        "  mkdir -p %{bdir}/ollama/build\n  cmake --fresh   --preset \"CUDA 12\"",
    ),
    (
        "# Licença do Ollama (Apache 2.0)",
        "# Licença do Ollama upstream; manter arquivo separado facilita auditoria da versão empacotada.",
    ),
)


def main() -> int:
    if not SPEC.exists():
        raise SystemExit(f"Spec file not found: {SPEC}")

    text = SPEC.read_text(encoding="utf-8")
    changed = False

    for old, new in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            changed = True
            print(f"applied: {old!r} -> {new!r}")
        elif new in text:
            print(f"already applied: {new!r}")
        else:
            print(f"warning: expected text not found: {old!r}")

    if changed:
        SPEC.write_text(text, encoding="utf-8")
        print(f"updated: {SPEC}")
    else:
        print("no changes needed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
