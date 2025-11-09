Name:           ollama-grid
Version:        0.12.9
Release:        1%{?dist}
Summary:        Modular Ollama packaging (CPU/Vulkan/ROCm/CUDA legacy) for Fedora/COPR
License:        Apache-2.0 AND MIT
URL:            https://github.com/ollama/ollama

# --------- SOURCE0: OLLAMAGRID (scripts + patch) ----------
Source0:         https://codeload.github.com/mwprado/ollama-grid/zip/refs/heads/main/ollama-grid-main.zip

# --------- SOURCE1: OLLAMA UPSTREAM ----------
Source1:          https://github.com/ollama/ollama/archive/refs/tags/v%{version}.tar.gz


# --------- Alternadores de backend (ative 1 por build) ----------
%bcond_without vulkan
%bcond_without rocm
%bcond_without cuda_legacy_129

# --------- Requisitos de build ----------
BuildRequires:   gcc gcc-c++ cmake make git-core golang patchelf tree
BuildRequires:   openmpi-devel
BuildRequires:   ccache

%if %{with vulkan}
BuildRequires:   pkgconfig(vulkan)
BuildRequires:   glslang
BuildRequires:   glslc
%endif

%if %{with rocm}
BuildRequires:   rocm-hip-devel
%endif

%if %{with cuda_legacy_129}
BuildRequires:   rocm-hip-devel
%endif

# --------- Destinos ----------
%global og_libdir   %{_libdir}/ollama
%global og_gobuild  go build -trimpath -buildmode=pie -ldflags "-s -w" .

%description
OllamaGrid — empacotamento modular do Ollama (Vulkan/ROCm/CUDA-12.9) com scripts/patch vindos do repositório OllamaGrid.

# ----------------- Subpackages -----------------
%package -n %{name}-common
Summary:   Arquivos comuns (binário e estrutura)
Requires(post): systemd
Requires(postun): systemd
%description -n %{name}-common
Arquivos comuns (binário /usr/bin/ollama, diretórios, sysusers e tmpfiles).

%package -n ollama-vulkan
Summary:   Ollama backend via Vulkan (universal GPU)
Requires:  %{name}-common = %{version}-%{release}
%description -n ollama-vulkan
Instala libs em %{og_libdir}/vulkan e wrapper /usr/bin/ollama-vulkan.

%package -n ollama-rocm
Summary:   Ollama backend via ROCm (AMD GPUs)
Requires:  %{name}-common = %{version}-%{release}
%description -n ollama-rocm
Instala libs em %{og_libdir}/rocm e wrapper /usr/bin/ollama-rocm.

%package -n ollama-cuda-legacy-12.9
Summary:   Ollama backend via CUDA 12.9 (NVIDIA compute 6.1 legado)
Requires:  %{name}-common = %{version}-%{release}
%description -n ollama-cuda-legacy-12.9
Instala libs em %{og_libdir}/cuda-12.9 e wrapper /usr/bin/ollama-cuda-legacy-12.9.

# ----------------- Prep -----------------
%prep
unzip %{SOURCE0}
tar -xzf %{SOURCE1}
tree

# Duplique a árvore do Ollama para cada backend
cp -a . ../ollama-0.12.9-vulkan
cp -a . ../ollama-0.12.9-rocm6
cp -a . ../ollama-0.12.9-cuda-12.9

# Copie do Source1 (ollama-grid) os SCRIPTS e o PATCH para dentro da árvore CUDA 12.9
# >>>>> AJUSTE estes caminhos se no seu repo forem diferentes! <<<<<
cp -a ollama-grid-%{gridcommit}/scripts/apply-cuda129-patch.sh  ../ollama-0.12.9-cuda-12.9/tools/
chmod +x ../ollama-0.12.9-cuda-12.9/tools/apply-cuda129-patch.sh

# ----------------- Build -----------------
%build
# Vulkan
%if %{with vulkan}
pushd ../ollama-0.12.9-vulkan
  cmake --preset "Vulkan" --fresh
  cmake --build build --preset "Vulkan" --parallel 9
popd
%endif

# ROCm
%if %{with rocm}
pushd ../ollama-0.12.9-rocm6
  cmake --preset "ROCm" --fresh -D GPU_TARGETS="gfx803;gfx1032;gfx1035"
  cmake --build build --preset "ROCm" --parallel 8
popd
%endif

# CUDA legacy 12.9 — aplica patch via script ANTES; reverte DEPOIS
%if %{with cuda_legacy_129}
pushd ../ollama-0.12.9-cuda-12.9

  # Ambiente CUDA 12.9
  export CUDAHOSTCXX=/usr/bin/g++-14
  export CPATH=/usr/include/openmpi-x86_64:$CPATH
  export PATH=$PATH:/usr/lib64/openmpi/bin
  export CC=/usr/bin/gcc-14
  export CXX=/usr/bin/g++-14
  export NVCC_CCBIN=/usr/bin/g++-14
  export CUDACXX=/usr/local/cuda-12.9/bin/nvcc

  export LD_LIBRARY_PATH=/usr/local/cuda-12.9/targets/x86_64-linux/lib:$LD_LIBRARY_PATH
  export CPATH=/usr/local/cuda-12.9/targets/x86_64-linux/include:$CPATH
  export PATH=/usr/local/cuda-12.9/bin:$PATH

  # Aplica patch (script do Source1)
  bash tools/apply-cuda129-patch.sh

  cmake --preset "CUDA 12" --fresh -D CMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
        -D CMAKE_CUDA_FLAGS=-gencode=arch=compute_61,code=compute_61
  cmake --build build --preset "CUDA 12" \
        -D CMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -gencode=arch=compute_61,code=compute_61"

  # Reverte patch (script do Source1)
  bash tools/revert-cuda129-patch.sh

popd
%endif

# Binário Go (build numa das árvores; ex.: Vulkan)
pushd ../ollama-0.12.9-vulkan
  %{og_gobuild}
popd

# ----------------- Install -----------------
%install
install -d %{buildroot}%{_bindir} %{buildroot}%{og_libdir} %{buildroot}%{_sysusersdir} %{buildroot}%{_tmpfilesdir}

# sysusers / tmpfiles
cat > %{buildroot}%{_sysusersdir}/ollama-grid.conf <<'EOF'
u ollama - "Ollama service user" - -
g ollama - - - -
EOF
cat > %{buildroot}%{_tmpfilesdir}/ollama-grid.conf <<'EOF'
d /var/lib/ollama 0750 ollama ollama -
d /var/log/ollama-grid 0750 ollama ollama -
d /run/ollama-grid 0750 ollama ollama -
EOF

# binário principal
install -m 0755 ../ollama-0.12.9-vulkan/ollama %{buildroot}%{_bindir}/ollama

# helper para limpar RUNPATH/RPATH
fix_rpath() { command -v patchelf >/dev/null 2>&1 && patchelf --remove-rpath "$1" || :; }

# Vulkan
%if %{with vulkan}
  install -d %{buildroot}%{og_libdir}/vulkan
  install -m 0755 ../ollama-0.12.9-vulkan/build/lib/ollama/libggml-vulkan.so %{buildroot}%{og_libdir}/vulkan/
  install -m 0755 ../ollama-0.12.9-vulkan/build/lib/ollama/libggml-base.so   %{buildroot}%{og_libdir}/vulkan/
  for f in %{buildroot}%{og_libdir}/vulkan/*.so; do fix_rpath "$f"; done
  cat > %{buildroot}%{_bindir}/ollama-vulkan <<'EOSH'
#!/usr/bin/env bash
export LD_LIBRARY_PATH="/usr/lib64/ollama/vulkan:${LD_LIBRARY_PATH}"
exec /usr/bin/ollama "$@"
EOSH
  chmod 0755 %{buildroot}%{_bindir}/ollama-vulkan
%endif

# ROCm
%if %{with rocm}
  install -d %{buildroot}%{og_libdir}/rocm
  install -m 0755 ../ollama-0.12.9-rocm6/build/lib/ollama/libggml-hip.so  %{buildroot}%{og_libdir}/rocm/
  install -m 0755 ../ollama-0.12.9-rocm6/build/lib/ollama/libggml-base.so %{buildroot}%{og_libdir}/rocm/
  for f in %{buildroot}%{og_libdir}/rocm/*.so; do fix_rpath "$f"; done
  cat > %{buildroot}%{_bindir}/ollama-rocm <<'EOSH'
#!/usr/bin/env bash
export LD_LIBRARY_PATH="/usr/lib64/ollama/rocm:${LD_LIBRARY_PATH}"
exec /usr/bin/ollama "$@"
EOSH
  chmod 0755 %{buildroot}%{_bindir}/ollama-rocm
%endif

# CUDA 12.9 (legacy)
%if %{with cuda_legacy_129}
  install -d %{buildroot}%{og_libdir}/cuda-12.9
  install -m 0755 ../ollama-0.12.9-cuda-12.9/build/lib/ollama/libggml-cuda.so %{buildroot}%{og_libdir}/cuda-12.9/
  install -m 0755 ../ollama-0.12.9-cuda-12.9/build/lib/ollama/libggml-base.so %{buildroot}%{og_libdir}/cuda-12.9/
  for f in %{buildroot}%{og_libdir}/cuda-12.9/*.so; do fix_rpath "$f"; done
  cat > %{buildroot}%{_bindir}/ollama-cuda-legacy-12.9 <<'EOSH'
#!/usr/bin/env bash
export LD_LIBRARY_PATH="/usr/lib64/ollama/cuda-12.9:${LD_LIBRARY_PATH}"
exec /usr/bin/ollama "$@"
EOSH
  chmod 0755 %{buildroot}%{_bindir}/ollama-cuda-legacy-12.9
%endif

# ----------------- Files -----------------
%files -n %{name}-common
%license LICENSE*
%doc README* ARCHITECTURE* ROADMAP* CONTRIBUTING*
%{_bindir}/ollama
%{_sysusersdir}/ollama-grid.conf
%{_tmpfilesdir}/ollama-grid.conf

%if %{with vulkan}
%files -n ollama-vulkan
%{_bindir}/ollama-vulkan
%dir %{og_libdir}/vulkan
%{og_libdir}/vulkan/libggml-vulkan.so
%{og_libdir}/vulkan/libggml-base.so
%endif

%if %{with rocm}
%files -n ollama-rocm
%{_bindir}/ollama-rocm
%dir %{og_libdir}/rocm
%{og_libdir}/rocm/libggml-hip.so
%{og_libdir}/rocm/libggml-base.so
%endif

%if %{with cuda_legacy_129}
%files -n ollama-cuda-legacy-12.9
%{_bindir}/ollama-cuda-legacy-12.9
%dir %{og_libdir}/cuda-12.9
%{og_libdir}/cuda-12.9/libggml-cuda.so
%{og_libdir}/cuda-12.9/libggml-base.so
%endif

# ----------------- Scriptlets -----------------
%post -n %{name}-common
%sysusers_create_compat %{_sysusersdir}/ollama-grid.conf >/dev/null 2>&1 || :
%tmpfiles_create %{_tmpfilesdir}/ollama-grid.conf >/dev/null 2>&1 || :

%changelog
* Fri Nov 07 2025 OllamaGrid <maintainers@ollamagrid.org> - 0.12.9-1
- Source0 = Ollama upstream (Forge), Source1 = ollama-grid (scripts/patch)
- Patch CUDA 12.9 aplicado via script pre-build e revertido pós-build
- Instalação explícita das .so conforme layout informado
