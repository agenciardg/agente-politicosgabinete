# Configuracao de Paineis - Deputado Andre Bueno (PL/SP)

Mapeamento dos paineis do Helena com as descricoes que o agente IA vai usar
para classificar cada demanda do cidadao.

---

## Paineis Ativos (recomendados para ativar no agente)

### Atendimento Geral
**Descricao para o agente:**
Painel principal de triagem. Use para demandas que nao se encaixam claramente em nenhuma categoria especifica, duvidas gerais sobre servicos do gabinete, solicitacoes de reuniao com o deputado, convites para eventos, sugestoes, elogios e primeiros contatos. Na duvida, classifique aqui.

### Saude
**Descricao para o agente:**
Demandas relacionadas a saude publica: hospitais estaduais, AMEs, UPAs, programas de saude do governo do estado, SUS (ambito estadual), falta de leitos, medicamentos de alto custo, mutiroes de saude, encaminhamentos medicos especializados, filas de espera, vacinacao.

### Educacao
**Descricao para o agente:**
Demandas relacionadas a educacao: escolas estaduais, universidades publicas estaduais, programas educacionais do estado, bolsas de estudo, infraestrutura de escolas estaduais, transporte escolar, creches, merenda escolar, falta de vagas.

### Seguranca
**Descricao para o agente:**
Demandas relacionadas a seguranca publica: policia militar, policia civil, delegacias, programas de seguranca do estado, violencia, areas de risco, policiamento, cameras de monitoramento, iluminacao em areas perigosas.

### Habitacao
**Descricao para o agente:**
Demandas relacionadas a moradia e habitacao: programas habitacionais (CDHU, Minha Casa Minha Vida), regularizacao fundiaria, moradia popular, familias em situacao de vulnerabilidade habitacional, despejos, ocupacoes, aluguel social.

### Servico Social
**Descricao para o agente:**
Demandas de assistencia social e populacao vulneravel. AREA PRIORITARIA DO DEPUTADO - ele preside a CPI dos Moradores em Situacao de Rua na Alesp. Inclui: populacao em situacao de rua, CRAS, CREAS, programas sociais, beneficios sociais, familias em vulnerabilidade, dependencia quimica, acolhimento institucional, cestas basicas.

### Juridico
**Descricao para o agente:**
Demandas de natureza juridica: orientacao legal, duvidas sobre direitos do cidadao, processos, documentacao, assistencia juridica gratuita, defensoria publica, questoes trabalhistas, previdenciarias, direito do consumidor.

### Legislativo
**Descricao para o agente:**
Demandas relacionadas a legislacao e projetos de lei: sugestoes de novos projetos de lei, duvidas sobre leis estaduais, acompanhamento de projetos em tramitacao na Alesp, pedidos de apoio a causas legislativas, audiencias publicas, abaixo-assinados.

### Espaco Publico
**Descricao para o agente:**
Demandas sobre espacos publicos: pracas, parques, areas de lazer, iluminacao publica, calcadas, acessibilidade, manutencao de espacos publicos, limpeza de terrenos baldios.

### Ruas e Bairros
**Descricao para o agente:**
Demandas de infraestrutura urbana: buracos nas ruas, asfalto, drenagem, esgoto, abastecimento de agua, sinalizacao de transito, limpeza publica, coleta de lixo, poda de arvores, calamento.

### Regularizacao
**Descricao para o agente:**
Demandas de regularizacao: documentos, alvaras, licencas, regularizacao de imoveis, certidoes, registros, pendencias burocraticas com orgaos publicos.

### Orientacao ONG
**Descricao para o agente:**
Demandas relacionadas a ONGs e organizacoes do terceiro setor: orientacao para criacao de ONGs, projetos sociais, captacao de recursos, parcerias com o poder publico, trabalho voluntario.

### Chefe Gabinete
**Descricao para o agente:**
Demandas que precisam de atencao especial e encaminhamento direto ao chefe de gabinete: casos complexos envolvendo multiplas areas, demandas urgentes de alto impacto, articulacao institucional, demandas de autoridades ou liderancas comunitarias.

### Agendamentos
**Descricao para o agente:**
Solicitacoes de agendamento: reunioes com o deputado, visitas ao gabinete na Alesp, participacao em eventos, audiencias publicas, reunioes com liderancas comunitarias.

---

## Paineis que NAO devem ser ativados no agente

| Painel | Motivo |
|--------|--------|
| Administracao | Uso interno do gabinete |
| Cadastro Pagina Site | Cadastros vindos do site, nao do WhatsApp |
| Instagram - Comentarios | Fluxo separado para redes sociais |
| Minhas tarefas (8x) | Paineis pessoais dos assessores |
| Triagem - Whatsapp | Painel interno de controle de triagem |

---

## Mapeamento dos Campos do Card por Painel

A maioria dos paineis ativos compartilha os mesmos campos customizados. Para cada campo, a instrucao de preenchimento:

| Campo do Card | Instrucao de Preenchimento |
|---------------|---------------------------|
| **Descricao Manifestacao** | Armazene o resumo COMPLETO e detalhado da demanda conforme descrito pelo cidadao. Inclua cidade, bairro, localizacao e qualquer detalhe relevante mencionado. Quanto mais detalhado, melhor para a equipe do gabinete. |
| **Nome Completo** | Nome completo do cidadao conforme coletado no inicio do atendimento. |
| **CPF** | CPF do cidadao, se informado. Deixe vazio se nao fornecido. |
| **Data Nascimento** | Data de nascimento do cidadao, se informada. |
| **Endereco** | Endereco completo do cidadao, se informado. |
| **Cidade** | Cidade do cidadao. Campo importante para mapear a base eleitoral. |
| **Estado** | Estado do cidadao (geralmente SP). |
| **CEP** | CEP do cidadao, se informado. |
| **E-mail** | Email do cidadao, se informado. |
| **Indicacao** | Como o cidadao conheceu o gabinete ou quem indicou o contato. |
| **No Sei** | Numero do processo SEI, se aplicavel (demandas formais). |
| **Arquivo** | Registre se o cidadao enviou algum documento/arquivo durante o atendimento. |
| **Data e Horario** | Data e horario do atendimento (preenchido automaticamente). |
| **Politica de Privacidade** | Registre "Aceito" se o cidadao concordou com o tratamento de dados. |
| **Redirecionamento Painel** | Se a demanda foi redirecionada de outro painel, registre o nome do painel de origem. |
| **Solicitacao** | Para paineis que tem este campo (Saude, Seguranca, etc), armazene um resumo curto da solicitacao em uma frase. |
