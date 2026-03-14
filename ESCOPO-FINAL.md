# ESCOPO FINAL — Sistema Multi-Tenant de Agentes de Gabinete

**Versao:** 1.0 FINAL
**Data:** 2026-03-14
**Status:** Aprovado para construcao

---

## PARTE 1 — O SISTEMA

---

## 1. Visao Geral

Sistema multi-tenant de agentes de gabinete politico (vereadores, deputados) com:
- Painel Super Admin para configuracao de tenants
- Dois agentes por tenant (Principal + Assessor)
- Integracao completa com CRM Helena
- Follow-up automatico com temporizacao
- Conclusao automatica de atendimento
- Metricas de uso por tenant
- Dados de configuracao no **Supabase (projeto RDG)**
- Dados de memoria/checkpoint no **PostgreSQL dedicado** (mesmo padrao do repo original)

---

## 2. Infraestrutura de Banco de Dados

### 2.1 Supabase RDG (Configuracao e Admin)

**Projeto:** `kfhenndnrbbvlwengrtw` (MCP `supabase-rdg`)

Armazena:
- Tabelas de tenants, agentes, paineis, campos, mapeamentos
- Usuarios admin (super_admin, tenant_admin)
- Metricas de atendimento
- Logs de erro
- Tudo que e configuracao/instrucao

### 2.2 PostgreSQL Dedicado (Memoria do Agente)

**Host:** `217.79.180.230:5432` (MCP `postgres`)

Armazena:
- Tabelas do LangGraph (checkpoints, writes, messages, sessions)
- Estado de conversa por tenant
- Fila de follow-up pendentes
- Mesmo padrao do repositorio original — nao muda

### 2.3 Por que dois bancos?

| Supabase RDG | PostgreSQL Dedicado |
|---|---|
| Configuracao, prompts, mapeamentos | Estado de conversa, checkpoints |
| Leitura frequente, escrita rara | Leitura e escrita a cada mensagem |
| Cache em memoria (TTL 5min) | Acesso direto sem cache |
| Admin panel consome | Agente LangGraph consome |
| Dados estáveis | Dados voláteis |

---

## 3. Arquitetura

```
                    +----------------------------------+
                    |        PAINEL SUPER ADMIN         |
                    |         (Next.js)                 |
                    +--------------+-------------------+
                                   |
                                   v
+---------+    +---------+    +----------------------+    +------------+    +-------------+
| WhatsApp |--->| Helena  |--->|   API Multi-Tenant   |--->| Supabase   |    | PostgreSQL  |
|          |<---| CRM     |<---|   (FastAPI)          |    | RDG        |    | Dedicado    |
+---------+    +---------+    +----------+-----------+    | (config)   |    | (memoria)   |
                    ^                    |                 +------------+    +-------------+
                    |         +----------+----------+
                    |         |          |          |
                    |   +-----v----+ +---v------+ +-v--------+
                    |   | AGENTE   | | AGENTE   | | CRON     |
                    +---| PRINCIP. | | ASSESSOR | | FOLLOW-UP|
                        +----------+ +----------+ +----------+
```

### 3.1 Recebimento de Mensagens

Webhook HTTP do n8n, mesmo formato do repo original + campo `tenant_slug`:

```json
{
  "mensagem": "Texto da mensagem",
  "numero": "+5511999999999",
  "sessionID": "uuid-da-sessao-helena",
  "card_id": "uuid-do-card-helena",
  "tenant_slug": "andre-santos"
}
```

- Identificacao do tenant: `SELECT * FROM agentpolitico_tenants WHERE slug = tenant_slug AND active = true` (cache 5min)
- Roteamento: numero na tabela `agentpolitico_assessor_numbers`? → Agente Assessor. Senao → Agente Principal.

### 3.2 Envio de Respostas

Direto via Helena API:
```
POST /chat/v1/message/send-sync
```
Retorna `already_sent: true` ao n8n para nao reenviar.

### 3.3 Conclusao de Atendimento

**Novo (nao existe no repo original).** O atendimento so e concluido em UMA situacao: apos o 3o follow-up por inatividade do cidadao.

```
PUT /chat/v1/session/{session_id}/complete
```

**IMPORTANTE:**
- Transferencia de atendimento para equipe **NAO conclui** o atendimento no CRM
- Follow-up 1 e 2 **NAO concluem** o atendimento
- Somente o follow-up 3 (encerramento) conclui o atendimento no CRM
- Isso fecha a conversa no CRM Helena, marcando como concluida

### 3.4 Limpeza de Memoria (PostgreSQL)

A memoria da conversa (checkpoints, writes do LangGraph) e limpa em DOIS momentos:

1. **Apos transferencia para equipe** — o agente transfere, cria o card, envia despedida, e limpa a memoria. Se o cidadao mandar nova mensagem, inicia conversa do zero.
2. **Apos 3o follow-up (conclusao)** — o sistema envia o 3o follow-up, conclui o atendimento no CRM, e limpa a memoria. Se o cidadao mandar nova mensagem depois, inicia conversa do zero.

**NAO limpa memoria:**
- Durante follow-up 1 ou 2 (a conversa ainda esta ativa, cidadao pode retomar)
- Enquanto houver interacao ativa entre agente e cidadao

---

## 4. Fluxo Completo do Agente Principal

### 4.1 ETAPA 1 — Coleta de Dados do Contato

```
1. Busca contato: GET /core/v1/contact/phonenumber/{phone}
2. Carrega campos ativos do banco (Supabase)
3. Compara com dados do contato → identifica vazios
4. Se todos preenchidos → ETAPA 2
5. Se faltam → coleta UM POR VEZ, pausadamente
6. Ao final → confirma com cidadao
7. Salva: PUT /core/v1/contact/phonenumber/{phone}
```

### 4.2 ETAPA 2 — Classificacao da Demanda

```
1. Carrega paineis ativos + descricoes (Supabase)
2. Monta prompt dinamico com categorias
3. Conversa ate entender a demanda
4. Classifica: { painel, descricao, resumo, urgencia }
```

### 4.3 ETAPA 3 — Transferencia + Criacao do Card

```
1. Transfere sessao:
   PUT /chat/v1/session/{session_id}/transfer
   Body: { type: "DEPARTMENT", newDepartmentId: "uuid" }

2. Busca campos customizados do painel destino:
   GET /crm/v1/panel/{panel_id}/custom-fields?NestedList=true

3. Duplica card para painel destino:
   POST /crm/v1/panel/card/{card_id}/duplicate
   Body: { copyToStepId: "step_uuid", options: { fields: ["All"], archiveOriginalCard: true } }

4. Atualiza card duplicado:
   PUT /crm/v1/panel/card/{new_card_id}
   Body: {
     fields: ["Title","Description","ContactIds","DueDate","TagIds","CustomFields"],
     title: "<NOME DO CONTATO>",
     description: "<DESCRICAO DA CLASSIFICACAO>",
     contactIds: ["<ID DO CONTATO>"],
     dueDate: "<DATA/HORA ATUAL + 24 HORAS (tz America/Sao_Paulo)>",
     tagNames: ["<NOME_PAINEL>", "<URGENCIA>", "whatsapp"],
     customFields: { ... mapeados conforme config do admin ... }
   }

5. Adiciona tag no contato:
   POST /core/v1/contact/phonenumber/{phone}/tags

6. Envia mensagem de despedida

7. Limpa memoria do LangGraph (checkpoints, writes) deste numero/tenant
   -> Cidadao manda nova mensagem = conversa nova do zero

NOTA: A transferencia NAO conclui o atendimento no CRM.
      A conclusao so acontece apos o 3o follow-up por inatividade.
```

#### Campos fixos do card (automaticos, admin NAO configura):

| Campo | Valor | Origem |
|---|---|---|
| **title** | Nome do contato | `contact_data.name` |
| **description** | Descricao da classificacao | `classification.descricao` |
| **contactIds** | ID do contato Helena | `contact_data.id` |
| **dueDate** | Data/hora atual + 24 horas (tz America/Sao_Paulo) | Calculado |
| **tagNames** | [nome_painel, urgencia, "whatsapp"] | Classificacao |

#### Campos customizados do card (admin configura o mapeamento):

Cada campo do card do painel tem uma instrucao do admin dizendo "o que armazenar". O agente preenche de acordo.

---

## 5. Follow-Up Automatico (NOVO)

### 5.1 Como funciona

Quando o cidadao para de responder durante a conversa (em qualquer etapa), o sistema envia follow-ups automaticos:

```
Cidadao manda mensagem
    |
    v
Agente responde e aguarda
    |
    ... 20 minutos sem resposta ...
    |
    v
FOLLOW-UP 1: Mensagem contextual lembrando da conversa
    "Oi [nome], ainda estou aqui! Voce gostaria de continuar
     com [contexto da conversa]?"
    |
    ... 1 hora sem resposta (da ultima mensagem do follow-up 1) ...
    |
    v
FOLLOW-UP 2: Segunda tentativa
    "Ola [nome], vi que voce nao conseguiu continuar.
     Estou a disposicao quando quiser retomar."
    |
    ... 1 hora sem resposta ...
    |
    v
FOLLOW-UP 3: Encerramento (gerado pelo LLM com base no prompt do admin)
    "Ola [nome], como nao tivemos retorno, estou encerrando
     este atendimento. O gabinete do [nome do politico] esta
     sempre a disposicao. E so mandar mensagem quando precisar!"
    |
    v
Conclui atendimento:
    PUT /chat/v1/session/{session_id}/complete
    Limpa memoria do LangGraph (checkpoints, writes) deste numero/tenant
    -> Cidadao manda nova mensagem = conversa nova do zero
```

### 5.2 Temporizacao

| Follow-up | Tempo apos ultima mensagem | Acao |
|---|---|---|
| 1o | 20 minutos | Lembrete contextual |
| 2o | 1 hora (apos follow-up 1) | Segunda tentativa |
| 3o | 1 hora (apos follow-up 2) | Encerramento + conclusao |

### 5.3 Regras

- O timer **reseta** se o cidadao responder a qualquer momento
- Se o cidadao responder apos follow-up 1 ou 2, a conversa continua normalmente de onde parou
- Se o cidadao responder APOS o follow-up 3 (atendimento concluido), inicia conversa NOVA
- As mensagens de follow-up sao geradas pelo LLM com base em: prompt de follow-up do admin + contexto da conversa + persona do agente
- O admin controla o tom e estilo de cada follow-up via aba "Follow-up" no painel
- Os prompts de follow-up sao editaveis por agente (tabela tenant_agent_followup_prompts)
- Os tempos (20min, 1h, 1h) sao configuráveis por tenant
- **Timezone: America/Sao_Paulo** para todos os calculos de tempo

### 5.4 Implementacao tecnica

```
Tabela: agentpolitico_follow_up_queue (PostgreSQL dedicado)

| Campo | Tipo | Descricao |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK tenants |
| session_id | VARCHAR | ID da sessao Helena |
| phone_number | VARCHAR | Numero do cidadao |
| agent_type | ENUM | principal/assessor |
| follow_up_number | INT | 1, 2 ou 3 |
| scheduled_at | TIMESTAMP | Quando enviar (tz Sao Paulo) |
| status | ENUM | pending/sent/cancelled |
| created_at | TIMESTAMP | |

Cron job: Roda a cada 1 minuto
  -> SELECT * FROM agentpolitico_follow_up_queue WHERE status = 'pending' AND scheduled_at <= NOW()
  -> Para cada registro:
     1. Verifica se cidadao respondeu (checkpoint atualizado?) -> cancela se sim
     2. Se nao respondeu -> gera mensagem via LLM -> envia via Helena
     3. Se follow_up_number = 3 -> conclui atendimento
     4. Se follow_up_number < 3 -> agenda proximo follow-up
```

Quando cidadao manda mensagem:
```
-> Cancela todos os follow-ups pendentes desse numero/tenant
-> UPDATE agentpolitico_follow_up_queue SET status = 'cancelled'
   WHERE tenant_id = X AND phone_number = Y AND status = 'pending'
```

---

## 6. Metricas de Atendimento

### 6.1 Tabela de eventos (Supabase RDG)

```sql
CREATE TABLE agentpolitico_tenant_attendance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id),
    agent_type VARCHAR(20) NOT NULL,         -- 'principal' ou 'assessor'
    phone_number VARCHAR(20) NOT NULL,
    session_id VARCHAR(100),
    event_type VARCHAR(50) NOT NULL,         -- ver tipos abaixo
    panel_name VARCHAR(255),                 -- painel de destino (se transferencia)
    metadata JSONB,                          -- dados extras
    event_date DATE NOT NULL,                -- data do evento (tz Sao Paulo)
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ap_attendance_tenant_date ON agentpolitico_tenant_attendance_events(tenant_id, event_date);
CREATE INDEX idx_ap_attendance_event_type ON agentpolitico_tenant_attendance_events(tenant_id, event_type, event_date);
```

### 6.2 Tipos de evento

| event_type | Quando | metadata |
|---|---|---|
| `conversation_started` | Primeira mensagem do dia de um numero | {} |
| `data_collection_complete` | ETAPA 1 concluida | { fields_collected: 5 } |
| `classification_complete` | ETAPA 2 concluida | { panel: "Saude", urgency: "alta" } |
| `transfer_complete` | ETAPA 3 concluida | { panel: "Saude", department: "Assessores Saude" } |
| `card_created` | Card criado no painel | { card_id: "uuid", panel: "Saude" } |
| `attendance_completed` | Atendimento concluido | { reason: "transferred" ou "follow_up_timeout" } |
| `follow_up_sent` | Follow-up enviado | { follow_up_number: 1 } |
| `follow_up_responded` | Cidadao respondeu apos follow-up | { follow_up_number: 1 } |
| `data_refused` | Cidadao recusou fornecer dados | {} |

### 6.3 Regra de contagem de atendimentos

- **Um atendimento = uma conversa iniciada em um dia**
- Se o cidadao manda 5 mensagens no mesmo dia → 1 atendimento
- Se manda mensagem apos meia-noite (America/Sao_Paulo) → novo atendimento
- Baseado no evento `conversation_started` por dia por numero

### 6.4 Metricas calculadas (exibidas no painel admin)

| Metrica | Calculo | Periodo |
|---|---|---|
| **Atendimentos por dia** | COUNT(conversation_started) GROUP BY event_date | Dia/semana/mes |
| **Atendimentos por semana** | Soma dos diarios | Ultima semana |
| **Atendimentos por mes** | Soma dos diarios | Ultimo mes |
| **Taxa de transferencia por painel** | COUNT(transfer_complete WHERE panel=X) / total | Mes |
| **Taxa de coleta de dados** | COUNT(data_collection_complete) / COUNT(conversation_started) | Mes |
| **Tempo medio ate transferencia** | AVG(transfer_complete.created_at - conversation_started.created_at) | Mes |
| **Taxa de follow-up** | COUNT(follow_up_sent) / COUNT(conversation_started) | Mes |
| **Taxa de retorno apos follow-up** | COUNT(follow_up_responded) / COUNT(follow_up_sent) | Mes |
| **Taxa de abandono** | COUNT(attendance_completed WHERE reason='follow_up_timeout') / total | Mes |

### 6.5 Tela de metricas no admin

```
+----------------------------------------------------------------------+
| Metricas - Gabinete Vereador Andre Santos                            |
+----------------------------------------------------------------------+
|                                                                      |
| Periodo: [Ultima semana v]                                           |
|                                                                      |
| +------------------+  +------------------+  +------------------+     |
| | Atendimentos     |  | Tempo medio      |  | Taxa de coleta   |     |
| |       127        |  |    8 min          |  |      78%         |     |
| | +12% vs anterior |  | -2min vs anterior |  | +5% vs anterior  |     |
| +------------------+  +------------------+  +------------------+     |
|                                                                      |
| Transferencias por painel:                                           |
| +--------------------------------------------------+                 |
| | Saude          ████████████████████  45 (35%)     |                 |
| | Educacao       ████████████         28 (22%)     |                 |
| | Zeladoria      ██████████           22 (17%)     |                 |
| | Juridico       ██████               15 (12%)     |                 |
| | Atend. Geral   █████                12 (9%)      |                 |
| | Outros         ██                    5 (4%)      |                 |
| +--------------------------------------------------+                 |
|                                                                      |
| Follow-ups:                                                          |
| +--------------------------------------------------+                 |
| | Enviados: 34    Retornaram: 21 (62%)              |                 |
| | Abandonos: 13 (38%)                                |                 |
| +--------------------------------------------------+                 |
|                                                                      |
+----------------------------------------------------------------------+
```

---

## 7. Modelo de Dados Completo

### 7.1 Supabase RDG — Tabelas de Configuracao

```sql
-- =============================================
-- USUARIOS DO PAINEL ADMIN
-- =============================================
CREATE TABLE agentpolitico_admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('super_admin', 'tenant_admin')),
    tenant_id UUID REFERENCES agentpolitico_tenants(id),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- TENANTS
-- =============================================
CREATE TABLE agentpolitico_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    helena_api_token TEXT,
    llm_api_key TEXT,
    llm_provider VARCHAR(20) DEFAULT 'grok',
    -- Follow-up config
    followup_1_minutes INT DEFAULT 20,
    followup_2_minutes INT DEFAULT 60,
    followup_3_minutes INT DEFAULT 60,
    -- Due date do card (sempre +24h, fixo)
    due_hours INT DEFAULT 24,
    -- Checkpoint config
    checkpoint_timeout_hours INT DEFAULT 168,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- AGENTES (principal + assessor por tenant)
-- =============================================
CREATE TYPE agentpolitico_agent_type_enum AS ENUM ('principal', 'assessor');

CREATE TABLE agentpolitico_tenant_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id) ON DELETE CASCADE,
    agent_type agentpolitico_agent_type_enum NOT NULL,
    name VARCHAR(100),
    persona_prompt TEXT NOT NULL,
    behavior_prompt TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, agent_type)
);

-- =============================================
-- NUMEROS DO AGENTE ASSESSOR
-- =============================================
CREATE TABLE agentpolitico_assessor_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agentpolitico_tenant_agents(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    label VARCHAR(100),
    active BOOLEAN DEFAULT true,
    UNIQUE(tenant_id, phone_number)
);
CREATE INDEX idx_ap_assessor_lookup ON agentpolitico_assessor_numbers(tenant_id, phone_number, active);

-- =============================================
-- PAINEIS SINCRONIZADOS DO HELENA
-- =============================================
CREATE TYPE agentpolitico_sync_status_enum AS ENUM ('synced', 'orphaned');

CREATE TABLE agentpolitico_tenant_panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id) ON DELETE CASCADE,
    helena_panel_id UUID NOT NULL,
    panel_name VARCHAR(255),
    sync_status agentpolitico_sync_status_enum DEFAULT 'synced',
    synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, helena_panel_id)
);

-- =============================================
-- VINCULO PAINEL <-> AGENTE (N:N)
-- =============================================
CREATE TABLE agentpolitico_tenant_agent_panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agentpolitico_tenant_agents(id) ON DELETE CASCADE,
    tenant_panel_id UUID REFERENCES agentpolitico_tenant_panels(id) ON DELETE CASCADE,
    agent_description TEXT,
    helena_step_id UUID,
    helena_department_id UUID,
    active BOOLEAN DEFAULT false,
    UNIQUE(agent_id, tenant_panel_id)
);
CREATE INDEX idx_ap_agent_panels_active ON agentpolitico_tenant_agent_panels(agent_id, active);

-- =============================================
-- STEPS DOS PAINEIS
-- =============================================
CREATE TABLE agentpolitico_tenant_panel_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_panel_id UUID REFERENCES agentpolitico_tenant_panels(id) ON DELETE CASCADE,
    helena_step_id UUID NOT NULL,
    step_name VARCHAR(255),
    step_order INT,
    synced_at TIMESTAMPTZ
);

-- =============================================
-- CAMPOS DO CONTATO (sincronizados)
-- =============================================
CREATE TABLE agentpolitico_tenant_contact_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id) ON DELETE CASCADE,
    helena_field_key VARCHAR(100) NOT NULL,
    helena_field_name VARCHAR(255),
    sync_status agentpolitico_sync_status_enum DEFAULT 'synced',
    synced_at TIMESTAMPTZ,
    UNIQUE(tenant_id, helena_field_key)
);

-- =============================================
-- VINCULO CAMPO CONTATO <-> AGENTE
-- =============================================
CREATE TABLE agentpolitico_tenant_agent_contact_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agentpolitico_tenant_agents(id) ON DELETE CASCADE,
    contact_field_id UUID REFERENCES agentpolitico_tenant_contact_fields(id) ON DELETE CASCADE,
    agent_instruction TEXT,
    field_order INT DEFAULT 0,
    required BOOLEAN DEFAULT true,
    active BOOLEAN DEFAULT false,
    UNIQUE(agent_id, contact_field_id)
);
CREATE INDEX idx_ap_contact_fields_active ON agentpolitico_tenant_agent_contact_fields(agent_id, active);

-- =============================================
-- CAMPOS CUSTOMIZADOS DO CARD DO PAINEL (sincronizados)
-- =============================================
CREATE TABLE agentpolitico_tenant_panel_custom_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_panel_id UUID REFERENCES agentpolitico_tenant_panels(id) ON DELETE CASCADE,
    helena_field_id VARCHAR(100) NOT NULL,
    helena_field_name VARCHAR(255),
    sync_status agentpolitico_sync_status_enum DEFAULT 'synced',
    synced_at TIMESTAMPTZ,
    UNIQUE(tenant_panel_id, helena_field_id)
);

-- =============================================
-- MAPEAMENTO DE CAMPOS DO CARD
-- =============================================
CREATE TABLE agentpolitico_tenant_agent_panel_field_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_panel_id UUID REFERENCES agentpolitico_tenant_agent_panels(id) ON DELETE CASCADE,
    panel_custom_field_id UUID REFERENCES agentpolitico_tenant_panel_custom_fields(id) ON DELETE CASCADE,
    storage_instruction TEXT,
    active BOOLEAN DEFAULT true,
    UNIQUE(agent_panel_id, panel_custom_field_id)
);

-- =============================================
-- DEPARTAMENTOS/EQUIPES
-- =============================================
CREATE TABLE agentpolitico_tenant_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id) ON DELETE CASCADE,
    helena_department_id UUID NOT NULL,
    department_name VARCHAR(255),
    synced_at TIMESTAMPTZ,
    UNIQUE(tenant_id, helena_department_id)
);

-- =============================================
-- PROMPTS DE FOLLOW-UP POR AGENTE
-- =============================================
CREATE TABLE agentpolitico_tenant_agent_followup_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agentpolitico_tenant_agents(id) ON DELETE CASCADE,
    followup_number INT NOT NULL CHECK (followup_number BETWEEN 1 AND 3),
    prompt_template TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_id, followup_number)
);
-- Exemplo de prompt_template:
-- Follow-up 1: "Lembre o cidadao da conversa de forma amigavel, pergunte se quer continuar"
-- Follow-up 2: "Diga que esta a disposicao quando quiser retomar"
-- Follow-up 3: "Se despeca de forma cordial, diga que o gabinete esta sempre disponivel"
-- O LLM usa esse prompt + contexto da conversa + persona para gerar a mensagem final

-- =============================================
-- TEMPLATES DE CONFIGURACAO RAPIDA
-- =============================================
CREATE TABLE agentpolitico_onboarding_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    persona_prompt_template TEXT,
    behavior_prompt_template TEXT,
    default_panels JSONB,
    default_contact_fields JSONB,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- METRICAS DE ATENDIMENTO
-- =============================================
CREATE TABLE agentpolitico_tenant_attendance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id),
    agent_type VARCHAR(20) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    session_id VARCHAR(100),
    event_type VARCHAR(50) NOT NULL,
    panel_name VARCHAR(255),
    metadata JSONB,
    event_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ap_attendance_tenant_date ON agentpolitico_tenant_attendance_events(tenant_id, event_date);
CREATE INDEX idx_ap_attendance_event_type ON agentpolitico_tenant_attendance_events(tenant_id, event_type, event_date);

-- =============================================
-- LOGS DE ERRO
-- =============================================
CREATE TABLE agentpolitico_tenant_error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES agentpolitico_tenants(id),
    error_type VARCHAR(50) NOT NULL,
    error_message TEXT,
    context JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ap_error_logs_tenant ON agentpolitico_tenant_error_logs(tenant_id, created_at);
```

### 7.2 PostgreSQL Dedicado — Tabelas de Memoria

```sql
-- Tabelas do LangGraph (mesmo padrao do repo original)
-- + coluna tenant_id para isolamento

-- langgraph_checkpoints (existente, adaptada)
-- langgraph_writes (existente, adaptada)
-- langgraph_messages (existente, adaptada)
-- langgraph_sessions (existente, adaptada)

-- =============================================
-- FILA DE FOLLOW-UP
-- =============================================
CREATE TABLE agentpolitico_follow_up_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    agent_type VARCHAR(20) NOT NULL,
    follow_up_number INT NOT NULL CHECK (follow_up_number BETWEEN 1 AND 3),
    scheduled_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ap_followup_pending ON agentpolitico_follow_up_queue(status, scheduled_at) WHERE status = 'pending';
CREATE INDEX idx_ap_followup_cancel ON agentpolitico_follow_up_queue(tenant_id, phone_number, status) WHERE status = 'pending';
```

---

## 8. Painel Super Admin — Funcionalidades

### 8.1 Dashboard (Super Admin)
- Lista de tenants com status, ultimo sync
- Metricas agregadas (total atendimentos do dia)

### 8.2 Configuracao do Tenant (abas)

**Aba Geral:**
- Nome, slug, token Helena, chave LLM
- Botao "Sincronizar com Helena"
- Config de follow-up (tempos: 20min, 1h, 1h — configuravel)
- Admins do tenant
- Status ativo/inativo

**Aba Agente Principal:**
- Prompt da persona (editavel)
- Prompt de comportamento (editavel)
- Campos de coleta (sincronizados, ativar/desativar, instrucao)
- Paineis ativos (ativar/desativar, equipe destino)
- Ao clicar painel: descricao + mapeamento de campos do card

**Aba Agente Assessor:**
- Toggle ativo/inativo
- Numeros da equipe
- Prompt persona + comportamento
- Campos de coleta (independente)
- Paineis ativos + mapeamento

**Aba Follow-up:**
- Prompt do follow-up 1 (editavel) — instrucao para o LLM gerar a mensagem do 1o lembrete
- Prompt do follow-up 2 (editavel) — instrucao para o 2o lembrete
- Prompt do follow-up 3 (editavel) — instrucao para a mensagem de despedida/encerramento
- Preview: mostra exemplo de como o LLM geraria cada mensagem com base na persona + prompt
- Nota: O LLM usa o prompt + contexto da conversa + persona do agente para gerar a mensagem real. O admin controla o TOM e ESTILO, nao o texto literal.

**Aba Metricas:**
- Atendimentos por dia/semana/mes
- Transferencias por painel
- Tempo medio ate transferencia
- Taxa de coleta de dados
- Follow-ups enviados/retornados/abandonados

### 8.3 Checklist de Onboarding

Ao criar tenant, mostra progresso visual:

```
[ ] Token Helena inserido
[ ] Sincronizacao realizada
[ ] Prompt da persona configurado
[ ] Pelo menos 1 painel ativado com descricao
[ ] Campos de coleta configurados
[ ] Mapeamento de campos do card feito
[ ] Tenant ativado
```

### 8.4 Validacao Pre-Ativacao

Antes de ativar, sistema valida:
- Token Helena funciona?
- Pelo menos 1 painel ativo com descricao?
- Prompt da persona preenchido?
- Pelo menos 1 campo de coleta ativo?
- Mapeamento de campos configurado nos paineis ativos?

### 8.5 Templates de Configuracao Rapida

Opcao ao criar tenant:
- "Gabinete de Vereador" — paineis e prompts padrao
- "Gabinete de Deputado" — paineis e prompts padrao
- "Configuracao Manual" — comeca do zero

---

## 9. Stack Tecnica

| Camada | Tecnologia |
|--------|-----------|
| Backend API | FastAPI (Python) |
| Agente IA | LangGraph |
| LLM | Grok (xAI) padrao, configuravel por tenant |
| Config DB | Supabase RDG (PostgreSQL gerenciado) |
| Memoria DB | PostgreSQL dedicado |
| Frontend Admin | Next.js (React) |
| Auth | JWT + bcrypt |
| Deploy | Docker + Docker Compose |
| Cron | APScheduler (Python) ou cron interno |
| Timezone | America/Sao_Paulo |

---

## PARTE 2 — SQUAD DE CONSTRUCAO

---

## 10. Squad: gabinete-tenant-builder

Squad customizado para construir o sistema, usando padroes dos squads nirvana-backend, saas-onboarding-activator e fabrica-de-genios.

### 10.1 Agentes do Squad

```
+------------------------------------------------------------------+
|                    SQUAD: gabinete-tenant-builder                  |
+------------------------------------------------------------------+
|                                                                    |
|  FASE 1: PLANEJAMENTO                                              |
|  +------------------+  +------------------+                        |
|  | SchemaArchitect  |  | SystemPlanner    |                        |
|  | (Banco de dados) |  | (Arquitetura)    |                        |
|  +------------------+  +------------------+                        |
|                                                                    |
|  FASE 2: BACKEND                                                   |
|  +------------------+  +------------------+  +------------------+  |
|  | ApiBuilder       |  | HelenaIntegrator |  | AuthEngineer     |  |
|  | (FastAPI admin)  |  | (Sync + Client)  |  | (JWT + RBAC)     |  |
|  +------------------+  +------------------+  +------------------+  |
|                                                                    |
|  FASE 3: AGENTE                                                    |
|  +------------------+  +------------------+                        |
|  | AgentRefactorer  |  | FollowUpBuilder  |                        |
|  | (Multi-tenant)   |  | (Cron + fila)    |                        |
|  +------------------+  +------------------+                        |
|                                                                    |
|  FASE 4: FRONTEND                                                  |
|  +------------------+                                              |
|  | AdminPanelBuilder|                                              |
|  | (Next.js)        |                                              |
|  +------------------+                                              |
|                                                                    |
|  FASE 5: QUALIDADE                                                 |
|  +------------------+  +------------------+                        |
|  | TestEngineer     |  | QualityAuditor   |                        |
|  | (Testes)         |  | (Revisao final)  |                        |
|  +------------------+  +------------------+                        |
|                                                                    |
+------------------------------------------------------------------+
```

### 10.2 Detalhamento de cada agente

#### **SchemaArchitect** (Fase 1)
- **O que faz:** Cria todas as tabelas no Supabase RDG e no PostgreSQL dedicado
- **Entradas:** Escopo final (este documento), MCP supabase-rdg, MCP postgres
- **Saidas:** Tabelas criadas, migrations documentadas, indexes otimizados
- **Ferramentas:** MCP supabase-rdg para criar tabelas de config, MCP postgres para tabelas de memoria

#### **SystemPlanner** (Fase 1)
- **O que faz:** Define a estrutura de pastas do projeto, dependencias, configs Docker
- **Entradas:** Escopo final, repositorio original como referencia
- **Saidas:** Estrutura de projeto, Dockerfile, docker-compose.yml, requirements.txt
- **Padrao:** Mesmo padrao do repo original (FastAPI + LangGraph + Docker)

#### **ApiBuilder** (Fase 2)
- **O que faz:** Implementa todos os endpoints da API admin (CRUD tenants, agentes, paineis, campos, metricas)
- **Entradas:** Schema do banco, escopo dos endpoints
- **Saidas:** Rotas FastAPI com Pydantic validation, paginacao, filtros
- **Padrao:** RESTful, Pydantic models, async
- **CRUD com cascade delete:** Ao deletar um tenant, TODAS as tabelas relacionadas (agentes, paineis, campos, mapeamentos, numeros assessor, prompts de follow-up, eventos de metricas, logs de erro) sao limpas automaticamente. O banco ja tem ON DELETE CASCADE, mas a API tambem limpa dados no PostgreSQL dedicado (checkpoints, follow-up queue) do tenant deletado.

#### **HelenaIntegrator** (Fase 2)
- **O que faz:** Implementa o servico de sincronizacao e adapta o helena_client para multi-tenant
- **Entradas:** Documentacao Helena, helena_client.py original
- **Saidas:** sync_service.py, helena_client.py adaptado (token como parametro)
- **Endpoints usados:** GET panels, GET departments, GET contact custom-fields, GET panel custom-fields, PUT session complete

#### **AuthEngineer** (Fase 2)
- **O que faz:** Implementa autenticacao JWT, bcrypt, RBAC (super_admin/tenant_admin)
- **Entradas:** Tabela admin_users, regras de acesso
- **Saidas:** auth_service.py, middleware de auth, rotas de login/refresh

#### **AgentRefactorer** (Fase 3)
- **O que faz:** Refatora o agente LangGraph para funcionar multi-tenant com config dinamica
- **Entradas:** Repositorio original completo, schema de config
- **Saidas:** Agente refatorado: prompts dinamicos, campos dinamicos, categorias dinamicas, mapeamento dinamico
- **Adapta:** graph.py, nodes.py, prompts.py, state.py, validate_contact.py, classify_demand.py, transfer_route.py
- **Elimina:** constants.py (substituido por config do banco)

#### **FollowUpBuilder** (Fase 3)
- **O que faz:** Implementa sistema de follow-up com fila e cron job
- **Entradas:** Tabela follow_up_queue, config de tempos por tenant
- **Saidas:** follow_up_service.py, cron job, integracao com webhook
- **Inclui:** Cancelamento automatico ao receber mensagem, conclusao de atendimento (PUT /session/complete)

#### **AdminPanelBuilder** (Fase 4)
- **O que faz:** Cria o frontend Next.js do painel admin completo
- **Entradas:** Endpoints da API, mockups do escopo
- **Saidas:** Painel com: dashboard, config tenant, agentes, paineis, campos, metricas, checklist onboarding
- **Stack:** Next.js, React, Tailwind CSS, JWT auth

#### **TestEngineer** (Fase 5)
- **O que faz:** Cria testes de integracao para API admin, testes do agente, testes do follow-up
- **Entradas:** Endpoints implementados, fluxos definidos
- **Saidas:** Suite de testes, cobertura 80%+

#### **QualityAuditor** (Fase 5)
- **O que faz:** Revisao final de codigo, seguranca, performance, documentacao
- **Entradas:** Todo o codigo construido
- **Saidas:** Relatorio de qualidade, correcoes aplicadas

### 10.3 Fluxo de execucao do squad

```
FASE 1: PLANEJAMENTO (paralelo)
  SchemaArchitect ──────────> Tabelas criadas
  SystemPlanner ────────────> Estrutura do projeto
                    |
                    v
FASE 2: BACKEND (paralelo parcial)
  AuthEngineer ─────────────> Auth pronto
  HelenaIntegrator ─────────> Sync + client pronto
  ApiBuilder ───────────────> API admin pronta
  (ApiBuilder depende de AuthEngineer e HelenaIntegrator)
                    |
                    v
FASE 3: AGENTE (paralelo)
  AgentRefactorer ──────────> Agente multi-tenant pronto
  FollowUpBuilder ──────────> Follow-up pronto
                    |
                    v
FASE 4: FRONTEND
  AdminPanelBuilder ────────> Painel admin pronto
                    |
                    v
FASE 5: QUALIDADE (sequencial)
  TestEngineer ─────────────> Testes passando
  QualityAuditor ───────────> Aprovacao final
```

### 10.4 Como os squads existentes ajudam

| Squad | Onde ajuda | Como |
|---|---|---|
| **nirvana-backend** | Fase 1-2 | Padroes de schema, migrations, Docker, auth, testes |
| **saas-onboarding-activator** | Fase 4 | Checklist onboarding, validacao pre-ativacao, templates |
| **fabrica-de-genios** | Fase 3 | Padrao de "DNA do agente" — o prompt da persona segue o conceito de SOUL.md (camadas de identidade, tom, regras). Cada tenant tem seu proprio "DNA de agente" configuravel. Tambem o padrao de rastreabilidade (cada decisao do agente e rastreavel) |

---

## 11. Ordem de Construcao (Fases Detalhadas)

### Fase 1: Banco + Estrutura (SchemaArchitect + SystemPlanner)
- [ ] Criar tabelas no Supabase RDG via MCP
- [ ] Criar tabelas de memoria no PostgreSQL dedicado via MCP
- [ ] Criar estrutura de pastas do projeto
- [ ] Configurar Docker, requirements.txt, .env

### Fase 2: Backend API (ApiBuilder + HelenaIntegrator + AuthEngineer)
- [ ] Implementar auth (JWT + bcrypt + middleware RBAC)
- [ ] Adaptar helena_client.py para receber token como parametro
- [ ] Implementar sync_service.py (sincronizacao com Helena)
- [ ] Implementar CRUD tenants (com cascade delete: limpa Supabase + PostgreSQL dedicado)
- [ ] Implementar CRUD agentes + prompts + prompts de follow-up
- [ ] Implementar config campos de coleta
- [ ] Implementar config paineis + mapeamento de campos
- [ ] Implementar CRUD numeros assessor
- [ ] Implementar endpoint de metricas
- [ ] Implementar endpoint de logs de erro
- [ ] Implementar validacao pre-ativacao
- [ ] Implementar templates de config rapida

### Fase 3: Agente Multi-Tenant (AgentRefactorer + FollowUpBuilder)
- [ ] Refatorar state.py (adicionar tenant_id, agent_type)
- [ ] Refatorar prompts.py (geracao dinamica: persona + comportamento + campos + paineis + mapeamento)
- [ ] Refatorar validate_contact.py (campos dinamicos do banco)
- [ ] Refatorar classify_demand.py (categorias = paineis ativos)
- [ ] Refatorar transfer_route.py (IDs e mapeamento do banco + conclusao de atendimento)
- [ ] Refatorar graph.py (config do tenant + grafo simplificado para assessor)
- [ ] Refatorar nodes.py (config dinamica)
- [ ] Refatorar webhook.py (identificacao tenant + roteamento agente)
- [ ] Eliminar constants.py
- [ ] Implementar follow_up_service.py (fila + cron)
- [ ] Implementar cancelamento de follow-up ao receber mensagem
- [ ] Implementar conclusao de atendimento (PUT /session/complete) — so no 3o follow-up
- [ ] Implementar limpeza de memoria (checkpoints/writes) apos transferencia e apos conclusao
- [ ] Implementar geracao de mensagens de follow-up via LLM (usando prompts do admin + contexto + persona)
- [ ] Implementar registro de eventos de metricas

### Fase 4: Frontend Admin (AdminPanelBuilder)
- [ ] Setup Next.js + Tailwind + auth JWT
- [ ] Dashboard com lista de tenants
- [ ] Pagina de config do tenant (abas)
- [ ] Aba Geral (token, sync, follow-up config, due date config)
- [ ] Aba Agente Principal (prompts, campos, paineis, mapeamento)
- [ ] Aba Agente Assessor (numeros, prompts, campos, paineis, mapeamento)
- [ ] Aba Follow-up (prompts editaveis dos 3 follow-ups por agente)
- [ ] Aba Metricas (graficos, tabelas)
- [ ] Checklist de onboarding
- [ ] Validacao pre-ativacao
- [ ] Templates de configuracao rapida

### Fase 5: Qualidade (TestEngineer + QualityAuditor)
- [ ] Testes de integracao API admin
- [ ] Testes do agente (fluxo completo)
- [ ] Testes do follow-up
- [ ] Testes de sincronizacao
- [ ] Revisao de seguranca
- [ ] Revisao de performance
- [ ] Documentacao final

---

## 12. Entregaveis Finais

| # | Entrega | Descricao |
|---|---------|-----------|
| 1 | **Banco de dados** | Tabelas no Supabase RDG + PostgreSQL dedicado |
| 2 | **API Admin** | FastAPI com auth, CRUD, sync, metricas, templates |
| 3 | **Agente Multi-Tenant** | LangGraph refatorado com config dinamica |
| 4 | **Agente Assessor** | Grafo simplificado com roteamento por numero |
| 5 | **Follow-Up** | Sistema de 3 follow-ups com conclusao automatica |
| 6 | **Conclusao de Atendimento** | PUT /session/complete integrado |
| 7 | **Metricas** | Eventos + dashboard por tenant |
| 8 | **Painel Admin** | Next.js com todas as funcionalidades |
| 9 | **Onboarding** | Checklist + validacao + templates |
| 10 | **Docker + Deploy** | Docker multi-stage + compose + CI/CD |

---

*Documento final aprovado para construcao. Todas as decisoes, fluxos, tabelas, endpoints e agentes de construcao estao definidos.*
