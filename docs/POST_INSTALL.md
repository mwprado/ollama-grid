# Pós-instalação: firewall e SELinux

Este procedimento é **manual**, após instalar `ollama-grid-balancer` e os backends necessários. O RPM não abre portas no firewall nem modifica automaticamente as políticas SELinux.

## 1. Isolar as portas dos backends

Os processos Ollama devem escutar **somente em loopback** (`127.0.0.1`), com as portas correspondentes:

| Porta TCP | Serviço | Exposição recomendada |
| --- | --- | --- |
| 11434 | CPU (escrita no model store e backup) | Somente loopback |
| 11435 | Vulkan | Somente loopback |
| 11436 | ROCm | Somente loopback |
| 11437 | CUDA 12.9 | Somente loopback |
| 11438 | CUDA 13 | Somente loopback |
| 8080 | Nginx / API do Ollama-Grid | Rede autorizada, se necessário |

Confira os listeners:

```bash
sudo ss -lntp | grep -E ':(8080|1143[4-8])\b'
```

Se um backend estiver escutando em `0.0.0.0` ou em um IP externo, ajuste seu `OLLAMA_HOST` para `127.0.0.1:<porta>` antes de expor o serviço. **O Nginx não protege requisições feitas diretamente às portas dos backends.**

## 2. firewalld (Fedora / sistemas com firewalld)

Verifique se o firewalld está ativo e identifique a zona da interface pela qual os clientes chegam:

```bash
sudo firewall-cmd --state
sudo firewall-cmd --get-active-zones
sudo firewall-cmd --zone=public --list-all
```

**Substitua `public` pela zona correta.** Se a API precisa ser acessada pela rede e a zona estiver adequadamente restrita, permita somente o frontend:

```bash
sudo firewall-cmd --permanent --zone=public --add-port=8080/tcp
sudo firewall-cmd --reload
```

Para remover eventuais permissões *explícitas de porta* dos backends nessa zona:

```bash
for port in 11434 11435 11436 11437 11438; do
    sudo firewall-cmd --permanent --zone=public --remove-port="${port}/tcp"
done
sudo firewall-cmd --reload
sudo firewall-cmd --zone=public --list-all
```

A remoção acima não substitui uma auditoria de serviços liberados, regras ricas, políticas, outras zonas ou regras externas. `firewalld` também não é uma barreira para acesso local a `127.0.0.1`.

**Se a API deve ser somente local, não abra a porta 8080 no firewall**; restrinja também o `listen` do Nginx a `127.0.0.1:8080`. Para acesso externo, considere limitar a origem a uma sub-rede confiável e usar TLS/autenticação, especialmente em redes não confiáveis.

## 3. SELinux (Nginx retornando 502)

No modo `Enforcing`, o SELinux pode bloquear conexões do Nginx aos serviços Ollama, inclusive em `127.0.0.1`. Um sintoma confirmado é:

```text
connect() to 127.0.0.1:11434 failed (13: Permission denied) while connecting to upstream
```

Diagnostique antes de alterar a política:

```bash
getenforce
getsebool httpd_can_network_connect
sudo tail -n 30 /var/log/nginx/error.log
sudo ausearch -m AVC -ts recent
```

Se o Nginx realmente estiver sofrendo negações de conexão e a boolean estiver `off`, habilite-a persistentemente:

```bash
sudo setsebool -P httpd_can_network_connect on
getsebool httpd_can_network_connect
```

Isso **não desativa o SELinux** e não exige reiniciar o Nginx. Contudo, `httpd_can_network_connect` é uma autorização **ampla para conexões de rede dos processos abrangidos pela política HTTPD**, não apenas para as cinco portas locais do Ollama-Grid. Em instalações com requisitos de isolamento mais rígidos, prefira desenvolver e auditar uma política SELinux específica para o serviço.

## 4. Validar

Com ao menos um backend ativo:

```bash
sudo nginx -t
curl -i http://127.0.0.1:8080/api/version
curl -i http://127.0.0.1:8080/api/tags
```

Para verificar as rotas explícitas, use somente os backends efetivamente ativos:

```bash
curl -i http://127.0.0.1:8080/cpu/api/version
curl -i http://127.0.0.1:8080/cuda12/api/version
```

Se ocorrer `502 Bad Gateway`, consulte `/var/log/nginx/error.log`: `Permission denied (13)` indica possível negação SELinux; `Connection refused (111)` indica tentativa contra uma porta sem listener; `no live upstreams` indica que o Nginx considera os destinos do upstream indisponíveis.

## 5. Limites da política de escrita

O Nginx encaminha `/api/pull`, `/api/create`, `/api/copy`, `/api/delete`, `/api/push` e `/api/blobs/...` para a CPU, de acordo com `/etc/ollama-grid/nginx/write-policy.conf`. Operações de inferência usam GPUs prioritariamente e CPU como backup.

Essas regras só valem para clientes que passam pela porta 8080. **Firewalls, binding em loopback e redirecionamento no Nginx não impedem que processos locais autorizados chamem diretamente a API de outro backend**. Centralizar o escritor no proxy também não substitui as garantias de atomicidade e integridade fornecidas pelo Ollama.

> Nota de empacotamento: as alterações acima são decisões de administração do sistema e não são aplicadas por `%post` no RPM. Arquivos Nginx empacotados como `%config(noreplace)` podem gerar `.rpmnew` durante upgrades; confira-os antes de recarregar o serviço.
