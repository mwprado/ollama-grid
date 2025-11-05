Name:           ollama
Version:        0.12.9
Release:        1%{?dist}
Summary:        Ollama CLI/daemon with modular backends
License:        Apache-2.0
URL:            https://github.com/ollama/ollama
Source0:        buildconfig.inc
Source10:       sysusers.d/ollama.conf
Source11:       tmpfiles.d/ollama.conf
Source20:       systemd/ollama@.service
Source30:       scripts/post_install_checks.sh

BuildRequires:  gcc, gcc-c++, make, cmake, git
BuildRequires:  pkgconfig(vulkan)
BuildRequires:  openmpi, openmpi-devel
Requires(post): systemd
Requires(postun): systemd

%bcond_without cpu
%bcond_without vulkan
%bcond_without rocm
%bcond_without cuda_latest
%bcond_without cuda_129

%description
Ollama com empacotamento modular de backends (CPU, Vulkan, ROCm, CUDA 12.9, CUDA latest).

%prep
%setup -T -c -n %{name}-%{version}
install -m0644 %{SOURCE0} buildconfig.inc

%build
# Placeholders: builds reais devem chamar cmake no código-fonte upstream.
echo "Build placeholders. Construa os backends fora e instale os .so via %%install."

%install
mkdir -p %{buildroot}/usr/lib64/ollama/{cpu,vulkan,rocm,cuda-12.9,cuda-latest}
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}%{_sysusersdir}
mkdir -p %{buildroot}%{_tmpfilesdir}
mkdir -p %{buildroot}%{_unitdir}

# Instala arquivos de sistema
install -Dpm0644 %{SOURCE10} %{buildroot}%{_sysusersdir}/ollama.conf
install -Dpm0644 %{SOURCE11} %{buildroot}%{_tmpfilesdir}/ollama.conf
install -Dpm0644 %{SOURCE20} %{buildroot}%{_unitdir}/ollama@.service

# Binário fictício (substitua pelo real no empacote final)
echo -e '#!/usr/bin/env bash\necho Ollama placeholder' > %{buildroot}/usr/bin/ollama
chmod 0755 %{buildroot}/usr/bin/ollama

%pre
%sysusers_create_compat ollama.conf

%post
%tmpfiles_create ollama.conf || :
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
/sbin/ldconfig || :

%postun
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
/sbin/ldconfig || :

%files
%license
%doc
/usr/bin/ollama
%{_sysusersdir}/ollama.conf
%{_tmpfilesdir}/ollama.conf
%{_unitdir}/ollama@.service
/usr/lib64/ollama

%changelog
* Wed Nov 05 2025 Community Build <builder@example> - 0.12.9-1
- Initial community packaging skeleton with modular backends
