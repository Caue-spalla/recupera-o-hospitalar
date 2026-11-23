"""Interface do laboratório de recuperação hospitalar."""

from decimal import Decimal
from math import isfinite
from pathlib import Path
from time import monotonic

import streamlit as st
from engine import apply_outages, dijkstra, edit_graph, example, kahn, outage_round, initialization_state, validate


ROOT = Path(__file__).parent
graph_component = st.components.v2.component(
    'hospital_graph',
    html='<section class="graph-shell" aria-label="Diagrama do grafo">'
         '<div class="graph-toolbar"></div><div class="graph-scroll">'
         '<div class="graph-board"></div></div><div class="graph-legend">'
         '<span data-availability="available">Ligação disponível</span>'
         '<span data-availability="unavailable">Ligação indisponível</span>'
         '<span data-state="Bloqueado">Serviço bloqueado</span>'
         '<span data-state="Indisponível">Serviço indisponível</span>'
         '</div><div class="graph-inspector"></div></section>',
    css=(ROOT / 'graph.css').read_text(encoding='utf-8-sig'),
    js=(ROOT / 'graph.js').read_text(encoding='utf-8-sig'),
)


def graph(vertices, edges, states, key, *, editable=False, excluded=None, path=(), providers=None):
    routing = key == 'route_graph'
    prefix = 'route' if routing else 'graph'
    position_key = f'{prefix}_positions'
    revision_key = f'{prefix}_revision'
    order, _, remaining, parents = kahn(vertices, edges)
    ranks = {}
    for vertex in order:
        ranks[vertex] = max((ranks[parent] + 1 for parent in parents[vertex]), default=0)
    fallback = max(ranks.values(), default=-1) + 1
    for index, vertex in enumerate(remaining):
        ranks[vertex] = fallback + index % 3
    selected = set(zip(path, path[1:]))
    providers = providers or {}
    result = graph_component(
        key=key,
        data={
            'editable': editable,
            'dependencies': not routing,
            'positions': st.session_state.get(position_key, {}),
            'revision': st.session_state.get(revision_key, 0),
            'nodes': [dict(id=vertex, **node, estado=states[vertex], rank=ranks[vertex])
                      for vertex, node in vertices.items()],
            'edges': [
                dict(source=a, target=b, active=(a, b) in selected,
                     provider=providers.get((a, b)),
                     excluded=excluded is not None and (a, b) in excluded,
                     metrics={field: str(value) if isinstance(value, Decimal) else value
                              for field, value in link.items()})
                for (a, b), link in edges.items()
            ],
        },
        on_edit_change=lambda: None,
    )
    move = result.get('move')
    if (editable and move and move.get('id') in vertices
            and move.get('revision') == st.session_state.get(revision_key, 0)):
        positions = dict(st.session_state.get(position_key, {}))
        position = {axis: move.get(axis) for axis in ('x', 'y')}
        if (all(type(value) is int and 0 <= value <= 10000 for value in position.values())
                and positions.get(move['id']) != position):
            positions[move['id']] = position
            st.session_state[position_key] = positions
            st.rerun()
    return result.edit


def edit_diagram(vertices, edges, states, *, routing=False, **display):
    prefix = 'route' if routing else 'graph'
    revision_key = f'{prefix}_revision'
    model_key = 'routing_model' if routing else 'dependency_model'
    graph_key = 'route_graph' if routing else 'dependency_graph'
    command = graph(vertices, edges, states, graph_key, editable=True, **display)
    if not command or command.get('revision') != st.session_state.get(revision_key, 0):
        return
    try:
        st.session_state[model_key] = edit_graph(*model(model_key), command, routing=routing)
    except ValueError as error:
        st.error(str(error))
        return
    if command['action'] == 'remove':
        st.session_state.get(f'{prefix}_positions', {}).pop(command['id'], None)
    st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1
    st.rerun()


def model(key='dependency_model'):
    return st.session_state.get(key, ([], []))


def load_example(routing=False):
    model_key, prefix, algorithm = (
        ('routing_model', 'route', 'dijkstra') if routing else ('dependency_model', 'graph', 'kahn')
    )
    st.session_state[model_key] = example(routing)
    for key in (f'{algorithm}_revision', f'{prefix}_revision'):
        st.session_state[key] = st.session_state.get(key, 0) + 1
    st.session_state[f'{algorithm}_step'] = 0
    st.session_state.pop(f'{prefix}_positions', None)
    if not routing:
        st.session_state.pop('outage_run', None)


def controls(total, key):
    step_key = f'{key}_step'
    current = st.session_state.get(step_key, 0)
    step = total if current is None else min(current, total)
    buttons = st.columns(3)
    for column, label, suffix, value, disabled in [
        (buttons[0], 'Reiniciar etapas', 'start', 0, step == 0),
        (buttons[1], 'Avançar uma etapa', 'next', step + 1, step >= total),
        (buttons[2], 'Executar até o fim', 'end', None, step >= total),
    ]:
        column.button(label, key=f'{key}_{suffix}', disabled=disabled,
                      on_click=st.session_state.__setitem__, args=(step_key, value))
    st.caption(f'Etapa {step} de {total}')
    return step


def sync_steps(key, inputs):
    if st.session_state.get(f'{key}_inputs') != inputs:
        if st.session_state.get(f'{key}_step', 0) is not None:
            st.session_state[f'{key}_step'] = 0
        st.session_state[f'{key}_inputs'] = inputs


def initialization(base, edges):
    run = st.session_state.get('outage_run')
    vertices = apply_outages(base, run['failed'] if run else ())
    names = {key: node['nome'] for key, node in vertices.items()}
    st.subheader('Inicialização dos serviços')
    st.markdown('Cada seta **A → B** indica que B precisa de A. Kahn retira da fila um '
                'serviço sem dependências estruturais restantes e reduz o grau de entrada '
                'dos seus sucessores. A disponibilidade é avaliada ao aplicar essa ordem ao hospital.')
    st.caption('Uma réplica atende à mesma dependência quando tem uma ligação direta com o consumidor. Cada instância mantém suas próprias dependências de inicialização.')
    st.button('Aplicar cenário de exemplo', key='kahn_restore', on_click=load_example,
              help='Substitui o grafo atual pelo exemplo e encerra a simulação de disponibilidade.')
    if not vertices:
        edit_diagram(vertices, edges, {})
        return
    diagram_slot = st.container()
    if run:
        st.caption('Simulação de disponibilidade ativa. A edição manual define o estado de base.')
    watched = st.multiselect(
        'Serviços monitorados', names, default=[key for key in ('portal', 'dispensacao') if key in names],
        format_func=lambda key: names.get(key, key),
        key=f'monitor_{st.session_state.get("kahn_revision", 0)}_{tuple(names)}',
    )
    order, frames, remaining, parents = kahn(vertices, edges)
    sync_steps('kahn', (base, edges))
    if remaining:
        st.error('Plano inválido. O grafo contém um ciclo. Corrija as dependências para iniciar os serviços.')
        st.write('Serviços que Kahn deixou sem processar (podem estar no ciclo ou depender dele): '
                 + ', '.join(names[key] for key in remaining))
    step = controls(len(order), 'kahn')
    states, blockers, providers, sequence = initialization_state(vertices, order, parents, step, bool(remaining))
    if watched:
        for offset in range(0, len(watched), 3):
            row = watched[offset:offset + 3]
            for column, key in zip(st.columns(len(row)), row):
                column.metric(names[key], 'Plano inválido' if remaining else states[key])
    with diagram_slot:
        edit_diagram(base, edges, states, providers=providers)
    if not remaining and order:
        st.markdown('**Uma ordem topológica válida**')
        st.write(' → '.join(names[key] for key in order))
    if not remaining and any(node.get('replica_of') for node in vertices.values()):
        st.write('Ordem de partida com réplicas — ' + (' → '.join(names[key] for key in sequence) or 'nenhum serviço apto'))
    show_providers(vertices, providers)
    current, queue, degrees = frames[step]
    with st.expander('Acompanhar Kahn', expanded=True):
        st.write(f'Último processado — {names[current] if current else "—"}')
        st.write('Fila de grau zero — ' + (', '.join(names[key] for key in queue) or 'vazia'))
        rows = [{'Serviço': names[key], 'Grau de entrada restante': degrees[key],
                 'Processado por Kahn': key in order[:step], 'Estado': states[key],
                 'Dependências que bloqueiam': ', '.join(names[p] for p in blockers.get(key, []))}
                for key in vertices]
        if rows:
            st.dataframe(rows, hide_index=True, width='stretch')


def show_providers(vertices, providers):
    if providers:
        st.markdown('**Instâncias que atendem às dependências**')
        st.dataframe([
            {'Dependência': vertices[parent]['nome'], 'Consumidor': vertices[target]['nome'],
             'Instância em uso': vertices[provider]['nome']}
            for (parent, target), provider in providers.items()
        ], hide_index=True)


def routing(vertices, edges):
    base, dependencies = validate(*model())
    if any(node.get('replica_of') for node in base.values()):
        run = st.session_state.get('outage_run')
        effective = apply_outages(base, run['failed'] if run else ())
        order, _, remaining, parents = kahn(effective, dependencies)
        _, _, providers, _ = initialization_state(effective, order, parents, len(order), bool(remaining))
        with st.expander('Failover de dependências do grafo de Inicialização'):
            st.caption('Prévia após executar a inicialização até o fim. A seleção por latência ou custo usa o grafo de requisições abaixo.')
            if providers:
                show_providers(base, providers)
            else:
                st.write('Nenhuma dependência está usando uma instância alternativa.')
    names = {key: node['nome'] for key, node in vertices.items()}
    st.subheader('Roteamento da consulta')
    st.markdown('As réplicas executam a mesma consulta autorizada. Após filtrar as ligações, '
                'Dijkstra escolhe o vértice de menor distância acumulada e tenta melhorar '
                'as distâncias dos vizinhos. Cada execução minimiza uma única métrica.')
    st.button('Aplicar cenário de exemplo', key='dijkstra_restore', on_click=load_example, args=(True,),
              help='Substitui o grafo de requisições pelo exemplo.')
    if not names:
        edit_diagram(vertices, edges, {}, routing=True)
        return
    diagram_slot = st.container()
    left, right, goal = st.columns(3)
    keys = list(names)
    endpoint_key = st.session_state.get('dijkstra_revision', 0)
    for endpoint in ('origem', 'destino'):
        key = f'{endpoint}_{endpoint_key}'
        if key in st.session_state and st.session_state[key] not in names:
            del st.session_state[key]
    source = left.selectbox('Origem', keys, index=keys.index('gateway') if 'gateway' in names else 0,
                            format_func=names.get, key=f'origem_{endpoint_key}')
    target = right.selectbox('Destino', keys, index=keys.index('resposta') if 'resposta' in names else len(keys) - 1,
                             format_func=names.get, key=f'destino_{endpoint_key}')
    objective = goal.selectbox('Objetivo', ['latencia', 'custo'],
                               format_func={'latencia': 'Menor latência', 'custo': 'Menor custo'}.get,
                               key=f'objetivo_{st.session_state.get("dijkstra_revision", 0)}')
    policy = st.session_state.get('dijkstra_revision', 0)
    left, right = st.columns(2)
    minimum = left.number_input('Taxa mínima por ligação (%)', 0.0, 100.0, 99.0,
                                step=0.1, format='%.2f', key=f'limite_{policy}')
    window = right.number_input('Janela de observação (min)', min_value=0.0, value=5.0,
                                step=1.0, key=f'janela_{policy}')
    if not isfinite(window) or window <= 0:
        st.error('Informe uma duração positiva e finita para a janela de observação.')
        return
    st.caption(f'Taxas sintéticas referentes a uma janela de {window:g} min. '
               f'Cada ligação precisa atingir pelo menos {minimum:g}%. '
               'A rota escolhida aparece em verde e as ligações excluídas ficam tracejadas.')
    sync_steps('dijkstra', (vertices, edges, source, target, objective, minimum, window))
    path, frames, excluded = dijkstra(vertices, edges, source, target, objective, Decimal(str(minimum)))
    step = controls(len(frames) - 1, 'dijkstra')
    finished = step == len(frames) - 1
    states = {key: 'Disponível' if node['disponivel'] else 'Indisponível'
              for key, node in vertices.items()}
    with diagram_slot:
        edit_diagram(vertices, edges, states, routing=True, excluded=excluded, path=path if finished else ())
    if finished and path:
        links = [edges[pair] for pair in zip(path, path[1:])]
        st.success(' → '.join(names[key] for key in path))
        left, right = st.columns(2)
        left.metric('Latência total', f"{sum(link['latencia'] for link in links):f} ms")
        right.metric('Custo total por requisição', f"R$ {sum(link['custo'] for link in links):f}")
    elif finished:
        unavailable = [names[key] for key in dict.fromkeys((source, target))
                       if not vertices[key]['disponivel']]
        detail = ' Vértice indisponível — ' + ', '.join(unavailable) + '.' if unavailable else ''
        st.warning('Nenhuma rota elegível para a política selecionada.' + detail)
    if excluded:
        with st.expander('Ligações excluídas', expanded=True):
            st.dataframe([{'Ligação': f'{names[a]} → {names[b]}', 'Motivos': ', '.join(reasons)}
                          for (a, b), reasons in excluded.items()], hide_index=True, width='stretch')
    current, distances, previous = frames[step]
    unit = 'ms' if objective == 'latencia' else 'R$'
    with st.expander('Acompanhar Dijkstra', expanded=True):
        st.write(f'Último vértice processado — {names[current] if current else "—"}')
        st.dataframe([{'Vértice': names[key],
                       f'Distância ({unit})': f'{distances[key]:f}' if key in distances else '∞',
                       'Predecessor': names[previous[key]] if key in previous else '—'}
                      for key in vertices], hide_index=True, width='stretch')


def about():
    st.subheader('O que precisa voltar primeiro?')
    st.markdown('Após uma interrupção, a equipe de TI precisa restabelecer o portal assistencial '
                'para consulta a prontuários e prescrições e a dispensação de medicamentos na farmácia. '
                'Uma falha no estoque afeta a dispensação. Uma falha nas prescrições afeta os dois fluxos. '
                'Com a consulta disponível, a equipe pode escolher entre réplicas autorizadas.')
    st.subheader('Arquitetura')
    st.markdown('O Streamlit mantém os controles na sessão e renderiza grafos direcionados com '
                'um componente de diagrama que segue o tema da interface. O arquivo **engine.py** valida vértices e ligações e usa listas de adjacência, '
                'uma fila de grau zero para Kahn e uma fila de prioridade para Dijkstra. '
                'O arquivo **app.py** apresenta as etapas e atualiza a interface.')
    st.code(Path(__file__).with_name('engine.py').read_text(encoding='utf-8-sig'),
            language='python', height=300)
    st.subheader('Soluções existentes')
    st.markdown("""
- **Docker Compose** coordena dependências de inicialização e pode aguardar verificações de saúde.
- **Kubernetes** usa init containers para pré-condições do pod e readiness probes para controlar sua prontidão.
- **HashiCorp Nomad** oferece descoberta de serviços e verificações de saúde.
- **Envoy Proxy** pode excluir do balanceamento instâncias com falhas.

O laboratório reúne recuperação parcial de fluxos, seleção de rotas e visualização
das etapas dos algoritmos com topologias e métricas editáveis. Os dados são fictícios.
""")


def availability():
    vertices, edges = validate(*model())
    run = st.session_state.get('outage_run')
    st.subheader('Simulador de disponibilidade')
    st.write('A cada intervalo, o simulador sorteia os vértices que ficam indisponíveis '
             'até a próxima rodada. Ao encerrar, vale novamente a disponibilidade manual.')
    if not vertices:
        st.info('Crie vértices na aba Inicialização para simular falhas.')
    if run:
        protected = run['protected']
        st.caption(f"Intervalo de {run['interval']} s · Até {run['count']} vértices por rodada")
        st.write('Protegidos — ' + (', '.join(node['nome'] for key, node in vertices.items()
                                             if key in protected) or 'nenhum'))
        if st.button('Encerrar simulação'):
            del st.session_state.outage_run
            st.rerun()
        failed = [node['nome'] for key, node in vertices.items()
                  if key in run['failed'] and node['disponivel']]
        st.write(f"Rodada {run['round']} · Falhas simuladas — " + (', '.join(failed) or 'nenhuma'))
        effective = apply_outages(vertices, run['failed'])
        order, _, remaining, parents = kahn(effective, edges)
        states, _, providers, _ = initialization_state(effective, order, parents, len(order), bool(remaining))
        graph(effective, edges, states, 'availability_graph', providers=providers)
        if remaining:
            st.warning('Existe um ciclo. A disponibilidade muda, mas o plano de inicialização está inválido.')
    elif vertices:
        left, right = st.columns(2)
        interval = left.number_input('Intervalo entre rodadas (s)', min_value=1, value=5, step=1)
        protected = st.multiselect('Vértices protegidos', list(vertices),
                                   format_func=lambda key: vertices[key]['nome'])
        eligible = sum(node['disponivel'] and key not in protected for key, node in vertices.items())
        count = right.number_input('Vértices indisponíveis por rodada', min_value=1,
                                   max_value=max(eligible, 1), value=1, step=1)
        if not eligible:
            st.info('Deixe ao menos um vértice disponível e sem proteção para iniciar.')
        if st.button('Iniciar simulação', disabled=not eligible):
            st.session_state.outage_run = dict(
                interval=interval, protected=set(protected), count=count,
                failed=set(), next_tick=monotonic() + interval, round=0,
            )
            st.rerun()


def outage_clock():
    run = st.session_state.get('outage_run')
    if not run or monotonic() < run['next_tick']:
        return
    vertices, _ = validate(*model())
    run['failed'] = outage_round(vertices, run['protected'], run['count'], run['failed'])
    run['next_tick'] = monotonic() + run['interval']
    run['round'] += 1
    st.rerun()


st.set_page_config(page_title='Recuperação Hospitalar', page_icon='🏥', layout='wide')
st.title('Recuperação hospitalar')
st.caption('Laboratório de Teoria dos Grafos · Simulação com dados fictícios')
st.write('Recupere o portal assistencial e a dispensação após uma interrupção e compare rotas para uma consulta hospitalar.')
init_tab, availability_tab, route_tab, about_tab = st.tabs(
    ['Inicialização', 'Simulador de disponibilidade', 'Roteamento', 'Cenário e arquitetura']
)
with init_tab:
    initialization(*validate(*model()))
with availability_tab:
    availability()
with route_tab:
    routing(*validate(*model('routing_model'), routing=True))
with about_tab:
    about()
if st.session_state.get('outage_run'):
    st.fragment(outage_clock, run_every=0.5)()
