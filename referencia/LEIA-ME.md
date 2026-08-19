# Tabelas de referência mantidas à mão

Esta pasta é diferente de `data/`. Tudo em `data/` é baixado do site do Tesouro ou
reconstruído pelos parsers, e por isso é ignorado pelo git — se apagar, o pipeline
regenera. **Aqui não.** O que está nesta pasta foi montado à mão, não existe para
download, e é versionado no git de propósito. Se você apagar, não volta.

---

## `paf_bandas.csv` — as metas do PAF, ano a ano

O PAF (Plano Anual de Financiamento) define, para cada ano, uma faixa de mínimo e
máximo para os indicadores da dívida. É contra essas faixas que os gráficos de
composição e de prazo médio comparam o realizado.

Cobre **2003 a 2026**, com 193 linhas.

### As colunas

| coluna | o que é |
|---|---|
| `ano` | o ano a que a meta se refere |
| `versao` | `original` ou `revisado` (ver abaixo) |
| `indicador` | um dos seis nomes fixos, listados adiante |
| `minimo` | piso da banda |
| `maximo` | teto da banda |
| `realizado` | o que de fato aconteceu no fechamento do ano |

### Os seis indicadores obrigatórios

Os nomes são fixos. Escreva exatamente assim, sem acento e sem espaço:

- `estoque_bilhoes` — estoque da DPF em mercado, em R$ bilhões
- `prazo_medio_anos` — prazo médio da DPF, em anos
- `prefixado_pct` — participação do prefixado, em % da DPF
- `indice_precos_pct` — participação do índice de preços, em % da DPF
- `taxa_flutuante_pct` — participação da taxa flutuante, em % da DPF
- `cambio_pct` — participação do câmbio, em % da DPF

Todo ano precisa dos seis. Faltar um é erro, e o validador acusa.

### O sétimo, que é opcional

- `vincendo_12m_pct` — participação do que vence em 12 meses, em % da DPF

**Por que é opcional.** A aba 5.7 do anexo do RMD já publica essa banda de **2003 a
2022**, e o nosso parser a lê de lá (`paf_metas.csv`). Aqui só precisam entrar os
anos que a 5.7 não alcança — exigi-lo em todo ano obrigaria a redigitar vinte anos de
dado que já temos por parser.

**Hoje há uma lacuna: 2023, 2024 e 2025.** A 5.7 termina em 2022 e este arquivo
começa em 2026. Nesses três anos o gráfico de composição por horizonte não desenha
banda nenhuma — o buraco é a lacuna, não um defeito. Para fechá-la, acrescente uma
linha por ano, no formato:

```
2025,original,vincendo_12m_pct,<mínimo>,<máximo>,
```

O `realizado` fica vazio: nenhuma coluna `realizado` deste arquivo é lida por nada.
Se um dia um ano aqui coincidir com um ano da 5.7, um teste confere que as duas
fontes dão a mesma banda — divergência aparece como teste vermelho, e não como
gráfico errado.

**Nota histórica:** até 2010 o PAF chamava a taxa flutuante de "Selic". É o mesmo
indicador, e aqui ele aparece sempre como `taxa_flutuante_pct`.

**Onde a banda entra:** este arquivo é a fonte da banda de quatro gráficos — a
composição do estoque por indexador, o prazo médio, a composição por horizonte
(pelo `vincendo_12m_pct`) e, quando houver, o estoque. Um valor errado aqui vira
banda errada no gráfico, que é defeito que ninguém enxerga olhando a figura — por
isso o validador roda **antes** de qualquer leitura, e um erro derruba a geração do
dashboard em vez de deixá-lo desenhar.

### Original e revisado

Em alguns anos o Tesouro revisa a meta no meio do caminho. Quando isso acontece, o
ano aparece **duas vezes**: uma linha com `versao = original` e outra com
`versao = revisado`, e o `realizado` é o mesmo nas duas.

Os gráficos usam a banda **revisada** quando ela existe, porque é a que estava em
vigor no fechamento — e desenham a original em linha fina por baixo, para ficar
visível que houve mudança.

Anos com revisão até agora: 2008, 2015, 2016, 2018, 2020, 2021, 2024 e 2025.

### Ano ainda aberto

O ano corrente tem banda mas **não tem realizado**, porque ainda não fechou. Nesse
caso a coluna `realizado` fica **vazia** — não escreva zero, não escreva "N/D". Zero
seria lido como "a composição foi a zero".

---

## Como acrescentar o PAF do ano que vem

1. Abra o `paf_bandas.csv` no Excel. Ele abre como planilha normal.
2. Acrescente **seis linhas** para o ano novo, uma por indicador, com `versao`
   igual a `original` e a coluna `realizado` vazia.
3. Salve **como CSV**, não como `.xlsx`. O Excel vai avisar que o formato tem
   limitações; pode confirmar.
4. Rode a verificação:

   PowerShell:

       $env:PYTHONPATH="src"; python -m tesouro.valida_referencia

   bash:

       PYTHONPATH=src python -m tesouro.valida_referencia

5. Se aparecer algum erro, ele diz a linha e o motivo. Corrija e rode de novo.

**Quando o ano fechar**, volte nas seis linhas daquele ano e preencha o `realizado`.
Se durante o ano o Tesouro revisar a meta, acrescente mais seis linhas com
`versao = revisado`, mantendo as originais.

---

## Por que CSV e não Excel

Foi decisão de projeto, em agosto de 2026, e vale registrar o motivo.

O CSV é texto puro, então o git consegue mostrar **exatamente quais linhas mudaram**
quando alguém acrescenta um ano. Com `.xlsx` o git só sabe dizer que o arquivo mudou,
e não o quê — o que é ruim para um dado que várias pessoas vão editar ao longo dos
anos.

Além disso, o arquivo original do PAF trazia uma armadilha: a linha do ano aberto
tinha **treze valores em vez de dezenove**, porque não havia coluna de realizado, e
as colunas escorregavam. Um leitor desatento leria o piso do prefixado como se fosse
o estoque. No CSV isso não acontece, porque cada coluna tem nome.

O arquivo original está guardado em `paf/` e não deve ser editado — ele é o registro
de onde este CSV veio.
