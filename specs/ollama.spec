Name:           ollama-grid
Version:        0.12.9
Release:        1%{?dist}
Summary:        Meta-pacote e backends do Ollama (Vulkan/ROCm/CUDA) com balanceador Nginx
License:        Apache-2.0 AND MIT
URL:            https://github.com/ollama/ollama

# ====== SOURCE0: OLLAMA (upstream) via Forge macros ======
%global forgeurl  https://github.com/ollama/ollama
%global commit    v%{version}
%forgemeta
Source0:         %{forgesource}

# ====== SOURCE1: OLLAMA-GRID (seus assets: scripts/patch/nginx/…) ======
# Ajuste gridcommit para um commit/tag do seu repo de empacotamento
%global gridurl    https://github.com/mwprado/ollama-grid
%global gridcommit main
Source1:          %{gridurl}/archive/%{gridcommit}/ollama-grid-%{gridcommit}.tar.gz

# ====== Seleção de backends (cada build pode habilitar 1..N) ======
%bcond_without vulkan
%bcond_without rocm
%bcond_without cuda
%bcond_without cuda_legacy_129

# ====== BuildRequires gerais ======
BuildRequires:    gcc gcc-c++ cmake make git-core golang patchelf
BuildRequires:    openmpi-devel

# Vulkan
%if %{with vulkan}
BuildRequires:    pkgconfig(vulkan)
BuildRequires:    glslang
BuildRequires:    glslc
%endif

# ROCm (ajuste conforme sua base de pacotes ROCm)
%if %{with rocm}
BuildRequires:    rocm-hip-runtime
BuildRequires:    rocm-cmake
BuildRequires:    hipblas
%endif

# CUDA (toolkit deve existir no host de build; não usar repositório NVIDIA no COPR)
%if %{with cuda} || %{with cuda_legacy_129}
BuildRequires:    which
%endif

# ====== Caminhos de instalação ======
%global og_libdir     %{_libdir}/ollama
%global og_confdir    /etc/ollama-grid
%global og_nginx_conf /etc/nginx/conf.d/ollama-grid.conf

# Comando comum de build do binário Go (repo root do Ollama)
%global og_gobuild    go build -trimpath -buildmode=pie -ldflags "-s -w" .

%description
OllamaGrid é um conjunto de pacotes para executar o Ollama em ambientes heterogêneos
(CPU/GPU) com empacotamentos separados por backend (Vulkan/ROCm/CUDA), integração
via Nginx e orquestração por serviços systemd.

# ==================== Subpackages ====================

# (1) Meta-pacote / balancer
%package -n ollama-grid
Summary:        Meta-pacote e balanceador Nginx para OllamaGrid
Requires:       ollama-grid-common = %{version}-%{release}
Recommends:     nginx
# Sugerimos pelo menos um backend; admin escolhe conforme hardware
Recommends:     ollama-grid-vulkan
%description -n ollama-grid
Meta-pacote do OllamaGrid que instala a configuração do Nginx e arquivos de integração.
Recomenda-se instalar ao menos um backend (Vulkan/ROCm/CUDA).

# (2) Common (binário e estrutura)
%package -n ollama-grid-common
Summary:        Arquivos comuns: binário do Ollama, sysusers/tmpfiles, diretórios
Requires(post): systemd
Requires(postun): systemd
%description -n ollama-grid-common
Arquivos comuns ao sistema (binário /usr/bin/ollama, usuários, diretórios, tmpfiles).

# (3) Vulkan
%package -n ollama-grid-vulkan
Summary:        Backend Vulkan (universal GPU: Intel/AMD/NVIDIA)
Requires:       ollama-grid-common = %{version}-%{release}
%description -n ollama-grid-vulkan
Bibliotecas Vulkan e wrapper /usr/bin/ollama-vulkan.

# (4) ROCm
%package -n ollama-grid-rocm
Summary:        Backend ROCm (GPUs AMD)
Requires:       ollama-grid-common = %{version}-%{release}
%description -n ollama-grid-rocm
Bibliotecas ROCm (HIP) e wrapper /usr/bin/ollama-rocm.

# (5) CUDA (moderno, sempre “latest” disponível no host de build)
%package -n ollama-grid-cuda
Summary:        Backend CUDA (GPUs NVIDIA modernas)
Requires:       ollama-grid-common = %{version}-%{release}
%description -n ollama-grid-cuda
Bibliotecas CUDA (moderno) e wrapper /usr/bin/ollama-cuda. Requer toolkit presente no host.

# (6) CUDA legacy 12.9 (ex.: Tesla P4, sm_61)
%package -n ollama-grid-cuda-legacy-12.9
Summary:        Backend CUDA 12.9 (legado) para GPUs NVIDIA compute 6.1
Requires:       ollama-grid-common = %{version}-%{release}
%description -n ollama-grid-cuda-legacy-12.9
Bibliotecas CUDA 12.9 (legado) e wrapper /usr/bin/ollama-cuda-legacy-12.9.
O patch é aplicado por script antes do build e revertido após o build.

# ==================== Prep ====================
%prep
# Source0: Ollama upstream
%forgesetup

# Source1: ollama-grid (assets) em ./ollama-grid-%{gridcommit}
%setup -q -T -D -a 1

# Duplica a árvore do Ollama para cada backend
cp -a . ../ollama-0.12.9-vulkan
cp -a . ../ollama-0.12.9-rocm6
cp -a . ../ollama-0.12.9-cuda-latest
cp -a . ../ollama-0.12.9-cuda-12.9

# Copia assets do Nginx (se existirem) do Source1
# (Ajuste este caminho se seu repo usar outro layout)
if [ -f ollama-grid-%{gridcommit}/packaging/nginx/ollama-grid.conf ]; then
  mkdir -p nginx-assets
  cp -a ollama-grid-%{gridcommit}/packaging/nginx/ollama-grid.conf nginx-assets/
fi

# Scripts/patch do CUDA 12.9: apply/revert/patch
if [ -d ../ollama-0.12.9-cuda-12.9 ]; then
  install -d ../ollama-0.12.9-cuda-12.9/tools
  # caminhos conforme você informou: scripts/apply-*.sh
  if [ -f ollama-grid-%{gridcommit}/scripts/apply-cuda129-patch.sh ]; then
    cp -a ollama-grid-%{gridcommit}/scripts/apply-cuda129-patch.sh ../ollama-0.12.9-cuda-12.9/tools/
  fi
  if [ -f ollama-grid-%{gridcommit}/scripts/revert-cuda129-patch.sh ]; then
    cp -a ollama-grid-%{gridcommit}/scripts/revert-cuda129-patch.sh ../ollama-0.12.9-cuda-12.9/tools/
  fi
  # patch preferencialmente em patches/, fallback em scripts/
  if [ -f ollama-grid-%{gridcommit}/patches/cuda129.patch ]; then
    cp -a ollama-grid-%{gridcommit}/patches/cuda129.patch ../ollama-0.12.9-cuda-12.9/tools/
  elif [ -f ollama-grid-%{gridcommit}/scripts/cuda129.patch ]; then
    cp -a ollama-grid-%{gridcommit}/scripts/cuda129.patch ../ollama-0.12.9-cuda-12.9/tools/
  fi
  chmod +x ../ollama-0.12.9-cuda-12.9/tools/*.sh 2>/dev/null || :
fi

# ==================== Build ====================
%build
# ---- Vulkan ----
%if %{with vulkan}
pushd ../ollama-0.12.9-vulkan
  cmake --preset "Vulkan" --fresh
  cmake --build build --preset "Vulkan" --parallel 9
popd
%endif

# ---- ROCm ----
%if %{with rocm}
pushd ../ollama-0.12.9-rocm6
  cmake --preset "ROCm" --fresh -D GPU_TARGETS="gfx803;gfx1032;gfx1035"
  cmake --build build --preset "ROCm" --parallel 8
popd
%endif

# ---- CUDA moderno (latest) — opcional; toolkit deve estar no PATH/ambiente ----
%if %{with cuda}
pushd ../ollama-0.12.9-cuda-latest
  # Se necessário, exporte CUDACXX/NVCC_CCBIN aqui para “latest”
  cmake --preset "CUDA" --fresh
  cmake --build build --preset "CUDA"
popd
%endif

# ---- CUDA legacy 12.9 — aplica patch ANTES; reverte DEPOIS ----
%if %{with cuda_legacy_129}
pushd ../ollama-0.12.9-cuda-12.9

  # Ambiente CUDA 12.9 (conforme você definiu)
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

  # Aplica patch via script (do Source1)
  if [ -x tools/apply-cuda129-patch.sh ]; then
    bash tools/apply-cuda129-patch.sh
  fi

  cmake --preset "CUDA 12" --fresh -D CMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
        -D CMAKE_CUDA_FLAGS=-gencode=arch=compute_61,code=compute_61
  cmake --build build --preset "CUDA 12" \
        -D CMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -gencode=arch=compute_61,code=compute_61"

  # Reverte patch após o build
  if [ -x tools/revert-cuda129-patch.sh ]; then
    bash tools/revert-cuda129-patch.sh
  fi

popd
%endif

# ---- Binário Go (compila uma única vez; uso a árvore Vulkan por conveniência) ----
pushd ../ollama-0.12.9-vulkan
  %{og_gobuild}
popd

# ==================== Install ====================
%install
install -d %{buildroot}%{_bindir} %{buildroot}%{og_libdir} %{buildroot}%{_sysusersdir} %{buildroot}%{_tmpfilesdir}
install -d %{buildroot}%{og_confdir}

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

# Binário principal
install -m 0755 ../ollama-0.12.9-vulkan/ollama %{buildroot}%{_bindir}/ollama

# Helper para limpar RUNPATH/RPATH
fix_rpath() { command -v patchelf >/dev/null 2>&1 && patchelf --remove-rpath "$1" || :; }

# ---- Vulkan (.so + wrapper) ----
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

# ---- ROCm (.so + wrapper) ----
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

# ---- CUDA moderno (.so + wrapper) ----
%if %{with cuda}
  install -d %{buildroot}%{og_libdir}/cuda
  # Ajuste os nomes/caminhos caso seu preset "CUDA" gere arquivos diferentes
  if [ -f ../ollama-0.12.9-cuda-latest/build/lib/ollama/libggml-cuda.so ]; then
    install -m 0755 ../ollama-0.12.9-cuda-latest/build/lib/ollama/libggml-cuda.so %{buildroot}%{og_libdir}/cuda/
  fi
  if [ -f ../ollama-0.12.9-cuda-latest/build/lib/ollama/libggml-base.so ]; then
    install -m 0755 ../ollama-0.12.9-cuda-latest/build/lib/ollama/libggml-base.so %{buildroot}%{og_libdir}/cuda/
  fi
  for f in %{buildroot}%{og_libdir}/cuda/*.so 2>/dev/null; do test -e "$f" && fix_rpath "$f"; done
  cat > %{buildroot}%{_bindir}/ollama-cuda <<'EOSH'
#!/usr/bin/env bash
export LD_LIBRARY_PATH="/usr/lib64/ollama/cuda:${LD_LIBRARY_PATH}"
exec /usr/bin/ollama "$@"
EOSH
  chmod 0755 %{buildroot}%{_bindir}/ollama-cuda
%endif

# ---- CUDA 12.9 legacy (.so + wrapper) ----
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

# ---- Nginx (meta) ----
# Instala conf padrão se veio no Source1; senão gera uma básica
install -d %{buildroot}%{_sysconfdir}/nginx/conf.d
if [ -f nginx-assets/ollama-grid.conf ]; then
  install -m 0644 nginx-assets/ollama-grid.conf %{buildroot}%{og_nginx_conf}
else
  # fallback mínimo
  cat > %{buildroot}%{og_nginx_conf} <<'NGX'
upstream ollama_nodes {
    server 127.0.0.1:11434; # CPU
    server 127.0.0.1:11435; # Vulkan
    server 127.0.0.1:11436; # ROCm
    server 127.0.0.1:11437; # CUDA
}
server {
    listen 8080;
    location / { proxy_pass http://ollama_nodes; proxy_buffering off; proxy_read_timeout 1h; proxy_send_timeout 1h; }
    location = /health { return 200 "ok\n"; }
}
NGX
fi

# ==================== Files ====================
# (1) Meta (balanceador)
%files -n ollama-grid
%license LICENSE*
%doc README* ARCHITECTURE* ROADMAP* CONTRIBUTING*
%config(noreplace) %{og_nginx_conf}
%dir %{og_confdir}

# (2) Common
%files -n ollama-grid-common
%{_bindir}/ollama
%{_sysusersdir}/ollama-grid.conf
%{_tmpfilesdir}/ollama-grid.conf

# (3) Vulkan
%if %{with vulkan}
%files -n ollama-grid-vulkan
%{_bindir}/ollama-vulkan
%dir %{og_libdir}/vulkan
%{og_libdir}/vulkan/libggml-vulkan.so
%{og_libdir}/vulkan/libggml-base.so
%endif

# (4) ROCm
%if %{with rocm}
%files -n ollama-grid-rocm
%{_bindir}/ollama-rocm
%dir %{og_libdir}/rocm
%{og_libdir}/rocm/libggml-hip.so
%{og_libdir}/rocm/libggml-base.so
%endif

# (5) CUDA (latest)
%if %{with cuda}
%files -n ollama-grid-cuda
%{_bindir}/ollama-cuda
%dir %{og_libdir}/cuda
%{og_libdir}/cuda/libggml-cuda.so
%{og_libdir}/cuda/libggml-base.so
%endif

# (6) CUDA 12.9 legacy
%if %{with cuda_legacy_129}
%files -n ollama-grid-cuda-legacy-12.9
%{_bindir}/ollama-cuda-legacy-12.9
%dir %{og_libdir}/cuda-12.9
%{og_libdir}/cuda-12.9/libggml-cuda.so
%{og_libdir}/cuda-12.9/libggml-base.so
%endif

# ==================== Scriptlets ====================
%post -n ollama-grid-common
%sysusers_create_compat %{_sysusersdir}/ollama-grid.conf >/dev/null 2>&1 || :
%tmpfiles_create %{_tmpfilesdir}/ollama-grid.conf >/dev/null 2>&1 || :

%changelog
* Sat Nov 08 2025 OllamaGrid <maintainers@ollamagrid.org> - 0.12.9-1
- Estrutura meta (ollama-grid) + common + backends (vulkan/rocm/cuda/cuda-12.9)
- Source0 = Ollama upstream; Source1 = ollama-grid (scripts/patch/nginx)
- CUDA 12.9: patch aplicado por script antes do build e revertido após o build
- Instalação explícita das .so conforme caminhos reais dos builds
