# ARCHITECTURE

Este documento descreve a arquitetura dos pacotes e serviços, com dois formatos de diagrama:
- **Mermaid** (renderiza no GitHub/GitLab)
- **ASCII** (compatível com qualquer terminal)

---

## 1) Visão atual (v1) — Stateless com Nginx

### 1.1 Diagrama (Mermaid)

```mermaid
flowchart LR
  Client[Cliente / App] -->|HTTP| Nginx[(ollama-balancer)]
  subgraph Host(s)
    direction TB
    Nginx -->|/cpu/| CPU[ollama@cpu:11434]
    Nginx -->|/vulkan/| VK[ollama@vulkan:11435]
    Nginx -->|/rocm/| ROCM[ollama@rocm:11436]
    Nginx -->|/cuda129/| C129[ollama@cuda-12.9:11437]
    Nginx -->|/cudalast/| CL[ollama@cuda-latest:11438]
  end
  classDef svc fill:#eef,stroke:#99f,stroke-width:1px;
  class Nginx,CPU,VK,ROCM,C129,CL svc;
```

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
|   :11434  |      |   :11435  |   |   :11436  |   |  -12.9    |       |  -latest  |
+-----------+      +-----------+   +-----------+   |   :11437   |       |   :11438  |
                                                   +-----------+       +-----------+
```

---

## 2) Visão futura (v2) — Sessiond + Sessões Persistentes

### 2.1 Diagrama (Mermaid)

```mermaid
flowchart LR
  Client[Cliente / App] -->|/chat (session_id)| Sessiond[(ollama-sessiond)]
  Sessiond -->|/history| DB[(SQLite/Redis)]
  Sessiond -->|HTTP| Nginx[(ollama-balancer)]
  Nginx --> CPU[ollama@cpu]
  Nginx --> VK[ollama@vulkan]
  Nginx --> ROCM[ollama@rocm]
  Nginx --> C129[ollama@cuda-12.9]
  Nginx --> CL[ollama@cuda-latest]
  classDef svc fill:#eef,stroke:#99f,stroke-width:1px;
  class Sessiond,Nginx,CPU,VK,ROCM,C129,CL svc;
```

### 2.2 Diagrama (ASCII)

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
|   :11434  |     |   :11435  |    |   :11436  |   |  -12.9    |    |  -latest  |
+-----------+     +-----------+    +-----------+   |   :11437   |    |   :11438  |
                                                   +-----------+    +-----------+
```

---

## 3) Diretórios & Convenções

- Binário: `/usr/bin/ollama`
- Libs por backend: `/usr/lib64/ollama/{cpu,vulkan,rocm,cuda-12.9,cuda-latest}`
- Configs (env): `/etc/ollama/{cpu,vulkan,rocm,cuda-12.9,cuda-latest}.env`
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
- CUDA-latest: `11438`
- Balancer (Nginx): `8080`

---

## 5) Notas de Operação

- Remover RPATH/RUNPATH dos `.so` no build.
- `restorecon -Rv` nos diretórios principais (SELinux).
- Timeouts longos no Nginx para inferência.
- Compartilhar diretório de modelos (RO) reduz cold-start.
