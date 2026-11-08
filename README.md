<p align="center">
  <img src="docs/mascot_chimera.png" width="280" alt="OllamaGrid — Chimera Mascot">
</p>

<h1 align="center">OllamaGrid</h1>
<p align="center">
  <b>One brain, many architectures.</b><br>
  Modular Ollama packaging and local backend routing for Fedora/COPR.
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

OllamaGrid é uma camada comunitária de empacotamento e operação do Ollama para Fedora/COPR. O projeto organiza builds por backend, serviços `systemd` independentes e um proxy Nginx para seleção explícita de backend.

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

## 🔐 Pós-instalação: firewall e SELinux

Após instalar o `ollama-grid-balancer`, **verifique o isolamento das portas 11434–11438**, exponha somente a API Nginx (`8080/tcp`) à rede autorizada e confira se o SELinux permite as conexões do Nginx aos backends.

O guia inclui configuração do `firewalld`, diagnóstico de `502 Bad Gateway` causado por `httpd_can_network_connect=off`, verificações e ressalvas de segurança. **O pacote não altera automaticamente firewall ou SELinux no `%post`.**

Consulte **[Pós-instalação: firewall e SELinux](docs/POST_INSTALL.md)**.

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

## 💬 Clientes recomendados

O Ollama-Grid expõe a API nativa do Ollama pelo **Nginx na porta `8080`**. Para conversar com os modelos, dois clientes interessantes são:

| Cliente | Perfil | Configuração recomendada |
|---|---|---|
| **[Moose](https://github.com/moooossee/moose)** | Aplicativo desktop nativo para Linux (GTK/libadwaita), com chats e arquivos locais | Selecionar a opção para conectar a uma **instância Ollama existente** e apontar para o endereço do Ollama-Grid |
| **[Open WebUI](https://github.com/open-webui/open-webui)** | Interface web self-hosted, com histórico, gerenciamento de modelos e recursos para múltiplos usuários | Configurar uma conexão do tipo **Ollama** com a URL-base do Nginx |

Em ambos os casos, use **`http://127.0.0.1:8080`** quando o cliente tiver acesso à mesma rede local do host e estiver sendo executado diretamente nele. Em outra máquina, substitua `127.0.0.1` pelo endereço do servidor, com acesso autorizado no firewall. **Não aponte o cliente diretamente para as portas 11434–11438**: isso contorna o failover e a política centralizada de escrita dos modelos.

### Moose

- Disponível no [Flathub](https://flathub.org/apps/io.github.moooossee.Moose), além do repositório do projeto.
- Na configuração, escolha **Ollama existente/externo**, e não o Ollama gerenciado pelo próprio Moose, para usar o Ollama-Grid.
- Se um modo de privacidade permitir somente o Ollama gerenciado pelo aplicativo, ajuste-o conforme a documentação do Moose para habilitar a conexão externa ao Ollama-Grid.

### Open WebUI

- Em **Admin → Settings → Connections**, configure uma conexão **Ollama** apontando para a API do Ollama-Grid, por exemplo `http://servidor:8080`.
- Também é possível usar `OLLAMA_BASE_URL=http://servidor:8080` na configuração inicial. A variável define a URL **base**, sem sufixo `/api`.
- Se Open WebUI estiver em Docker/Podman, `localhost` aponta para o **contêiner**, não para o host. Use um endereço do host acessível ao contêiner; no Podman, por exemplo, `host.containers.internal` quando disponível.
- Caso ambos rodem na mesma máquina, evite conflito entre as portas HTTP do **Open WebUI** e do **Nginx Ollama-Grid** (que utiliza a porta `8080`).

A URL pública do Ollama-Grid é suficiente para listar modelos, fazer inferência e solicitar downloads: o Nginx encaminha operações de escrita (`/api/pull`, `/api/create` etc.) ao backend CPU e prioriza as GPUs para consultas. Os clientes são **opcionais** e não são dependências RPM do Ollama-Grid.

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

## 🔭 Evolução futura: afinidade de execução

A fase v1 mantém a seleção explícita de backend por rota. Em releases posteriores, o `ollama-sessiond` deverá introduzir seleção automática entre backends elegíveis, considerando diferentes formas de afinidade:

- **afinidade de sessão:** manter, preferencialmente, uma conversa no backend já utilizado;
- **afinidade de modelo:** direcionar cada modelo aos backends compatíveis ou definidos por política;
- **afinidade de capacidade:** considerar memória disponível, arquitetura, carga, latência, throughput e estado de saúde;
- **afinidade de residência:** preferir o backend em que o modelo já esteja carregado em RAM ou VRAM.

A afinidade será tratada como preferência, não como restrição absoluta. Compatibilidade, capacidade disponível e failover terão precedência quando o backend preferencial não puder atender à requisição.

Inicialmente, a residência do modelo poderá ser registrada apenas como metadado para orientar o roteamento. Em uma fase posterior, esse mecanismo poderá evoluir para gerenciamento ativo de cache, com políticas de retenção, descarregamento, prefetch e eventual replicação de modelos entre backends equivalentes.

Consulte [`ARCHITECTURE.md`](ARCHITECTURE.md) e [`ROADMAP.md`](ROADMAP.md) para a evolução planejada do `ollama-sessiond`.

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