Name:           ollama-grid
Version:        0.33.3
Release:        1%{?dist}
Summary:        Meta-pacote e backends do Ollama (Vulkan/ROCm/CUDA) com balanceador Nginx
License:        MIT
URL:            https://github.com/mwprado/ollama-grid

# ====== SOURCE0: OLLAMA-GRID (assets: scripts/patch/nginx/systemd/tmpfiles/sysusers) =====
Source0:        https://github.com/mwprado/ollama-grid/archive/refs/heads/main.tar.gz

# ====== SOURCE1: OLLAMA upstream ======
Source1:        https://github.com/ollama/ollama/archive/refs/tags/v%{version}.tar.gz

# ====== Seleção de backends (cada build pode habilitar 1..N) ======
%bcond_without cpu
%bcond_without vulkan

%if 0%{?rhel} == 9
%bcond_with rocm
%else
%bcond_without rocm
%endif

%if 0%{?rhel} == 9
%bcond_without cuda12
%else
%bcond_with cuda12
%endif

%bcond_without cuda

# ====== Caminhos de instalação ======

%global _debugsource_packages 0
%global debug_package %{nil}

%global og_libdir %{_libdir}/ollama-grid
%global og_confdir %{_sysconfdir}/ollama-grid
%global og_nginx_conf %{_sysconfdir}/nginx/conf.d/ollama-grid.conf
%global build_uuid %(uuidgen | tr -d '\n')

%global bdir %{_builddir}/%{name}-%{version}/%{build_uuid}

%global og_licensedir %{_licensedir}/ollama-grid

# Comando comum de build do binário Go (repo root do Ollama)
%global og_go_ldflag_vulkan %{nil}
%global og_go_ldflag_cuda   %{nil}
%global og_go_ldflag_cuda12 %{nil} 
%global og_go_ldflag_cpu    %{nil} 
%global og_go_ldflag_rocm   %{nil} 

%global og_gobuild go build -trimpath -buildmode=pie


%global c_compiler gcc
%global cpp_compiler g++

%if 0%{?rhel} == 9
%global cuda_cc  /opt/rh/gcc-toolset-14/root/usr/bin/gcc
%global cuda_cxx /opt/rh/gcc-toolset-14/root/usr/bin/g++
%else
%global cuda_cc  /usr/bin/gcc-14
%global cuda_cxx /usr/bin/g++-14
%endif

%if 0%{?rhel} == 9
%global og_cpu_compat -DGGML_CPU_ALL_VARIANTS=OFF
%else
%global og_cpu_compat %{nil}
%endif
  
# ====== BuildRequires gerais ======
BuildRequires:    gcc gcc-c++ cmake make git-core golang patchelf systemd-rpm-macros
BuildRequires:    openmpi-devel
BuildRequires:    util-linux
# Vulkan
%if %{with vulkan}
BuildRequires:    pkgconfig(vulkan)
BuildRequires:    glslang
BuildRequires:    glslc
BuildRequires:    cmake(SPIRV-Headers)
%endif

# ROCm (ajuste conforme sua base de pacotes ROCm)
%if %{with rocm} && "%{_arch}" == "x86_64"
BuildRequires:    rocm-devel
#BuildRequires:    rocm-hip-devel hipblas-devel 
%endif

# CUDA (toolkit deve existir no host de build; não usar repositório NVIDIA no COPR)
%if %{with cuda} || %{with cuda12}
%if 0%{?rhel} == 9
BuildRequires: gcc-toolset-14-gcc
BuildRequires: gcc-toolset-14-gcc-c++
%else
BuildRequires: gcc14
%endif
%endif

%if %{with cuda}
BuildRequires:    cuda-toolkit-13-0
%endif

%if %{with cuda12}
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
Instale pelo menos um backend (CPU/Vulkan/ROCm/CUDA).

# (3) CPU
%package -n ollama-grid-cpu
Summary:        Backend CPU
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cpu
Bibliotecas CPU e wrapper /usr/bin/ollama-grid-cpu.

# (4) Vulkan
%if %{with vulkan}
%package -n ollama-grid-vulkan
Summary:        Backend Vulkan (universal GPU: Intel/AMD/NVIDIA)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-vulkan
Bibliotecas Vulkan e wrapper /usr/bin/ollama-grid-vulkan.
%endif

%if %{with rocm} && "%{_arch}" == "x86_64"
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

%if %{with cuda12}
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

%if %{with cuda12}
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
pushd %{bdir}/ollama
mkdir -p  %{bdir}/ollama/build
cmake --fresh --preset Default \
   -DOLLAMA_LLAMA_BACKENDS="" \
   -DCMAKE_HIP_COMPILER=NOTFOUND \
   -DCMAKE_CUDA_COMPILER=NOTFOUND \
   -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE \
   -DCMAKE_BUILD_TYPE=Release \
   %{og_cpu_compat} \
   -B %{bdir}/ollama/build
cmake --build %{bdir}/ollama/build --parallel %{?_smp_build_ncpus}
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++
export CGO_ENABLED=1
  %{og_gobuild} %{og_go_ldflag_cpu} -o %{bdir}/ollama/build/ollama-grid-cpu .
popd
mv %{bdir}/ollama/build %{bdir}/build-cpu 
%endif

echo "#---Vulkan---#"
%if %{with vulkan}
  pushd %{bdir}/ollama
  mkdir -p %{bdir}/ollama/build
  cmake --fresh --preset Default \
    -DOLLAMA_LLAMA_BACKENDS=vulkan \
    -DCMAKE_HIP_COMPILER=NOTFOUND \
    -DCMAKE_CUDA_COMPILER=NOTFOUND \
    -DCMAKE_BUILD_TYPE=Release \
    %{og_cpu_compat} \
    -B %{bdir}/ollama/build
  cmake --build %{bdir}/ollama/build --parallel %{?_smp_build_ncpus}
  export CC=/usr/bin/gcc
  export CXX=/usr/bin/g++
  export CGO_ENABLED=1
    %{og_gobuild} %{og_go_ldflag_vulkan} -o %{bdir}/ollama/build/ollama-grid-vulkan .    
  popd
  mv %{bdir}/ollama/build %{bdir}/build-vulkan
%endif

echo "#---ROCm---#"
%if %{with rocm} && "%{_arch}" == "x86_64"
  pushd %{bdir}/ollama
  mkdir -p %{bdir}/ollama/build
  cmake --fresh --preset Default \
       -DOLLAMA_LLAMA_BACKENDS=rocm_v7_2 \
       -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE \
       -DCMAKE_CUDA_COMPILER=NOTFOUND \
       -DAMDGPU_TARGETS="gfx1030;gfx1100;gfx1101;gfx1102;gfx1200;gfx1201" \
       -DCMAKE_BUILD_TYPE=Release \
       %{og_cpu_compat} \
       -B %{bdir}/ollama/build
  cmake --build %{bdir}/ollama/build --parallel %{?_smp_build_ncpus}
  export CC=/usr/bin/gcc
  export CXX=/usr/bin/g++
  export CGO_ENABLED=1
    %{og_gobuild} %{og_go_ldflag_rocm} -o %{bdir}/ollama/build/ollama-grid-rocm . 
  popd
  mv %{bdir}/ollama/build %{bdir}/build-rocm
%endif

echo "#---CUDA 13---#"
%if %{with cuda}
  pushd %{bdir}/ollama

  export CC=%{cuda_cc}
  export CXX=%{cuda_cxx}
  export CUDAHOSTCXX=%{cuda_cxx}
  export CUDACXX=/usr/local/cuda-13.0/bin/nvcc

  mkdir -p %{bdir}/ollama/build

  cmake --fresh --preset Default \
    -DOLLAMA_LLAMA_BACKENDS=cuda_v13 \
    -DCUDAToolkit_ROOT=/usr/local/cuda-13.0 \
    -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE \
    -DCMAKE_HIP_COMPILER=NOTFOUND \
    -DCMAKE_CUDA_FLAGS="-I%{bdir}/cuda13_include -Wno-deprecated-gpu-targets -Xcompiler=-fPIC -Xcompiler=-fno-PIE" \
    -DCMAKE_BUILD_TYPE=Release \
    %{og_cpu_compat} \
    -B %{bdir}/ollama/build

  cmake --build %{bdir}/ollama/build --parallel %{?_smp_build_ncpus}

  export CGO_ENABLED=1
  %{og_gobuild} %{og_go_ldflag_cuda} \
    -o %{bdir}/ollama/build/ollama-grid-cuda .

  popd
  mv %{bdir}/ollama/build %{bdir}/build-cuda
%endif

echo "#---CUDA 12---#"
%if %{with cuda12}
  pushd %{bdir}/ollama

  export CC=%{cuda_cc}
  export CXX=%{cuda_cxx}
  export CUDAHOSTCXX=%{cuda_cxx}
  export CUDACXX=/usr/local/cuda-12.9/bin/nvcc

  mkdir -p %{bdir}/ollama/build

  cmake --fresh --preset Default \
    -DOLLAMA_LLAMA_BACKENDS=cuda_v12 \
    -DCUDAToolkit_ROOT=/usr/local/cuda-12.9 \
    -DCMAKE_DISABLE_FIND_PACKAGE_Vulkan=TRUE \
    -DCMAKE_HIP_COMPILER=NOTFOUND \
    -DCMAKE_CUDA_FLAGS="-I%{bdir}/cuda12_include -Wno-deprecated-gpu-targets -Xcompiler=-fPIC -Xcompiler=-fno-PIE" \
    -DCMAKE_BUILD_TYPE=Release \
    %{og_cpu_compat} \
    -B %{bdir}/ollama/build

  cmake --build %{bdir}/ollama/build --parallel %{?_smp_build_ncpus}

  export CGO_ENABLED=1
  %{og_gobuild} %{og_go_ldflag_cuda12} \
    -o %{bdir}/ollama/build/ollama-grid-cuda12 .

  popd
  mv %{bdir}/ollama/build %{bdir}/build-cuda12
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
  %{buildroot}%{_libexecdir}/ollama-grid/

%if %{with cpu}
install -d \
  %{buildroot}%{_libexecdir}/ollama-grid/cpu \
  %{buildroot}%{_libexecdir}/ollama-grid/cpu/bin \
  %{buildroot}%{_libexecdir}/ollama-grid/cpu/lib \
  %{buildroot}%{_libexecdir}/ollama-grid/cpu/lib/ollama 
%endif

%if %{with vulkan}
install -d \
  %{buildroot}%{_libexecdir}/ollama-grid/vulkan \
  %{buildroot}%{_libexecdir}/ollama-grid/vulkan/bin \
  %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib \
  %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama 
%endif
%if %{with rocm} && "%{_arch}" == "x86_64"
install -d \
  %{buildroot}%{_libexecdir}/ollama-grid/rocm \
  %{buildroot}%{_libexecdir}/ollama-grid/rocm/bin \
  %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib \
  %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama 
%endif  

%if %{with cuda}
install -d \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda/bin \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama
%endif

%if %{with cuda12}
install -d \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda12 \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda12/bin \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama 
%endif
  
# --- sysusers / tmpfiles (arquivos do repositório) ---
install -m 0644 %{bdir}/ollama-grid/sysusers.d/ollama-grid.conf %{buildroot}%{_sysusersdir}/ollama-grid.conf
install -m 0644 %{bdir}/ollama-grid/tmpfiles.d/ollama-grid.conf %{buildroot}%{_tmpfilesdir}/ollama-grid.conf
install -Dpm644 %{bdir}/ollama-grid/systemd/ollama-grid@.service %{buildroot}%{_unitdir}/ollama-grid@.service
install -Dpm644 %{bdir}/ollama-grid/systemd/ollama-grid-balancer.service %{buildroot}%{_unitdir}/ollama-grid-balancer.service

# Licença do Ollama upstream; manter arquivo separado facilita auditoria da versão empacotada.
install -m 0644 %{bdir}/ollama/LICENSE \
    %{buildroot}%{og_licensedir}/LICENSE.ollama

# Licença do ollama-grid (MIT)
install -m 0644 %{bdir}/ollama-grid/LICENSE \
    %{buildroot}%{og_licensedir}/LICENSE.ollama-grid

# pais (base package vai "possuir")
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid


# CPU
%if %{with cpu}
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cpu
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cpu
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/cpu.conf    %{buildroot}%{og_confdir}/cpu.conf
%endif

# Vulkan
%if %{with vulkan}
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/vulkan
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/vulkan
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/vulkan.conf    %{buildroot}%{og_confdir}/vulkan.conf
%endif

# ROCm
%if %{with rocm} && "%{_arch}" == "x86_64"
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
%if %{with cuda12}
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cuda12
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cuda12
install -Dpm0640 %{bdir}/ollama-grid/etc/ollama-grid/cuda12.conf    %{buildroot}%{og_confdir}/cuda12.conf
%endif

# ============================
# BINÁRIOS (um por backend)
# ============================

# --- utilitário para limpar RPATH/RUNPATH (ignora se patchelf não existir) ---
fix_rpath() { command -v patchelf >/dev/null 2>&1 && patchelf --remove-rpath "$1" || :; }

# CPU  — publica como /usr/bin/ollama-grid-cpu
%if %{with cpu}
  install -m 0755 %{bdir}/build-cpu/ollama-grid-cpu         %{buildroot}%{_libexecdir}/ollama-grid/cpu/bin/ollama-grid-cpu
  ln -sr %{_libexecdir}/ollama-grid/cpu/bin/ollama-grid-cpu %{buildroot}%{_bindir}/ollama-grid-cpu  
%endif

# Vulkan
%if %{with vulkan}
  install -m 0755 %{bdir}/build-vulkan/ollama-grid-vulkan %{buildroot}%{_libexecdir}/ollama-grid/vulkan/bin/ollama-grid-vulkan
  ln -sr %{_libexecdir}/ollama-grid/vulkan/bin/ollama-grid-vulkan %{buildroot}%{_bindir}/ollama-grid-vulkan
%endif

# ROCm
%if %{with rocm} && "%{_arch}" == "x86_64"
  install -m 0755 %{bdir}/build-rocm/ollama-grid-rocm     %{buildroot}%{_libexecdir}/ollama-grid/rocm/bin/ollama-grid-rocm
  ln -sr %{_libexecdir}/ollama-grid/rocm/bin/ollama-grid-rocm %{buildroot}%{_bindir}/ollama-grid-rocm
    
%endif

# CUDA (atual)
%if %{with cuda}
  install -m 0755 %{bdir}/build-cuda/ollama-grid-cuda     %{buildroot}%{_libexecdir}/ollama-grid/cuda/bin/ollama-grid-cuda
  ln -sr %{_libexecdir}/ollama-grid/cuda/bin/ollama-grid-cuda %{buildroot}%{_bindir}/ollama-grid-cuda  
%endif

# CUDA 12.9 (legacy)
%if %{with cuda12}
  install -m 0755 %{bdir}/build-cuda12/ollama-grid-cuda12 %{buildroot}%{_libexecdir}/ollama-grid/cuda12/bin/ollama-grid-cuda12
  ln -sr %{_libexecdir}/ollama-grid/cuda12/bin/ollama-grid-cuda12 %{buildroot}%{_bindir}/ollama-grid-cuda12    
%endif

# ============================
# BIBLIOTECAS (instaladas por backend)
# ============================

# CPU
%if %{with cpu}
  # Bibliotecas comuns
  install -m 0644 \
    %{bdir}/build-cpu/lib/ollama/*.so* \
    %{buildroot}%{_libexecdir}/ollama-grid/cpu/lib/ollama/

  # Executáveis auxiliares do runtime
  install -m 0755 \
    %{bdir}/build-cpu/lib/ollama/llama-server \
    %{buildroot}%{_libexecdir}/ollama-grid/cpu/lib/ollama/

  install -m 0755 \
    %{bdir}/build-cpu/lib/ollama/llama-quantize \
    %{buildroot}%{_libexecdir}/ollama-grid/cpu/lib/ollama/

  # Remove RPATH/RUNPATH somente das bibliotecas
  for f in %{buildroot}%{_libexecdir}/ollama-grid/cpu/lib/ollama/*.so*; do
    [ -e "$f" ] || continue
    fix_rpath "$f"
  done
%endif

# Vulkan
%if %{with vulkan}
  # Bibliotecas comuns
  install -m 0644 \
    %{bdir}/build-vulkan/lib/ollama/*.so* \
    %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama/

  # Executáveis auxiliares do runtime
  install -m 0755 \
    %{bdir}/build-vulkan/lib/ollama/llama-server \
    %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama/

  install -m 0755 \
    %{bdir}/build-vulkan/lib/ollama/llama-quantize \
    %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama/

  # Backend Vulkan específico
  install -d \
    %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama/vulkan

  install -m 0644 \
    %{bdir}/build-vulkan/lib/ollama/vulkan/*.so* \
    %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama/vulkan/

  # Remove RPATH/RUNPATH das bibliotecas comuns
  for f in %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama/*.so*; do
    [ -e "$f" ] || continue
    fix_rpath "$f"
  done

  # Remove RPATH/RUNPATH das bibliotecas Vulkan
  for f in %{buildroot}%{_libexecdir}/ollama-grid/vulkan/lib/ollama/vulkan/*.so*; do
    [ -e "$f" ] || continue
    fix_rpath "$f"
  done
%endif

# ROCm
%if %{with rocm} && "%{_arch}" == "x86_64"
  # Bibliotecas comuns
  install -m 0644 \
    %{bdir}/build-rocm/lib/ollama/*.so* \
    %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama/

  # Executáveis auxiliares do runtime
  install -m 0755 \
    %{bdir}/build-rocm/lib/ollama/llama-server \
    %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama/

  install -m 0755 \
    %{bdir}/build-rocm/lib/ollama/llama-quantize \
    %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama/

  # Backend ROCm específico
  install -d \
    %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama/rocm_v7_2

  install -m 0644 \
    %{bdir}/build-rocm/lib/ollama/rocm_v7_2/*.so* \
    %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama/rocm_v7_2/

  # Remove RPATH/RUNPATH das bibliotecas comuns
  for f in %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama/*.so*; do
    [ -e "$f" ] || continue
    fix_rpath "$f"
  done

  # Remove RPATH/RUNPATH das bibliotecas ROCm
  for f in %{buildroot}%{_libexecdir}/ollama-grid/rocm/lib/ollama/rocm_v7_2/*.so*; do
    [ -e "$f" ] || continue
    fix_rpath "$f"
  done
%endif

# CUDA (atual)
%if %{with cuda}
  # Bibliotecas comuns
  install -m 0644 \
    %{bdir}/build-cuda/lib/ollama/*.so* \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama/

  # Executáveis auxiliares do runtime
  install -m 0755 \
    %{bdir}/build-cuda/lib/ollama/llama-server \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama/

  install -m 0755 \
    %{bdir}/build-cuda/lib/ollama/llama-quantize \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama/

  # Backend CUDA 13 específico
  install -d \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama/cuda_v13

  install -m 0644 \
    %{bdir}/build-cuda/lib/ollama/cuda_v13/libggml-cuda.so \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama/cuda_v13/

  # Remove RPATH/RUNPATH das bibliotecas comuns
  for f in %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama/*.so*; do
    [ -e "$f" ] || continue
    fix_rpath "$f"
  done

  # Remove RPATH/RUNPATH das bibliotecas CUDA
  fix_rpath \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda/lib/ollama/cuda_v13/libggml-cuda.so
%endif

# CUDA 12.9 (legacy)
%if %{with cuda12}
  # Bibliotecas comuns
  install -m 0644 \
    %{bdir}/build-cuda12/lib/ollama/*.so* \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama/

  # Executáveis auxiliares do runtime
  install -m 0755 \
    %{bdir}/build-cuda12/lib/ollama/llama-server \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama/

  install -m 0755 \
    %{bdir}/build-cuda12/lib/ollama/llama-quantize \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama/

  # Backend CUDA 12 específico
  install -d \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama/cuda_v12

  install -m 0644 \
    %{bdir}/build-cuda12/lib/ollama/cuda_v12/libggml-cuda.so \
    %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama/cuda_v12/

  # Remove RPATH/RUNPATH das bibliotecas comuns
  for f in %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama/*.so*; do
    [ -e "$f" ] || continue
    fix_rpath "$f"
  done

  # Remove RPATH/RUNPATH das bibliotecas CUDA 12
  fix_rpath \
  %{buildroot}%{_libexecdir}/ollama-grid/cuda12/lib/ollama/cuda_v12/libggml-cuda.so
%endif

# ============================
# NGINX (balanceador)
# ============================
install -m 0644 %{bdir}/ollama-grid/nginx/ollama-grid.conf \
  %{buildroot}%{_sysconfdir}/nginx/conf.d/ollama-grid.conf

# proprietary guard
%if %{with cuda} || %{with cuda12}
if find %{buildroot} -type f \( \
     -name 'libcudart.so*' -o \
     -name 'libcublas.so*' -o \
     -name 'libcublasLt.so*' -o \
     -name 'libcusparse.so*' -o \
     -name 'libcusolver.so*' -o \
     -name 'libcurand.so*' -o \
     -name 'libcufft.so*' -o \
     -name 'libnvrtc.so*' \
   \) -print | grep -q .; then
    echo "ERROR: NVIDIA CUDA runtime library found in buildroot"
    exit 1
fi
%endif



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
%if %{with cpu}
%files -n ollama-grid-cpu 
# binário

%{_bindir}/ollama-grid-cpu
%{_libexecdir}/ollama-grid/cpu/bin/ollama-grid-cpu
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cpu.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/cpu
%dir %{_libexecdir}/ollama-grid/cpu/bin
%dir %{_libexecdir}/ollama-grid/cpu/lib
%dir %{_libexecdir}/ollama-grid/cpu/lib/ollama
%{_libexecdir}/ollama-grid/cpu/lib/ollama/*.so*
%{_libexecdir}/ollama-grid/cpu/lib/ollama/llama-server
%{_libexecdir}/ollama-grid/cpu/lib/ollama/llama-quantize

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cpu
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cpu
%endif

# ============================
# Subpacote: Vulkan
# ============================
%if %{with vulkan}
%files -n ollama-grid-vulkan

# binário do backend
%{_bindir}/ollama-grid-vulkan
%{_libexecdir}/ollama-grid/vulkan/bin/ollama-grid-vulkan
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/vulkan.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/vulkan
%dir %{_libexecdir}/ollama-grid/vulkan/bin
%dir %{_libexecdir}/ollama-grid/vulkan/lib
%dir %{_libexecdir}/ollama-grid/vulkan/lib/ollama
%{_libexecdir}/ollama-grid/vulkan/lib/ollama/*.so*
%{_libexecdir}/ollama-grid/vulkan/lib/ollama/llama-server
%{_libexecdir}/ollama-grid/vulkan/lib/ollama/llama-quantize

%dir %{_libexecdir}/ollama-grid/vulkan/lib/ollama/vulkan
%{_libexecdir}/ollama-grid/vulkan/lib/ollama/vulkan/*.so*

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/vulkan
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/vulkan

%endif

# ============================
# Subpacote: ROCm
# ============================
%if %{with rocm} && "%{_arch}" == "x86_64"
%files -n ollama-grid-rocm

# binário do backend
%{_bindir}/ollama-grid-rocm
%{_libexecdir}/ollama-grid/rocm/bin/ollama-grid-rocm
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/rocm.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/rocm
%dir %{_libexecdir}/ollama-grid/rocm/bin
%dir %{_libexecdir}/ollama-grid/rocm/lib
%dir %{_libexecdir}/ollama-grid/rocm/lib/ollama
%{_libexecdir}/ollama-grid/rocm/lib/ollama/*.so*
%{_libexecdir}/ollama-grid/rocm/lib/ollama/llama-server
%{_libexecdir}/ollama-grid/rocm/lib/ollama/llama-quantize

%dir %{_libexecdir}/ollama-grid/rocm/lib/ollama/rocm_v7_2
%{_libexecdir}/ollama-grid/rocm/lib/ollama/rocm_v7_2/*.so*

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
%{_libexecdir}/ollama-grid/cuda/bin/ollama-grid-cuda
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cuda.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/cuda
%dir %{_libexecdir}/ollama-grid/cuda/bin
%dir %{_libexecdir}/ollama-grid/cuda/lib
%dir %{_libexecdir}/ollama-grid/cuda/lib/ollama
%{_libexecdir}/ollama-grid/cuda/lib/ollama/*.so*
%{_libexecdir}/ollama-grid/cuda/lib/ollama/llama-server
%{_libexecdir}/ollama-grid/cuda/lib/ollama/llama-quantize
%dir %{_libexecdir}/ollama-grid/cuda/lib/ollama/cuda_v13
%{_libexecdir}/ollama-grid/cuda/lib/ollama/cuda_v13/libggml-cuda.so

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cuda
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cuda

%endif

# ============================
# Subpacote: CUDA 12.9 (legacy)
# ============================

%if %{with cuda12}

%files -n ollama-grid-cuda12

# binário do backend
%{_bindir}/ollama-grid-cuda12
%{_libexecdir}/ollama-grid/cuda12/bin/ollama-grid-cuda12

%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cuda12.conf

# libs do backend
%dir %{_libexecdir}/ollama-grid/cuda12
%dir %{_libexecdir}/ollama-grid/cuda12/bin
%dir %{_libexecdir}/ollama-grid/cuda12/lib
%dir %{_libexecdir}/ollama-grid/cuda12/lib/ollama
%{_libexecdir}/ollama-grid/cuda12/lib/ollama/*.so*
%{_libexecdir}/ollama-grid/cuda12/lib/ollama/llama-server
%{_libexecdir}/ollama-grid/cuda12/lib/ollama/llama-quantize
%dir %{_libexecdir}/ollama-grid/cuda12/lib/ollama/cuda_v12
%{_libexecdir}/ollama-grid/cuda12/lib/ollama/cuda_v12/libggml-cuda.so

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cuda12
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cuda12

%endif

# ---- Common ----

%post -n ollama-grid-common
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
%if %{with cuda12}
%post -n ollama-grid-cuda12
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
%if %{with rocm} && "%{_arch}" == "x86_64"
%post -n ollama-grid-rocm
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
