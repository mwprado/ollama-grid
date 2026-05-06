# ROADMAP — OllamaGrid

Este roadmap define a evolução do projeto partindo de uma arquitetura **stateless** com rotas explícitas por backend até um modelo com sessões persistentes e, posteriormente, estado distribuído.

---

## Visão geral por fases

| Fase | Objetivo | Persistência | Componentes-chave | Resultado esperado |
|-----:|----------|--------------|-------------------|--------------------|
| v1 | Operação stateless com seleção explícita de backend | Sem DB | `ollama-grid@{cpu,vulkan,rocm,cuda12,cuda}`, `ollama-grid-balancer` | Serviços independentes, backend selecionável por rota e compatibilidade básica com clientes Ollama |
| v2 | Sessões persistentes e afinidade de backend | SQLite/Redis | `ollama-sessiond`, Nginx, backends OllamaGrid | Histórico centralizado, `session_id`, afinidade, failover e telemetria inicial |
| v3 | Estado distribuído e recuperação semântica | PostgreSQL + Vector DB | `ollama-sessiond`, Postgres, Qdrant/Milvus/Chroma | Escala horizontal, retenção longa e contexto recuperável por embeddings |

---

## Fase v1 — Stateless com Nginx

**Status:** em estabilização.

Componentes:

- múltiplos serviços `systemd@` por backend;
- arquivos `.conf` dedicados em `/etc/ollama-grid/`;
- Nginx com rotas explícitas por backend;
- backends vinculados a `127.0.0.1` por padrão;
- exposição externa concentrada no Nginx.

### Rotas v1

| Rota | Backend |
|------|---------|
| `/api/...` | CPU padrão |
| `/cpu/api/...` | CPU |
| `/vulkan/api/...` | Vulkan |
| `/rocm/api/...` | ROCm |
| `/cuda12/api/...` | CUDA 12.9 legado |
| `/cuda/api/...` | CUDA atual |

### Benefícios

- Simplicidade operacional.
- Depuração direta por backend.
- Menor superfície de rede, porque backends escutam em localhost.
- Compatibilidade com clientes Ollama simples via `/api/...`.

### Limitações

- Sem continuidade automática de conversa entre requisições se o cliente não reenviar histórico.
- Sem afinidade automática por sessão.
- Sem decisão inteligente por modelo, carga, memória ou disponibilidade.
- Sem failover semântico: o Nginx apenas roteia HTTP.

---

## Fase v2 — Semi-stateful com `ollama-sessiond`

**Meta:** centralizar estados de conversa via `session_id` e introduzir política de backend.

O `ollama-sessiond` deve funcionar como middleware REST:

1. recebe chamada do cliente;
2. busca histórico da sessão;
3. seleciona backend elegível;
4. envia requisição para o backend OllamaGrid;
5. registra resposta, latência, backend usado e metadados.

### Persistência inicial

- SQLite para instalação local simples.
- Redis opcional para TTL e maior desempenho.

### Esquema mínimo

Tabela `sessions`:

- `id` UUID, chave primária;
- `created_at` timestamp;
- `updated_at` timestamp;
- `meta` JSON.

Tabela `messages`:

- `id` chave primária;
- `session_id` referência para `sessions.id`;
- `role` com valores `system`, `user`, `assistant` ou `tool`;
- `content` texto;
- `meta` JSON;
- `ts` timestamp.

### API proposta

```text
POST   /session                -> cria sessão; retorna {session_id}
POST   /session/{id}/append    -> adiciona mensagem
GET    /session/{id}/history   -> retorna messages[] pronto para Ollama
POST   /chat                   -> usa session_id, seleciona backend e chama Ollama
DELETE /session/{id}           -> encerra ou remove sessão
GET    /healthz                -> healthcheck do sessiond
```

### Regras de roteamento v2

- Afinidade por sessão: a primeira chamada define backend preferencial.
- Failover: se backend falhar, escolher próximo backend elegível.
- Política por modelo: alguns modelos podem ser restritos a backends específicos.
- Política por capacidade: evitar CPU para modelos grandes quando GPU estiver disponível.

---

## Fase v3 — Stateful distribuído + Vector Store

**Objetivo:** ampliar persistência, observabilidade e recuperação de contexto.

Componentes planejados:

- PostgreSQL como persistência principal;
- campo `jsonb` para metadados;
- Vector DB para busca semântica;
- pipeline de embeddings;
- métricas e tracing.

### Pipeline de contexto

1. Ingestão: mensagens e documentos são fragmentados e indexados.
2. Consulta: cada `/chat` recupera top-k fragmentos relevantes.
3. Composição: contexto recuperado é anexado ao `messages[]`.
4. Execução: requisição segue para backend selecionado.

---

## Segurança e conformidade

- Serviços devem rodar como `User=ollama-grid`.
- Configurações em `/etc/ollama-grid` devem ser controladas por `root:ollama-grid`.
- Backends devem escutar em `127.0.0.1` por padrão.
- Publicação externa deve ocorrer somente via Nginx.
- Usar TLS, autenticação e rate limit quando exposto fora do host local.
- Validar tamanho de entrada, número máximo de mensagens e limites de payload.

---

## Roadmap técnico imediato

### v1 — estabilização

- [x] Padronizar nomes `ollama-grid-*`.
- [x] Usar `ollama-grid@<backend>` como padrão de serviço.
- [x] Vincular backends a `127.0.0.1` por padrão.
- [x] Definir Nginx com rotas explícitas por backend.
- [x] Endurecer propriedade de `/etc/ollama-grid`.
- [x] Criar patch conservador para estabilização inicial do spec RPM.
- [ ] Aplicar localmente `packaging/ollama-grid.spec.stabilization.patch` e revisar o resultado.
- [ ] Validar `rpmbuild -ba packaging/ollama-grid.spec` em ambiente Fedora.
- [ ] Validar `nginx -t` em ambiente Fedora.
- [ ] Validar `systemctl enable --now ollama-grid@cpu`.
- [ ] Validar smoke tests por rota `/api/version`.
- [ ] Criar release `v0.1.0-alpha` após validação local.

### v2 — sessiond

- [ ] Implementar `ollama-sessiond` mínimo.
- [ ] Adicionar armazenamento SQLite.
- [ ] Implementar endpoint `/chat` com `session_id`.
- [ ] Adicionar afinidade por sessão.
- [ ] Adicionar failover básico.
- [ ] Empacotar `ollama-sessiond` como subpacote próprio.

### v3 — persistência distribuída e busca semântica

- [ ] Migrar persistência para PostgreSQL.
- [ ] Introduzir Vector DB.
- [ ] Adicionar pipeline de embeddings.
- [ ] Adicionar métricas, tracing e dashboards.
- [ ] Definir política de retenção/arquivamento de sessões.

---

## Notas operacionais

- Compartilhar `/var/lib/ollama-grid/models` entre backends reduz duplicação e cold-start.
- Manter changelog registrando versão exata do Toolkit CUDA usada nos builds.
- Executar `restorecon -Rv /etc/ollama-grid /var/lib/ollama-grid /var/log/ollama-grid` em sistemas SELinux quando necessário.

---

## Licenças

- OllamaGrid: MIT.
- Ollama upstream: verificar a licença do código empacotado na versão usada.
- Modelos executados pelo OllamaGrid possuem licenças próprias e independentes.
