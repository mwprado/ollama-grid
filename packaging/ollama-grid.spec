Name:           ollama-grid
Version:        0.13.4
Release:        11%{?dist}
Summary:        Meta-pacote e backends do Ollama (Vulkan/ROCm/CUDA) com balanceador Nginx
License:        Apache-2.0 AND MIT
URL:            https://github.com/ollama/ollama

# ====== SOURCE0: OLLAMA-GRID (seus assets: scripts/patch/nginx/…) =====
Source0:        https://github.com/mwprado/ollama-grid/archive/refs/heads/main.tar.gz

# ====== SOURCE1: OLLAMA (upstream) via Forge macros ======
Source1:        https://github.com/ollama/ollama/archive/refs/tags/v%{version}.tar.gz

# ====== Seleção de backends (cada build pode habilitar 1..N) ======
%bcond_without cpu
%bcond_without vulkan
%bcond_without rocm
%bcond_with cuda
%bcond_without cuda_12_9

# ====== Caminhos de instalação ======
%global og_libdir %{_libdir}/ollama-grid
%global og_confdir %{_sysconfdir}/ollama-grid
%global og_nginx_conf %{_sysconfdir}/nginx/conf.d/ollama-grid.conf
%global build_uuid %(uuidgen | tr -d '\n')

%global bdir %{_builddir}/%{name}-%{version}/%{build_uuid}

%global og_licensedir %{_licensedir}/ollama-grid

# Comando comum de build do binário Go (repo root do Ollama)
%global og_go_ldflag_vulkan -ldflags "-s -w -linkmode=external -extldflags '-Wl,--enable-new-dtags -Wl,-rpath,\$ORIGIN'"
%global og_go_ldflag_cuda   -ldflags "-s -w -linkmode=external -extldflags '-Wl,--enable-new-dtags -Wl,-rpath,\$ORIGIN/'"
%global og_go_ldflag_cuda12 -ldflags "-s -w -linkmode=external -extldflags '-Wl,--enable-new-dtags -Wl,-rpath,\$ORIGIN'"
%global og_go_ldflag_cpu    -ldflags "-s -w -linkmode=external -extldflags '-Wl,--enable-new-dtags -Wl,-rpath,\$ORIGIN'"
%global og_go_ldflag_rocm   -ldflags "-s -w -linkmode=external -extldflags '-Wl,--enable-new-dtags -Wl,-rpath,\$ORIGIN'"

%global og_gobuild go build -trimpath -buildmode=pie
  



# ====== BuildRequires gerais ======
BuildRequires:    gcc gcc-c++ cmake make git-core golang patchelf systemd-rpm-macros
BuildRequires:    openmpi-devel
BuildRequires:    util-linux
# Vulkan
%if %{with vulkan}
BuildRequires:    pkgconfig(vulkan)
BuildRequires:    glslang
BuildRequires:    glslc
%endif

# ROCm (ajuste conforme sua base de pacotes ROCm)
%if %{with rocm}
BuildRequires:    rocm-devel
#BuildRequires:    rocm-hip-devel hipblas-devel 
%endif

# CUDA (toolkit deve existir no host de build; não usar repositório NVIDIA no COPR)
%if %{with cuda} || %{with cuda_12_9}
BuildRequires:    gcc14-c++
BuildRequires:    gcc14
%endif

%if %{with cuda}
BuildRequires:    cuda-toolkit-13-0
%endif

%if %{with cuda_12_9}
BuildRequires:    cuda-toolkit-12-9
%endif


%description
OllamaGrid é um conjunto de pacotes para executar o Ollama em ambientes heterogêneos
(CPU/GPU) com empacotamentos separados por backend (Vulkan/ROCm/CUDA), integração
via Nginx e orquestração por serviços systemd.

# ==================== Subpackages ====================

# (1) Common (binário e estrutura)
%package -n ollama-grid-common
Requires(post): systemd
Requires(postun): systemd

Summary:        Arquivos comuns: sysusers/tmpfiles, diretórios e units systemd
%description -n ollama-grid-common
Arquivos comuns ao sistema (usuário/grupo ollama-grid, diretórios padrão, tmpfiles e template de serviço systemd).

# (2) Balancer (apenas Nginx + conf)
%package -n ollama-grid-balancer
Summary:        Balanceador Nginx e integração do OllamaGrid
Requires:       ollama-grid-common = %{version}-%{release}
Requires:     nginx

%description -n ollama-grid-balancer
Subpacote contendo a configuração do Nginx para o OllamaGrid e arquivos de integração.
Instale pelo menos um backend (Vulkan/ROCm/CUDA).

# (3) CPU
%package -n ollama-grid-cpu
Summary:        Backend CPU
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cpu
Bibliotecas Vulkan e wrapper /usr/bin/ollama-grid-cpu.

# (4) Vulkan
%if %{with vulkan}
%package -n ollama-grid-vulkan
Summary:        Backend Vulkan (universal GPU: Intel/AMD/NVIDIA)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-vulkan
Bibliotecas Vulkan e wrapper /usr/bin/ollama-grid-vulkan.
%endif

%if %{with rocm}
# (5) ROCm
%package -n ollama-grid-rocm
Summary:        Backend ROCm (GPUs AMD)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-rocm
Bibliotecas ROCm (HIP) e wrapper /usr/bin/ollama-grid-rocm.
%endif

%if %{with cuda}
# (6) CUDA (moderno, sempre “latest” disponível no host de build)
%package -n ollama-grid-cuda
Summary:        Backend CUDA (GPUs NVIDIA modernas)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cuda
Bibliotecas CUDA (moderno) e wrapper /usr/bin/ollama-grid-cuda. Requer toolkit presente no host.
%endif

%if %{with cuda_12_9}
# (7) CUDA legacy 12.9 (ex.: Tesla P4, sm_61)
%package -n ollama-grid-cuda12
Summary:        Backend CUDA 12.9 (legado) para GPUs NVIDIA compute 6.1
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cuda12
Bibliotecas CUDA 12.9 (legado) e wrapper /usr/bin/ollama-grid-cuda12.
O patch é aplicado por script antes do build e revertido após o build.
%endif

echo "# ==================== Prep ==================== #"
%prep
# Cria raiz estável e NÃO extrai nada ainda
%setup -q -T -c

# Pastas de trabalho
mkdir -p %{bdir}/ollama-grid %{bdir}/ollama 

# Extrai os dois tarballs achatando o topo (independe do nome interno)
tar -xzf %{SOURCE0} -C %{bdir}/ollama-grid --strip-components=1
tar -xzf %{SOURCE1} -C %{bdir}/ollama --strip-components=1

%if %{with cuda}
mkdir %{bdir}/cuda13_include
cp -a /usr/local/cuda-13.0/targets/x86_64-linux/include/* %{bdir}/cuda13_include/
pushd %{bdir}/cuda13_include/crt
  %if 0%{?fedora} == 43
    cp -a %{bdir}/ollama-grid/scripts/cuda13-math-functions.h.patch %{bdir}/cuda13_include/crt/
    patch -u < cuda13-math-functions.h.patch
  %elif 0%{?fedora} == 42
    cp -a %{bdir}/ollama-grid/scripts/f42-cuda12-math-functions.h.patch %{bdir}/cuda12_include/crt/                           
    patch -u < f42-cuda12-math-functions.h.patch
  %endif
popd
%endif

%if %{with cuda_12_9}
mkdir %{bdir}/cuda12_include/
cp -a /usr/local/cuda-12.9/targets/x86_64-linux/include/* %{bdir}/cuda12_include/
pushd %{bdir}/cuda12_include/crt
  %if 0%{?fedora} == 43
    cp -a %{bdir}/ollama-grid/scripts/cuda12-math-functions.h.patch %{bdir}/cuda12_include/crt/                           
    patch -u < cuda12-math-functions.h.patch
  %elif 0%{?fedora} == 42
    cp -a %{bdir}/ollama-grid/scripts/f42-cuda12-math-functions.h.patch %{bdir}/cuda12_include/crt/                           
    patch -u < f42-cuda12-math-functions.h.patch
  %endif
popd
%endif

echo "# ==================== Build =================== #"
%build

echo "#---CPU---#"
%if %{with cpu}
mkdir -p %{bdir}/build-cpu
cmake -S %{bdir}/ollama -B %{bdir}/build-cpu --fresh --preset "CPU" \
   -DCMAKE_HIP_COMPILER=NOTFOUND \
   -DCMAKE_CUDA_COMPILER=NOTFOUND \
   -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE
cmake --build %{bdir}/build-cpu --parallel %{?_smp_build_ncpus}
export CC=gcc
export CXX=g++
export CGO_ENABLED=1
export LD_LIBRARY_PATH=%{bdir}/build-cpu/lib/ollama:$LD_LIBRARY_PATH
pushd %{bdir}/ollama
  %{og_gobuild} %{og_go_ldflag_CPU} -o %{bdir}/build-cpu/ollama-grid-cpu  .
popd

%endif

echo "#---Vulkan---#"
%if %{with vulkan}
  mkdir -p %{bdir}/build-vulkan
  cmake -S %{bdir}/ollama -B %{bdir}/build-vulkan --fresh --preset "Vulkan" \
    -DCMAKE_HIP_COMPILER=NOTFOUND \
    -DCMAKE_CUDA_COMPILER=NOTFOUND
  cmake --build %{bdir}/build-vulkan --parallel %{?_smp_build_ncpus}
  export CC=gcc
  export CXX=g++
  export CGO_ENABLED=1
  export LD_LIBRARY_PATH=%{bdir}/build-vulkan/lib/ollama:$LD_LIBRARY_PATH
  pushd %{bdir}/ollama
    %{og_gobuild} %{og_go_ldflag_vulkan} -o %{bdir}/build-vulkan/ollama-grid-vulkan .
  popd
%endif

echo "#---ROCm---#"
%if %{with rocm}
  mkdir -p %{bdir}/build-rocm
  cmake -S %{bdir}/ollama -B %{bdir}/build-rocm --fresh --preset "ROCm 6" \
       -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE \
       -DCMAKE_CUDA_COMPILER=NOTFOUND \
       -DAMDGPU_TARGETS="gfx803;gfx1032;gfx1035" \
       -DGPU_TARGETS="gfx803;gfx1032;gfx1035"
  cmake --build %{bdir}/build-rocm --parallel %{?_smp_build_ncpus}
  export CC=gcc
  export CXX=g++
  export CGO_ENABLED=1
  export LD_LIBRARY_PATH=%{bdir}/build-rocm/lib/ollama:$LD_LIBRARY_PATH
  pushd %{bdir}/ollama
    %{og_gobuild} -o %{bdir}/build-rocm/ollama-grid-rocm .
  popd
%endif

echo "#---CUDA 13---#"
%if %{with cuda}
  
  mkdir -p %{bdir}/build-cuda
  cmake -S %{bdir}/ollama -B %{bdir}/build-cuda --fresh --preset "CUDA" \
    -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE \
    -DCMAKE_HIP_COMPILER=NOTFOUND \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DCMAKE_C_COMPILER=/usr/bin/gcc-14 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 \
    -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.0/bin/nvcc \
    -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-14 \
    -DCMAKE_CUDA_FLAGS="-I%{bdir}/cuda13_include -Wno-deprecated-gpu-targets -Xcompiler=-fPIC -Xcompiler=-fno-PIE" \
    -DCMAKE_CXX_FLAGS="-I%{bdir}/cuda13_include -fPIC" \
    -DCMAKE_C_FLAGS="-I%{bdir}/cuda13_include -fPIC"

  cmake --build %{bdir}/build-cuda --parallel %{?_smp_build_ncpus}
  export CC=/usr/bin/gcc-14
  export CXX=/usr/bin/g++-14
  export CGO_ENABLED=1
  export LD_LIBRARY_PATH=%{bdir}/build-cuda/lib/ollama:$LD_LIBRARY_PATH
  pushd %{bdir}/ollama
    %{og_gobuild} -o %{bdir}/build-cuda/ollama-grid-cuda .
  popd
%endif

echo "#---CUDA 12---#"
%if %{with cuda_12_9}

  mkdir -p %{bdir}/build-cuda12
  cmake -S %{bdir}/ollama -B %{bdir}/build-cuda12 --fresh --preset "CUDA 12" \
    -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE \
    -DCMAKE_HIP_COMPILER=NOTFOUND \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DCMAKE_C_COMPILER=/usr/bin/gcc-14 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 \
    -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
    -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-14 \
    -DCMAKE_CUDA_FLAGS="-I%{bdir}/cuda12_include -Wno-deprecated-gpu-targets -Xcompiler=-fPIC -Xcompiler=-fno-PIE" \
    -DCMAKE_CXX_FLAGS="-I%{bdir}/cuda12_include -fPIC" \
    -DCMAKE_C_FLAGS="-I%{bdir}/cuda12_include -fPIC"
  cmake --build %{bdir}/build-cuda12 --parallel %{?_smp_build_ncpus}
  export CC=/usr/bin/gcc-14
  export CXX=/usr/bin/g++-14
  export CGO_ENABLED=1
  export LD_LIBRARY_PATH=%{bdir}/build-cuda12/lib/ollama:$LD_LIBRARY_PATH
  pushd %{bdir}/ollama
    %{og_gobuild} -o %{bdir}/build-cuda12/ollama-grid-cuda12 .
  popd
%endif

echo "# ==================== Install ==================== #"
%install
rm -rf %{buildroot}

# --- diretórios base ---
install -d \
  %{buildroot}%{_bindir} \
  %{buildroot}%{_sysusersdir} \
  %{buildroot}%{_tmpfilesdir} \
  %{buildroot}%{_unitdir} \
  %{buildroot}%{og_confdir} \
  %{buildroot}%{og_licensedir} \
  %{buildroot}%{_sysconfdir}/nginx/conf.d \
  %{buildroot}%{_libexecdir}/ollama-grid/cpu \
  %{buildroot}%{_libexecdir}/ollama-grid/vulkan \
  %{buildroot}%{_libexecdir}/ollama-grid/rocm \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda12
  
# --- sysusers / tmpfiles (arquivos do repositório) ---
install -m 0644 %{bdir}/ollama-grid/sysusers.d/ollama-grid.conf %{buildroot}%{_sysusersdir}/ollama-grid.conf
install -m 0644 %{bdir}/ollama-grid/tmpfiles.d/ollama-grid.conf %{buildroot}%{_tmpfilesdir}/ollama-grid.conf
install -Dpm644 %{bdir}/ollama-grid/systemd/ollama-grid@.service %{buildroot}%{_unitdir}/ollama-grid@.service
install -Dpm644 %{bdir}/ollama-grid/systemd/ollama-grid-balancer.service %{buildroot}%{_unitdir}/ollama-grid-balancer.service

# Licença do Ollama (Apache 2.0)
install -m 0644 %{bdir}/ollama/LICENSE \
    %{buildroot}%{og_licensedir}/LICENSE.ollama

# Licença do ollama-grid (MIT)
install -m 0644 %{bdir}/ollama-grid/LICENSE \
    %{buildroot}%{og_licensedir}/LICENSE.ollama-grid

# pais (base package vai "possuir")
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid


# CPU (sempre)
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cpu
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cpu
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/cpu.conf    %{buildroot}%{og_confdir}/cpu.conf

# Vulkan
%if %{with vulkan}
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/vulkan
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/vulkan
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/vulkan.conf    %{buildroot}%{og_confdir}/vulkan.conf
%endif

# ROCm
%if %{with rocm}
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/rocm
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/rocm
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/rocm.conf    %{buildroot}%{og_confdir}/rocm.conf
%endif

# CUDA (atual)
%if %{with cuda}
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cuda
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cuda
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/cuda.conf    %{buildroot}%{og_confdir}/cuda.conf
%endif

# CUDA 12.9 (legacy)
%if %{with cuda_12_9}
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cuda12
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cuda12
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/cuda12.conf    %{buildroot}%{og_confdir}/cuda12.conf
%endif

# --- utilitário para limpar RPATH/RUNPATH (ignora se patchelf não existir) ---
fix_rpath() { command -v patchelf >/dev/null 2>&1 && patchelf --remove-rpath "$1" || :; }

# ============================
# BINÁRIOS (um por backend)
# ============================

# CPU (sempre) — publica como /usr/bin/ollama-grid-cpu
install -m 0755 %{bdir}/build-cpu/ollama-grid-cpu %{buildroot}%{_libexecdir}/ollama-grid/cpu/ollama-grid-cpu

# Vulkan
%if %{with vulkan}
  install -m 0755 %{bdir}/build-vulkan/ollama-grid-vulkan %{buildroot}%{_libexecdir}/ollama-grid/vulkan/ollama-grid-vulkan
%endif

# ROCm
%if %{with rocm}
  install -m 0755 %{bdir}/build-rocm/ollama-grid-rocm %{buildroot}%{_libexecdir}/ollama-grid/rocm/ollama-grid-rocm
%endif

# CUDA (atual)
%if %{with cuda}
  install -m 0755 %{bdir}/build-cuda/ollama-grid-cuda %{buildroot}%{_libexecdir}/ollama-grid/cuda/ollama-grid-cuda
%endif

# CUDA 12.9 (legacy)
%if %{with cuda_12_9}
  install -m 0755 %{bdir}/build-cuda12/ollama-grid-cuda12 %{buildroot}%{_libexecdir}/ollama-grid/cuda12/ollama-grid-cuda12
%endif

# ============================
# BIBLIOTECAS (instaladas por backend)
# ============================

%if %{with cpu}
  install -d %{buildroot}%{_libexecdir}/ollama-grid/cpu

  # base + variantes CPU
  install -m 0755 %{bdir}/build-cpu/lib/ollama/libggml-base.so %{buildroot}%{_libexecdir}/ollama-grid/cpu/
  install -m 0755 %{bdir}/build-cpu/lib/ollama/libggml-cpu-*.so %{buildroot}%{_libexecdir}/ollama-grid/cpu/

  for f in %{buildroot}%{_libexecdir}/ollama-grid/cpu/*.so; do fix_rpath "$f"; done
  
  ln -sr %{_libexecdir}/ollama-grid/cpu/ollama-grid-cpu \
  %{buildroot}%{_bindir}/ollama-grid-cpu
  
%endif

# Vulkan
%if %{with vulkan}
  install -d %{buildroot}%{_libexecdir}/ollama-grid/vulkan
  install -m 0755 %{bdir}/build-vulkan/lib/ollama/libggml-*.so %{buildroot}%{_libexecdir}/ollama-grid/vulkan/
  for f in %{buildroot}%{_libexecdir}/ollama-grid/vulkan/*.so; do fix_rpath "$f"; done
  
  ln -sr %{_libexecdir}/ollama-grid/vulkan/ollama-grid-vulkan \
  %{buildroot}%{_bindir}/ollama-grid-vulkan
%endif

# ROCm
%if %{with rocm}
  install -d %{buildroot}%{_libexecdir}/ollama-grid/rocm
  install -m 0755 %{bdir}/build-rocm/lib/ollama/libggml-*.so  %{buildroot}%{_libexecdir}/ollama-grid/rocm/
  for f in %{buildroot}%{_libexecdir}/ollama-grid/rocm/*.so; do fix_rpath "$f"; done
  
  ln -sr %{_libexecdir}/ollama-grid/rocm/ollama-grid-rocm \
  %{buildroot}%{_bindir}/ollama-grid-rocm
%endif

# CUDA (atual)
%if %{with cuda}
  install -d %{buildroot}%{_libexecdir}/ollama-grid/cuda
  install -m 0755 %{bdir}/build-cuda/lib/ollama/libggml-*.so %{buildroot}%{_libexecdir}/ollama-grid/cuda/
  for f in %{buildroot}%{_libexecdir}/ollama-grid/cuda/*.so; do fix_rpath "$f"; done
  
  ln -sr %{_libexecdir}/ollama-grid/cuda/ollama-grid-cuda \
  %{buildroot}%{_bindir}/ollama-grid-cuda
%endif

# CUDA 12.9 (legacy)
%if %{with cuda_12_9}
  install -d %{buildroot}%{_libexecdir}/ollama-grid/cuda12
  install -m 0755 %{bdir}/build-cuda12/lib/ollama/libggml-*.so %{buildroot}%{_libexecdir}/ollama-grid/cuda12/
  for f in %{buildroot}%{_libexecdir}/ollama-grid/cuda12/*.so; do fix_rpath "$f"; done
  
  ln -sr %{_libexecdir}/ollama-grid/cuda12/ollama-grid-cuda12 \
  %{buildroot}%{_bindir}/ollama-grid-cuda12
%endif

# ============================
# NGINX (balanceador)
# ============================
install -m 0644 %{bdir}/ollama-grid/nginx/ollama-grid.conf \
  %{buildroot}%{_sysconfdir}/nginx/conf.d/ollama-grid.conf

# ==================== Files ====================

# ============================
# Subpacote: COMMON
# ============================

%files -n ollama-grid-common

%dir %{og_licensedir}
%license %{og_licensedir}/LICENSE.ollama
%license %{og_licensedir}/LICENSE.ollama-grid

%dir %{og_confdir}
# sysusers / tmpfiles
%config(noreplace) %{_sysusersdir}/ollama-grid.conf
%config(noreplace) %{_tmpfilesdir}/ollama-grid.conf
%{_unitdir}/ollama-grid@.service

# ============================
# Subpacote: BALANCER (Nginx)
# ============================
%files -n ollama-grid-balancer
# arquivo de configuração do Nginx
%config(noreplace) %{_sysconfdir}/nginx/conf.d/ollama-grid.conf
%{_unitdir}/ollama-grid-balancer.service

# ============================
# Subpacote: CPU
# ============================
%files -n ollama-grid-cpu 
# binário

%{_bindir}/ollama-grid-cpu
%{_libexecdir}/ollama-grid/cpu/ollama-grid-cpu
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cpu.conf

# libs do backend
%dir %dir %{_libexecdir}/ollama-grid/cpu
%{_libexecdir}/ollama-grid/cpu/*.so

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cpu
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cpu

# ============================
# Subpacote: Vulkan
# ============================
%if %{with vulkan}
%files -n ollama-grid-vulkan

# binário do backend
%{_bindir}/ollama-grid-vulkan
%{_libexecdir}/ollama-grid/vulkan/ollama-grid-vulkan
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/vulkan.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/vulkan
%{_libexecdir}/ollama-grid/vulkan/*.so

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/vulkan
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/vulkan

%endif

# ============================
# Subpacote: ROCm
# ============================
%if %{with rocm}
%files -n ollama-grid-rocm

# binário do backend
%{_bindir}/ollama-grid-rocm
%{_libexecdir}/ollama-grid/rocm/ollama-grid-rocm
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/rocm.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/rocm
%{_libexecdir}/ollama-grid/rocm/*.so

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/rocm
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/rocm

%endif

# ============================
# Subpacote: CUDA (atual)
# ============================

%if %{with cuda}

%files -n ollama-grid-cuda

# binário do backend
%{_bindir}/ollama-grid-cuda
%{_libexecdir}/ollama-grid/cuda/ollama-grid-cuda
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cuda.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/cuda
%{_libexecdir}/ollama-grid/cuda/*.so

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cuda
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cuda

%endif

# ============================
# Subpacote: CUDA 12.9 (legacy)
# ============================

%if %{with cuda_12_9}

%files -n ollama-grid-cuda12

# binário do backend
%{_bindir}/ollama-grid-cuda12
%{_libexecdir}/ollama-grid/cuda12/ollama-grid-cuda12

%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cuda12.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/cuda12
%{_libexecdir}/ollama-grid/cuda12/*.so

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cuda12
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cuda12

%endif

# ---- Common ----

%post -n ollama-grid-common
ldconfig
# cria usuário, diretórios persistentes e temporários
%sysusers_create_compat %{_sysusersdir}/ollama-grid.conf || :
%tmpfiles_create %{_tmpfilesdir}/ollama-grid.conf || :

# registra o TEMPLATE no systemd
%systemd_post ollama-grid@.service

%preun -n ollama-grid-common
%systemd_preun ollama-grid@.service

%postun -n ollama-grid-common
%systemd_postun_with_restart ollama-grid@.service

# ---- Balancer ----

%post -n ollama-grid-balancer
ldconfig
if [ $1 -eq 1 ] ; then
    systemctl enable --now ollama-grid-balancer.service >/dev/null 2>&1 || :
else
    systemctl try-restart ollama-grid-balancer.service >/dev/null 2>&1 || :
fi

%preun -n ollama-grid-balancer
if [ $1 -eq 0 ] ; then
    systemctl disable --now ollama-grid-balancer.service >/dev/null 2>&1 || :
fi
# ---- CPU ----

%if %{with cpu}
%post -n ollama-grid-cpu
ldconfig
if [ $1 -eq 1 ] ; then
    # instalação nova → cria e inicia a instância CPU
    systemctl enable --now ollama-grid@cpu.service >/dev/null 2>&1 || :
else
    # upgrade → tenta reiniciar a instância se existir
    systemctl try-restart ollama-grid@cpu.service >/dev/null 2>&1 || :
fi

%preun -n ollama-grid-cpu
if [ $1 -eq 0 ] ; then
    # remoção → desativa e para a instância
    systemctl disable --now ollama-grid@cpu.service >/dev/null 2>&1 || :
fi
%endif

# ---- cuda ----
%if %{with cuda}
%post -n ollama-grid-cuda
ldconfig
if [ $1 -eq 1 ] ; then
    systemctl enable --now ollama-grid@cuda.service >/dev/null 2>&1 || :
else
    systemctl try-restart ollama-grid@cuda.service >/dev/null 2>&1 || :
fi
%preun -n ollama-grid-cuda
if [ $1 -eq 0 ] ; then
    systemctl disable --now ollama-grid@cuda.service >/dev/null 2>&1 || :
fi
%endif

# ---- cuda-12.9 ----
%if %{with cuda_12_9}
%post -n ollama-grid-cuda12
ldconfig
if [ $1 -eq 1 ] ; then
    systemctl enable --now ollama-grid@cuda12.service >/dev/null 2>&1 || :
else
    systemctl try-restart ollama-grid@cuda12.service >/dev/null 2>&1 || :
fi
%preun -n ollama-grid-cuda12
if [ $1 -eq 0 ] ; then
    systemctl disable --now ollama-grid@cuda12.service >/dev/null 2>&1 || :
fi
%endif

# ---- ROCm ----
%if %{with rocm}
%post -n ollama-grid-rocm
ldconfig
if [ $1 -eq 1 ] ; then
    systemctl enable --now ollama-grid@rocm.service >/dev/null 2>&1 || :
else
    systemctl try-restart ollama-grid@rocm.service >/dev/null 2>&1 || :
fi

%preun -n ollama-grid-rocm
if [ $1 -eq 0 ] ; then
    systemctl disable --now ollama-grid@rocm.service >/dev/null 2>&1 || :
fi
%endif

# ---- Vulkan ----
%if %{with vulkan}
%post -n ollama-grid-vulkan
ldconfig
if [ $1 -eq 1 ] ; then
    systemctl enable --now ollama-grid@vulkan.service >/dev/null 2>&1 || :
else
    systemctl try-restart ollama-grid@vulkan.service >/dev/null 2>&1 || :
fi

%preun -n ollama-grid-vulkan
if [ $1 -eq 0 ] ; then
    systemctl disable --now ollama-grid@vulkan.service >/dev/null 2>&1 || :
fi
%endif

# ==================== Scriptlets ====================
%changelog
* Wed Nov 19 2025 Moacyr Prado <seuemail@exemplo> - 0.12.11-12
- Refatoração do spec para múltiplos backends (CPU/Vulkan/ROCm/CUDA/CUDA-12.9)
- Integração com sysusers/tmpfiles e serviços systemd (template + backends + balancer)

* Sat Nov 08 2025 OllamaGrid <maintainers@ollamagrid.org> - 0.12.9-1
- Estrutura meta (ollama-grid) + common + backends (vulkan/rocm/cuda/cuda-12.9)
- Source0 = Ollama upstream; Source1 = ollama-grid (scripts/patch/nginx)
- CUDA 12.9: patch aplicado por script antes do build e revertido após o build
- Instalação explícita das .so conforme caminhos reais dos builds
