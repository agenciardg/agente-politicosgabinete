# Painel: Servico Social

## Campo: Nome do Painel no Helena

```
servico_social
```

## Campo: Descricao para o Agente

Copie no campo "Descricao para o Agente" no admin:

```
Demandas de assistencia social: CadUnico, NIS, situacao de rua, vulnerabilidade, depressao, ansiedade, saude mental (vulnerabilidade social), cesta basica, idoso abandonado, crianca sozinha, maus tratos, violencia domestica, dependencia quimica, abuso, negligencia, CRAS, CREAS.

Palavras-chave: CadUnico, NIS, cadastro, situacao de rua, vulnerabilidade, depressao, saude mental, cesta basica, idoso abandonado, crianca sozinha, maus tratos, violencia domestica, dependencia quimica, CRAS, CREAS.

IMPORTANTE: NAO explicar procedimentos do CadUnico ou CRAS. Em situacoes de risco (crianca, idoso, violencia), acolha com MUITA sensibilidade. Apenas colete os dados e transfira.
```

## Campo: Requisitos Pre-Transferencia (opcional)

```
Antes de transferir, pergunte com sensibilidade:
- Qual a situacao que esta enfrentando?
- Ja procurou algum servico de assistencia social (CRAS, CREAS)?
- Tem CadUnico ou NIS?
```

## Campos Customizados Sugeridos

| Campo Helena | fill_type | Instrucao de Coleta |
|-------------|-----------|-------------------|
| Data e Horario | auto | (automatico) |
| Descricao Manifestacao | auto | (automatico) |
| Tipo de Demanda | auto | (automatico) |
| Nome Completo | contact | (do cadastro) |
| Bairro | contact | (do cadastro) |
| Situacao | collect | Pergunte com sensibilidade qual a situacao que esta enfrentando |
| CadUnico/NIS | collect | Pergunte se possui CadUnico ou NIS |
| Servico Social Anterior | collect | Pergunte se ja procurou CRAS, CREAS ou outro servico de assistencia |

## Quando Direcionar para este Painel

- CadUnico, NIS
- Situacao de rua
- Vulnerabilidade social
- Depressao, ansiedade (como vulnerabilidade, nao medico)
- Cesta basica
- Idoso abandonado ou em situacao de risco
- Crianca sozinha, maus tratos, negligencia
- Violencia domestica
- Dependencia quimica
- CRAS, CREAS

## Quando NAO Direcionar para este Painel

- Depressao/ansiedade com pedido de consulta medica -> Saude
- Pensao alimenticia, divorcio -> informar que nao atende questoes judiciais de familia
