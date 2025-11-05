# ROADMAP — Ollama Community Build (Fedora 43 / GCC‑14)

Este roadmap define a evolução do projeto partindo de uma arquitetura **stateless** (v1) até um modelo **stateful distribuído** (v3), mantendo compatibilidade com múltiplos backends (CPU, Vulkan, ROCm, CUDA‑12.9, CUDA‑latest) e o pacote `ollama-balancer`.

---

## Visão Geral por Fases

| Fase | Objetivo | Persistência | Componentes-Chave | Resultado |
|-----:|----------|--------------|-------------------|-----------|
| v1 | Operação stateless | Sem DB | `ollama@{cpu,vulkan,rocm,cuda-12.9,cuda-latest}`, `ollama-balancer` (nginx) | Serviços independentes e balanceados; o cliente envia o histórico completo em cada requisição |
| v2 | Sessões persistentes | SQLite/Redis | `ollama-sessiond` (middleware REST), balancer idem | Contexto da conversa sincronizado entre backends; identificação por `session_id` |
| v3 | Estado distribuído e busca semântica | PostgreSQL + Vector DB | `ollama-sessiond` + (Qdrant/Milvus/Chroma) | Escala horizontal, retenção longa de histórico, contexto recuperável e expandido por embeddings |

---

## Fase v1 — Stateless (Atual)

**Status:** Implementado
- Múltiplos serviços `systemd@` por backend com `.env` dedicados.
- `ollama-balancer` (nginx) roteando por caminho (`/cpu/`, `/rocm/`, `/cuda129/`, `/cuda/`, `/vulkan/`).
- **Estado da conversa enviado pelo cliente** (lista `messages[]` em cada chamada `/api/chat`).

**Benefícios:**
- Simplicidade operacional e facilidade de debug.
- Balanceamento independente do backend.

**Limitações:**
- Sem “continuidade” automática entre serviços se o cliente não reenviar o histórico.

---

## Fase v2 — Semi‑Stateful com `ollama-sessiond`

**Meta:** Centralizar estados de conversa via `session_id`.
- Introduzir serviço **`ollama-sessiond`** (REST) para armazenar histórico de mensagens e metadados de sessão (usuário, modelo, tempo, tags).
- Persistência inicial: **SQLite** (local) ou **Redis** (TTL, alta performance).

### Esquema de Dados (mínimo)

**Tabela `sessions` (SQLite/Postgres):**
- `id` (UUID, PK)
- `created_at` (timestamp)
- `updated_at` (timestamp)
- `meta` (JSONB) — atributos livres (modelo preferido, idioma, etc.)

**Tabela `messages`**
- `id` (PK, autoincrement/UUID)
- `session_id` (FK → sessions.id, index)
- `role` (TEXT) — `system|user|assistant|tool`
- `content` (TEXT)
- `meta` (JSONB) — tokens, latência, backend utilizado, etc.
- `ts` (timestamp, index)

### API (proposta)

```
POST   /session                → cria sessão; retorna {session_id}
POST   /session/{id}/append    → adiciona mensagem {role, content, meta?}
GET    /session/{id}/history   → retorna array messages[] pronto p/ Ollama
POST   /chat                   → {session_id, model, options?} → chama Ollama
DELETE /session/{id}           → encerra e/or soft‑delete
```

> O endpoint `/chat` do `sessiond` faz o “middleware”: busca histórico, injeta em `messages[]`, define o backend alvo (regra/round‑robin/afinidade) e repassa ao Ollama selecionado.

### Regras de Roteamento (exemplos)

- **Afinidade por sessão**: primeira chamada define o backend com melhor compatibilidade (ex.: CUDA‑12.9 para P4) e persiste no `meta`; seguintes chamadas seguem a afinidade.
- **Failover**: se backend indisponível (`/api/version` falha), escolher próximo elegível (Vulkan → CPU).

### Migração v1 → v2

- Adicionar pacote `ollama-sessiond` (binário + unit `ollama-sessiond.service`).
- Nginx: opcionalmente adicionar um *location* `/chat/` apontando para o sessiond.
- Clientes podem usar **apenas** o `sessiond` como frontend.

---

## Fase v3 — Stateful Distribuído + Vector Store

**Objetivo:** Escala e inteligência do contexto.
- Migrar persistência principal para **PostgreSQL** (alta confiabilidade, `jsonb`).
- Adicionar **Vector DB** (Qdrant, Milvus, Chroma) para:
  - indexar trechos relevantes (mensagens longas, documentos anexos);
  - fazer **busca semântica** e reforçar o contexto antes de chamar o Ollama.

### Pipelines de Contexto

1. **Ingestão**: novas mensagens → split → embeddings → grava Vector DB (por `session_id` e `message_id`).
2. **Consulta**: a cada `/chat`, buscar top‑k itens relevantes no Vector DB e anexar ao `messages[]` como contexto “retrieval‑augmented”.

### Esquema de Dados (extensão)

- `sessions` e `messages` em Postgres como acima.
- **Índices**: (`session_id`, `ts`), GIN para `meta` (`jsonb_path_ops`), e FTS opcional em `content`.
- Vector DB: `namespace=session_id`, `id=message_id#chunk`, `embedding`, `payload` (metadata).

### Operação e Observabilidade

- Health checks: `/api/version` (Ollama) e `/healthz` (sessiond).
- Métricas: latência por backend, tokens/s, taxa de erros.
- Tracing (opcional): OpenTelemetry no `sessiond` para rastrear requisição → backend.

---

## Segurança & Conformidade

- **Isolamento**: `User=ollama`, `NoNewPrivileges=yes`, `ProtectSystem=full` nos serviços.
- **Entrada**: validar tamanho de entrada e número máx. de mensagens por requisição.
- **TLS**: terminação TLS no `ollama-balancer` quando publicação externa.
- **Cotas**: rate‑limits no nginx (`limit_req_zone`) e quotas por IP/usuário (opcional).

---

## Desempenho & Afinidade

- **CUDA‑latest** → maior throughput; usado como favorito quando disponível.
- **CUDA‑12.9** → compat para placas antigas (sm_61).
- **ROCm** → para hosts AMD com bom ROCm/hipBLAS.
- **Vulkan** → fallback universal; bom equilíbrio multi‑vendor.
- **CPU** → último recurso e para ambientes sem GPU.

Sugerido: manter **pesos** por backend no balanceador (ou afinidade por sessão no `sessiond`).

---

## Roadmap Técnico (tarefas)

### v1 (feito)
- [x] Pacotes: `ollama`, `ollama-backend-*`, `ollama-balancer`
- [x] systemd@ por backend + `.env`
- [x] Nginx com paths por backend e health‑check
- [x] Scripts auxiliares (`apply-cuda129-patch.sh`, `detect_cuda.sh`)

### v2
- [ ] Implementar `ollama-sessiond` (REST) — linguagem sugerida: Go ou Python (FastAPI)
- [ ] Armazenar sessões/mensagens (SQLite/Redis)
- [ ] Endpoint `/chat` integrando sessão + chamada ao Ollama
- [ ] Afinidade por sessão e failover
- [ ] Embalar como `ollama-sessiond` (spec + unit)

### v3
- [ ] Migrar para PostgreSQL (jsonb) e introduzir Vector DB
- [ ] Pipelines de embeddings (ingestão/consulta)
- [ ] Métricas, tracing, dashboards
- [ ] Política de retenção/arquivamento de sessões

---

## Notas Operacionais

- Compartilhar (`read‑only` quando possível) `/var/lib/ollama/models` entre nós reduz tempo de cold‑start.
- Manter **changelog** registrando versão exata de Toolkit CUDA usada nos builds.
- Executar `restorecon -Rv /etc/ollama /var/lib/ollama /var/log/ollama` após instalação em SELinux.

---

## Licenças

- Ollama: Apache‑2.0 (upstream).
- Empacotamento e scripts: MIT (neste repositório).
