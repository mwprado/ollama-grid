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

<p align="center">
  <img src="https://img.shields.io/badge/status-em%20desenvolvimento-orange" alt="Status: Em desenvolvimento">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT">
  <img src="https://img.shields.io/badge/Fedora-43-informational" alt="Fedora 43">
  <img src="https://img.shields.io/badge/GCC-14-blue" alt="GCC 14">
</p>

---

> ⚠️ **Status: Em desenvolvimento (Alpha)**
>
> Este projeto ainda está em fase de desenvolvimento ativo.  
> Alterações na estrutura, empacotamento e documentação podem ocorrer até a estabilização da primeira versão pública.

---

## Objetivo

OllamaGrid é uma camada comunitária de empacotamento e operação do Ollama para Fedora/COPR, com backends separados por arquitetura, serviços `systemd` independentes e um balanceador/proxy Nginx.

O projeto não substitui o Ollama upstream. Ele organiza builds e serviços para ambientes heterogêneos, por exemplo CPU, Vulkan, ROCm, CUDA moderno e CUDA legado.

---

## 📦 Estrutura dos pacotes

Os pacotes usam o prefixo `ollama-grid-*` para evitar colisão semântica com o projeto Ollama upstream.

| Pacote | Descrição |
|---------|------------|
| `ollama-grid-common` | Arquivos comuns: usuário, grupo, tmpfiles, units systemd e diretórios. |
| `ollama-grid-cpu` | Backend genérico CPU/fallback. |
| `ollama-grid-vulkan` | Backend universal baseado em Vulkan. |
| `ollama-grid-rocm` | Backend para GPUs AMD via ROCm. |
| `ollama-grid-cuda` | Backend para GPUs NVIDIA modernas. |
| `ollama-grid-cuda12` | Backend CUDA 12.9 legado, útil para GPUs Compute 6.1, como Tesla P4. |
| `ollama-grid-balancer` | Configuração Nginx para proxy e roteamento entre backends. |

---

## ⚙️ Estrutura de instalação recomendada

```text
/usr/lib/systemd/system/ollama-grid@.service
/usr/lib/systemd/system/ollama-grid-balancer.service
/etc/ollama-grid/                  ← configurações específicas por backend
/etc/nginx/conf.d/ollama-grid.conf ← proxy/balancer principal
/var/lib/ollama-grid/              ← dados e modelos
/var/log/ollama-grid/              ← logs dos serviços
/run/ollama-grid/                  ← PID e sockets, quando necessário
```

> **Nota:** O diretório correto é `tmpfiles.d`, e não `tempfiles.d`.

---

## 🌐 Balanceador Nginx

O pacote `ollama-grid-balancer` instala a configuração padrão do Nginx em:

```text
/etc/nginx/conf.d/ollama-grid.conf
```

A fase v1 usa roteamento explícito por caminho:

| Rota | Backend |
|------|---------|
| `/api/...` | CPU padrão, compatível com clientes Ollama simples |
| `/cpu/api/...` | `ollama-grid@cpu` |
| `/vulkan/api/...` | `ollama-grid@vulkan` |
| `/rocm/api/...` | `ollama-grid@rocm` |
| `/cuda/api/...` | `ollama-grid@cuda` |
| `/cuda12/api/...` | `ollama-grid@cuda12` |

Os backends escutam em `127.0.0.1` por padrão. A exposição externa deve ser feita pelo Nginx, preferencialmente com TLS, autenticação e rate limit quando aplicável.

Recarregue após editar:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🧩 Backends e portas

| Backend | Serviço | Porta padrão |
|----------|---------|--------------|
| CPU | `ollama-grid@cpu` | `127.0.0.1:11434` |
| Vulkan | `ollama-grid@vulkan` | `127.0.0.1:11435` |
| ROCm | `ollama-grid@rocm` | `127.0.0.1:11436` |
| CUDA 12.9 legado | `ollama-grid@cuda12` | `127.0.0.1:11437` |
| CUDA atual | `ollama-grid@cuda` | `127.0.0.1:11438` |
| Nginx | `ollama-grid-balancer` | `0.0.0.0:8080` |

---

## 🔧 Serviços

```bash
# Serviços principais
sudo systemctl enable --now ollama-grid@cpu
sudo systemctl enable --now ollama-grid@vulkan
sudo systemctl enable --now ollama-grid@rocm
sudo systemctl enable --now ollama-grid@cuda
sudo systemctl enable --now ollama-grid@cuda12

# Balanceador
sudo systemctl enable --now ollama-grid-balancer
```

---

## ✅ Testes

```bash
curl -sSf http://localhost:8080/health
curl -sSf http://localhost:8080/api/version
curl -sSf http://localhost:8080/cpu/api/version
curl -sSf http://localhost:8080/vulkan/api/version
curl -sSf http://localhost:8080/rocm/api/version
curl -sSf http://localhost:8080/cuda/api/version
curl -sSf http://localhost:8080/cuda12/api/version
```

Use apenas as rotas correspondentes aos backends instalados e ativos.

---

## Licenças

- OllamaGrid: MIT.
- Ollama upstream: ver licença do projeto upstream empacotado na versão usada.
- Modelos executados pelo OllamaGrid possuem licenças próprias e independentes.

---

### Disclaimer

OllamaGrid é um projeto comunitário independente e não é afiliado, endossado nem patrocinado por NVIDIA, AMD, Khronos Group ou Ollama.  
Os logotipos e marcas mencionados são propriedade de seus respectivos detentores.  
Os símbolos utilizados nas ilustrações e materiais gráficos são representações artísticas originais, criadas apenas para fins ilustrativos e educativos, visando demonstrar compatibilidade técnica entre diferentes arquiteturas.
