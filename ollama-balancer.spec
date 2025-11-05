Name:           ollama-balancer
Version:        0.1.0
Release:        1%{?dist}
Summary:        Reverse proxy and load balancer for Ollama backends
License:        MIT
URL:            https://example.org/ollama-balancer
Source10:       nginx/nginx.conf
Source11:       systemd/ollama-balancer.service
Source12:       etc/ollama/balancer/ollama-balancer.env

Requires:       nginx
Requires(post): systemd
Requires(postun): systemd

%description
Pacote de balanceador (Nginx) para instâncias Ollama por backend.

%prep
%setup -T -c -n %{name}-%{version}

%build
: # nada a compilar

%install
mkdir -p %{buildroot}/etc/ollama/balancer
mkdir -p %{buildroot}%{_unitdir}

install -Dpm0644 %{SOURCE10} %{buildroot}/etc/ollama/balancer/nginx.conf
install -Dpm0644 %{SOURCE11} %{buildroot}%{_unitdir}/ollama-balancer.service
install -Dpm0644 %{SOURCE12} %{buildroot}/etc/ollama/balancer/ollama-balancer.env

%post
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
/usr/bin/systemctl enable --now ollama-balancer.service >/dev/null 2>&1 || true

%postun
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :

%files
/etc/ollama/balancer/nginx.conf
/etc/ollama/balancer/ollama-balancer.env
%{_unitdir}/ollama-balancer.service

%changelog
* Wed Nov 05 2025 Community Build <builder@example> - 0.1.0-1
- Initial balancer package (nginx-based)
