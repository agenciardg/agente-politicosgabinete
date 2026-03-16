# Painel: Juridico

## Campo: Nome do Painel no Helena

```
juridico
```

## Campo: Descricao para o Agente

Copie no campo "Descricao para o Agente" no admin:

```
Demandas juridicas previdenciarias: prova de vida INSS, aposentadoria, pensao por morte, auxilio-doenca, BPC/LOAS, auxilio-acidente, revisao de beneficio, pericia medica.

Palavras-chave: prova de vida, INSS, aposentadoria, pensao, auxilio-doenca, BPC, LOAS, auxilio-acidente, revisao, pericia, beneficio previdenciario.

IMPORTANTE: NAO confirmar ajuda com questoes judiciais de familia (pensao alimenticia, divorcio, guarda). NAO explicar procedimentos do INSS ou legislacao previdenciaria. Apenas colete os dados e transfira.
```

## Campo: Requisitos Pre-Transferencia (opcional)

```
Antes de transferir, pergunte:
- Qual a questao previdenciaria? (aposentadoria, auxilio-doenca, prova de vida, etc.)
- Ja tem requerimento ou processo no INSS?
- Possui numero do beneficio ou NIT?
```

## Campos Customizados Sugeridos

| Campo Helena | fill_type | Instrucao de Coleta |
|-------------|-----------|-------------------|
| Data e Horario | auto | (automatico) |
| Descricao Manifestacao | auto | (automatico) |
| Tipo de Demanda | auto | (automatico) |
| Nome Completo | contact | (do cadastro) |
| Bairro | contact | (do cadastro) |
| Tipo Questao Previdenciaria | collect | Pergunte qual a questao (aposentadoria, auxilio-doenca, prova de vida, etc.) |
| Processo INSS | collect | Pergunte se ja tem requerimento ou processo no INSS |
| Numero Beneficio | collect | Pergunte o numero do beneficio ou NIT se possuir |

## Quando Direcionar para este Painel

- Prova de vida INSS
- Aposentadoria (qualquer tipo)
- Pensao por morte
- Auxilio-doenca
- BPC/LOAS
- Auxilio-acidente
- Revisao de beneficio previdenciario
- Pericia medica do INSS

## Quando NAO Direcionar para este Painel

- Pensao alimenticia -> informar que nao atende questoes de familia
- Divorcio, guarda de filhos -> informar que nao atende questoes de familia
- Questoes trabalhistas (CLT, demissao) -> Atendimento Geral
