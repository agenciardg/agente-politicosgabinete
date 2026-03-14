# Guia dos Squads Disponiveis

Explicacao simples do que cada squad faz e quando usar.

---

## DESENVOLVIMENTO

### api-development (`/api`)
**O que faz:** Cria APIs REST completas — design OpenAPI, CRUD com Zod e Prisma, documentacao Swagger, testes de integracao.
**Quando usar:** Quando precisar criar ou estruturar uma API do zero.

### nirvana-backend (`/bk`)
**O que faz:** Analisa frontends e monta backends completos com Supabase, Redis, MinIO, Docker. Deploya em VPS.
**Quando usar:** Quando tiver um frontend pronto e precisar do backend inteiro.

### design-system-nirvana (`/ds`)
**O que faz:** Gera Design Systems atomicos com validacao SEO/acessibilidade e documentacao Storybook.
**Quando usar:** Quando precisar de um sistema de design padronizado (tokens, componentes, docs).

---

## LANDING PAGES

### landing-page-nirvana (`/lp`)
**O que faz:** Cria landing pages com Next.js, Tailwind, shadcn/ui. Usa estrategia AIDA e copywriting Hormozi.
**Quando usar:** Landing page de conversao com framework moderno.

### nirvana-landingpage (`/nirvana-landingpage`)
**O que faz:** Squad fullstack para landing pages. Cada secao e planejada, escrita, desenhada e construida por agentes separados.
**Quando usar:** Landing page mais elaborada onde cada secao precisa de atencao individual.

### ultimate-landingpage (`/ultimate-lp`)
**O que faz:** O mais completo. 9 agentes: discovery, pesquisa, copy, design system, imagens IA, frontend Next.js, backend FastAPI com admin panel, integracoes (WhatsApp, email), QA.
**Quando usar:** Landing page de alta conversao que precisa de backend, admin e integracoes.

---

## COPYWRITING E VENDAS

### high-conversion-copy (`/hcc`)
**O que faz:** Copywriting de alta conversao — pesquisa de avatar, headlines, sales pages, email sequences, ads copy, revisao CRO.
**Quando usar:** Quando precisar de textos de venda para infoprodutos.

### high-conversion-copywriting (`/hcc`)
**O que faz:** Similar ao anterior — pesquisa de avatar, estrategia, copy, otimizacao e revisao.
**Quando usar:** Mesma funcao, versao alternativa.

### copywriting-infoprodutos (`/cw`)
**O que faz:** Pipeline completo para infoprodutos: pesquisa de avatar, big idea, headlines, paginas de venda, roteiros VSL, sequencias de email.
**Quando usar:** Quando for criar um lancamento de infoproduto do zero.

### sales-funnel-masters (`/sfm`)
**O que faz:** 20 mind-clones de especialistas mundiais (Brunson, Hormozi, Cialdini, etc.) para funis de venda, precificacao, copy, lancamentos, trafego.
**Quando usar:** Quando quiser opiniao de "especialistas" sobre estrategia de vendas/funil.

---

## CONTEUDO E MARCA

### content-factory-squad (`/cfs`)
**O que faz:** Producao de conteudo em escala — planejamento editorial, artigos, adaptacao para redes sociais, briefs de imagem, agendamento.
**Quando usar:** Quando precisar de calendario editorial e conteudo em volume.

### brandcraft (`/brandcraft`)
**O que faz:** Extrai design system de URLs, cria documentos visuais (PDF, PPTX, carousels, social cards, videos). 9 agentes especializados.
**Quando usar:** Quando precisar de materiais visuais consistentes com uma marca.

---

## IA E CONTEXTO

### nirvana-context-engineering (`/ncea`)
**O que faz:** Engenharia de contexto para agentes de IA — entrevista, analise, design e geracao de artefatos de contexto otimizados.
**Quando usar:** Quando quiser melhorar prompts, CLAUDE.md, ou instrucoes de agentes.

### nirvana-context-enricher (`/nce`)
**O que faz:** Pesquisa paralela profunda sobre qualquer topico — deep research, skills, bibliotecas GitHub, papers academicos.
**Quando usar:** Quando precisar pesquisar um tema a fundo antes de implementar.

### nirvana-context-window-optimizer (`/ncwo`)
**O que faz:** Audita e otimiza configs de IA (.claude, .codex, .gemini, etc.) para reduzir consumo de context window.
**Quando usar:** Quando suas configuracoes de IA estiverem pesadas/grandes demais.

### fabrica-de-genios (`/fdg`)
**O que faz:** Transforma conhecimento bruto em "mind-clones" de IA completos. Pipeline de 5 estagios com 36 agentes.
**Quando usar:** Quando quiser criar um agente que simule uma pessoa/especialista especifico.

---

## DEVOPS E SEGURANCA

### incident-response-squad (`/irs`)
**O que faz:** Resposta a incidentes — analise de logs, causa raiz, execucao de runbooks, comunicacao de status, post-mortems.
**Quando usar:** Quando tiver um incidente em producao e precisar investigar.

### soc-alert-triage (`/sat`)
**O que faz:** Triagem de alertas de seguranca — classificacao, filtragem de falsos positivos, priorizacao, enriquecimento com threat intel.
**Quando usar:** Quando tiver alertas de seguranca para analisar.

---

## RH

### resume-screener-squad (`/rss`)
**O que faz:** Triagem de curriculos — parsing de CVs, matching de skills com vaga, auditoria de vieses, ranking de candidatos, resumos para gestores.
**Quando usar:** Quando precisar filtrar candidatos de um processo seletivo.

---

## SAAS

### saas-onboarding-activator (`/soa`)
**O que faz:** Ativacao de usuarios SaaS — rastreamento comportamental, checklists personalizados, "aha moments", tooltips, outreach proativo para reduzir churn.
**Quando usar:** Quando estiver projetando o onboarding de um produto SaaS.

---

## CRYPTO

### crypto-token-forge (`/ctf`)
**O que faz:** Criacao de tokens na Solana — tokenomics, SPL/Token-2022, metadados, pools de liquidez, seguranca, listagem.
**Quando usar:** Quando quiser lancar um token crypto na Solana.

---

## UTILIDADES

### nirvana-squad-creator (`/nsc`)
**O que faz:** Cria novos squads a partir de linguagem natural — analisa, gera agentes, tasks, workflows, valida e publica.
**Quando usar:** Quando quiser criar um squad novo personalizado.

### nirvana-readme-architect (`/nra`)
**O que faz:** Gera READMEs perfeitos — analise de codebase, template por tipo de projeto, badges, TOC, validacao de 25+ pontos.
**Quando usar:** Quando precisar de um README profissional para um projeto.

---

## Resumo rapido: Quais usar neste projeto (agente-gabinetetenant)?

| Fase do projeto | Squad util | Por que |
|---|---|---|
| Pesquisa de como implementar | **nirvana-context-enricher** (`/nce`) | Pesquisa profunda sobre LangGraph multi-tenant, Helena API |
| Melhorar prompts dos agentes | **nirvana-context-engineering** (`/ncea`) | Otimizar os prompts do sistema |
| Criar a API admin | **api-development** (`/api`) | Estruturar API REST com docs |
| Criar o backend completo | **nirvana-backend** (`/bk`) | Backend com Supabase, Docker |
| Criar o frontend admin | **landing-page-nirvana** (`/lp`) ou **ultimate-landingpage** (`/ultimate-lp`) | Painel admin web |
| Projetar onboarding de tenants | **saas-onboarding-activator** (`/soa`) | Fluxo de ativacao de novos gabinetes |
| README do projeto | **nirvana-readme-architect** (`/nra`) | Documentacao profissional |
