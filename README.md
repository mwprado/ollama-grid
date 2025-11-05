
<p align="center">
  <img src="docs/mascot_chimera.png" width="280" alt="OllamaGrid — Chimera Mascot">
</p>

<h1 align="center">OllamaGrid</h1>
<p align="center">
  <b>One brain, many architectures.</b><br>
  Modular and distributed Ollama packaging for Fedora/COPR.
</p>

<p align="center">
  <a href="ARCHITECTURE.md">Architecture</a> •
  <a href="ROADMAP.md">Roadmap</a> •
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

# Ollama Community Build — Fedora 43 / GCC‑14

Empacotamento comunitário do **Ollama 0.12.9** com _backends_ modulares (CPU, Vulkan, ROCm, CUDA‑12.9 e CUDA‑latest) e um pacote de **balanceador** (Nginx) para ambientes heterogêneos (Intel/AMD/NVIDIA).

> Objetivo: permitir instalação co‑existente de múltiplos backends (na mesma máquina ou distribuídos), cada um com serviço, configuração e pasta próprios.

---

## Pacotes fornecidos

- `ollama` — pacote base (binário/serviço e libs comuns, perfil CPU).
- `ollama-backend-vulkan` — backend universal via Vulkan.
- `ollama-backend-rocm` — backend AMD (HIP/rocBLAS).
- `ollama-backend-cuda-12.9` — backend NVIDIA legado (ex.: Tesla P4, sm_61).
- `ollama-backend-cuda-latest` — backend NVIDIA atual (CUDA 13).
- `ollama-balancer` — Nginx como proxy reverso/balanceador.

Cada backend instala em diretório próprio:

```
/usr/lib64/ollama/{cpu,vulkan,rocm,cuda-12.9,cuda-latest}
```

e possui um arquivo de ambiente em:

```
/etc/ollama/{cpu,vulkan,rocm,cuda-12.9,cuda-latest}.env
```

---

## Requisitos

- **Fedora 43**, **GCC 14** nativo.
- Drivers correspondentes (RPM Fusion ou oficiais).
- Para **compilar** CUDA localmente:
  - CUDA 12.9 (repo NVIDIA Fedora 41, testado no F43).
  - CUDA 13 (repo NVIDIA Fedora 42).
- OpenMPI, pkgconfig(vulkan) para builds.
- Root para instalar/gerenciar serviços.

---

## Usuário, diretórios e permissões

Criados via `sysusers.d` / `tmpfiles.d`:

```
User/Group: ollama
/var/lib/ollama   (0750, ollama:ollama)
/var/log/ollama   (0750, ollama:ollama)
/etc/ollama       (0750, root:ollama)
```

Após instalar, recomenda‑se:

```bash
sudo restorecon -Rv /etc/ollama /var/lib/ollama /var/log/ollama
```

---

## Serviços (systemd)

Serviço _template_: `ollama@.service`

Ativar por backend:
```bash
sudo systemctl enable --now ollama@cpu
sudo systemctl enable --now ollama@vulkan
sudo systemctl enable --now ollama@rocm
sudo systemctl enable --now ollama@cuda-12.9
sudo systemctl enable --now ollama@cuda-latest
```

Cada serviço lê um `.env` próprio com porta, `LD_LIBRARY_PATH` e `OLLAMA_MODELS`. Portas padrão:

| Backend | Porta |
|--------:|------:|
| CPU | 11434 |
| Vulkan | 11435 |
| ROCm | 11436 |
| CUDA‑12.9 | 11437 |
| CUDA‑latest | 11438 |

### Hardening sugerido
No unit file já constam `User=ollama`, `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=full`, `ProtectHome=read-only`.

---

## Balanceador (`ollama-balancer`)

Instala Nginx + `ollama-balancer.service` e o config padrão em `/etc/ollama/balancer/nginx.conf`:
- _Paths_ por backend: `/cpu/`, `/vulkan/`, `/rocm/`, `/cuda129/`, `/cudalast/`
- _Health_: `/api/version`
- Timeouts longos para inferências.

Ativar:
```bash
sudo systemctl enable --now ollama-balancer
```

SELinux/Firewall (se expor porta 8080):
```bash
sudo setsebool -P httpd_can_network_connect 1
sudo firewall-cmd --add-port=8080/tcp --permanent && sudo firewall-cmd --reload
```

Testes rápidos:
```bash
curl http://localhost:8080/health
curl http://localhost:8080/cpu/api/version
curl http://localhost:8080/cudalast/api/version
```

---

## Estado da conversa (contexto)

O Ollama é **stateless**: o cliente deve enviar `messages[]` em toda chamada `/api/chat`.  
Para manter sessões entre backends/hosts, ver **ROADMAP.md** (fase v2: `ollama-sessiond` com SQLite/Redis; fase v3: Postgres + Vector DB).

---

## Scripts

- `scripts/apply-cuda129-patch.sh` — **ADMIN** aplica/reverte patch em arquivos do **CUDA 12.9** (backup automático e `--dry-run`).  
  Exemplo:
  ```bash
  sudo ./apply-cuda129-patch.sh     --patch /caminho/para/fix.patch     --target targets/x86_64-linux/include/seu_arquivo.h
  ```
- `scripts/detect_cuda.sh` — detecta `nvcc` e gera `buildconfig.inc` (para SRPM/COPR).
- `scripts/post_install_checks.sh` — _smoke tests_ de versão e health endpoints.

---

## Empacotamento (Copr)

- `specs/ollama.spec` — esqueleto com subpacotes (CPU, Vulkan, ROCm, CUDA‑12.9, CUDA‑latest).
- `specs/ollama-balancer.spec` — Nginx + unit.

Diretrizes:
- Remover **RPATH/RUNPATH** dos `.so` durante `%install`.
- **CUDA**: não usar `BuildRequires` no COPR; gere **SRPM** a partir de build local com Toolkit oficial.
- Variantes CUDA em diretórios separados e (opcionalmente) gerenciar `cuda-current` via `alternatives`.

Exemplos de build do SRPM (local):
```bash
rpmbuild -bs packaging/specs/ollama.spec   --define "_sourcedir $(pwd)/packaging"   --define "_srcrpmdir $(pwd)/dist"   --with cpu --with vulkan --with cuda_129 --without rocm

rpmbuild -bs packaging/specs/ollama-balancer.spec   --define "_sourcedir $(pwd)/packaging"   --define "_srcrpmdir $(pwd)/dist"
```

Submeter ao COPR:
```bash
copr-cli build mwprado/ollama dist/ollama-0.12.9-1.fc43.src.rpm
copr-cli build mwprado/ollama dist/ollama-balancer-0.1.0-1.fc43.src.rpm
```

---

## Estrutura do repositório (neste ZIP)

```
packaging/
  README.md
  ROADMAP.md
  specs/
    ollama.spec
    ollama-balancer.spec
  sysusers.d/ollama.conf
  tmpfiles.d/ollama.conf
  systemd/
    ollama@.service
    ollama-balancer.service
  etc/ollama/
    cpu.env
    vulkan.env
    rocm.env
    cuda-12.9.env
    cuda-latest.env
    balancer/ollama-balancer.env
  nginx/nginx.conf
  scripts/
    apply-cuda129-patch.sh
    detect_cuda.sh
    post_install_checks.sh
  buildconfig.inc
```

---

## Licenças

- Ollama (upstream): Apache‑2.0
- Empacotamento e scripts deste projeto: MIT

---

## Suporte & Contribuição

- Issues e PRs são bem‑vindos
- Veja também **ROADMAP.md** para a evolução (sessiond, DBs, métricas)

---
### Disclaimer

OllamaGrid é um projeto comunitário independente e não é afiliado, endossado nem patrocinado por NVIDIA, AMD ou Khronos Group.
Os logotipos e marcas mencionados (NVIDIA, CUDA, ROCm e Vulkan) são propriedade de seus respectivos detentores.
Os símbolos utilizados nas ilustrações e materiais gráficos são representações artísticas originais, criadas apenas para fins ilustrativos e educativos,
visando demonstrar compatibilidade técnica entre diferentes arquiteturas.

