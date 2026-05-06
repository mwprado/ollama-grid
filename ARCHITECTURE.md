# ARCHITECTURE — OllamaGrid

Este documento descreve a arquitetura dos pacotes e serviços do OllamaGrid.

OllamaGrid é uma camada Fedora/COPR para empacotar e operar múltiplos backends do Ollama com serviços `systemd` separados e proxy Nginx.

---

## 1) Visão atual v1 — Stateless com Nginx

A fase v1 é propositalmente simples: cada backend roda como uma instância independente de `ollama-grid@.service`, e o Nginx expõe rotas explícitas para cada backend.

```text
+-------------------+        HTTP        +-------------------------+
|   Cliente / App   |  ----------------> |   ollama-grid-balancer  |
+-------------------+                    |         Nginx           |
                                         +-----------+-------------+
                                                     |
       /api/            /cpu/          /vulkan/       /rocm/       /cuda12/       /cuda/
        |                 |               |             |             |             |
+-------v------+   +------v------+   +----v-----+   +---v----+   +----v-----+   +---v----+
| CPU default  |   | CPU backend |   | Vulkan   |   | ROCm   |   | CUDA12   |   | CUDA   |
| 127.0.0.1    |   | 127.0.0.1   |   | :11435   |   | :11436 |   | :11437   |   | :11438 |
| :11434       |   | :11434      |   +----------+   +--------+   +----------+   +--------+
+--------------+   +-------------+
```

### Semântica das rotas

| Rota pública | Backend interno |
|-------------|------------------|
| `/api/...` | CPU padrão em `127.0.0.1:11434` |
| `/cpu/api/...` | CPU em `127.0.0.1:11434` |
| `/vulkan/api/...` | Vulkan em `127.0.0.1:11435` |
| `/rocm/api/...` | ROCm em `127.0.0.1:11436` |
| `/cuda12/api/...` | CUDA 12.9 legado em `127.0.0.1:11437` |
| `/cuda/api/...` | CUDA atual em `127.0.0.1:11438` |

A rota `/api/...` preserva compatibilidade com clientes simples do Ollama. As rotas com prefixo permitem depuração e seleção explícita de backend.

---

## 2) Visão futura v2 — Sessiond + afinidade de backend

A fase v2 introduz `ollama-sessiond`, uma camada REST para manter histórico e metadados de sessão.

```text
+-------------------+     /chat session_id     +-------------------+
|   Cliente / App   | -----------------------> |  ollama-sessiond  |
+-------------------+                          +---------+---------+
                                                        |
                                                        | histórico / afinidade
                                                        v
                                                +-------+-------+
                                                | SQLite/Redis  |
                                                +-------+-------+
                                                        |
                                                        v
                                                +-------+-------+
                                                |     Nginx     |
                                                +---+---+---+---+
                                                    |   |   |
                                                   CPU ROCm CUDA...
```

A responsabilidade do `sessiond` é resolver:

- persistência de histórico;
- afinidade por sessão;
- failover entre backends elegíveis;
- seleção de backend por capacidade, modelo ou política;
- métricas de latência, erro e throughput.

---

## 3) Diretórios e convenções

| Recurso | Caminho |
|--------|---------|
| Units systemd | `/usr/lib/systemd/system/ollama-grid@.service` |
| Binários por backend | `/usr/libexec/ollama-grid/<backend>/bin/` |
| Bibliotecas por backend | `/usr/libexec/ollama-grid/<backend>/lib/ollama/` |
| Wrappers públicos | `/usr/bin/ollama-grid-<backend>` |
| Configs por backend | `/etc/ollama-grid/<backend>.conf` |
| Dados/modelos | `/var/lib/ollama-grid/models` |
| Logs | `/var/log/ollama-grid/` |
| Nginx | `/etc/nginx/conf.d/ollama-grid.conf` |

**Usuário/Grupo:** `ollama-grid` via `sysusers.d`.

---

## 4) Portas padrão

| Backend | Porta |
|---------|-------|
| CPU | `127.0.0.1:11434` |
| Vulkan | `127.0.0.1:11435` |
| ROCm | `127.0.0.1:11436` |
| CUDA 12.9 | `127.0.0.1:11437` |
| CUDA atual | `127.0.0.1:11438` |
| Nginx | `0.0.0.0:8080` |

---

## 5) Notas operacionais

- Backends escutam em `127.0.0.1` por padrão.
- Exposição externa deve ocorrer via Nginx.
- Use TLS, autenticação e rate limit antes de expor fora da máquina local.
- Remover RPATH/RUNPATH dos `.so` no build reduz acoplamento ao ambiente de compilação.
- Em sistemas com SELinux, executar `restorecon -Rv /etc/ollama-grid /var/lib/ollama-grid /var/log/ollama-grid` após instalação, se necessário.
- Compartilhar o diretório de modelos entre backends reduz cold-start e duplicação de disco.
