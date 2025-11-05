# ARCHITECTURE — Ollama Community Build

Este documento descreve a arquitetura dos pacotes e serviços, com dois formatos de diagrama:
- **Mermaid** (renderiza no GitHub/GitLab)
- **ASCII** (compatível com qualquer terminal)

---

## 1) Visão atual (v1) — Stateless com Nginx

### 1.2 Diagrama (ASCII)

```
+-------------------+        HTTP        +---------------------+
|   Cliente / App   |  ----------------> |   ollama-balancer   |
+-------------------+                    |       (Nginx)       |
                                         +----------+----------+
                                                    |
     /cpu/           /vulkan/         /rocm/         /cuda129/          /cudalast/
      |                  |               |               |                   |
+-----v-----+      +-----v-----+   +-----v-----+   +-----v-----+       +-----v-----+
| ollama@cpu|      |ollama@vulk|   |ollama@rocm|   |ollama@cuda|       |ollama@cuda|
|   :11434  |      |   :11435  |   |   :11436  |   |  -12.9    |       |   :11438  |
+-----------+      +-----------+   +-----------+   |  :11437   |       +-----------+
                                                   +-----------+       
```

---

## 2) Visão futura (v2) — Sessiond + Sessões Persistentes

```
+-------------------+     /chat (session_id)     +-------------------+
|   Cliente / App   | -------------------------> |  ollama-sessiond  |
+-------------------+                             +---------+---------+
                                                   | /history|
                                                   v         |
                                              +----+----+    |
                                              | SQLite |<----+
                                              | Redis  |
                                              +---------+
                                                   |
                                                   v  HTTP
                                             +-----+-----+
                                             |   Nginx   |
                                             +--+---+---++
                                                |   |   |
     /cpu/           /vulkan/         /rocm/        /cuda129/        /cudalast/
      |                 |                |               |                |
+-----v-----+     +-----v-----+    +-----v-----+   +-----v-----+    +-----v-----+
| ollama@cpu|     |ollama@vulk|    |ollama@rocm|   |ollama@cuda|    |ollama@cuda|
|   :11434  |     |   :11435  |    |   :11436  |   |  -12.9    |    |   :11438  |
+-----------+     +-----------+    +-----------+   |  :11437   |    +-----------+
                                                   +-----------+    
```

---

## 3) Diretórios & Convenções

- Binário: `/usr/bin/ollama`
- Libs por backend: `/usr/lib64/ollama/{cpu,vulkan,rocm,cuda-12.9,cuda}`
- Configs (env): `/etc/ollama/{cpu,vulkan,rocm,cuda-12.9,cuda}.env`
- Dados/modelos: `/var/lib/ollama/<backend>/models`
- Logs: `/var/log/ollama/`
- Balanceador: `/etc/ollama/balancer/nginx.conf`

**Usuário/Grupo:** `ollama` (via sysusers).

---

## 4) Portas (padrão)

- CPU: `11434`
- Vulkan: `11435`
- ROCm: `11436`
- CUDA-12.9: `11437`
- CUDA: `11438`
- Balancer (Nginx): `8080`

---

## 5) Notas de Operação

- Remover RPATH/RUNPATH dos `.so` no build.
- `restorecon -Rv` nos diretórios principais (SELinux).
- Timeouts longos no Nginx para inferência.
- Compartilhar diretório de modelos (RO) reduz cold-start.
