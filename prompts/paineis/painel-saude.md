# Painel: Saude

## Campo: Nome do Painel no Helena

```
saude
```

## Campo: Descricao para o Agente

Copie no campo "Descricao para o Agente" no admin:

```
Demandas de saude publica: consultas medicas, exames, cirurgias, Cartao SUS, hospital, UBS, posto de saude, SUS, especialistas, AME, remedios, medicamentos, internacao, leito, ambulancia, vacinacao, fisioterapia, ortopedia, oftalmologia, dentista, saude mental, psiquiatra, psicologo.

Palavras-chave: consulta, medico, marcar, agendar, exame, cirurgia, hospital, UBS, posto, SUS, Cartao SUS, especialista, AME, remedio, medicamento, internacao, leito, ambulancia, vacina, fisioterapia, dentista, psiquiatra, psicologo.

IMPORTANTE: NAO explique procedimentos medicos ou do SUS. NAO diga como funciona agendamento. Apenas colete os dados e transfira.
```

## Campo: Requisitos Pre-Transferencia (opcional)

```
Antes de transferir, pergunte ao cidadao:
- Qual o problema de saude ou procedimento que precisa?
- Ja possui Cartao SUS?
- Ja esta em acompanhamento em alguma unidade de saude?
```

## Campos Customizados Sugeridos

| Campo Helena | fill_type | Instrucao de Coleta |
|-------------|-----------|-------------------|
| Data e Horario | auto | (automatico - DD/MM/YYYY - HH:MM) |
| Descricao Manifestacao | auto | (automatico - resumo da conversa) |
| Tipo de Demanda | auto | (automatico - classificacao) |
| Nome Completo | contact | (do cadastro) |
| Bairro | contact | (do cadastro) |
| Problema/Procedimento | collect | Pergunte qual problema de saude ou procedimento o cidadao precisa |
| Cartao SUS | collect | Pergunte se possui Cartao SUS e o numero, se tiver |
| Unidade de Saude | collect | Pergunte se ja e atendido em alguma UBS, hospital ou AME |

## Quando Direcionar para este Painel

O agente deve direcionar para SAUDE quando o cidadao mencionar:
- Consultas medicas ou agendamento
- Exames, cirurgias, procedimentos
- Hospital, UBS, posto de saude, AME
- Cartao SUS, SUS
- Especialistas medicos
- Remedios, medicamentos
- Internacao, leito, ambulancia
- Vacinacao, fisioterapia
- Saude mental (se claramente medico - se for vulnerabilidade social, vai para Servico Social)

## Quando NAO Direcionar para este Painel

- Depressao/ansiedade como vulnerabilidade social -> Servico Social
- Saude do trabalhador / acidente de trabalho -> pode ser Juridico
