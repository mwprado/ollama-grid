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

## 📦 Estrutura dos pacotes

O OllamaGrid é dividido em módulos independentes, podendo ser instalados no mesmo host ou distribuídos em nós diferentes.
Cada backend utiliza sua própria configuração, binário e serviço `systemd`.

| Pacote | Descrição |
|---------|------------|
| `ollama-cpu` | Backend genérico (CPU / fallback). |
| `ollama-vulkan` | Backend universal baseado em Vulkan. |
| `ollama-rocm` | Backend para GPUs AMD, sempre rastreando a última versão estável do ROCm. |
| `ollama-cuda` | Backend para GPUs NVIDIA modernas, sempre rastreando a última versão estável do CUDA Toolkit. |
| `ollama-cuda-legacy-12.9` | Backend fixo para GPUs NVIDIA Compute 6.1 (ex.: Tesla P4). |
| `ollama-balancer` | Serviço Nginx responsável pelo balanceamento entre os backends. |

---

## ⚙️ Estrutura de instalação recomendada

```
/usr/lib/systemd/system/ollama@.service
/usr/lib/systemd/system/ollama-balancer.service
/etc/ollama-grid/                  ← configurações específicas
/etc/nginx/conf.d/ollama-grid.conf ← proxy/balancer principal
/var/log/ollama-grid/              ← logs dos serviços
/run/ollama-grid/                  ← PID e sockets (tmpfiles.d)
```

> **Nota:** O diretório correto é `tmpfiles.d`, e não `tempfiles.d`.

---

## 🌐 Balanceador (Nginx)

O pacote `ollama-balancer` instala a configuração padrão do Nginx em:

```
/etc/nginx/conf.d/ollama-grid.conf
```

Trecho simplificado:

```nginx
upstream ollama_nodes {
    server 127.0.0.1:11434; # CPU
    server 127.0.0.1:11435; # Vulkan
    server 127.0.0.1:11436; # ROCm
    server 127.0.0.1:11437; # CUDA
    # server 127.0.0.1:11439; # CUDA Legacy 12.9 (opcional)
}

server {
    listen 8080;
    location / {
        proxy_pass http://ollama_nodes;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_buffering off;
    }

    location = /health { return 200 "ok\n"; }
}
```

Recarregue após editar:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🧩 Backends e versões

| Backend | Suporte | Versão |
|----------|----------|----------|
| CPU | genérica | nativo |
| Vulkan | genérico (AMD/Intel/NVIDIA) | última versão |
| ROCm | GPUs AMD | última versão |
| CUDA | GPUs NVIDIA modernas | última versão |
| CUDA (legacy) | GPUs NVIDIA Compute 6.1 (ex: Tesla P4) | pacote `ollama-cuda-legacy-12.9` |

> **Nota:** Pacotes `ollama-cuda` e `ollama-rocm` sempre se referem à versão mais recente estável disponível
> nos repositórios oficiais NVIDIA e AMD ROCm, respectivamente.  
> Versões legadas utilizam o formato `ollama-cuda-legacy-{versão}`.

---

## 🔧 Serviços

```bash
# Serviços principais
sudo systemctl enable --now ollama@cpu
sudo systemctl enable --now ollama@vulkan
sudo systemctl enable --now ollama@rocm
sudo systemctl enable --now ollama@cuda
sudo systemctl enable --now ollama@cuda-legacy-12.9

# Balanceador
sudo systemctl enable --now ollama-balancer
```

---

## ✅ Testes

```bash
curl -sSf http://localhost:8080/health
curl -sSf http://localhost:8080/cpu/api/version
curl -sSf http://localhost:8080/cuda/api/version
```

---

### Disclaimer

OllamaGrid é um projeto comunitário independente e não é afiliado, endossado nem patrocinado por NVIDIA, AMD ou Khronos Group.  
Os logotipos e marcas mencionados (NVIDIA, CUDA, ROCm e Vulkan) são propriedade de seus respectivos detentores.  
Os símbolos utilizados nas ilustrações e materiais gráficos são representações artísticas originais, criadas apenas para fins ilustrativos e educativos,  
visando demonstrar compatibilidade técnica entre diferentes arquiteturas.

---
