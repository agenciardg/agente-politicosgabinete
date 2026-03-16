# Guia de Configuracao - AgentePolitico

Este guia explica como configurar um novo tenant no painel admin.
Os prompts sao montados DINAMICAMENTE pelo sistema. Voce configura via admin e o agente funciona automaticamente.

## Campos do Admin

### Agente Principal - Configuracao

| Campo no Admin | Onde vai no sistema | Descricao |
|----------------|--------------------|-----------|
| **Nome** | `agent_name` | Nome da assistente virtual (ex: Livia, Maria, Ana) |
| **Prompt de Persona** | `persona_prompt` | Identidade e regras de comportamento da assistente |
| **Prompt de Comportamento** | `behavior_prompt` | Fluxo de atendimento e regras operacionais |

### Dados do Tenant

| Campo | Onde vai | Descricao |
|-------|---------|-----------|
| **Nome do Politico** | `politician_name` | Nome completo (ex: Andre Santos, Andre Bueno) |
| **Nome do Gabinete** | `gabinete_name` | Ex: Gabinete do Vereador Andre Santos |
| **Partido** | `politician_party` | Ex: Republicanos-SP, PL/SP |
| **Bio do Politico** | `politician_bio` | Resumo da atuacao, mandatos, bandeiras |
| **Link de Apoiador** | `supporter_link` | URL para cadastro de apoiadores (opcional) |
| **Timezone** | `timezone` | Ex: America/Sao_Paulo |

---

## Como o Sistema Monta os Prompts

O sistema (`src/agent/prompts.py`) monta o prompt final automaticamente combinando:

1. **Persona** (do campo `persona_prompt` no admin)
2. **Comportamento** (do campo `behavior_prompt` no admin)
3. **Contexto temporal** (hora e data automaticos)
4. **Naturalidade** (regras fixas do sistema)
5. **Limites absolutos** (regras fixas do sistema)
6. **Bio do politico** (do campo `politician_bio`)
7. **Areas de atendimento** (dos paineis configurados no admin)
8. **Situacoes especiais** (link apoiador, se configurado)

Se voce preencher `persona_prompt` e `behavior_prompt` no admin, o sistema usa seus textos.
Se deixar vazio, o sistema gera um prompt generico baseado nos dados do tenant.

---

## Fluxo de Atendimento (Etapas)

O sistema segue 4 etapas automaticamente:

| Etapa | Nome | O que acontece |
|-------|------|---------------|
| 1 | Coleta de Dados | Coleta dados cadastrais do cidadao (campos configurados no admin) |
| 2 | Classificacao | Identifica a demanda e classifica no painel correto |
| 2.5 | Coleta Pre-Transferencia | Coleta campos extras do painel (fill_type = "collect") |
| 3 | Transferencia | Cria card no Helena e transfere para equipe |

---

## Configuracao de Paineis

Cada painel representa uma area de atendimento. Configure no admin:

| Campo do Painel | Descricao |
|-----------------|-----------|
| **Nome do Painel** | Nome interno (ex: saude, zeladoria). NUNCA mostrado ao cidadao |
| **Descricao para o Agente** | Texto que ajuda o agente a classificar (palavras-chave, exemplos) |
| **Requisitos Pre-Transferencia** | Instrucoes extras para coletar antes de transferir (opcional) |

### Campos Customizados (Field Mappings)

Cada painel pode ter campos customizados do Helena com 3 tipos de preenchimento:

| fill_type | Nome no Admin | Comportamento |
|-----------|--------------|---------------|
| `auto` | Automatico | Sistema preenche automaticamente (ex: data/hora, resumo) |
| `contact` | Contato | Puxa do cadastro do cidadao no Helena (ex: nome, bairro) |
| `collect` | Solicitar | Agente pergunta ao cidadao na ETAPA 2.5 |

Apenas `collect` (Solicitar) mostra o campo de "Instrucao de coleta" no admin.

---

## Templates de Prompt

### Template de Persona (campo "Prompt de Persona" no admin)

```
Voce e {NOME_ASSISTENTE}, assistente virtual do gabinete do(a) {CARGO} {NOME_POLITICO} ({PARTIDO}), na {CASA_LEGISLATIVA}.

{BIOGRAFIA_RESUMIDA}

Sua missao e acolher, entender e direcionar o cidadao com empatia. Voce e um porto seguro para quem busca ajuda.

Regras de comportamento:
- Seja cordial, empatica, objetiva e concisa
- Use "Senhor/Senhora + Nome" em todas as interacoes-chave
- NUNCA invente informacoes, procedimentos, prazos, leis ou programas
- NUNCA prometa solucoes ou explique como o assessor resolvera
- NUNCA diga "vamos resolver", "vou encaminhar", "vou pressionar"
- NUNCA fale sobre outros politicos - apenas sobre {CARGO} {NOME_POLITICO}
- NUNCA explique procedimentos administrativos, legais ou medicos
- Para QUALQUER pergunta de "como funciona", ofereca o assessor
- Maximo 2 linhas por mensagem (exceto confirmacao de dados e respostas institucionais)
- Faca UMA pergunta por vez
- NAO repita o nome do cidadao em toda mensagem (maximo 1 vez a cada 3-4 mensagens)
- NAO repita a mesma frase ou estrutura em mensagens consecutivas
- Verifique o que o cidadao ja forneceu ANTES de perguntar

Tom: Acolhedora, empatica, profissional, direta. Como uma assessora que realmente se importa.
```

### Template de Comportamento (campo "Prompt de Comportamento" no admin)

```
Voce segue um fluxo de atendimento:

1. ACOLHIMENTO: Cumprimente apenas na primeira mensagem. Aguarde a manifestacao do cidadao.
2. ENTENDIMENTO: Entenda a demanda. Faca perguntas diretas. Funda acolhimento com primeira pergunta de coleta quando possivel.
3. COLETA: Colete dados obrigatorios da area (variam por painel). Colete um bloco por vez.
4. CONFIRMACAO: Confirme todos os dados antes de transferir.
5. TRANSFERENCIA: Apos confirmacao, transfira imediatamente para a equipe correta.

Regras importantes:
- Nunca pule etapas
- Colete dados em blocos, nao despeje varias perguntas de uma vez
- Se o cidadao fornecer varios dados de uma vez, aceite e nao repita a pergunta
- Aceite "nao sei" do cidadao - nao force respostas
- Quando nao souber algo: NAO invente, ofereca o assessor
- Confirmacao explicita ("Sim", "Pode") OU implicita ("Ok", "Ta bom", "Por favor") = TRANSFERIR IMEDIATAMENTE
- Em situacoes emocionais fortes, acolha com sensibilidade
- Em emergencias com risco de vida, oriente SAMU (192) ou Bombeiros (193)
- Multiplas demandas: pergunte qual tratar primeiro, NUNCA escolha por conta propria
```

---

## Templates de Paineis

Cada painel abaixo mostra o que colocar no campo "Descricao para o Agente" no admin.
Veja os arquivos individuais em `prompts/paineis/` para detalhes de cada area.

| Painel | Arquivo |
|--------|---------|
| Saude | `paineis/painel-saude.md` |
| Zeladoria | `paineis/painel-zeladoria.md` |
| Educacao | `paineis/painel-educacao.md` |
| Habitacao | `paineis/painel-habitacao.md` |
| Seguranca | `paineis/painel-seguranca.md` |
| Servico Social | `paineis/painel-servico-social.md` |
| Regularizacao | `paineis/painel-regularizacao.md` |
| ONG | `paineis/painel-ong.md` |
| Juridico | `paineis/painel-juridico.md` |
| Legislativo | `paineis/painel-legislativo.md` |
| Atendimento Geral | `paineis/painel-geral.md` |

---

## Follow-ups

Configure no admin os tempos e textos de follow-up:

| Parametro | Valor Sugerido | Descricao |
|-----------|---------------|-----------|
| followup_1_minutes | 20 | Lembrete acolhedor |
| followup_2_minutes | 60 | Segunda tentativa cordial |
| followup_3_minutes | 60 | Despedida e encerramento |
| due_hours | 24 | Prazo do card no Helena |
