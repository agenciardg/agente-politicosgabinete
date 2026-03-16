# Deploy no Portainer - Repositorio Privado

## Repositorio

URL: https://github.com/agenciardg/agentepolitico-gabinete.git
Branch: main
Visibilidade: Privado

---

## Passo 1: Criar Personal Access Token no GitHub

1. Acesse: GitHub > Settings > Developer settings > Personal access tokens > Fine-grained tokens
2. Clique "Generate new token"
3. Nome: "Portainer Deploy"
4. Expiration: escolha (90 dias ou sem expiracao)
5. Resource owner: agenciardg
6. Repository access: "Only select repositories" > selecione "agentepolitico-gabinete"
7. Permissions:
   - Contents: Read-only
   - Metadata: Read-only
8. Clique "Generate token"
9. COPIE O TOKEN (so aparece uma vez)

---

## Passo 2: Configurar Stack no Portainer

1. Acesse o Portainer: http://217.79.180.230:9000
2. Va em Stacks > Add Stack
3. Selecione "Repository"
4. Preencha:

| Campo | Valor |
|-------|-------|
| Name | agentepolitico-gabinete |
| Repository URL | https://github.com/agenciardg/agentepolitico-gabinete |
| Repository reference | refs/heads/main |
| Compose path | docker-compose.prod.yml |
| Authentication | ON |
| Username | agenciardg |
| Personal Access Token | (cole o token do passo 1) |
| GitOps updates | ON (opcional - atualiza automatico) |

---

## Passo 3: Environment Variables

Adicione as variaveis de ambiente (mesmas do portainer.env):

| Variavel | Valor |
|----------|-------|
| SUPABASE_URL | https://kfhenndnrbbvlwengrtw.supabase.co |
| SUPABASE_KEY | (sua service key) |
| SUPABASE_DB_URL | (sua connection string) |
| POSTGRES_HOST | 217.79.180.230 |
| POSTGRES_PORT | 5432 |
| POSTGRES_DB | postgres |
| POSTGRES_USER | postgres |
| POSTGRES_PASSWORD | 5d3dd65370a0efcd1004c570d4d8de27 |
| JWT_SECRET | (seu secret) |
| GROK_API_KEY | (chave xAI) |
| GROK_MODEL | grok-4-1-fast-non-reasoning |
| HELENA_API_TOKEN | (token Helena) |
| HELENA_BOT_NUMBER | (numero do bot) |

Ou use "Load variables from .env file" e carregue o portainer.env

---

## Passo 4: Deploy

1. Clique "Deploy the stack"
2. Aguarde o Portainer clonar o repo e subir os containers
3. Verifique os logs dos containers para erros

---

## Atualizando apos mudancas

### Opcao A: GitOps automatico
Se habilitou "GitOps updates", o Portainer verifica o repo periodicamente e atualiza sozinho.

### Opcao B: Manual
1. Va em Stacks > agentepolitico-gabinete
2. Clique "Pull and redeploy"

### Opcao C: Rebuild de imagens
Se mudou o codigo (nao so o compose), precisa rebuildar as imagens Docker:

```bash
# No servidor ou via CI/CD
docker build -t ghcr.io/agenciardg/agentepolitico-gabinete/api:latest .
docker build -t ghcr.io/agenciardg/agentepolitico-gabinete/admin:latest ./admin
docker push ghcr.io/agenciardg/agentepolitico-gabinete/api:latest
docker push ghcr.io/agenciardg/agentepolitico-gabinete/admin:latest
```

Depois faca "Pull and redeploy" no Portainer.

---

## IMPORTANTE: Imagens Docker

O docker-compose.prod.yml usa imagens pre-construidas do GHCR:
- ghcr.io/agenciardg/agente-politicosgabinete/api:latest
- ghcr.io/agenciardg/agente-politicosgabinete/admin:latest

Se quiser que o Portainer faca build direto do codigo (sem GHCR), troque o compose para usar "build" ao inves de "image":

```yaml
services:
  agent-api:
    build:
      context: .
      dockerfile: Dockerfile
    # ... resto igual

  admin:
    build:
      context: ./admin
      dockerfile: Dockerfile
    # ... resto igual
```

---

## Verificacao

Apos deploy, teste:
- API: http://217.79.180.230:8010/api/v1/health
- Admin: http://217.79.180.230:3010
