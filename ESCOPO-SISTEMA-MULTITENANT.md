# Sistema Multi-Tenant de Agentes de Gabinete

## Documento de Escopo Completo

**Versao:** 3.0
**Data:** 2026-03-14
**Status:** Aguardando validacao

---

## 1. Visao Geral

Sistema multi-tenant que permite replicar agentes de gabinete politico (vereadores, deputados) de forma independente, onde cada conta (tenant) tem sua propria configuracao de agente, integracao com CRM Helena, e regras de atendimento.

**Objetivo:** Um unico deploy que serve N gabinetes, configuraveis via painel Super Admin, sem necessidade de alterar codigo para cada novo cliente.

**Principio fundamental de armazenamento:**
- **No banco de dados local (PostgreSQL):** Apenas configuracoes, instrucoes, prompts, mapeamentos e estado do LangGraph
- **No CRM Helena:** Todas as informacoes coletadas nas conversas (dados do contato, cards, tags, etc.)
- O sistema NUNCA armazena dados de cidadaos localmente — sempre salva direto no Helena

---

## 2. Arquitetura Geral

```
                    +----------------------------------+
                    |        PAINEL SUPER ADMIN         |
                    |    (configuracao de tenants)       |
                    +--------------+-------------------+
                                   |
                                   v
+---------+    +---------+    +----------------------+    +------------+
| WhatsApp |--->| Helena  |--->|   API Multi-Tenant   |--->| PostgreSQL |
|          |<---| CRM     |<---|   (FastAPI)          |<---|  (config)  |
+---------+    +---------+    +----------+-----------+    +------------+
                    ^                    |
                    |         +----------+----------+
                    |         |                     |
                    |   +-----v------+       +------v-----+
                    |   |  AGENTE    |       |  AGENTE     |
                    +---|  PRINCIPAL |       |  ASSESSOR   |
                        | (Gabinete) |       | (Secundario)|
                        +------------+       +-------------+
```

### 2.1 Recebimento de Mensagens

O sistema recebe mensagens via **webhook HTTP do n8n**, no mesmo formato do repositorio original. O n8n DEVE enviar um campo adicional obrigatorio `tenant_slug` para identificar o tenant:

```json
{
  "mensagem": "Texto da mensagem do usuario",
  "numero": "+5511999999999",
  "sessionID": "uuid-da-sessao-helena",
  "card_id": "uuid-do-card-helena",
  "tenant_slug": "andre-santos"
}
```

**Identificacao do tenant (DEFINIDO):**
- O `tenant_slug` e o campo **obrigatorio** que identifica o tenant
- O n8n e configurado uma vez por tenant com o slug fixo no payload
- O sistema faz lookup direto no banco: `SELECT * FROM tenants WHERE slug = tenant_slug AND active = true`
- Esse lookup e **cacheado em memoria** (TTL 5 minutos) para evitar query a cada mensagem
- Se o tenant nao for encontrado ou estiver inativo, retorna erro 404 e NAO processa a mensagem

**O n8n e responsavel por:**
- Receber o webhook da Helena quando chega mensagem no WhatsApp
- Repassar para a API do sistema com o `tenant_slug` incluido
- Cada tenant tem seu proprio fluxo n8n (configuracao simples: apenas mudar o slug)

### 2.2 Envio de Respostas (Outbound)

O agente envia respostas **diretamente via API Helena**, sem passar pelo n8n:

```
Agente gera resposta
    |
    v
POST /chat/v1/message/send-sync (Helena API)
Body: {
    "channelId": "<canal-whatsapp-do-tenant>",
    "contactId": "<id-contato>",
    "message": "<resposta-do-agente>"
}
    |
    v
Helena envia via WhatsApp para o cidadao
```

**Resposta do webhook para o n8n:**
```json
{
  "success": true,
  "message": "Resposta enviada",
  "already_sent": true,
  "current_phase": "ETAPA_1",
  "transferred": false
}
```

O campo `already_sent: true` indica ao n8n que NAO deve reenviar a mensagem — o sistema ja enviou direto via Helena.

### 2.3 Fluxo de Decisao: Qual agente atende?

```
Webhook recebe: { mensagem, numero, sessionID, card_id, tenant_slug }
        |
        v
1. Identifica tenant pelo tenant_slug (com cache)
   -> Se nao encontrado: retorna 404
        |
        v
2. O numero do remetente esta na lista de assessores DESTE tenant?
   SELECT * FROM assessor_numbers
   WHERE tenant_id = X AND phone_number = numero AND active = true
   (Obs: a busca e SEMPRE dentro do tenant ja identificado.
    O mesmo numero pode ser assessor no tenant A e cidadao no tenant B)
        |
   +----+----+
   SIM       NAO
   |          |
   v          v
AGENTE      AGENTE
ASSESSOR    PRINCIPAL
(prompt 2)  (prompt 1 - gabinete)
```

---

## 3. Ciclo de Vida da Conversa

### 3.1 Inicio de Conversa

Uma conversa inicia quando o sistema recebe a primeira mensagem de um numero que NAO tem checkpoint ativo no LangGraph para aquele tenant.

### 3.2 Controle de Concorrencia

```
Mensagem chega para tenant X, numero Y
        |
        v
Adquire lock por chave: "tenant_X:numero_Y"
(asyncio.Lock por sessao, mesmo mecanismo do repo original)
        |
        v
Se lock ja adquirido (outra mensagem do mesmo numero em processamento):
   -> Aguarda liberacao do lock (timeout 30s)
   -> Se timeout: retorna { "success": false, "message": "em processamento" }
        |
        v
Processa mensagem normalmente
        |
        v
Libera lock
```

**Deduplicacao:** Mesma mensagem (mesmo texto + mesmo numero) dentro de 120 segundos e ignorada (mesmo mecanismo do repo original).

### 3.3 Timeout e Abandono

- Se o cidadao nao responde por **24 horas** durante a coleta de dados (ETAPA 1):
  - O checkpoint e mantido (dados parciais preservados)
  - Na proxima mensagem, retoma de onde parou
- Se o cidadao nao responde por **7 dias**:
  - Os checkpoints sao limpos automaticamente (cron job)
  - Na proxima mensagem, comeca conversa nova
- O admin pode configurar esses tempos por tenant (campo opcional)

### 3.4 Fim de Conversa

- **ETAPA 3 concluida:** Apos transferir + criar card, checkpoints sao limpos imediatamente
- **Recusa de dados ([RECUSA_DADOS]):** Pula para ETAPA 2 (tenta classificar mesmo assim)
- **Transferencia concluida:** Proxima mensagem do mesmo numero inicia conversa nova

---

## 4. Componentes do Sistema

### 4.1 Painel Super Admin

Interface web onde o administrador configura cada tenant.

#### 4.1.1 Modelo de Acesso (Autorizacao)

O painel tem dois niveis de acesso:

| Papel | Pode ver | Pode editar |
|-------|----------|-------------|
| **Super Admin** | Todos os tenants | Criar/editar/desativar tenants, criar admins |
| **Admin do Tenant** | Apenas seu tenant | Prompts, campos, paineis, numeros assessor |

- Login via email + senha com JWT (expiracao 24h, refresh token 7 dias)
- Senhas armazenadas com bcrypt
- Tabela `admin_users` no banco (ver secao 5)
- Super Admin cria contas de Admin do Tenant durante o onboarding
- Futuro: MFA opcional

#### 4.1.2 Gestao de Tenants (Contas)

Apenas Super Admin:
- Criar novo tenant (nome do gabinete, slug identificador)
- Ativar / desativar tenant
- Visualizar lista de tenants ativos
- Criar Admin do Tenant

#### 4.1.3 Configuracao Helena (por tenant)

- Campo para inserir o **Token da API Helena**
- Botao **"Sincronizar"** que, ao clicar:
  - Busca todos os paineis do CRM via `GET /crm/v1/panel`
  - Busca todas as equipes/departamentos via `GET /v2/department`
  - Busca campos customizados do contato via `GET /core/v1/contact/custom-field`
  - Busca campos customizados de cada painel via `GET /crm/v1/panel/{id}/custom-fields`
  - Exibe os resultados para o admin configurar

**O que a sincronizacao traz:**

| Origem no Helena | O que sincroniza | Onde aparece no painel |
|---|---|---|
| `GET /crm/v1/panel` | Lista de paineis + steps | Aba de Paineis (para ativar/desativar) |
| `GET /v2/department` | Equipes/departamentos | Dropdown de equipe em cada painel |
| `GET /core/v1/contact/custom-field` | Campos do card de contato | Aba de Campos de Coleta |
| `GET /crm/v1/panel/{id}/custom-fields` | Campos customizados do card do painel | Config de cada painel (mapeamento de campos) |

#### 4.1.4 Gestao de Paineis (Visibilidade do Agente)

Apos sincronizar, o admin ve a lista completa de paineis do CRM. Para cada painel:

| Campo | Descricao |
|-------|-----------|
| **Nome do painel** | Nome vindo do Helena (ex: "Demandas Saude") — somente leitura |
| **Status** | `ativo` / `inativo` / `orfao` (ver abaixo) |
| **Descricao para o agente** | Texto livre que descreve QUANDO o agente deve transferir para esse painel |
| **Step padrao** | Em qual etapa do pipeline o card e criado (dropdown com steps sincronizados) |
| **Equipe/Departamento** | Para qual equipe a sessao de chat e transferida (dropdown sincronizado) |
| **Mapeamento de campos** | Quais campos do card do painel serao preenchidos e com que informacao |

**Status "orfao":** Se durante uma sincronizacao o sistema detecta que um painel ativo no sistema NAO existe mais no Helena, ele recebe status `orfao`. O agente NAO tenta operar em paineis orfaos. O admin ve um aviso na interface pedindo para desativar ou remapear.

**Exemplo de "Descricao para o agente":**

> **Painel: Saude**
> "Transferir para este painel quando o cidadao solicitar ajuda relacionada a: consultas medicas, medicamentos, UBS, UPA, hospitais, postos de saude, vacinas, exames, cirurgias, ambulancias, SAMU, saude mental, dependencia quimica, ou qualquer outra demanda de saude publica."

> **Painel: Educacao**
> "Transferir para este painel quando o cidadao solicitar ajuda relacionada a: vagas em escolas, creches, matriculas, transporte escolar, uniforme, material escolar, merenda, problemas em escolas municipais, ou qualquer demanda educacional."

**Por que isso e importante:** O agente usa essas descricoes para decidir para QUAL painel transferir. Sem descricao, ele nao sabe classificar.

#### 4.1.5 Campos de Coleta do Contato (Etapa 1)

**Esses campos vem diretamente do Helena.** Quando o admin clica "Sincronizar", o sistema busca os campos customizados do card de contato via `GET /core/v1/contact/custom-field` e exibe todos automaticamente na lista.

O admin NAO cria campos manualmente — ele apenas:
- **Ativa/desativa** campos que ja existem no Helena
- Coloca uma **instrucao breve** de como o agente deve solicitar aquele campo
- Marca se e **obrigatorio** ou **opcional**

```
+----------------------------------------------------------------------+
| Campos de Coleta (sincronizados do card de contato Helena)            |
+----------------------------------------------------------------------+
|                                                                      |
| Esses campos foram trazidos do seu CRM Helena.                       |
| Ative os que deseja que o agente solicite ao cidadao.                |
|                                                                      |
| +----------------+-------+------+-----------------------------------+|
| | Campo Helena   | Ativo | Obr. | Instrucao para o agente           ||
| +----------------+-------+------+-----------------------------------+|
| | email          | [x]   | [x]  | "Solicite o e-mail do cidadao"   ||
| | cpf            | [x]   | [x]  | "Solicite o CPF"                 ||
| | data-nascimento| [x]   | [ ]  | "Solicite a data de nascimento"  ||
| | cep            | [x]   | [x]  | "Solicite o CEP"                 ||
| | endereco       | [x]   | [x]  | "Solicite o endereco completo"   ||
| | bairro         | [x]   | [x]  | "Solicite o bairro"              ||
| | cidade         | [x]   | [x]  | "Solicite a cidade"              ||
| | estado         | [x]   | [x]  | "Solicite o estado"              ||
| | rg             | [ ]   | [ ]  | —                                 ||
| | telefone-fixo  | [ ]   | [ ]  | —                                 ||
| | profissao      | [ ]   | [ ]  | —                                 ||
| +----------------+-------+------+-----------------------------------+|
|                                                                      |
| Ultimo sync: 14/03/2026 10:30     [Sincronizar novamente]           |
+----------------------------------------------------------------------+
```

**Regras de funcionamento:**
- Campos vem do Helena via sincronizacao — se criar um campo novo la no Helena e sincronizar aqui, ele aparece automaticamente
- O admin ativa os campos que quer que o agente solicite
- O admin coloca instrucao breve descrevendo o que e aquele campo (ex: "Solicite o CPF", "Solicite o RG, que e documento de identidade")
- O agente so coleta campos que estejam **ativos**
- O agente so coleta campos que estejam **vazios** no contato do Helena (se ja tiver preenchido, nao pede)
- Campos **obrigatorios**: o agente insiste ate 2 vezes
- Campos **opcionais**: o agente pede uma vez, se o cidadao recusar, segue em frente
- Coleta e feita **um campo por vez**, pausadamente, na conversa
- Ao final, o agente confirma todos os dados coletados com o cidadao
- Confirmado, salva via `PUT /core/v1/contact/phonenumber/{phone}` no Helena

#### 4.1.6 Mapeamento de Campos do Card do Painel

Quando o agente transfere para um painel e cria/duplica o card, ele precisa preencher os campos customizados daquele card. Esses campos tambem vem do Helena via sincronizacao (`GET /crm/v1/panel/{id}/custom-fields`).

Para cada painel ativo, o admin configura o que vai em cada campo do card:

```
+----------------------------------------------------------------------+
| Mapeamento de Campos - Painel: Demandas Saude                        |
+----------------------------------------------------------------------+
|                                                                      |
| Quando o agente criar um card neste painel, ele vai preencher        |
| os campos abaixo com as informacoes da conversa.                     |
|                                                                      |
| +---------------------+-------+-------------------------------------+|
| | Campo do Card       | Ativo | O que armazenar                     ||
| +---------------------+-------+-------------------------------------+|
| | Solicitacao         | [x]   | "Nome/tipo da solicitacao"           ||
| | Manifestacao        | [x]   | "Categoria da demanda"               ||
| | Desc. Manifestacao  | [x]   | "Resumo completo da conversa"        ||
| | CPF                 | [x]   | "CPF do cidadao"                     ||
| | Email               | [x]   | "Email do cidadao"                   ||
| | CEP                 | [x]   | "CEP do cidadao"                     ||
| | Endereco            | [x]   | "Endereco completo"                  ||
| | Bairro              | [x]   | "Bairro do cidadao"                  ||
| | Cidade              | [x]   | "Cidade do cidadao"                  ||
| | Estado              | [x]   | "Estado do cidadao"                  ||
| | Data Nascimento     | [x]   | "Data de nascimento do cidadao"      ||
| | Data Cadastro       | [x]   | "Data em que o cidadao entrou em     ||
| |                     |       |  contato (automatico)"               ||
| | Urgencia            | [x]   | "Nivel de urgencia: baixa/media/alta"||
| +---------------------+-------+-------------------------------------+|
|                                                                      |
| [Salvar] [Cancelar]                                                  |
+----------------------------------------------------------------------+
```

**Esse mesmo mapeamento se aplica ao Agente Assessor** — quando o assessor cria card em um painel, ele tambem precisa saber o que colocar em cada campo.

#### 4.1.7 Prompt do Agente Principal (Completo)

O admin tem controle total sobre o prompt do agente. O prompt e dividido em **duas areas editaveis**:

```
+----------------------------------------------------------------------+
| Configuracao de Prompt - Agente Principal                            |
+----------------------------------------------------------------------+
|                                                                      |
| -- PROMPT DA PERSONA E TOM --                                        |
| (Define quem e o agente, como se comporta, tom de voz)               |
| +------------------------------------------------------------------+ |
| | Voce e a Livia, assistente virtual do gabinete do                 | |
| | Vereador Andre Santos, Sao Paulo/SP.                              | |
| |                                                                    | |
| | Seu papel e receber os cidadaos com cordialidade,                 | |
| | entender suas demandas e encaminha-los para a equipe              | |
| | correta.                                                           | |
| |                                                                    | |
| | Tom: educada, empatica, objetiva.                                 | |
| | Nunca prometa acoes em nome do vereador.                          | |
| +------------------------------------------------------------------+ |
|                                                                      |
| -- PROMPT DE COMPORTAMENTO E REGRAS --                               |
| (Define COMO o agente conduz a conversa, formato de trabalho)        |
| +------------------------------------------------------------------+ |
| | Regras de conduta:                                                 | |
| | - Sempre cumprimente o cidadao pelo nome quando disponivel        | |
| | - Seja breve nas respostas, maximo 3 frases por mensagem          | |
| | - Quando pedir informacao, explique por que precisa               | |
| | - Se o cidadao ficar irritado, demonstre empatia                  | |
| | - Nunca fale "nao posso ajudar", sempre encaminhe                 | |
| | - Se nao entender a demanda apos 2 tentativas,                    | |
| |   classifique como atendimento geral                              | |
| |                                                                    | |
| | Formato de coleta de dados:                                        | |
| | - Peca um dado por vez                                             | |
| | - Apos coletar todos, apresente um resumo                         | |
| | - Peca confirmacao antes de salvar                                 | |
| | - Se o cidadao corrigir algum dado, atualize e confirme           | |
| +------------------------------------------------------------------+ |
|                                                                      |
| [Salvar]                                                             |
+----------------------------------------------------------------------+
```

**O que o sistema injeta automaticamente (o admin NAO precisa escrever):**
- Lista de campos ativos para coleta (vem da configuracao de campos)
- Lista de categorias/paineis ativos com descricoes (vem da config de paineis)
- Instrucoes tecnicas dos marcadores (`[DADOS_CONFIRMADOS]`, `[CLASSIFICAR_DEMANDA]`, `[RECUSA_DADOS]`)
- Contexto da etapa atual (campos faltantes, dados ja coletados)

**O admin controla:**
- Quem e o agente (persona, nome, tom)
- Como o agente se comporta (regras, formato de conversa, limites)
- Pode mudar completamente a forma como o agente conduz o atendimento por tenant

---

### 4.2 Agente Assessor (Segundo Agente)

#### 4.2.1 O que e

Um segundo agente dentro do mesmo tenant, com configuracao completamente independente, que atende **numeros especificos** em vez do publico geral.

#### 4.2.2 Caso de uso

O vereador/deputado e sua equipe interna mandam mensagem para o mesmo numero do WhatsApp. Em vez de serem atendidos pelo agente de gabinete, eles sao atendidos pelo **Agente Assessor**.

#### 4.2.3 Fluxo do Agente Assessor (diferente do Principal)

O Agente Assessor usa um **grafo LangGraph simplificado de 2 etapas** (NAO usa as 3 etapas do principal):

```
ETAPA A: Coleta de informacoes da demanda (via conversa)
    |
    v
ETAPA B: Classificacao + criacao de card no painel correto
```

**Diferenca do Agente Principal:**
- **NAO tem ETAPA 1 de dados do contato** (por padrao) — assessores sao equipe interna, nao precisam informar CPF/email. Porem, o admin PODE ativar campos de coleta do contato para o assessor se quiser (a configuracao e independente).
- O assessor vai direto para a conversa sobre a demanda
- Apos entender, classifica e cria card no painel correto (mesma logica de mapeamento de campos)

Se o admin ativar campos de coleta para o assessor, o fluxo vira 3 etapas (igual ao principal). Mas por padrao, todos os campos de coleta do assessor vem **desativados**.

#### 4.2.4 Configuracao no Super Admin

```
+----------------------------------------------------------------------+
| Agente Assessor                                                 [ON] |
+----------------------------------------------------------------------+
|                                                                      |
| -- NUMEROS QUE USAM ESTE AGENTE --                                   |
| +---------------------------------------------+                     |
| | +5511999990001  | Vereador Andre    | [x]   |                     |
| | +5511999990002  | Chefe de Gab.     | [x]   |                     |
| | +5511999990003  | Assessor Paulo    | [x]   |                     |
| | +5511999990004  | Assessor Maria    | [x]   |                     |
| +---------------------------------------------+                     |
| Numero: [              ] Label: [              ] [Adicionar]         |
|                                                                      |
| -- PROMPT DO ASSESSOR (PERSONA) --                                   |
| +------------------------------------------------------------------+ |
| | Voce e o assistente interno do gabinete do Vereador Andre Santos. | |
| | Voce auxilia a equipe interna com:                                 | |
| | - Agendamentos de reunioes e visitas                               | |
| | - Registro de demandas prioritarias                                | |
| | - Criacao de cards para acompanhamento                             | |
| +------------------------------------------------------------------+ |
|                                                                      |
| -- PROMPT DO ASSESSOR (COMPORTAMENTO) --                             |
| +------------------------------------------------------------------+ |
| | - Seja direto e objetivo (equipe interna)                          | |
| | - Pergunte as informacoes necessarias para o card                  | |
| | - Sempre confirme antes de criar o card                            | |
| | - Colete: assunto, descricao, prioridade (baixa/media/alta)       | |
| +------------------------------------------------------------------+ |
|                                                                      |
| -- CAMPOS DE COLETA DO CONTATO (ASSESSOR) --                        |
| (Mesmos campos sincronizados, config independente, tudo OFF)         |
| +----------------+-------+------+----------------------------------+ |
| | Campo Helena   | Ativo | Obr. | Instrucao                        | |
| +----------------+-------+------+----------------------------------+ |
| | email          | [ ]   | [ ]  | —                                 | |
| | cpf            | [ ]   | [ ]  | —                                 | |
| | cep            | [ ]   | [ ]  | —                                 | |
| +----------------+-------+------+----------------------------------+ |
|                                                                      |
| -- PAINEIS ATIVOS (ASSESSOR) --                                      |
| +---------------------+-------+---------------------------+          |
| | Painel              | Ativo | Equipe destino            |          |
| +---------------------+-------+---------------------------+          |
| | Agenda Interna      | [x]   | Equipe Gabinete        v |          |
| | Demandas VIP        | [x]   | Assessores Diretos     v |          |
| | Demandas Saude      | [ ]   | —                        |          |
| | Demandas Educacao   | [ ]   | —                        |          |
| +---------------------+-------+---------------------------+          |
| (Clique no painel para configurar descricao e campos do card)        |
|                                                                      |
| [Salvar]                                                             |
+----------------------------------------------------------------------+
```

#### 4.2.5 Config. Painel do Assessor (ao clicar no painel)

```
+----------------------------------------------------------------------+
| Configurar Painel: Agenda Interna                                    |
| Agente: Assessor                                                     |
+----------------------------------------------------------------------+
|                                                                      |
| Step padrao: [Novos v]                                               |
| Equipe: [Equipe Gabinete v]                                          |
|                                                                      |
| -- Descricao para o agente (quando transferir para ca) --            |
| +------------------------------------------------------------------+ |
| | Transferir para este painel quando o assessor solicitar           | |
| | agendamento de reuniao, visita, ou evento do gabinete.            | |
| +------------------------------------------------------------------+ |
|                                                                      |
| -- Campos do Card (sincronizados do painel Helena) --                |
| +---------------------+-------+-------------------------------------+|
| | Campo do Card       | Ativo | O que armazenar neste campo         ||
| +---------------------+-------+-------------------------------------+|
| | Titulo              | [x]   | "Assunto principal da demanda"       ||
| | Descricao           | [x]   | "Resumo completo da conversa"        ||
| | Data Contato        | [x]   | "Data do contato (automatico)"       ||
| | Prioridade          | [x]   | "Nivel: baixa/media/alta"            ||
| | Responsavel         | [ ]   | —                                    ||
| +---------------------+-------+-------------------------------------+|
|                                                                      |
| [Salvar] [Voltar]                                                    |
+----------------------------------------------------------------------+
```

---

## 5. Modelo de Dados

### 5.1 Tabelas

```sql
-- =============================================
-- USUARIOS DO PAINEL ADMIN
-- =============================================
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,    -- bcrypt
    name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('super_admin', 'tenant_admin')),
    tenant_id UUID REFERENCES tenants(id),  -- NULL para super_admin
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
-- Indice: email (ja unique)
-- Regra: se role = 'tenant_admin', tenant_id obrigatorio
-- Regra: se role = 'super_admin', tenant_id deve ser NULL

-- =============================================
-- TENANT (conta/gabinete)
-- =============================================
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,           -- "Gabinete Vereador Andre Santos"
    slug VARCHAR(100) UNIQUE NOT NULL,    -- "andre-santos"
    helena_api_token TEXT,                -- Token encriptado (AES-256)
    llm_api_key TEXT,                     -- Chave do LLM encriptada (NULL = usa compartilhada)
    llm_provider VARCHAR(20) DEFAULT 'grok',  -- "grok", "openai", etc.
    checkpoint_timeout_hours INT DEFAULT 168,  -- 7 dias padrao para limpar checkpoints
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
-- Indice: slug (ja unique)

-- =============================================
-- AGENTES (principal + assessor por tenant)
-- =============================================
CREATE TYPE agent_type_enum AS ENUM ('principal', 'assessor');

CREATE TABLE tenant_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    agent_type agent_type_enum NOT NULL,
    name VARCHAR(100),                    -- "Livia" ou "Assistente Interno"
    persona_prompt TEXT NOT NULL,         -- Prompt da persona e tom
    behavior_prompt TEXT,                 -- Prompt de comportamento e regras
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, agent_type)
);

-- =============================================
-- NUMEROS DO AGENTE ASSESSOR
-- =============================================
CREATE TABLE assessor_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES tenant_agents(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,    -- "+5511999990001"
    label VARCHAR(100),                   -- "Vereador" / "Chefe de Gabinete"
    active BOOLEAN DEFAULT true,
    UNIQUE(tenant_id, phone_number)
);
-- Indice: (tenant_id, phone_number, active) para lookup rapido

-- =============================================
-- PAINEIS SINCRONIZADOS DO HELENA
-- =============================================
CREATE TYPE sync_status_enum AS ENUM ('synced', 'orphaned');

CREATE TABLE tenant_panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    helena_panel_id UUID NOT NULL,        -- ID do painel no Helena
    panel_name VARCHAR(255),              -- Nome vindo do Helena (somente leitura)
    sync_status sync_status_enum DEFAULT 'synced',
    synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, helena_panel_id)
);

-- =============================================
-- VINCULO PAINEL <-> AGENTE (N:N)
-- Um painel pode estar ativo no principal E no assessor
-- Cada vinculo tem sua propria configuracao
-- =============================================
CREATE TABLE tenant_agent_panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES tenant_agents(id) ON DELETE CASCADE,
    tenant_panel_id UUID REFERENCES tenant_panels(id) ON DELETE CASCADE,
    agent_description TEXT,               -- Descricao para o agente saber quando transferir
    helena_step_id UUID,                  -- Step padrao para criar card
    helena_department_id UUID,            -- Equipe para transferir sessao
    active BOOLEAN DEFAULT false,         -- Admin ativa manualmente
    UNIQUE(agent_id, tenant_panel_id)
);

-- =============================================
-- STEPS DOS PAINEIS (sincronizados do Helena)
-- =============================================
CREATE TABLE tenant_panel_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_panel_id UUID REFERENCES tenant_panels(id) ON DELETE CASCADE,
    helena_step_id UUID NOT NULL,
    step_name VARCHAR(255),
    step_order INT,
    synced_at TIMESTAMP
);

-- =============================================
-- CAMPOS DO CARD DE CONTATO (sincronizados do Helena)
-- Usados na ETAPA 1 - coleta de dados do cidadao
-- =============================================
CREATE TABLE tenant_contact_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    helena_field_key VARCHAR(100) NOT NULL,  -- Nome do campo no Helena (ex: "cpf", "email")
    helena_field_name VARCHAR(255),          -- Nome legivel (ex: "CPF", "E-mail")
    sync_status sync_status_enum DEFAULT 'synced',
    synced_at TIMESTAMP,
    UNIQUE(tenant_id, helena_field_key)
);

-- =============================================
-- VINCULO CAMPO DE CONTATO <-> AGENTE
-- Cada agente pode ativar/desativar campos diferentes
-- =============================================
CREATE TABLE tenant_agent_contact_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES tenant_agents(id) ON DELETE CASCADE,
    contact_field_id UUID REFERENCES tenant_contact_fields(id) ON DELETE CASCADE,
    agent_instruction TEXT,               -- "Solicite o CPF do cidadao"
    field_order INT DEFAULT 0,            -- Ordem de coleta na conversa
    required BOOLEAN DEFAULT true,        -- Obrigatorio ou opcional
    active BOOLEAN DEFAULT false,         -- Admin ativa manualmente
    UNIQUE(agent_id, contact_field_id)
);

-- =============================================
-- CAMPOS CUSTOMIZADOS DO CARD DO PAINEL (sincronizados)
-- Usados na ETAPA 3 - preenchimento do card ao transferir
-- =============================================
CREATE TABLE tenant_panel_custom_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_panel_id UUID REFERENCES tenant_panels(id) ON DELETE CASCADE,
    helena_field_id VARCHAR(100) NOT NULL, -- ID do campo no Helena
    helena_field_name VARCHAR(255),        -- Nome legivel do campo
    sync_status sync_status_enum DEFAULT 'synced',
    synced_at TIMESTAMP,
    UNIQUE(tenant_panel_id, helena_field_id)
);

-- =============================================
-- MAPEAMENTO: O QUE ARMAZENAR EM CADA CAMPO DO CARD
-- Vinculado ao agente+painel, pois principal e assessor
-- podem mapear diferente
-- =============================================
CREATE TABLE tenant_agent_panel_field_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_panel_id UUID REFERENCES tenant_agent_panels(id) ON DELETE CASCADE,
    panel_custom_field_id UUID REFERENCES tenant_panel_custom_fields(id) ON DELETE CASCADE,
    storage_instruction TEXT,             -- "Resumo completo da conversa"
    active BOOLEAN DEFAULT true,
    UNIQUE(agent_panel_id, panel_custom_field_id)
);

-- =============================================
-- DEPARTAMENTOS/EQUIPES SINCRONIZADOS
-- =============================================
CREATE TABLE tenant_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    helena_department_id UUID NOT NULL,
    department_name VARCHAR(255),
    synced_at TIMESTAMP,
    UNIQUE(tenant_id, helena_department_id)
);

-- =============================================
-- CHECKPOINTS DO LANGGRAPH (ja existente, adaptado)
-- =============================================
-- As tabelas langgraph_checkpoints, langgraph_writes, etc.
-- ganham coluna tenant_id para isolamento entre tenants
```

### 5.2 Diagrama de Relacoes

```
admin_users
  \-- -> tenants (tenant_admin ve apenas seu tenant)

tenants
  |
  +-- tenant_agents (1 principal + 1 assessor)
  |     |
  |     +-- assessor_numbers (N numeros por assessor)
  |     |
  |     +-- tenant_agent_contact_fields (N campos de coleta por agente)
  |     |     \-- -> tenant_contact_fields (campo sincronizado)
  |     |
  |     +-- tenant_agent_panels (N paineis por agente, com config propria)
  |           |    \-- -> tenant_panels (painel sincronizado)
  |           |
  |           +-- tenant_agent_panel_field_mappings (o que armazenar em cada campo)
  |                 \-- -> tenant_panel_custom_fields (campo do card sincronizado)
  |
  +-- tenant_panels (paineis sincronizados do Helena)
  |     +-- tenant_panel_steps (steps de cada painel)
  |     +-- tenant_panel_custom_fields (campos do card de cada painel)
  |
  +-- tenant_contact_fields (campos do contato sincronizados)
  |
  +-- tenant_departments (equipes sincronizadas)
```

---

## 6. Fluxo Completo do Agente Principal (Multi-Tenant)

### 6.1 Recebimento de Mensagem

```
1. Webhook recebe do n8n:
   POST /api/v1/webhook/whatsapp
   { mensagem, numero, sessionID, card_id, tenant_slug }

2. Identifica tenant pelo slug (cache 5min):
   SELECT * FROM tenants WHERE slug = 'andre-santos' AND active = true
   -> Se nao encontrado: retorna 404

3. Adquire lock por "tenant_id:numero" (previne concorrencia)

4. Verifica deduplicacao (mesmo texto + numero em 120s -> ignora)

5. Verifica se remetente e assessor:
   SELECT * FROM assessor_numbers
   WHERE tenant_id = X AND phone_number = numero AND active = true

6. Carrega configuracao do agente correto (cache 5min):
   - Prompt (persona + comportamento)
   - Campos de coleta ativos com instrucoes
   - Paineis ativos com descricoes (exclui orfaos)
   - Mapeamento de campos dos paineis
   - Token Helena do tenant

7. Executa grafo LangGraph com configuracao dinamica

8. Envia resposta diretamente via Helena API:
   POST /chat/v1/message/send-sync

9. Retorna ao n8n: { success: true, already_sent: true, ... }

10. Libera lock
```

### 6.2 ETAPA 1 — Coleta de Dados (Dinamica)

```
1. Busca contato no Helena (usando token DO TENANT)
   GET /core/v1/contact/phonenumber/{phone}

2. Carrega campos de coleta configurados para este agente:
   SELECT tcf.helena_field_key, tacf.agent_instruction, tacf.required
   FROM tenant_agent_contact_fields tacf
   JOIN tenant_contact_fields tcf ON tcf.id = tacf.contact_field_id
   WHERE tacf.agent_id = X AND tacf.active = true
   ORDER BY tacf.field_order

3. Compara campos configurados vs dados do contato no Helena
   -> Identifica campos VAZIOS que estao ATIVOS

4. Se NENHUM campo ativo OU todos preenchidos -> pula para ETAPA 2
   Se faltam campos -> Agente coleta UM POR VEZ na conversa

5. Coleta pausada:
   - Pede um campo (usando a instrucao configurada)
   - Espera resposta
   - Pede proximo campo
   - ... ate coletar todos

6. Ao final, apresenta resumo e pede confirmacao

7. Confirmado -> salva no Helena:
   PUT /core/v1/contact/phonenumber/{phone}
   Body: { customFields: { campo1: valor1, campo2: valor2, ... } }
```

### 6.3 ETAPA 2 — Classificacao (Dinamica)

```
1. Carrega paineis ATIVOS deste agente (exclui orfaos):
   SELECT tp.panel_name, tap.agent_description
   FROM tenant_agent_panels tap
   JOIN tenant_panels tp ON tp.id = tap.tenant_panel_id
   WHERE tap.agent_id = X AND tap.active = true AND tp.sync_status = 'synced'

2. Monta prompt de classificacao dinamicamente com as descricoes:
   "As categorias disponiveis sao:
    - Demandas Saude: quando o cidadao solicitar ajuda com consultas, UBS...
    - Demandas Educacao: quando solicitar vagas em escolas, creches...
    - Demandas Zeladoria: quando solicitar tapa-buraco, poda de arvore..."

3. Agente conversa ate entender a demanda

4. Classifica usando os paineis ativos como categorias

5. Resultado: { painel: "Demandas Saude", descricao: "...", resumo: "..." }
```

### 6.4 ETAPA 3 — Transferencia e Card (Dinamica)

```
1. Busca configuracao do painel classificado:
   SELECT tap.helena_step_id, tap.helena_department_id, tp.helena_panel_id
   FROM tenant_agent_panels tap
   JOIN tenant_panels tp ON tp.id = tap.tenant_panel_id
   WHERE tap.agent_id = X AND tp.panel_name = 'Demandas Saude'

2. Busca mapeamento de campos do card:
   SELECT tpcf.helena_field_id, tapfm.storage_instruction
   FROM tenant_agent_panel_field_mappings tapfm
   JOIN tenant_panel_custom_fields tpcf ON tpcf.id = tapfm.panel_custom_field_id
   WHERE tapfm.agent_panel_id = Y AND tapfm.active = true

3. Transfere sessao para departamento correto:
   PUT /chat/v1/session/{session_id}/transfer
   Body: { departmentId: helena_department_id }

4. Cria/duplica card no painel correto:
   POST /crm/v1/panel/card/{card_id}/duplicate
   Body: { panelId: helena_panel_id, stepId: helena_step_id }

5. Atualiza card com dados mapeados dinamicamente:
   PUT /crm/v2/panel/card/{new_card_id}
   -> Para cada campo mapeado, preenche de acordo com storage_instruction

6. Adiciona tags ao contato:
   POST /core/v1/contact/phonenumber/{phone}/tags

7. Limpa checkpoints do LangGraph (permite nova conversa)

8. Envia mensagem de despedida via Helena:
   POST /chat/v1/message/send-sync
```

---

## 7. Tratamento de Erros

### 7.1 Erros da API Helena

| Cenario | Comportamento |
|---------|---------------|
| **Helena fora do ar (timeout/5xx)** | Retry com backoff exponencial (3 tentativas, 1s/2s/4s). Se falhar, envia ao cidadao: "Desculpe, estamos com dificuldade tecnica. Tente novamente em alguns minutos." e preserva checkpoint. |
| **Token invalido (401)** | NAO faz retry. Marca tenant com flag `helena_error`. Admin ve alerta no painel. Responde ao cidadao com mensagem generica de indisponibilidade. |
| **Contato nao encontrado (404)** | Trata como contato novo — segue fluxo normal de coleta de dados. |
| **Card nao encontrado na duplicacao** | Cria card novo em vez de duplicar. Loga o erro. |
| **Transferencia falha** | Cria o card mesmo assim (dados nao se perdem). Loga erro. Admin ve alerta. |
| **Rate limit (429)** | Retry apos tempo indicado no header. Se persistir, aguarda e tenta na proxima mensagem. |

### 7.2 Erros do LLM

| Cenario | Comportamento |
|---------|---------------|
| **LLM fora do ar** | Responde: "Estou com dificuldade no momento. Tente novamente em instantes." Preserva checkpoint. |
| **Classificacao ambigua** | Se o LLM nao conseguir classificar com confianca apos 2 tentativas, classifica como painel de "atendimento geral" (o admin deve ter um painel catch-all ativo). |
| **Resposta sem marcador esperado** | Continua conversa normalmente — so processa marcadores quando aparecem. |

### 7.3 Falha Parcial na ETAPA 3

Se a ETAPA 3 falha no meio (ex: card duplicado mas nao atualizado):

```
1. Salva estado de "transferencia parcial" no checkpoint
2. Na proxima tentativa, retoma de onde parou:
   - Se card ja duplicado -> so atualiza
   - Se card ja atualizado -> so transfere sessao
   - Se tudo feito -> so limpa e envia despedida
3. Cada sub-etapa e idempotente
```

---

## 8. Funcionalidade de Sincronizacao

### O que acontece quando o admin clica "Sincronizar"

```
Botao "Sincronizar" clicado
        |
        v
1. GET /crm/v1/panel (lista todos os paineis)
   -> Para cada painel:
      GET /crm/v1/panel/{id} (busca steps)
      GET /crm/v1/panel/{id}/custom-fields (busca campos do card)
   -> Salva em: tenant_panels, tenant_panel_steps, tenant_panel_custom_fields
        |
        v
2. GET /v2/department (lista equipes)
   -> Salva em: tenant_departments
        |
        v
3. GET /core/v1/contact/custom-field (campos do card de contato)
   -> Salva em: tenant_contact_fields
        |
        v
4. Cria vinculos iniciais (inativos) para os agentes:
   -> tenant_agent_panels (todos inativos por padrao)
   -> tenant_agent_contact_fields (todos inativos por padrao)
   -> tenant_agent_panel_field_mappings (todos inativos por padrao)
        |
        v
5. Detecta itens orfaos:
   -> Paineis que estavam no banco mas NAO vieram na sincronizacao:
      Se estiver ativo -> marca sync_status = 'orphaned'
      Se estiver inativo -> remove do banco
   -> Campos de contato idem
   -> Campos de card idem
        |
        v
6. Exibe para o admin:
   "Sincronizacao concluida!
    - 8 paineis encontrados (3 ativos, 5 inativos)
    - 12 equipes encontradas
    - 15 campos de contato encontrados
    - AVISO: 1 painel orfao detectado (verificar)"
```

**Regras da sincronizacao:**
- NUNCA desativa paineis/campos ja ativos pelo admin
- Adiciona novos itens como **inativos** por padrao
- Atualiza nomes de itens existentes
- Itens inativos que nao existem mais no Helena sao **removidos**
- Itens ativos que nao existem mais no Helena sao marcados **orfaos** (com aviso)
- Pode ser executada quantas vezes quiser sem perder configuracao

---

## 9. Geracao Dinamica de Prompts

O sistema monta o prompt final automaticamente combinando pecas configuraveis:

```
+---------------------------------------------------------------+
|                    PROMPT FINAL DO AGENTE                       |
|                                                                 |
|  +-----------------------------------------------------------+ |
|  | 1. REGRAS DO SISTEMA (fixo no codigo)                      | |
|  |    Marcadores, formato de resposta, controle de fluxo      | |
|  |    [DADOS_CONFIRMADOS], [CLASSIFICAR_DEMANDA], etc.        | |
|  +-----------------------------------------------------------+ |
|                          +                                      |
|  +-----------------------------------------------------------+ |
|  | 2. PROMPT DA PERSONA (editavel pelo admin)                 | |
|  |    "Voce e a Livia, assistente do Vereador X..."           | |
|  +-----------------------------------------------------------+ |
|                          +                                      |
|  +-----------------------------------------------------------+ |
|  | 3. PROMPT DE COMPORTAMENTO (editavel pelo admin)           | |
|  |    "Seja breve, maximo 3 frases por mensagem..."           | |
|  |    "Peca um dado por vez, confirme antes de salvar..."     | |
|  +-----------------------------------------------------------+ |
|                          +                                      |
|  +-----------------------------------------------------------+ |
|  | 4. CAMPOS DE COLETA ATIVOS (gerado do banco)               | |
|  |    "Campos para solicitar: cpf (Solicite o CPF),           | |
|  |     email (Solicite o e-mail), cep (Solicite o CEP)..."   | |
|  +-----------------------------------------------------------+ |
|                          +                                      |
|  +-----------------------------------------------------------+ |
|  | 5. CATEGORIAS/PAINEIS ATIVOS (gerado do banco)             | |
|  |    "Categorias disponiveis:                                 | |
|  |     - Demandas Saude: quando pedir ajuda medica...         | |
|  |     - Demandas Educacao: quando pedir vaga escolar..."     | |
|  +-----------------------------------------------------------+ |
|                          +                                      |
|  +-----------------------------------------------------------+ |
|  | 6. MAPEAMENTO DE CAMPOS DO CARD (gerado do banco)          | |
|  |    "Ao criar card, preencher:                               | |
|  |     - Solicitacao: nome da solicitacao                      | |
|  |     - Descricao: resumo completo..."                       | |
|  +-----------------------------------------------------------+ |
|                          +                                      |
|  +-----------------------------------------------------------+ |
|  | 7. CONTEXTO DA ETAPA ATUAL (gerado pelo estado)            | |
|  |    Campos faltantes, dados ja coletados, classificacao     | |
|  +-----------------------------------------------------------+ |
|                                                                 |
+---------------------------------------------------------------+
```

**Blocos 1:** Fixo no codigo — admin nao mexe
**Blocos 2 e 3:** Editaveis pelo admin — controle total por tenant
**Blocos 4, 5, 6:** Gerados automaticamente a partir da configuracao no banco
**Bloco 7:** Gerado em tempo real pelo estado da conversa

---

## 10. Telas do Super Admin

### 10.1 Dashboard

```
+----------------------------------------------------------------------+
|  AGENTE GABINETE - Super Admin                              [Sair]   |
+----------------------------------------------------------------------+
|                                                                      |
|  Tenants Ativos: 5                                                   |
|                                                                      |
|  +------------------------------------------------------------------+|
|  | Nome                    | Status | Ultimo Sync        | Acao     ||
|  +--------------------------+--------+--------------------+----------+|
|  | Gab. Vereador Andre     | * ON   | 14/03/2026 10:30   | [config] ||
|  | Gab. Deputada Maria     | * ON   | 13/03/2026 15:00   | [config] ||
|  | Gab. Vereador Joao      | * ON   | 14/03/2026 08:00   | [config] ||
|  | Gab. Vereadora Ana      | o OFF  | nunca              | [config] ||
|  | Gab. Deputado Carlos    | * ON   | 12/03/2026 09:30   | [config] ||
|  +------------------------------------------------------------------+|
|                                                                      |
|  [+ Novo Tenant]                                                     |
|                                                                      |
+----------------------------------------------------------------------+
```

### 10.2 Configuracao do Tenant - Aba Geral

```
+----------------------------------------------------------------------+
|  Gabinete Vereador Andre Santos                                      |
+----------------------------------------------------------------------+
|  [*Geral] [Agente Principal] [Agente Assessor]                       |
+----------------------------------------------------------------------+
|                                                                      |
|  -- Dados Gerais --                                                  |
|  Nome: [Gabinete Vereador Andre Santos        ]                      |
|  Slug: [andre-santos] (usar no n8n como tenant_slug)                 |
|  Token Helena: [pn_*************************  ]                      |
|  Chave LLM: [Usar compartilhada v]                                   |
|                                                                      |
|  [Sincronizar com Helena]  Ultimo sync: 14/03/2026 10:30             |
|  Resultado: 8 paineis, 12 equipes, 15 campos de contato             |
|  ! AVISO: 1 painel orfao detectado                                   |
|                                                                      |
|  -- Admins deste Tenant --                                           |
|  +--------------------------------------------+                     |
|  | admin@gabinete.com  | Admin | [Remover]     |                     |
|  +--------------------------------------------+                     |
|  [+ Adicionar admin]                                                 |
|                                                                      |
|  Status: * Ativo    [Desativar]                                      |
|                                                                      |
|  [Salvar]                                                            |
+----------------------------------------------------------------------+
```

### 10.3 Aba: Agente Principal

```
+----------------------------------------------------------------------+
|  [Geral] [*Agente Principal] [Agente Assessor]                       |
+----------------------------------------------------------------------+
|                                                                      |
|  -- Prompt da Persona --                                             |
|  +------------------------------------------------------------------+|
|  | Voce e a Livia, assistente virtual do gabinete do                 ||
|  | Vereador Andre Santos, Sao Paulo/SP.                              ||
|  | Tom: educada, empatica, objetiva.                                 ||
|  +------------------------------------------------------------------+|
|                                                                      |
|  -- Prompt de Comportamento --                                       |
|  +------------------------------------------------------------------+|
|  | - Sempre cumprimente pelo nome quando disponivel                  ||
|  | - Seja breve, maximo 3 frases por mensagem                        ||
|  | - Peca um dado por vez, confirme antes de salvar                  ||
|  | - Se nao entender apos 2 tentativas, classifique geral           ||
|  +------------------------------------------------------------------+|
|                                                                      |
|  -- Campos de Coleta (sincronizados do contato Helena) --            |
|  +----------------+-------+------+-----------------------------------+|
|  | Campo Helena   | Ativo | Obr. | Instrucao para o agente           ||
|  +----------------+-------+------+-----------------------------------+|
|  | email          | [x]   | [x]  | "Solicite o e-mail"              ||
|  | cpf            | [x]   | [x]  | "Solicite o CPF"                 ||
|  | data-nascimento| [x]   | [ ]  | "Solicite a data de nascimento"  ||
|  | cep            | [x]   | [x]  | "Solicite o CEP"                 ||
|  | endereco       | [x]   | [x]  | "Solicite o endereco completo"   ||
|  | bairro         | [x]   | [x]  | "Solicite o bairro"              ||
|  | cidade         | [x]   | [x]  | "Solicite a cidade"              ||
|  | estado         | [x]   | [x]  | "Solicite o estado"              ||
|  | rg             | [ ]   | [ ]  | —                                 ||
|  | profissao      | [ ]   | [ ]  | —                                 ||
|  +----------------+-------+------+-----------------------------------+|
|                                                                      |
|  -- Paineis Ativos (Agente Principal) --                             |
|  +--------------------+--------+--------------------------+          |
|  | Painel             | Status | Equipe destino           |          |
|  +--------------------+--------+--------------------------+          |
|  | Demandas Saude     | [x]    | Assessores Saude      v |          |
|  | Demandas Educacao  | [x]    | Assessores Educacao   v |          |
|  | Demandas Zeladoria | [x]    | Assessores Zeladoria  v |          |
|  | Atend. Geral       | [x]    | Recepcao             v |          |
|  | Agenda Interna     | [ ]    | —                        |          |
|  | Financeiro         | [ ]    | —                        |          |
|  | ! Marketing (orfao)| [!]    | — desativar              |          |
|  +--------------------+--------+--------------------------+          |
|  (Clique no painel para configurar descricao e campos do card)       |
|                                                                      |
|  [Salvar]                                                            |
+----------------------------------------------------------------------+
```

### 10.4 Configuracao do Painel (ao clicar)

```
+----------------------------------------------------------------------+
|  Configurar Painel: Demandas Saude                                   |
|  Agente: Principal                                                   |
+----------------------------------------------------------------------+
|                                                                      |
|  Step padrao: [Novos Atendimentos v]                                 |
|  Equipe: [Assessores Saude v]                                        |
|                                                                      |
|  -- Descricao para o agente (quando transferir para ca) --           |
|  +------------------------------------------------------------------+|
|  | Transferir para este painel quando o cidadao solicitar ajuda      ||
|  | relacionada a: consultas medicas, medicamentos, UBS, UPA,         ||
|  | hospitais, postos de saude, vacinas, exames, cirurgias,           ||
|  | ambulancias, SAMU, saude mental, dependencia quimica,             ||
|  | ou qualquer demanda de saude publica.                             ||
|  +------------------------------------------------------------------+|
|                                                                      |
|  -- Campos do Card (sincronizados do painel Helena) --               |
|  +---------------------+-------+-------------------------------------+|
|  | Campo do Card       | Ativo | O que armazenar neste campo         ||
|  +---------------------+-------+-------------------------------------+|
|  | Solicitacao         | [x]   | "Nome/tipo da solicitacao"           ||
|  | Manifestacao        | [x]   | "Categoria da demanda"               ||
|  | Desc. Manifestacao  | [x]   | "Resumo completo da conversa"        ||
|  | CPF                 | [x]   | "CPF do cidadao"                     ||
|  | Email               | [x]   | "Email do cidadao"                   ||
|  | CEP                 | [x]   | "CEP do cidadao"                     ||
|  | Endereco            | [x]   | "Endereco completo"                  ||
|  | Data Cadastro       | [x]   | "Data do contato (automatico)"       ||
|  | Urgencia            | [x]   | "Nivel: baixa/media/alta"            ||
|  +---------------------+-------+-------------------------------------+|
|                                                                      |
|  [Salvar] [Voltar]                                                   |
+----------------------------------------------------------------------+
```

---

## 11. Stack Tecnica

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| Backend API | **FastAPI** (Python) | Ja usado no sistema atual |
| Agente IA | **LangGraph** | Ja usado, workflow comprovado |
| LLM | **Grok** (xAI) padrao | Pode ser trocado por tenant (campo llm_provider) |
| Banco de dados | **PostgreSQL** | Ja usado, adiciona tabelas de config |
| Frontend Admin | **Next.js** (React) | Painel moderno |
| Auth Admin | **JWT** + bcrypt | Login do Super Admin e Admin do Tenant |
| Deploy | **Docker** + **Docker Compose** | Mesmo modelo atual |
| Orquestracao | **n8n** | Webhook que repassa mensagens com tenant_slug |

**Onde fica cada coisa:**
- **PostgreSQL:** Configuracoes, prompts, mapeamentos, estado LangGraph, usuarios admin
- **Helena CRM:** Dados de cidadaos, cards, contatos, tags, historico de conversa
- **Cache em memoria:** Lookup de tenant por slug, config do agente (TTL 5min)

---

## 12. Mudancas no Codigo Atual

### O que MANTEM igual:
- Estrutura base do grafo LangGraph (etapas)
- Logica de marcadores (`[DADOS_CONFIRMADOS]`, `[CLASSIFICAR_DEMANDA]`, `[RECUSA_DADOS]`)
- Client do Helena (`helena_client.py`) — agora recebe token como parametro
- Client do CEP (`cep_client.py`) — sem mudancas
- Logica de dedup e session lock (agora com tenant_id na chave)
- Envio de resposta direto via Helena API (already_sent=true)

### O que MUDA:
| Arquivo | Mudanca |
|---------|---------|
| `constants.py` | **Eliminado** — categorias vem do banco |
| `prompts.py` | **Refatorado** — monta prompt dinamico: persona + comportamento + campos + paineis |
| `settings.py` | **Refatorado** — carrega config por tenant |
| `helena_client.py` | **Adaptado** — recebe token como parametro (nao mais do .env) |
| `validate_contact.py` | **Adaptado** — campos de coleta dinamicos vindos do banco |
| `classify_demand.py` | **Adaptado** — categorias sao os paineis ativos com descricoes |
| `transfer_route.py` | **Adaptado** — IDs e mapeamento de campos do banco |
| `webhook.py` | **Adaptado** — identifica tenant por slug + rota agente |
| `graph.py` | **Adaptado** — recebe config do tenant + grafo simplificado para assessor |
| `nodes.py` | **Adaptado** — usa config dinamica em vez de constantes |
| `state.py` | **Adaptado** — adiciona tenant_id e agent_type ao estado |

### O que e NOVO:
| Componente | Descricao |
|-----------|-----------|
| `src/models/` | Modelos SQLAlchemy de todas as tabelas |
| `src/services/tenant_service.py` | CRUD de tenants, carregar config |
| `src/services/sync_service.py` | Logica de sincronizacao com Helena |
| `src/services/auth_service.py` | Autenticacao JWT + bcrypt |
| `src/api/routes/admin.py` | Endpoints do painel admin |
| `src/api/routes/auth.py` | Login, refresh token |
| `frontend/` | Painel Super Admin em Next.js |

---

## 13. Endpoints da API

### 13.1 Webhook (recebe mensagens)

```
POST   /api/v1/webhook/whatsapp                Recebe mensagem do n8n
```

### 13.2 Autenticacao

```
POST   /api/v1/auth/login                      Login (email + senha) -> JWT
POST   /api/v1/auth/refresh                    Refresh token
POST   /api/v1/auth/change-password            Trocar senha
```

### 13.3 Admin - Tenants (Super Admin)

```
POST   /api/v1/admin/tenants                              Criar tenant
GET    /api/v1/admin/tenants                              Listar tenants
GET    /api/v1/admin/tenants/{id}                         Detalhes do tenant
PUT    /api/v1/admin/tenants/{id}                         Atualizar tenant
PUT    /api/v1/admin/tenants/{id}/deactivate              Desativar tenant
```

### 13.4 Admin - Sincronizacao

```
POST   /api/v1/admin/tenants/{id}/sync                   Sincronizar com Helena
```

### 13.5 Admin - Usuarios (Super Admin)

```
POST   /api/v1/admin/users                               Criar admin
GET    /api/v1/admin/users                               Listar admins
PUT    /api/v1/admin/users/{uid}                         Atualizar admin
PUT    /api/v1/admin/users/{uid}/deactivate              Desativar admin
```

### 13.6 Admin - Agentes (Admin do Tenant)

```
GET    /api/v1/admin/tenants/{id}/agents                  Listar agentes
PUT    /api/v1/admin/tenants/{id}/agents/{type}           Atualizar agente (prompts)
```

### 13.7 Admin - Campos de Coleta do Contato

```
GET    /api/v1/admin/tenants/{id}/agents/{type}/contact-fields    Listar campos
PUT    /api/v1/admin/tenants/{id}/agents/{type}/contact-fields    Atualizar config
```

### 13.8 Admin - Paineis por Agente

```
GET    /api/v1/admin/tenants/{id}/agents/{type}/panels            Listar paineis
PUT    /api/v1/admin/tenants/{id}/agents/{type}/panels/{pid}      Configurar painel
```

### 13.9 Admin - Mapeamento de Campos do Card

```
GET    /api/v1/admin/tenants/{id}/agents/{type}/panels/{pid}/field-mappings    Listar
PUT    /api/v1/admin/tenants/{id}/agents/{type}/panels/{pid}/field-mappings    Atualizar
```

### 13.10 Admin - Numeros do Assessor

```
GET    /api/v1/admin/tenants/{id}/assessor-numbers        Listar numeros
POST   /api/v1/admin/tenants/{id}/assessor-numbers        Adicionar numero
DELETE /api/v1/admin/tenants/{id}/assessor-numbers/{nid}   Remover numero
```

### 13.11 Admin - Dados Sincronizados (somente leitura)

```
GET    /api/v1/admin/tenants/{id}/departments              Listar equipes
GET    /api/v1/admin/tenants/{id}/panels                   Listar paineis sincronizados
GET    /api/v1/admin/tenants/{id}/panels/{pid}/steps       Listar steps do painel
GET    /api/v1/admin/tenants/{id}/panels/{pid}/custom-fields  Listar campos do card
GET    /api/v1/admin/tenants/{id}/contact-fields           Listar campos do contato
```

**Paginacao:** Todos os endpoints GET de listagem suportam `?page=1&page_size=50` (padrao 50, max 100).

---

## 14. Seguranca do Webhook

O endpoint de webhook (`POST /api/v1/webhook/whatsapp`) e protegido por:

1. **Token Bearer fixo** configurado no n8n e no sistema (variavel de ambiente `WEBHOOK_SECRET`)
2. Toda requisicao sem o header `Authorization: Bearer {WEBHOOK_SECRET}` e rejeitada com 401
3. Opcional futuro: whitelist de IPs do n8n

---

## 15. Fluxo de Onboarding (Novo Gabinete)

```
Passo 1: Super Admin cria tenant
   -> Nome: "Gabinete Deputada Maria Silva"
   -> Slug: "maria-silva"
   -> Token Helena: pn_xxxxxxxxxxxx
   -> Cria usuario Admin do Tenant (email + senha)

Passo 2: Configura n8n
   -> Cria fluxo n8n com tenant_slug: "maria-silva"
   -> Aponta webhook do Helena para o n8n
   -> n8n repassa para API com o slug

Passo 3: Admin do Tenant faz login e sincroniza
   -> Clica "Sincronizar com Helena"
   -> Sistema busca: paineis, steps, campos de card, campos de contato, equipes

Passo 4: Configurar Agente Principal
   -> Escrever prompt da persona (quem e, tom de voz)
   -> Escrever prompt de comportamento (como conduz a conversa)
   -> Ativar campos de coleta + instrucao breve em cada um
   -> Ativar paineis + descricao de cada um
   -> Mapear campos do card de cada painel
   -> Selecionar equipe destino para cada painel

Passo 5 (opcional): Configurar Agente Assessor
   -> Adicionar numeros da equipe interna
   -> Escrever prompts do assessor
   -> Ativar paineis + descricoes
   -> Mapear campos do card
   -> Ativar campos de coleta se necessario

Passo 6: Ativar tenant
   -> Agente comeca a funcionar
```

---

## 16. Seguranca Geral

- **Tokens Helena** armazenados encriptados no banco (AES-256)
- **Chaves LLM** encriptadas no banco
- **Senhas admin** bcrypt com salt
- **Isolamento total** entre tenants (queries sempre filtram por tenant_id)
- **Auth do painel** via JWT (24h) + refresh token (7 dias)
- **Webhook protegido** por Bearer token fixo
- **Dados de cidadaos NUNCA ficam no banco local** — sempre salvos direto no Helena
- **Rate limiting** por tenant para proteger APIs Helena
- **Logs** com tenant_id para auditoria

---

## 17. Escalabilidade

| Cenario | Solucao |
|---------|---------|
| 10 tenants | Unico servidor, Docker Compose |
| 50 tenants | Servidor maior, connection pooling, cache Redis |
| 100+ tenants | Multiplos workers, fila de mensagens (Redis/Celery) |

---

## 18. Resumo das Entregas

| # | Entrega | Descricao |
|---|---------|-----------|
| 1 | **Banco multi-tenant** | Schema completo com 13 tabelas |
| 2 | **Sincronizacao Helena** | Auto-descoberta de paineis, equipes, campos + status orfao |
| 3 | **Auth + Usuarios** | JWT, bcrypt, super_admin e tenant_admin |
| 4 | **API Admin** | CRUD completo + endpoints de config + paginacao |
| 5 | **Refatoracao do agente** | Config dinamica, prompts editaveis, mapeamento de campos |
| 6 | **Agente Assessor** | Roteamento por numero + grafo simplificado (2 etapas) |
| 7 | **Tratamento de erros** | Retry, fallback, recuperacao parcial, alertas |
| 8 | **Painel Super Admin** | Frontend Next.js completo |
| 9 | **Testes e Deploy** | Testes + Docker + CI/CD |

---

## 19. Proximos Passos

Apos validacao deste documento:

1. **Fase 1:** Banco de dados (schema completo + migrations) + Auth
2. **Fase 2:** Sincronizacao Helena + API Admin (CRUD tenants, agentes, paineis, campos)
3. **Fase 3:** Refatoracao do agente para multi-tenant (prompts dinamicos, config do banco)
4. **Fase 4:** Agente Assessor (roteamento por numero + grafo simplificado)
5. **Fase 5:** Frontend Super Admin (Next.js)
6. **Fase 6:** Tratamento de erros, testes, seguranca e deploy

---

*Documento v3.0 — Revisado com correcoes criticas (identificacao de tenant, ciclo de vida da conversa, modelo de autorizacao, tratamento de erros, status orfao, fluxo do assessor, envio de mensagens). Aguardando validacao para iniciar construcao.*
