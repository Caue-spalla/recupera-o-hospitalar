# Recuperação hospitalar

Laboratório interativo de Teoria dos Grafos. Em um hospital fictício, simula a recuperação do portal assistencial e da dispensação e a escolha de uma rota para uma consulta autorizada.

## Executar localmente

Se a pasta `.venv` já existe e tem as dependências instaladas, inicie o simulador diretamente.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Para preparar o ambiente pela primeira vez com o `uv` instalado, execute estes comandos na pasta do projeto.

```powershell
uv venv --python 3.12
uv pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abra o endereço local exibido pelo Streamlit. A interface abre com grafos vazios. Use **Aplicar cenário de exemplo** no modo que deseja demonstrar.

## Demonstrar no seminário

- **Inicialização.** Aplique o cenário hospitalar. Use **+ Novo vértice** para criar um item avulso ou **+** em um vértice para criar um dependente. Para ligar vértices existentes, use o botão **→** na origem e selecione o destino. Avance uma etapa para acompanhar a fila de Kahn. Execute até o fim, clique em Estoque, desmarque sua disponibilidade, salve e observe que só Dispensação fica bloqueada. Restaure Estoque e desmarque Prescrições para bloquear as duas saídas. Adicione a ligação **Portal assistencial → Autenticação** para demonstrar a invalidação do plano por ciclo.
- **Failover de autenticação.** Use o **+** do Banco operacional para criar a API Emergencial e selecione **Réplica de → Autenticação**. Ligue a API ao Prontuário, marque Autenticação como indisponível e execute até o fim. O Portal inicia, enquanto Estoque e Dispensação ficam bloqueados. Para recuperar a Dispensação, ligue a API também ao Estoque. As ligações com **↪** mostram qual réplica atende à dependência. A aba Roteamento também mostra as substituições previstas ao fim da inicialização.
- **Simulador de disponibilidade.** Configure o intervalo em segundos, quantos vértices podem falhar por rodada e quais ficam protegidos. A primeira rodada ocorre após o intervalo escolhido. Encerrar a simulação restaura a disponibilidade manual.
- **Roteamento.** Aplique o cenário de exemplo ou crie um grafo com os mesmos controles da Inicialização. Clique no botão de uma ligação para editar latência, custo, taxa de sucesso e ativação. Execute até o fim com limite de 99% e objetivo de latência para escolher A. Mude para custo para escolher B. Selecione latência e reduza o limite a 94% para escolher C. Desative as ligações que saem do Gateway para demonstrar ausência de rota.
- **Cenário e arquitetura.** Use a seção do próprio aplicativo para apresentar o problema, as estruturas de dados, o código e as soluções de mercado. A mecânica de cada algoritmo aparece junto às respectivas etapas.

## Testar

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

## Publicar

1. Use esta pasta como raiz do repositório GitHub, com `app.py` e `requirements.txt` no primeiro nível. Inclua `.streamlit/config.toml` para manter a configuração do aplicativo.
2. No Streamlit Community Cloud, selecione o repositório e a branch, indique `app.py` como arquivo principal e selecione Python 3.12.
3. Após publicar, abra o link em outro dispositivo e aplique os cenários de exemplo para verificar a Inicialização e o Roteamento.
