# Admin Django - Importacao e Exportacao

## Cadastro Basico De Equipamentos

Na lista `Equipamentos e Producao -> Equipamentos`, os botoes nativos
`Importar` e `Exportar` trabalham somente com os campos do equipamento.

A identidade do equipamento e:

```text
linha + codigo do equipamento
```

Assim, `L01/E001` e `L02/E001` continuam sendo equipamentos diferentes.

## Variaveis De Um Equipamento

Abra o equipamento que deseja configurar. Na tela de edicao existem as acoes:

```text
Exportar variaveis
Importar variaveis
```

O arquivo e individual e tem o nome da linha e do equipamento. Ele possui tres
abas:

| Aba | Conteudo |
| --- | --- |
| `Variaveis padrao` | Variaveis operacionais conhecidas pelo sistema, como estado, velocidade, contagens, OP e SKU. |
| `Sensores` | Sensores do equipamento, limites de processo e campos do Golden State. |
| `Analise e historico` | Variaveis livres coletadas para graficos, analises e historico. Nao sao os valores historicos do InfluxDB. |

Todas as linhas carregam:

```text
linha_codigo
equipamento_codigo
```

Ao importar, o sistema confere esses dois codigos com o equipamento aberto. Um
arquivo de `L01/E001` nao pode ser aplicado por engano em `L02/E001`.

## Regras Da Importacao

- Use primeiro `Validar planilha`; essa etapa nao salva dados.
- `Importar salvando` so grava quando todas as abas estiverem sem erros.
- Um erro em qualquer linha desfaz a importacao inteira.
- Itens ausentes na planilha nao sao excluidos.
- A importacao nao altera o cadastro basico do equipamento.
- A importacao nao altera nem apaga valores historicos do InfluxDB.
- Em `Sensores`, codigo vazio cria um sensor novo e gera `S001`, `S002`, etc.
  Exporte novamente depois para guardar o codigo gerado.

## Atualizar O Servidor OT

Sincronize a pasta padrao no Windows para:

```text
D:\migrations\pacote-vm-linux-dev
```

Depois rode na VM:

```bash
sudo bash /mnt/windows-migrations/pacote-vm-linux-dev/update-ot.sh
```

O pacote recria somente o Django quando apenas o overlay Django mudou. Nao
remove volumes, MySQL ou InfluxDB.
