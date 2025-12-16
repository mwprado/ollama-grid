Name:           ollama-grid
Version:        0.13.4
Release:        2%{?dist}
Summary:        Meta-pacote e backends do Ollama (Vulkan/ROCm/CUDA) com balanceador Nginx
License:        Apache-2.0 AND MIT
URL:            https://github.com/ollama/ollama

# ====== SOURCE0: OLLAMA-GRID (seus assets: scripts/patch/nginx/…) =====
Source0:        https://github.com/mwprado/ollama-grid/archive/refs/heads/main.tar.gz

# ====== SOURCE1: OLLAMA (upstream) via Forge macros ======
Source1:        https://github.com/ollama/ollama/archive/refs/tags/v%{version}.tar.gz

# ====== Seleção de backends (cada build pode habilitar 1..N) ======
%bcond_without cpu
%bcond_with vulkan
%bcond_with rocm
%bcond_with cuda
%bcond_without cuda_12_9

# ====== Caminhos de instalação ======
%global og_libdir %{_libdir}/ollama-grid
%global og_confdir %{_sysconfdir}/ollama-grid
%global og_nginx_conf %{_sysconfdir}/nginx/conf.d/ollama-grid.conf

%global og_licensedir %{_licensedir}/ollama-grid

# Comando comum de build do binário Go (repo root do Ollama)
%global og_gobuild    go build -trimpath -buildmode=pie -ldflags "-s -w" 



# ====== BuildRequires gerais ======
BuildRequires:    gcc gcc-c++ cmake make git-core golang patchelf systemd-rpm-macros
BuildRequires:    openmpi-devel

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
BuildRequires:  cuda-toolkit-13-0
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
Bibliotecas Vulkan e wrapper /usr/bin/ollama-grid-cpu.

# (4) Vulkan
%package -n ollama-grid-vulkan
Summary:        Backend Vulkan (universal GPU: Intel/AMD/NVIDIA)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-vulkan
Bibliotecas Vulkan e wrapper /usr/bin/ollama-grid-vulkan.

# (5) ROCm
%package -n ollama-grid-rocm
Summary:        Backend ROCm (GPUs AMD)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-rocm
Bibliotecas ROCm (HIP) e wrapper /usr/bin/ollama-grid-rocm.

# (6) CUDA (moderno, sempre “latest” disponível no host de build)
%package -n ollama-grid-cuda
Summary:        Backend CUDA (GPUs NVIDIA modernas)
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cuda
Bibliotecas CUDA (moderno) e wrapper /usr/bin/ollama-grid-cuda. Requer toolkit presente no host.

# (7) CUDA legacy 12.9 (ex.: Tesla P4, sm_61)
%package -n ollama-grid-cuda-12-9
Summary:        Backend CUDA 12.9 (legado) para GPUs NVIDIA compute 6.1
Requires:       ollama-grid-common = %{version}-%{release}

%description -n ollama-grid-cuda-12-9
Bibliotecas CUDA 12.9 (legado) e wrapper /usr/bin/ollama-grid-cuda-12.9.
O patch é aplicado por script antes do build e revertido após o build.

# ==================== Prep ====================
%prep
# Cria raiz estável e NÃO extrai nada ainda
%setup -q -T -c -n wsp

# Pastas de trabalho
mkdir -p ./source/ollama-grid ./source/ollama ./build

# Extrai os dois tarballs achatando o topo (independe do nome interno)
tar -xzf %{SOURCE0} -C ./source/ollama-grid --strip-components=1
tar -xzf %{SOURCE1} -C ./source/ollama --strip-components=1

# Duplica a árvore do OLLAMA para cada backend dentro de build/
cp -a source/ollama source/ollama-%{version}-cpu 
cp -a source/ollama source/ollama-%{version}-vulkan
cp -a source/ollama source/ollama-%{version}-rocm
cp -a source/ollama source/ollama-%{version}-cuda
cp -a source/ollama source/ollama-%{version}-cuda-12.9


%if %{with cuda}
mkdir ./source/cuda_include
cp -a /usr/local/cuda-13.0/targets/x86_64-linux/include/* ./source/cuda_include/
cp -a ./source/cuda-13-0-math-functions.h.patch ./source/cuda_include/crt
pushd ./source/cuda_include
patch -u < ./cuda-13-0-math-functions.h.patch
popd
%endif

%if %{with cuda_12_9}
echo $PWD
pwd
mkdir ./source/cuda_include-12.9/
cp -a /usr/local/cuda-12.9/targets/x86_64-linux/include/* ./source/cuda_include-12.9/
cp -a ./source/ollama-grid/scripts/cuda-12-9-math-functions.h.patch ./source/cuda_include-12.9/crt/                           
pushd ./source/cuda_include-12.9/crt
patch -u < cuda-12-9-math-functions.h.patch
popd
%endif



# Copia assets do Nginx (se existirem) do Source1
# (Ajuste este caminho se seu repo usar outro layout)
# mkdir -p nginx-assets
# cp -a ./source/ollama-grid/nginx/ollama-grid.conf nginx-assets/

# ==================== Build ====================
%build

# ---- CPU ----"
echo "#---CPU---#"
%if %{with cpu}
pushd ./source/ollama-%{version}-cpu  
cmake --preset "CPU" --fresh 
cmake --build build --parallel --preset "CPU"
%{og_gobuild} -o ../../build/ollama-cpu .
popd
%endif

# ---- Vulkan ----
echo "#---Vulkan---#"
%if %{with vulkan}
  pushd ./source/ollama-%{version}-vulkan  
  cmake --preset "Vulkan" --fresh 
  cmake --build build --parallel --preset "Vulkan"
  %{og_gobuild} -o ../../build/ollama-vulkan .
  popd
%endif

# ---- ROCm ----
echo "#---ROCm---#"
%if %{with rocm}
  pushd ./source/ollama-%{version}-rocm  
  cmake --preset "ROCm 6" --fresh -D AMDGPU_TARGETS="gfx803;gfx1032;gfx1035" -D GPU_TARGETS="gfx803;gfx1032;gfx1035"
  cmake --build build --parallel --preset "ROCm 6"
  %{og_gobuild} -o ../../build/ollama-rocm .
  popd
%endif

# ---- CUDA 13 moderno (latest) — opcional; toolkit deve estar no PATH/ambiente ----
echo "#---CUDA 13---#"
%if %{with cuda}
  pushd ./source/ollama-%{version}-cuda
  
  export CUDAHOSTCXX=/usr/bin/g++
  export CPATH=/usr/include/openmpi-x86_64:$CPATH
  export PATH=$PATH:/usr/lib64/openmpi/bin
  export CC=/usr/bin/gcc
  export CXX=/usr/bin/g++
  export NVCC_CCBIN=/usr/bin/g++
  export CUDACXX=/usr/local/cuda-13.0/bin/nvcc
  export LD_LIBRARY_PATH=/usr/local/cuda-13.0/targets/x86_64-linux/lib:$LD_LIBRARY_PATH
  #export CPATH=/usr/local/cuda-13.0/targets/x86_64-linux/include:$CPATH
  export CPATH=$PWD/source/cuda_include/$CPATH
  export PATH=/usr/local/cuda-13.0/bin:$PATH
  export GGML_VULKAN_DISABLE=1
    
  # Se necessário, exporte CUDACXX/NVCC_CCBIN aqui para “latest”
  cmake --preset "CUDA 13" --fresh \
        -D GGML_VULKAN=OFF \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -fPIC" \
        -D CMAKE_CUDA_COMPILER=/usr/local/cuda-13.0/bin/nvcc
#        -D CUDA_ARCHITECTURES="12.0;9.0;8.9;8.6;8.0;7.5;7.0" 
  cmake --build build --parallel --preset "CUDA 13" \
        -D CMAKE_CUDA_FLAGS="-Wno-deprecated-gpu-targets -Xcompiler -fPIE -fPIC" \
        -D CMAKE_CUDA_COMPILER=/usr/local/cuda-13.0/bin/nvcc 
#        -D CUDA_ARCHITECTURES="12.0;9.0;8.9;8.6;8.0;7.5;7.0"
  %{og_gobuild} -o ../../build/ollama-cuda .
  popd
%endif

# ---- CUDA legacy 12.9 ----
echo "#---CUDA 12---#"
%if %{with cuda_12_9}
  pushd ./source/ollama-%{version}-cuda-12.9

  cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_CUDA=ON \
    -DGGML_VULKAN=OFF \
    -DGGML_OPENCL=OFF \
    -DGGML_METAL=OFF \
    -DGGML_HIP=OFF \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DCMAKE_C_COMPILER=/usr/bin/gcc-14 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 \
    -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
    -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-14 \
    -DCMAKE_CUDA_ARCHITECTURES="50;52;60;61;70;75;80;86;89;90;90a;120" \
    -DCMAKE_CUDA_FLAGS="-I%{_builddir}/wsp/source/cuda_include-12.9 -Wno-deprecated-gpu-targets -Xcompiler=-fPIC -Xcompiler=-fno-PIE" \
    -DCMAKE_CXX_FLAGS="-I%{_builddir}/wsp/source/cuda_include-12.9 -fPIC" \
    -DCMAKE_C_FLAGS="-I%{_builddir}/wsp/source/cuda_include-12.9 -fPIC"

  cmake --build build --parallel

  # Ambiente CUDA 12.9
  #export CC=/usr/bin/gcc-14
  #export CXX=/usr/bin/g++-14
  #export CUDAHOSTCXX=/usr/bin/g++-14
  #export NVCC_CCBIN=/usr/bin/g++-14
  #export CUDACXX=/usr/local/cuda-12.9/bin/nvcc
  #export PATH=/usr/local/cuda-12.9/bin:$PATH
  #export CUDA_COMPAT_INC="%{_builddir}/wsp/source/cuda_include-12.9"

  #cmake --preset "CUDA 12" --fresh \
  #      -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  #      -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc \
  #      -DCMAKE_CUDA_FLAGS="-I${CUDA_COMPAT_INC} -Wno-deprecated-gpu-targets -Xcompiler=-fPIC -Xcompiler=-fno-PIE" \
  #      -DCMAKE_CXX_FLAGS="-I${CUDA_COMPAT_INC} $CMAKE_CXX_FLAGS -fPIC" \
  #      -DCMAKE_C_FLAGS="-I${CUDA_COMPAT_INC} $CMAKE_C_FLAGS -fPIC" 

  #cmake --build build --parallel --preset "CUDA 12"

  #%{og_gobuild} -o ../../build/ollama-cuda-12.9 .

  popd
%endif

# ==================== Install ====================
%install
rm -rf %{buildroot}

# --- diretórios base ---
install -d \
  %{buildroot}%{_bindir} \
  %{buildroot}%{og_libdir} \
  %{buildroot}%{_sysusersdir} \
  %{buildroot}%{_tmpfilesdir} \
  %{buildroot}%{_unitdir} \
  %{buildroot}%{og_confdir} \
  %{buildroot}%{og_licensedir} \
  %{buildroot}%{_sysconfdir}/nginx/conf.d \
  %{buildroot}%{_sysconfdir}/ld.so.conf.d
  
# --- sysusers / tmpfiles (arquivos do repositório) ---
install -m 0644 source/ollama-grid/sysusers.d/ollama-grid.conf %{buildroot}%{_sysusersdir}/ollama-grid.conf
install -m 0644 source/ollama-grid/tmpfiles.d/ollama-grid.conf %{buildroot}%{_tmpfilesdir}/ollama-grid.conf
install -Dpm644 source/ollama-grid/systemd/ollama-grid@.service %{buildroot}%{_unitdir}/ollama-grid@.service
install -Dpm644 source/ollama-grid/systemd/ollama-grid-balancer.service %{buildroot}%{_unitdir}/ollama-grid-balancer.service

# Licença do Ollama (Apache 2.0)
install -m 0644 source/ollama/LICENSE \
    %{buildroot}%{og_licensedir}/LICENSE.ollama

# Licença do ollama-grid (MIT)
install -m 0644 source/ollama-grid/LICENSE \
    %{buildroot}%{og_licensedir}/LICENSE.ollama-grid

# pais (base package vai "possuir")
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid
install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid

# ============================
# ld.so.conf.d (um .conf por backend/pacote)
# ============================
# CPU (sempre)
install -m 0644 source/ollama-grid/lib64/ollama-grid-cpu.conf \
  %{buildroot}%{_sysconfdir}/ld.so.conf.d/ollama-grid-cpu.conf
install -Dpm0640 source/ollama-grid/etc/ollama-grid/cpu.conf    %{buildroot}%{og_confdir}/cpu.conf

install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cpu
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cpu

# Vulkan
%if %{with vulkan}
install -m 0644 source/ollama-grid/lib64/ollama-grid-vulkan.conf \
  %{buildroot}%{_sysconfdir}/ld.so.conf.d/ollama-grid-vulkan.conf
install -Dpm0640 source/ollama-grid/etc/ollama-grid/vulkan.conf %{buildroot}%{og_confdir}/vulkan.conf

install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/vulkan
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/vulkan

%endif

# ROCm
%if %{with rocm}
install -m 0644 source/ollama-grid/lib64/ollama-grid-rocm.conf \
  %{buildroot}%{_sysconfdir}/ld.so.conf.d/ollama-grid-rocm.conf
install -Dpm0640 source/ollama-grid/etc/ollama-grid/rocm.conf   %{buildroot}%{og_confdir}/rocm.conf

install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/rocm
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/rocm
%endif

# CUDA (atual)
%if %{with cuda}
install -m 0644 source/ollama-grid/lib64/ollama-grid-cuda.conf \
  %{buildroot}%{_sysconfdir}/ld.so.conf.d/ollama-grid-cuda.conf
install -Dpm0640 source/ollama-grid/etc/ollama-grid/cuda.conf   %{buildroot}%{og_confdir}/cuda.conf

install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cuda
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cuda

%endif

# CUDA 12.9 (legacy)
%if %{with cuda_12_9}
install -m 0644 source/ollama-grid/lib64/ollama-grid-cuda-12.9.conf \
  %{buildroot}%{_sysconfdir}/ld.so.conf.d/ollama-grid-cuda-12.9.conf
install -Dpm0640 source/ollama-grid/etc/ollama-grid/cuda-12.9.conf   %{buildroot}%{og_confdir}/cuda-12.9.conf

install -d -m 0755 %{buildroot}%{_localstatedir}/log/ollama-grid/cuda-12.9
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/ollama-grid/cuda-12.9

%endif

# --- utilitário para limpar RPATH/RUNPATH (ignora se patchelf não existir) ---
fix_rpath() { command -v patchelf >/dev/null 2>&1 && patchelf --remove-rpath "$1" || :; }

# ============================
# BINÁRIOS (um por backend)
# ============================

# CPU (sempre) — publica como /usr/bin/ollama-grid-cpu
install -m 0755 ./build/ollama-cpu %{buildroot}%{_bindir}/ollama-grid-cpu

# Conveniência: apontar /usr/bin/ollama-grid para o CPU por padrão (symlink)
# ln -sfn ollama-grid-cpu %{buildroot}%{_bindir}/ollama-grid

# Vulkan
%if %{with vulkan}
  install -m 0755 ./build/ollama-vulkan %{buildroot}%{_bindir}/ollama-grid-vulkan
%endif

# ROCm
%if %{with rocm}
  install -m 0755 ./build/ollama-rocm %{buildroot}%{_bindir}/ollama-grid-rocm
%endif

# CUDA (atual)
%if %{with cuda}
  install -m 0755 ./build/ollama-cuda %{buildroot}%{_bindir}/ollama-grid-cuda
%endif

# CUDA 12.9 (legacy)
%if %{with cuda_12_9}
  install -m 0755 ./build/ollama-cuda-12.9 %{buildroot}%{_bindir}/ollama-grid-cuda-12.9
%endif

# ============================
# BIBLIOTECAS (instaladas por backend)
# ============================

%if %{with cpu}
  install -d %{buildroot}%{og_libdir}/cpu

  # base + variantes CPU
  install -m 0755 ./source/ollama-%{version}-cpu/build/lib/ollama/libggml-base.so %{buildroot}%{og_libdir}/cpu/
  install -m 0755 ./source/ollama-%{version}-cpu/build/lib/ollama/libggml-cpu-*.so %{buildroot}%{og_libdir}/cpu/

  for f in %{buildroot}%{og_libdir}/cpu/*.so; do fix_rpath "$f"; done
%endif

# Vulkan
%if %{with vulkan}
  install -d %{buildroot}%{og_libdir}/vulkan
  install -m 0755 ./source/ollama-%{version}-vulkan/build/lib/ollama/libggml-vulkan.so %{buildroot}%{og_libdir}/vulkan/
  install -m 0755 ./source/ollama-%{version}-vulkan/build/lib/ollama/libggml-base.so   %{buildroot}%{og_libdir}/vulkan/
  for f in %{buildroot}%{og_libdir}/vulkan/*.so; do fix_rpath "$f"; done
%endif

# ROCm
%if %{with rocm}
  install -d %{buildroot}%{og_libdir}/rocm
  install -m 0755 ./source/ollama-%{version}-rocm/build/lib/ollama/libggml-hip.so  %{buildroot}%{og_libdir}/rocm/
  install -m 0755 ./source/ollama-%{version}-rocm/build/lib/ollama/libggml-base.so %{buildroot}%{og_libdir}/rocm/
  for f in %{buildroot}%{og_libdir}/rocm/*.so; do fix_rpath "$f"; done
%endif

# CUDA (atual)
%if %{with cuda}
  install -d %{buildroot}%{og_libdir}/cuda
  install -m 0755 ./source/ollama-%{version}-cuda/build/lib/ollama/libggml-cuda.so %{buildroot}%{og_libdir}/cuda/
  install -m 0755 ./source/ollama-%{version}-cuda/build/lib/ollama/libggml-base.so %{buildroot}%{og_libdir}/cuda/
  for f in %{buildroot}%{og_libdir}/cuda/*.so; do fix_rpath "$f"; done
%endif

# CUDA 12.9 (legacy)
%if %{with cuda_12_9}
  install -d %{buildroot}%{og_libdir}/cuda-12.9
  install -m 0755 ./source/ollama-%{version}-cuda-12.9/build/lib/ollama/libggml-cuda.so %{buildroot}%{og_libdir}/cuda-12.9/
  install -m 0755 ./source/ollama-%{version}-cuda-12.9/build/lib/ollama/libggml-base.so %{buildroot}%{og_libdir}/cuda-12.9/
  for f in %{buildroot}%{og_libdir}/cuda-12.9/*.so; do fix_rpath "$f"; done
%endif

# ============================
# NGINX (balanceador)
# ============================
install -m 0644 source/ollama-grid/nginx/ollama-grid.conf \
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
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cpu.conf

# libs do backend
%dir %{og_libdir}/cpu
%{og_libdir}/cpu/*.so

# ld.so.conf.d (CPU)
%config(noreplace) %{_sysconfdir}/ld.so.conf.d/ollama-grid-cpu.conf

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cpu
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cpu

# ============================
# Subpacote: Vulkan
# ============================
%if %{with vulkan}
%files -n ollama-grid-vulkan
# binário do backend
%{_bindir}/ollama-grid-vulkan
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/vulkan.conf

# libs do backend
%dir %{og_libdir}/vulkan
%{og_libdir}/vulkan/*.so

# ld.so.conf.d do backend
%config(noreplace) %{_sysconfdir}/ld.so.conf.d/ollama-grid-vulkan.conf

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
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/rocm.conf

# libs do backend
%dir %{og_libdir}/rocm
%{og_libdir}/rocm/*.so

# ld.so.conf.d do backend
%config(noreplace) %{_sysconfdir}/ld.so.conf.d/ollama-grid-rocm.conf

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
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cuda.conf

# libs do backend
%dir %{og_libdir}/cuda
%{og_libdir}/cuda/*.so

# ld.so.conf.d do backend
%config(noreplace) %{_sysconfdir}/ld.so.conf.d/ollama-grid-cuda.conf

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cuda
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cuda

%endif

# ============================
# Subpacote: CUDA 12.9 (legacy)
# ============================
%if %{with cuda_12_9}

%files -n ollama-grid-cuda-12-9

# binário do backend
%{_bindir}/ollama-grid-cuda-12.9
%config(noreplace) %attr(0640,root,ollama-grid) /etc/ollama-grid/cuda-12.9.conf

# libs do backend
%dir %{og_libdir}/cuda-12.9
%{og_libdir}/cuda-12.9/*.so

# ld.so.conf.d do backend
%config(noreplace) %{_sysconfdir}/ld.so.conf.d/ollama-grid-cuda-12.9.conf

%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/lib/ollama-grid/cuda-12.9
%dir %attr(0755,ollama-grid,ollama-grid) %{_localstatedir}/log/ollama-grid/cuda-12.9

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
%if %{with cuda_12_9}
%post -n ollama-grid-cuda-12-9
if [ $1 -eq 1 ] ; then
    systemctl enable --now ollama-grid@cuda-12.9.service >/dev/null 2>&1 || :
else
    systemctl try-restart ollama-grid@cuda-12.9.service >/dev/null 2>&1 || :
fi
%preun -n ollama-grid-cuda-12-9
if [ $1 -eq 0 ] ; then
    systemctl disable --now ollama-grid@cuda-12.9.service >/dev/null 2>&1 || :
fi
%endif

# ---- ROCm ----
%if %{with rocm}
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
