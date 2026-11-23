# Escopo do projeto — Orquestração de microsserviços hospitalares

**Versão:** 1.0 — 12/11/2026  
**Natureza:** aplicação acadêmica interativa de Teoria dos Grafos  
**Situação:** planejamento; aplicação funcional ainda a desenvolver  
**Referência da avaliação:** [Escopo.txt](Escopo.txt)

## 1. Objetivo

Desenvolver uma aplicação web pública para simular a recuperação de serviços digitais de um hospital e a escolha de rotas de requisição entre instâncias equivalentes.

A aplicação deverá permitir alterar os grafos e os parâmetros na interface, recalcular os resultados e explicar as decisões de dois algoritmos:

- **Kahn:** calcular uma ordem de inicialização que respeite dependências obrigatórias.
- **Dijkstra:** encontrar uma rota de menor latência ou menor custo entre as alternativas que atendam aos requisitos de disponibilidade e estabilidade.

O resultado será um laboratório didático. A aplicação simulará estados, métricas e requisições, sem executar serviços hospitalares reais.

## 2. Problema e cenário hospitalar

Após uma interrupção, a equipe de TI precisa restabelecer dois fluxos digitais:

1. **Portal assistencial:** consulta ao prontuário e às prescrições.
2. **Dispensação de medicamentos:** acesso às prescrições e ao estoque pela farmácia.

Os fluxos compartilham serviços, mas possuem dependências distintas. Uma falha no estoque deve impedir a dispensação sem bloquear o portal. Uma falha nas prescrições deve afetar ambos, conforme o modelo cadastrado.

Com os serviços disponíveis, uma consulta poderá ter diferentes instâncias equivalentes para atendê-la. A rota mais rápida pode ter custo maior ou não atender ao limite mínimo de estabilidade. O usuário deverá conseguir visualizar essa escolha.

**Público:** alunos, professor e profissionais de TI em treinamento. O hospital e seus dados serão fictícios; a arquitetura é um modelo didático proposto pelo grupo.

## 3. Dois grafos com significados diferentes

| Aspecto | Grafo de dependências | Grafo de requisições |
|---|---|---|
| Vértice | Serviço a inicializar | Ponto da chamada ou instância equivalente |
| Aresta A → B | B depende obrigatoriamente de A | A chamada pode seguir de A para B |
| Regra | Todas as dependências de B precisam estar disponíveis | Escolher um caminho elegível entre origem e destino |
| Pesos | Não utilizados na primeira versão | Latência e custo por ligação |
| Algoritmo principal | Kahn | Dijkstra |
| Pergunta | O que pode iniciar e o que fica bloqueado? | Qual caminho atende à política escolhida? |

Uma rota alternativa não poderá ser usada para pular autenticação ou qualquer etapa obrigatória do negócio. As alternativas deverão representar a mesma operação, com acesso autorizado aos mesmos dados.

## 4. Modo de inicialização

### 4.1 Cenário inicial

O cenário terá **8 serviços, 10 dependências, duas fontes e duas saídas**.

| Serviço | Dependências diretas obrigatórias |
|---|---|
| Banco clínico | Nenhuma — primeira fonte |
| Banco operacional | Nenhuma — segunda fonte |
| Autenticação | Banco operacional |
| Prontuário | Banco clínico e Autenticação |
| Estoque | Banco operacional e Autenticação |
| Prescrições | Prontuário |
| Portal assistencial | Prontuário e Prescrições — primeira saída |
| Dispensação | Prescrições e Estoque — segunda saída |

“Entradas e saídas do grafo” significam serviços de origem e serviços finais. Elas são diferentes das variáveis de entrada e dos resultados da aplicação.

### 4.2 Funcionamento

1. Validar os serviços e as dependências cadastradas.
2. Executar Kahn para obter uma ordem topológica ou detectar que há ciclo.
3. Se houver ciclo, informar que o plano está inválido e impedir a execução do plano completo até a correção.
4. Para um grafo válido, percorrer a ordem e avaliar a disponibilidade própria de cada serviço e de seus predecessores.
5. Liberar serviços aptos, bloquear os afetados e preservar os ramos independentes.
6. Recalcular os estados após qualquer alteração relevante, sem reutilizar resultados anteriores incompatíveis.

**Regra central:** um serviço só pode iniciar se estiver disponível e todas as suas dependências obrigatórias já estiverem disponíveis na simulação.

Uma indisponibilidade não será tratada como ciclo. A detecção de ciclos é estrutural e independe dos estados de disponibilidade.

### 4.3 Variáveis de entrada

| Variável | Formato | Exemplo |
|---|---|---|
| Serviços | Lista de identificadores únicos e nomes | `estoque`, `prescricoes` |
| Dependências | Pares de identificadores origem → destino | Estoque → Dispensação |
| Disponibilidade própria | Booleano por serviço | Estoque indisponível |
| Saídas monitoradas | Seleção de serviços existentes | Portal e Dispensação |

Avançar uma etapa, executar até o fim e restaurar o cenário serão comandos da interface. A seleção de saídas monitoradas muda o resumo exibido, sem alterar o grafo.

### 4.4 Resultados esperados

- Grafo direcionado com os estados dos serviços.
- Uma ordem topológica válida, sem apresentá-la como a única ordem possível.
- Evolução da fila, graus de entrada e serviços processados para explicar Kahn.
- Estados distinguíveis: pendente, apto a iniciar, iniciado, indisponível e bloqueado por dependência.
- Motivos de bloqueio, indicando as dependências responsáveis.
- Situação separada das duas saídas monitoradas.
- Aviso de ciclo quando não existir ordenação completa.

Os vértices restantes após Kahn podem incluir integrantes do ciclo e serviços dependentes dele. O sistema não deverá afirmar que todos os restantes pertencem ao ciclo.

## 5. Modo de roteamento

### 5.1 Política de escolha

O usuário escolherá **um objetivo por execução**:

- **Menor latência:** minimizar a soma das latências das ligações, em ms.
- **Menor custo:** minimizar a soma dos custos das ligações, em R$ por requisição.

Antes de executar Dijkstra, a aplicação deverá excluir vértices indisponíveis e ligações desativadas ou com taxa de sucesso inferior ao limite escolhido.

A estabilidade será um **filtro por ligação**, definido como taxa de sucesso em uma janela de observação informada. Não será uma otimização da probabilidade de sucesso da rota inteira. Milissegundos, reais e percentuais não serão somados em uma pontuação arbitrária.

### 5.2 Variáveis de entrada

| Variável | Formato / unidade | Regra |
|---|---|---|
| Vértices e ligações | Grafo direcionado | Referências devem existir |
| Origem e destino | Identificadores existentes | Escolhidos pelo usuário |
| Disponibilidade dos vértices | Booleano | Vértice indisponível não pode integrar a rota |
| Ativação das ligações | Booleano | Ligação desativada não pode integrar a rota |
| Latência por ligação | Número finito ≥ 0, em ms | Estimativa aditiva de uma etapa sequencial |
| Custo por ligação | Número finito ≥ 0, em R$ por requisição | Custo atribuído à etapa |
| Taxa de sucesso por ligação | Número finito de 0 a 100% | Dado sintético de uma janela definida |
| Janela de observação | Duração positiva; inicialmente 5 minutos | Contextualiza as taxas informadas |
| Limite mínimo de sucesso | Número finito de 0 a 100% | Aplicado a cada ligação; igualdade é aceita |
| Objetivo | Latência ou custo | Define o peso utilizado por Dijkstra |

As métricas serão informadas pelo usuário ou carregadas com o cenário de exemplo. A janela contextualiza os dados; não haverá coleta automática de telemetria na primeira versão.

### 5.3 Exemplo inicial de rotas alternativas

Uma consulta seguirá do Gateway até Resposta, passando por uma das três réplicas equivalentes. Cada rota possui duas ligações.

| Rota | Latências dos trechos | Custos dos trechos | Taxas de sucesso dos trechos | Totais |
|---|---|---|---|---|
| Gateway → A → Resposta | 5 e 15 ms | R$ 0,001 e R$ 0,003 | 99,9% e 99,8% | 20 ms; R$ 0,004 |
| Gateway → B → Resposta | 10 e 25 ms | R$ 0,001 e R$ 0,001 | 99,9% e 99,9% | 35 ms; R$ 0,002 |
| Gateway → C → Resposta | 3 e 7 ms | R$ 0,001 e R$ 0,002 | 99,9% e 95,0% | 10 ms; R$ 0,003 |

- Com limite de **99% por ligação**, C fica inelegível. A vence por latência e B vence por custo.
- Com limite de **94% por ligação**, C volta a ser elegível e vence por latência.
- Sem caminho elegível, a aplicação deve informar **ausência de rota**, sem reduzir o limite silenciosamente.

### 5.4 Resultados esperados

- Grafo com as ligações, seus pesos e as alternativas excluídas.
- Caminho selecionado destacado e sequência de vértices.
- Latência total estimada e custo total da rota escolhida, independentemente do objetivo selecionado.
- Objetivo e limite de estabilidade utilizados.
- Motivos de exclusão: indisponibilidade, ligação desativada ou taxa insuficiente.
- Evolução das distâncias e predecessores para explicar Dijkstra.
- Informação de ausência de caminho quando aplicável.

Em caso de empate, qualquer caminho ótimo é válido; a interface não deverá afirmar que há uma única solução.

## 6. Funcionalidades incluídas

1. Carregar e restaurar os cenários hospitalares de exemplo.
2. Cadastrar e editar serviços, vértices e ligações pela interface.
3. Alternar disponibilidade e modificar os parâmetros numéricos.
4. Executar cada algoritmo por etapas ou até o resultado final.
5. Atualizar o grafo e os resultados após as alterações do usuário.
6. Explicar a matemática, a modelagem e os motivos das decisões na própria aplicação.
7. Mostrar a comparação com soluções existentes e as escolhas de arquitetura.
8. Disponibilizar a aplicação por link público para a apresentação final.

Os dois modos terão cenários próprios. Não será necessário implementar sincronização automática entre as duas topologias na primeira versão; seus significados e estados deverão estar identificados na interface.

## 7. Plataforma e arquitetura propostas

| Parte | Escolha proposta | Responsabilidade |
|---|---|---|
| Linguagem | Python | Modelos, validação e algoritmos |
| Interface | Streamlit | Controles, execução por etapas e resultados |
| Visualização | Graphviz integrado ao Streamlit | Grafos direcionados com rótulos e destaques |
| Motor de inicialização | Kahn implementado pelo grupo | Ordenação e diagnóstico de ciclo |
| Motor de roteamento | Dijkstra implementado pelo grupo | Menor caminho com pesos não negativos |
| Publicação | Streamlit Community Cloud | Link público |
| Código | Repositório GitHub | Código-fonte e instruções de execução |

Separar o motor lógico da interface, preservando a estrutura mínima necessária para testar os algoritmos sem abrir a aplicação. Listas de adjacência representarão os grafos; graus de entrada e fila apoiarão Kahn; fila de prioridade apoiará Dijkstra.

Essas escolhas dependem de uma verificação de renderização e publicação no ambiente proposto. Não será necessário banco persistente, autenticação de usuários ou infraestrutura de contêineres para o simulador.

## 8. Validação e critérios de aceitação

| Caso | Resultado obrigatório |
|---|---|
| Dependências válidas | Cada dependência precede o dependente na ordem calculada |
| Cenário completo disponível | Portal e Dispensação tornam-se disponíveis ao concluir a execução |
| Apenas Estoque indisponível | Portal permanece disponível; Dispensação fica bloqueada |
| Apenas Prescrições indisponíveis | As duas saídas ficam bloqueadas |
| Restauração do serviço que falhou | Estados são recalculados e dependentes aptos podem iniciar |
| Inclusão de Portal → Autenticação | Detectar ciclo e invalidar o plano completo |
| Grafo vazio ou serviços independentes | Resultado coerente, sem falha da aplicação |
| Limite de 99%, objetivo latência | Selecionar A no exemplo de roteamento |
| Limite de 99%, objetivo custo | Selecionar B no exemplo de roteamento |
| Limite de 94%, objetivo latência | Selecionar C no exemplo de roteamento |
| Nenhum caminho elegível | Informar ausência de rota, sem alterar a política |
| Peso negativo, infinito ou não numérico | Rejeitar a entrada com mensagem clara |
| Nome vazio, ID repetido ou referência inexistente | Rejeitar sem deixar o modelo parcialmente alterado |
| Ligação duplicada | Rejeitar ou editar a existente, sem duplicação silenciosa |
| Remoção de vértice com ligações | Exigir remover as ligações ou explicar explicitamente a remoção conjunta |
| Edição depois de uma execução | Não exibir o resultado antigo como se correspondesse ao grafo novo |
| Link público | Abrir e interagir a partir de outro dispositivo, sem sessão do desenvolvedor |

**Garantias limitadas ao modelo:** respeitar dependências na inicialização; escolher um caminho de menor peso no grafo elegível; não utilizar ligações que violem o filtro. A qualidade do resultado depende da topologia e das métricas informadas.

## 9. Soluções existentes e diferencial

| Solução | Recurso relacionado |
|---|---|
| Docker Compose | Dependências de inicialização e espera por verificações de saúde |
| Kubernetes | Pré-condições com init containers e controle de prontidão com readiness probes |
| HashiCorp Nomad | Descoberta de serviços e verificações de saúde |
| Envoy Proxy | Detecção de instâncias com falhas e exclusão do balanceamento |

O diferencial proposto é reunir, em uma aplicação didática, a visualização de dependências, a recuperação parcial dos dois fluxos e a escolha de rotas com parâmetros editáveis, expondo as etapas dos algoritmos.

O projeto não pretende substituir essas ferramentas ou afirmar que o mercado não possui recursos semelhantes. Init containers do Kubernetes não equivalem a uma ordenação global de todos os microsserviços de um cluster.

Fontes oficiais consultadas para o planejamento:

- [Docker Compose — ordem de inicialização](https://docs.docker.com/compose/how-tos/startup-order/)
- [Kubernetes — init containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
- [Kubernetes — verificações de saúde e prontidão](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Nomad — descoberta de serviços](https://developer.hashicorp.com/nomad/docs/job-declare/service-discovery)
- [Envoy — detecção de instâncias com falhas](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/outlier)
- [NetworkX — Dijkstra e pesos não negativos](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths/dijkstra.html)

## 10. Limites e itens fora do escopo

- Dados reais de pacientes e integração com prontuários ou hospitais reais.
- Execução efetiva de microsserviços, Kubernetes, Docker, failover ou balanceamento em produção.
- Healthchecks, captura de requisições ou coleta automática de latência e taxas de sucesso.
- Garantias clínicas, disponibilidade real ou cumprimento de SLA.
- Otimização simultânea de latência, custo e estabilidade com uma função de pontuação composta.
- Cálculo da probabilidade de sucesso fim a fim ou modelagem de correlação entre falhas.
- Escalonamento de recursos, minimização do tempo total de recuperação e execução paralela real.
- Modelagem de filas, congestionamento, concorrência, retries e consistência entre réplicas.
- Persistência entre sessões, contas de usuário e controle de acesso à aplicação.

Custos e latências serão aditivos para etapas sequenciais simuladas. A estabilidade por ligação é um critério de elegibilidade; não comprova a confiabilidade global da rota.

## 11. Entregas e etapas

### Apresentação intermediária — 13/11/2026

Apresentar tema, plataforma proposta, variáveis de entrada, resultados esperados, soluções existentes e diferencial. O arquivo [Apresentacao_13-11.html](Apresentacao_13-11.html) apoia essa etapa.

### Implementação e entrega final

1. Validar o recorte com o professor e confirmar a data final.
2. Implementar e testar Kahn e a propagação de disponibilidade.
3. Implementar e testar Dijkstra e os filtros de elegibilidade.
4. Integrar controles, grafos e explicação das etapas.
5. Verificar os cenários de aceitação e as validações de entrada.
6. Publicar a aplicação e testar acesso externo.
7. Ensaiar os dois modos e documentar como executar localmente.

**Entregáveis finais:** aplicação pública funcional, código-fonte, instruções de execução e cenários demonstráveis. Conforme o enunciado, o seminário final deverá utilizar exclusivamente a aplicação.

## 12. Cobertura dos quatro pilares da avaliação

| Pilar | Como será demonstrado |
|---|---|
| Cenário | Recuperação dos fluxos assistencial e de dispensação em hospital fictício |
| Matemática | Kahn, dependências, ciclos, Dijkstra e pesos não negativos |
| Arquitetura e código | Estruturas de dados, separação do motor, ferramentas e validações |
| Interação | Alterar disponibilidade, dependências, ms, custos e estabilidade; observar o recálculo |

Este documento consolida o escopo acordado no planejamento. Os resultados apresentados nos exemplos são expectativas verificáveis; não representam uma aplicação final já implementada.
