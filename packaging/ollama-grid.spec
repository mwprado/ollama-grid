Name:           ollama-grid
Version:        0.12.9
Release:        2%{?dist}
Summary:        Meta-pacote e backends do Ollama (Vulkan/ROCm/CUDA) com balanceador Nginx
License:        Apache-2.0 AND MIT
URL:            https://github.com/ollama/ollama

# ====== SOURCE0: OLLAMA-GRID (seus assets: scripts/patch/nginx/…) =====
Source0:        https://github.com/mwprado/ollama-grid/archive/refs/heads/main.tar.gz

# ====== SOURCE1: OLLAMA (upstream) via Forge macros ======
Source1:        https://github.com/ollama/ollama/archive/refs/tags/v0.12.9.tar.gz


# ====== Seleção de backends (cada build pode habilitar 1..N) ======
%bcond_with cpu
%bcond_with vulkan
%bcond_with rocm
%bcond_with cuda
%bcond_without cuda_legacy_129

# ====== BuildRequires gerais ======
BuildRequires:    gcc gcc-c++ cmake make git-core golang patchelf tree
BuildRequires:    openmpi-devel

# Vulkan
%if %{with vulkan}
BuildRequires:    pkgconfig(vulkan)
BuildRequires:    glslang
BuildRequires:    glslc
%endif

# ROCm (ajuste conforme sua base de pacotes ROCm)
%if %{with rocm}
BuildRequires:    rocm-hip-devel
%endif

# CUDA (toolkit deve existir no host de build; não usar repositório NVIDIA no COPR)
%if %{with cuda} || %{with cuda_legacy_129}
BuildRequires:    gcc14
%endif

# ====== Caminhos de instalação ======
%global og_libdir     %{_libdir}/ollama
%global og_confdir    /etc/ollama-grid
%global og_nginx_conf /etc/nginx/conf.d/ollama-grid.conf

# Comando comum de build do binário Go (repo root do Ollama)
%global og_gobuild    go build -trimpath -buildmode=pie -ldflags "-s -w" 

%description
OllamaGrid é um conjunto de pacotes para executar o Ollama em ambientes heterogêneos
(CPU/GPU) com empacotamentos separados por backend (Vulkan/ROCm/CUDA), integração
via Nginx e orquestração por serviços systemd.

# ==================== Subpackages ====================

# (1) Common (binário e estrutura)
%package -n ollama-grid-common
Summary:        Arquivos comuns: binário do Ollama, sysusers/tmpfiles, diretórios
Requires(post): systemd
Requires(postun): systemd

%description -n ollama-grid-common
Arquivos comuns ao sistema (binário /usr/bin/ollama, usuários, diretórios, tmpfiles).

# (2) Balancer (apenas Nginx + conf)
%package -n ollama-grid-balancer
Summary:        Balanceador Nginx e integração do OllamaGrid
Requires:       ollama-grid-common = %{version}-%{release}
Recommends:     nginx
# Se quiser forçar nginx como dependência dura, troque Recommends: por Requires:
# Requires:     nginx

%description -n ollama-grid-balancer
Subpacote contendo a configuração do Nginx para o OllamaGrid e arquivos de integração.
Instale pelo menos um backend (Vulkan/ROCm/CUDA).

# (3) CPU
%package -n ollama-grid-cpu
Summary:        Backend CPU
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cpu
Bibliotecas Vulkan e wrapper /usr/bin/ollama-cpu.


# (4) Vulkan
%package -n ollama-grid-vulkan
Summary:        Backend Vulkan (universal GPU: Intel/AMD/NVIDIA)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-vulkan
Bibliotecas Vulkan e wrapper /usr/bin/ollama-vulkan.

# (5) ROCm
%package -n ollama-grid-rocm
Summary:        Backend ROCm (GPUs AMD)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-rocm
Bibliotecas ROCm (HIP) e wrapper /usr/bin/ollama-rocm.

# (6) CUDA (moderno, sempre “latest” disponível no host de build)
%package -n ollama-grid-cuda
Summary:        Backend CUDA (GPUs NVIDIA modernas)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cuda
Bibliotecas CUDA (moderno) e wrapper /usr/bin/ollama-cuda. Requer toolkit presente no host.

# (7) CUDA legacy 12.9 (ex.: Tesla P4, sm_61)
%package -n ollama-grid-cuda-legacy-12.9
Summary:        Backend CUDA 12.9 (legado) para GPUs NVIDIA compute 6.1
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cuda-legacy-12.9
Bibliotecas CUDA 12.9 (legado) e wrapper /usr/bin/ollama-cuda-legacy-12.9.
O patch é aplicado por script antes do build e revertido após o build.

# ==================== Prep ====================
%prep
# Cria raiz estável e NÃO extrai nada ainda
%setup -q -T -c -n wsp
pwd

# Pastas de trabalho
mkdir -p ./source/ollama-grid ./source/ollama ./build

# Extrai os dois tarballs achatando o topo (independe do nome interno)
tar -xzf %{SOURCE0} -C ./source/ollama-grid --strip-components=1
tar -xzf %{SOURCE1} -C ./source/ollama --strip-components=1

# Duplica a árvore do OLLAMA para cada backend dentro de build/
cp -a source/ollama source/ollama-0.12.9-cpu 
cp -a source/ollama source/ollama-0.12.9-vulkan
cp -a source/ollama source/ollama-0.12.9-rocm
cp -a source/ollama source/ollama-0.12.9-cuda
cp -a source/ollama source/ollama-0.12.9-cuda-12.9



# Copia assets do Nginx (se existirem) do Source1
# (Ajuste este caminho se seu repo usar outro layout)
mkdir -p nginx-assets
cp -a source/ollama-grid/balancer/ollama-balancer.env nginx-assets/

# ==================== Build ====================
%build

# ---- CPU ----"
echo "#---CPU---#"
%if %{with cpu}
pushd ./source/ollama-0.12.9-cpu  
cmake --preset "CPU" --fresh 
cmake --build build --parallel 8 --preset "CPU"
%{og_gobuild} -o ../../build/ollama-cpu .
popd
%endif

# ---- Vulkan ----
echo "#---Vulkan---#"
%if %{with vulkan}
  pushd ./source/ollama-0.12.9-vulkan  
  cmake --preset "Vulkan" --fresh 
  cmake --build build --parallel 8 --preset "Vulkan"
  %{og_gobuild} -o ../../build/ollama-vulkan .
  popd
%endif

# ---- ROCm ----
echo "#---ROCm---#"
%if %{with rocm}
  pushd ./source/ollama-0.12.9-rocm  
  cmake --preset "ROCm 6" --fresh -D AMDGPU_TARGETS="gfx803;gfx1032;gfx1035" -D GPU_TARGETS="gfx803;gfx1032;gfx1035"
  cmake --build build --parallel 8 --preset "ROCm 6"
  %{og_gobuild} -o ../../build/ollama-rocm .
  popd
%endif

# ---- CUDA 13 moderno (latest) — opcional; toolkit deve estar no PATH/ambiente ----
echo "#---CUDA 13---#"
%if %{with cuda}
  pushd ./source/ollama-0.12.9-cuda
  
  export CUDAHOSTCXX=/usr/bin/g++
  export CPATH=/usr/include/openmpi-x86_64:$CPATH
  export PATH=$PATH:/usr/lib64/openmpi/bin
  export CC=/usr/bin/gcc
  export CXX=/usr/bin/g++
  export NVCC_CCBIN=/usr/bin/g++
  export CUDACXX=/usr/local/cuda-13.0/bin/nvcc
  export LD_LIBRARY_PATH=/usr/local/cuda-13.0/targets/x86_64-linux/lib:$LD_LIBRARY_PATH
  export CPATH=/usr/local/cuda-13.0/targets/x86_64-linux/include:$CPATH
  export PATH=/usr/local/cuda-13.0/bin:$PATH
    
  # Se necessário, exporte CUDACXX/NVCC_CCBIN aqui para “latest”
  cmake --preset "CUDA 13" --fresh \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -fPIC" \
        -D CMAKE_CUDA_COMPILER=/usr/local/cuda-13.0/bin/nvcc
#        -D CUDA_ARCHITECTURES="12.0;9.0;8.9;8.6;8.0;7.5;7.0" 
  cmake --build build --parallel 8 --preset "CUDA 13" \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -fPIC" \
        -D CMAKE_CUDA_COMPILER=/usr/local/cuda-13.0/bin/nvcc 
#        -D CUDA_ARCHITECTURES="12.0;9.0;8.9;8.6;8.0;7.5;7.0"
  %{og_gobuild} -o ../../build/ollama-cuda .
  popd
%endif

# ---- CUDA legacy 12.9 ----
echo "#---CUDA 12---#"
%if %{with cuda_legacy_129}
  pushd ./source/ollama-0.12.9-cuda-12.9

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

  cmake --preset "CUDA 12" --fresh -D CMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -fPIC"
#        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -fPIC -gencode=arch=compute_61,code=compute_61" \ 
#        -D CUDA_ARCHITECTURES="6.1;6.0;5.2;5.0"
  cmake --build build --parallel 8 --preset "CUDA 12" \
        -D CMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -fPIC"
#        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -gencode=arch=compute_61,code=compute_61"
#        -D CUDA_ARCHITECTURES="6.1;6.0;5.2;5.0"
        
  %{og_gobuild} -o ../../build/ollama-cuda-12.9 .
  
  # Reverte patch após o build
  #if [ -x tools/revert-cuda129-patch.sh ]; then
  #  bash tools/revert-cuda129-patch.sh
  #fi

  popd
%endif

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

install -m 0644 nginx-assets/ollama-grid.conf %{buildroot}%{og_nginx_conf}

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
