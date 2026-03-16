# Painel: Regularizacao

## Campo: Nome do Painel no Helena

```
regularizacao
```

## Campo: Descricao para o Agente

Copie no campo "Descricao para o Agente" no admin:

```
Demandas de regularizacao: imovel, terreno, documentacao pessoal, IPTU, conta de luz, conta de agua, certidoes, alvaras, licencas, escritura, usucapiao, zoneamento, construcao irregular, auto de vistoria.

Palavras-chave: regularizar, imovel, terreno, IPTU, documento, certidao, alvara, escritura, usucapiao, zoneamento, construcao, auto de vistoria, conta de luz, conta de agua.

IMPORTANTE: NAO explique procedimentos de regularizacao ou legislacao. Apenas colete os dados e transfira.
```

## Campo: Requisitos Pre-Transferencia (opcional)

```
Antes de transferir, pergunte:
- O que precisa regularizar? (imovel, documento, IPTU, etc.)
- Possui algum documento do imovel ou processo em andamento?
- Qual o endereco do imovel (se aplicavel)?
```

## Campos Customizados Sugeridos

| Campo Helena | fill_type | Instrucao de Coleta |
|-------------|-----------|-------------------|
| Data e Horario | auto | (automatico) |
| Descricao Manifestacao | auto | (automatico) |
| Tipo de Demanda | auto | (automatico) |
| Nome Completo | contact | (do cadastro) |
| Bairro | contact | (do cadastro) |
| Tipo Regularizacao | collect | Pergunte o que precisa regularizar (imovel, IPTU, documento, etc.) |
| Documentacao Existente | collect | Pergunte se possui algum documento do imovel ou processo em andamento |
| Endereco Imovel | collect | Pergunte o endereco do imovel se for demanda imobiliaria |

## Quando Direcionar para este Painel

- Regularizacao de imovel, terreno
- IPTU (isencao, revisao, divida)
- Conta de luz ou agua
- Certidoes, alvaras, licencas
- Escritura, usucapiao
- Zoneamento, construcao irregular
- Documentacao pessoal

## Quando NAO Direcionar para este Painel

- Moradia (programa habitacional) -> Habitacao
- Problemas de infraestrutura NA RUA -> Zeladoria
