# Analise dos Squads e Recomendacoes para o Projeto

**Data:** 2026-03-14
**Referencia:** ESCOPO-SISTEMA-MULTITENANT.md v3.0

Este documento apresenta a analise de cada squad relevante sobre o projeto, o que eles trazem de valor, o que pode ser mudado, e ideias adicionais.

---

## 1. Correcao Importante: Fluxo de Criacao do Card

Antes das recomendacoes dos squads, preciso alinhar um ponto critico que voce mencionou. Analisei novamente o repositorio original e o fluxo exato de criacao do card e:

### Como funciona hoje (repositorio original):

```
1. Transfere sessao de chat para o departamento correto
   PUT /chat/v1/session/{session_id}/transfer
   Body: { type: "DEPARTMENT", newDepartmentId: "uuid" }

2. Busca campos customizados do painel destino
   GET /crm/v1/panel/{panel_id}/custom-fields?NestedList=true
   -> Retorna lista de { id, name, key, type }

3. Duplica o card original para o painel destino
   POST /crm/v1/panel/card/{card_id}/duplicate
   Body: { copyToStepId: "step_uuid", options: { fields: ["All"], archiveOriginalCard: true } }
   -> Arquiva o card original

4. Atualiza o card duplicado com TODOS os dados:
   PUT /crm/v1/panel/card/{new_card_id}
   Body: {
     fields: ["Title", "Description", "ContactIds", "DueDate", "TagIds", "CustomFields"],
     title: "Joao Silva",                    <- NOME DO CONTATO
     description: "Problema com iluminacao", <- DESCRICAO DA CLASSIFICACAO
     contactIds: ["contact-uuid"],           <- ID DO CONTATO VINCULADO AO CARD
     dueDate: "2024-12-25T15:30:45+00:00",  <- AGORA + 24 HORAS
     tagNames: ["Zeladoria", "media", "whatsapp"],  <- CATEGORIA + URGENCIA + "whatsapp"
     customFields: {
       "field_key_solicitacao": "Iluminacao publica",
       "field_key_manifestacao": "Problema rua escura",
       "field_key_desc_manifestacao": "Resumo completo da conversa...",
       "field_key_cpf": "12345678901",
       "field_key_email": "joao@email.com",
       "field_key_cep": "01001-000",
       "field_key_endereco": "Rua X, 123",
       "field_key_bairro": "Centro",
       "field_key_cidade": "Sao Paulo",
       "field_key_estado": "SP",
       "field_key_data_nascimento": "15/03/1990",
       "field_key_data_cadastro": "14/03/2026",
       "field_key_nome_completo": "Joao Silva"
     }
   }

5. Adiciona tag de categoria no contato
   POST /core/v1/contact/phonenumber/{phone}/tags
   Body: { tagNames: ["Zeladoria"] }
```

### O que isso significa para o multi-tenant:

O mapeamento de campos no escopo (secao 4.1.6) esta correto, mas precisa garantir que o card SEMPRE tenha:

| Campo fixo | Origem | Obrigatorio |
|---|---|---|
| **title** | Nome do contato (`contact_data.name`) | SIM |
| **description** | Descricao da classificacao | SIM |
| **contactIds** | ID do contato no Helena | SIM |
| **dueDate** | Data atual + 24h (configuravel por tenant) | SIM |
| **tagNames** | Nome do painel + urgencia + "whatsapp" | SIM |

Esses campos sao **fixos do sistema** — o admin NAO configura. O que o admin configura sao os **customFields** (mapeamento de campos do card).

**Isso ja esta no escopo v3.0, mas quero deixar explicito que o titulo do card = nome do contato e o contactId e sempre vinculado automaticamente.**

---

## 2. Analise do Squad: api-development

### O que ele faz
Pipeline completo de API REST: design OpenAPI 3.0 -> implementacao CRUD -> documentacao Swagger -> testes -> monitoramento. Usa TypeScript, Express, Zod, Prisma.

### Relevancia para o projeto: MEDIA

**Problema:** O squad usa stack **TypeScript/Express/Prisma**, mas o projeto atual e **Python/FastAPI/SQLAlchemy**. Nao faz sentido trocar a stack do backend.

**O que aproveitar:**
- **Padrao de design API-first** — Criar spec OpenAPI 3.0 da API admin ANTES de implementar
- **Validacao com Zod** — Equivalente: usar **Pydantic** no FastAPI (ja nativo)
- **Documentacao Swagger** — FastAPI ja gera automaticamente, mas podemos estruturar melhor
- **Monitoramento de performance** — Metricas de latencia por tenant (p50/p95/p99) e boa ideia

### Recomendacao
**NAO usar este squad para implementar**, pois a stack nao bate. Porem, adotar os **padroes de design**:
- Criar spec OpenAPI da API admin antes de codar
- Usar Pydantic para validacao de todos os inputs
- Adicionar metricas de latencia por tenant como feature futura

---

## 3. Analise do Squad: nirvana-backend

### O que ele faz
10 agentes que cobrem o ciclo completo de backend: analise de frontend, arquitetura, banco de dados, API, auth, integracao, infra Docker, testes, qualidade. Usa Hono, Drizzle, Supabase self-hosted, Redis, MinIO, Caddy.

### Relevancia para o projeto: ALTA (parcial)

**Problema:** Stack diferente (Hono/Drizzle vs FastAPI/SQLAlchemy), mas os **padroes e agentes** sao muito uteis.

### O que aproveitar (por agente):

| Agente | Aproveitamento | Como aplicar |
|---|---|---|
| **VisionArchitect** | Brainstorm de arquitetura | Avaliar trade-offs (monolito vs microservicos, SQL vs JSONB config) |
| **SystemArchitect** | Design de arquitetura | Definir camadas, contratos de API, ADRs (Architecture Decision Records) |
| **DatabaseEngineer** | Schema + migrations | Criar migrations versionadas, indexes otimizados, RLS se usar Supabase |
| **AuthSecurity** | Auth + RBAC | Implementar JWT + RBAC (super_admin/tenant_admin) |
| **InfraEngineer** | Docker + deploy | Docker multi-stage, docker-compose prod, CI/CD |
| **TestEngineer** | Testes | Testes de integracao da API admin + testes do agente |
| **QualitySentinel** | Auditoria final | Revisar codigo, performance, seguranca antes de deploy |

### Recomendacoes deste squad para o projeto:

1. **ADRs (Architecture Decision Records)** — Documentar decisoes como:
   - "Por que PostgreSQL e nao MongoDB para config?"
   - "Por que ENUM em vez de JSONB para config de tenant?"
   - "Por que cache em memoria e nao Redis para lookup de tenant?"

2. **Indexes explicitamente planejados:**
   ```sql
   CREATE INDEX idx_assessor_lookup ON assessor_numbers(tenant_id, phone_number, active);
   CREATE INDEX idx_agent_panels_active ON tenant_agent_panels(agent_id, active);
   CREATE INDEX idx_contact_fields_active ON tenant_agent_contact_fields(agent_id, active);
   ```

3. **Migrations versionadas** em vez de rodar SQL direto:
   ```
   migrations/
   ├── 001_create_tenants.sql
   ├── 002_create_agents.sql
   ├── 003_create_panels.sql
   ├── 004_create_fields.sql
   └── 005_create_admin_users.sql
   ```

4. **Docker multi-stage** (ja no escopo, mas detalhar):
   ```
   Stage 1: Builder (instala deps, compila)
   Stage 2: Runtime (copia apenas o necessario, roda como non-root)
   ```

5. **Health check por tenant** — Alem do health geral, ter endpoint que verifica se o token Helena de cada tenant ainda e valido.

---

## 4. Analise do Squad: saas-onboarding-activator

### O que ele faz
5 agentes focados em ativacao de usuarios SaaS: tracking comportamental, checklists personalizados, identificacao de "aha moments", tooltips contextuais, outreach proativo.

### Relevancia para o projeto: ALTA (para o painel admin)

O sistema multi-tenant e essencialmente um **SaaS B2B** — cada gabinete e um "cliente" que precisa ser onboardado. O squad traz insights valiosos.

### Recomendacoes para o projeto:

#### 4.1 Checklist de Onboarding no Painel Admin

Quando o admin cria um novo tenant, mostrar um checklist visual de progresso:

```
+----------------------------------------------------------------------+
| Configuracao do Gabinete                        Progresso: 40%       |
+----------------------------------------------------------------------+
|                                                                      |
| [x] 1. Token Helena inserido                                        |
| [x] 2. Sincronizacao realizada                                      |
| [ ] 3. Prompt da persona configurado                                |
| [ ] 4. Pelo menos 1 painel ativado com descricao                   |
| [ ] 5. Campos de coleta configurados                                |
| [ ] 6. Mapeamento de campos do card feito                          |
| [ ] 7. Tenant ativado                                                |
|                                                                      |
| Proximo passo: Configure o prompt da persona do agente               |
+----------------------------------------------------------------------+
```

**Por que:** Reduz drasticamente o risco de ativacao incompleta. O admin sabe exatamente o que falta.

#### 4.2 Validacao Pre-Ativacao

Antes de permitir ativar o tenant, o sistema valida:
- Token Helena funciona? (faz GET /v1/panel de teste)
- Pelo menos 1 painel ativo com descricao preenchida?
- Prompt da persona nao esta vazio?
- Pelo menos 1 campo de coleta ativo?
- Mapeamento de campos do card configurado nos paineis ativos?

Se faltar algo, mostra aviso claro do que precisa ser feito.

#### 4.3 Template de Configuracao Rapida

Oferecer "templates" pre-configurados para acelerar o onboarding:

```
+----------------------------------------------------------------------+
| Iniciar com Template                                                 |
+----------------------------------------------------------------------+
|                                                                      |
| [Gabinete de Vereador]  — 6 paineis padrao, prompt generico         |
| [Gabinete de Deputado]  — 8 paineis padrao, prompt generico         |
| [Configuracao Manual]   — Comecar do zero                           |
|                                                                      |
+----------------------------------------------------------------------+
```

O template pre-preenche:
- Prompt da persona (generico, admin so troca o nome)
- Prompt de comportamento (regras padrao)
- Descricoes dos paineis padrao (saude, educacao, zeladoria, etc.)
- Campos de coleta padrao (email, cpf, cep, endereco)

Admin so precisa:
1. Colar o token Helena
2. Sincronizar
3. Ajustar o nome do politico no prompt
4. Mapear paineis sincronizados com os do template
5. Ativar

**Tempo de onboarding: de 15 para 5 minutos.**

#### 4.4 Metricas de Uso por Tenant (futuro)

Dashboard no Super Admin com:
- Atendimentos por dia/semana/mes
- Taxa de transferencia por painel (para onde mais transfere)
- Taxa de coleta de dados (% de contatos completos)
- Tempo medio de conversa ate transferencia

---

## 5. Analise do Squad: fabrica-de-genios

### O que ele faz
Pipeline industrial de 5 estagios que transforma conhecimento bruto (videos, PDFs, transcricoes) em "mind-clones" de IA — agentes autonomos com personalidade, DNA de conhecimento, playbooks e capacidade de deliberacao. 36 agentes em 5 squads.

### Relevancia para o projeto: BAIXA (por enquanto)

**Por que baixa:** O sistema multi-tenant nao precisa criar "mind-clones" de politicos. O agente e generico (recebe prompt configuravel) e nao replica a personalidade do vereador/deputado.

### Onde PODERIA ser util no futuro:

Se um gabinete quiser um agente que **fale como o vereador** (tom de voz, expressoes, posicionamento politico), o Fabrica de Genios poderia:

1. Processar discursos, entrevistas, posts do politico
2. Extrair o "DNA" de comunicacao dele (5 camadas)
3. Gerar um SOUL.md que define como o agente se comunica
4. Esse SOUL.md seria usado como prompt da persona no sistema

**Mas isso e feature avancada para o futuro, nao para o MVP.**

### Recomendacao
**NAO usar agora.** Guardar como possibilidade futura de "agente personalizado premium" — onde o gabinete paga mais para ter um agente que fala exatamente como o politico.

---

## 6. Analise do Squad: nirvana-squad-creator

### O que ele faz
Gera squads AIOS completos a partir de linguagem natural. Pipeline de 9 fases: analise, criacao de agentes, tasks, workflows, otimizacao, validacao, README multi-idioma, deploy.

### Relevancia para o projeto: POSSIVEL (para criar squad customizado)

### Ideia: Criar um squad especifico para este projeto

Podemos usar o nirvana-squad-creator para gerar um **squad "agente-gabinete-builder"** que automatize a construcao do sistema. O prompt seria algo como:

```
"Crie um squad para construir um sistema multi-tenant de agentes de gabinete
politico com integracao Helena CRM. O squad deve ter agentes especializados em:
- Schema de banco multi-tenant com PostgreSQL
- API admin FastAPI com auth JWT
- Sincronizacao automatica com Helena CRM
- Refatoracao de agente LangGraph para config dinamica
- Frontend admin Next.js
- Testes de integracao
- Docker e deploy"
```

**O que ele geraria:**
- 6-8 agentes especializados (SchemaArchitect, ApiBuilder, HelenaIntegrator, AgentRefactorer, FrontendBuilder, TestEngineer, etc.)
- Tasks com contratos de entrada/saida explicitos
- Workflow sequencial/paralelo otimizado
- Config de tech stack, coding standards
- README em 6 idiomas

### Recomendacao
**POSSIVEL usar**, mas nao e obrigatorio. O projeto pode ser construido sem um squad dedicado — os squads existentes (nirvana-backend para infra, api-development para padroes) ja cobrem as necessidades. Criar um squad dedicado so vale a pena se voce planeja **replicar** esse tipo de projeto para outros clientes alem de gabinetes.

---

## 7. Sugestoes Adicionais (nao cobertas no escopo atual)

### 7.1 Mensagens de Midia (Imagens, Audio, Documentos)

O escopo atual so trata mensagens de texto. O que acontece quando o cidadao manda:
- Foto de um buraco na rua?
- Audio descrevendo o problema?
- PDF de um documento?

**Sugestao:** No MVP, o agente responde: "Recebi seu arquivo. Por favor, descreva por texto o que voce precisa para que eu possa encaminhar corretamente." E armazena o arquivo como anexo no card.

### 7.2 Historico de Conversas

O escopo nao menciona visualizacao de conversas no painel admin. Pode ser util para:
- Admin ver como o agente esta atendendo
- Identificar problemas de prompt
- Treinar o agente com exemplos reais

**Sugestao:** Endpoint `GET /api/v1/admin/tenants/{id}/conversations` que busca historico do LangGraph checkpoints. Feature futura.

### 7.3 Modo de Teste

Antes de ativar o tenant em producao, o admin deveria poder:
- Enviar mensagem de teste simulando um cidadao
- Ver como o agente responde
- Verificar se a classificacao esta correta
- Testar se o card e criado no painel certo

**Sugestao:** Endpoint `POST /api/v1/admin/tenants/{id}/test-message` que simula uma conversa sem enviar via WhatsApp.

### 7.4 Duplicacao de Tenant (Clone)

Quando gabinetes tem configuracao parecida, seria util:
- Clonar tenant existente
- Mudar apenas nome, token Helena, e prompt da persona
- Manter paineis, campos, mapeamentos como base

**Sugestao:** Botao "Duplicar Tenant" no dashboard.

### 7.5 Logs de Erros por Tenant

Dashboard de erros no painel do Super Admin:
- Falhas de API Helena (por tenant)
- Erros de LLM
- Cards nao criados
- Transferencias falhas

**Sugestao:** Tabela `tenant_error_logs` com timestamp, tipo, mensagem, tenant_id. Exibir no dashboard.

### 7.6 Due Date Configuravel

Hoje o card tem due date de 24h fixo. No multi-tenant, cada gabinete pode querer tempo diferente:
- Urgencia alta: 12h
- Urgencia media: 24h
- Urgencia baixa: 48h

**Sugestao:** Adicionar campos `due_hours_high`, `due_hours_medium`, `due_hours_low` na tabela `tenants`.

---

## 8. Resumo: O que implementar e o que NAO implementar

### IMPLEMENTAR NO MVP (Fase 1-6 do escopo):

| Item | Fonte |
|---|---|
| Checklist de onboarding visual | saas-onboarding-activator |
| Validacao pre-ativacao | saas-onboarding-activator |
| Templates de configuracao rapida | saas-onboarding-activator |
| Migrations versionadas | nirvana-backend |
| Indexes explicitos | nirvana-backend |
| Docker multi-stage | nirvana-backend |
| Card com title=nome, contactId vinculado | Repositorio original |
| Campos fixos do card (title, description, contactIds, dueDate, tags) | Repositorio original |

### IMPLEMENTAR DEPOIS DO MVP:

| Item | Fonte | Prioridade |
|---|---|---|
| Modo de teste (simular conversa) | Analise propria | Alta |
| Metricas de uso por tenant | saas-onboarding-activator | Media |
| Logs de erros por tenant | Analise propria | Media |
| Due date configuravel por urgencia | Analise propria | Media |
| Duplicacao de tenant (clone) | Analise propria | Baixa |
| Historico de conversas no admin | Analise propria | Baixa |
| Tratamento de midia (foto, audio) | Analise propria | Baixa |
| Health check de token por tenant | nirvana-backend | Baixa |

### NAO IMPLEMENTAR (desnecessario agora):

| Item | Motivo |
|---|---|
| Trocar stack para TypeScript/Express | Projeto ja e Python/FastAPI, funciona bem |
| Fabrica de Genios / mind-clones | Feature premium futura, nao MVP |
| Criar squad customizado | Projeto pode ser construido sem squad dedicado |
| Marketplace de mind-clones | Totalmente fora do escopo |
| Supabase self-hosted | Complexidade desnecessaria, PostgreSQL direto e suficiente |

---

## 9. Conclusao

Os squads mais uteis para o projeto sao:
1. **saas-onboarding-activator** — Traz padroes de UX que simplificam o onboarding de novos gabinetes (checklist, validacao, templates)
2. **nirvana-backend** — Traz padroes de infra e qualidade (migrations, indexes, Docker, testes)
3. **api-development** — Traz padroes de design de API (OpenAPI first, validacao, docs)

Os outros squads (fabrica-de-genios, nirvana-squad-creator) sao interessantes mas nao necessarios para o MVP.

**O escopo v3.0 esta solido.** As principais adicoes recomendadas sao:
- Checklist de onboarding no painel
- Validacao pre-ativacao
- Templates de configuracao rapida
- Modo de teste
- Campos fixos do card explicitamente documentados

---

*Documento de recomendacoes baseado na analise de 5 squads. Referencia: ESCOPO-SISTEMA-MULTITENANT.md v3.0*
