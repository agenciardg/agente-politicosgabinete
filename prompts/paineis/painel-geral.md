# Painel: Atendimento Geral

## Campo: Nome do Painel no Helena

```
atendimento_geral
```

## Campo: Descricao para o Agente

Copie no campo "Descricao para o Agente" no admin:

```
Fallback para demandas que nao se encaixam em nenhuma outra categoria. Usar quando: pergunta fora do escopo das demais areas + cidadao pediu assessor, informacao desconhecida, mensagem vaga apos 2 tentativas de entendimento, qualquer situacao onde o agente nao sabe classificar a demanda.
```

## Campo: Requisitos Pre-Transferencia (opcional)

```
(deixar vazio - nao ha requisitos pre-transferencia para atendimento geral)
```

## Campos Customizados Sugeridos

| Campo Helena | fill_type | Instrucao de Coleta |
|-------------|-----------|-------------------|
| Data e Horario | auto | (automatico) |
| Descricao Manifestacao | auto | (automatico) |
| Tipo de Demanda | auto | (automatico) |
| Nome Completo | contact | (do cadastro) |
| Bairro | contact | (do cadastro) |

## Quando Direcionar para este Painel

Este e o painel de ULTIMO RECURSO. Usar quando:

- Demanda nao se encaixa em nenhuma das categorias especificas
- Cidadao fez pergunta fora do escopo e pediu para falar com assessor
- Informacao desconhecida pelo agente
- Mensagem continua vaga apos 2 tentativas de entendimento
- Qualquer situacao onde o agente nao sabe como classificar
- Cidadao quer falar com "alguem" sem especificar o assunto
- Elogios, reclamacoes sobre o gabinete, convites, parcerias genericas

## Quando NAO Direcionar para este Painel

- Se a demanda se encaixa CLARAMENTE em qualquer outro painel, use o painel especifico
- Atendimento Geral e sempre a ULTIMA opcao
