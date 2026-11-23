from copy import deepcopy
from decimal import Decimal
import unittest

from streamlit.testing.v1 import AppTest

from engine import apply_outages, dijkstra, edit_graph, example, kahn, outage_round, startup, initialization_state, validate


class EngineTests(unittest.TestCase):
    def test_startup(self):
        nodes, links = example(False)
        vertices, edges = validate(nodes, links)
        order, frames, remaining, parents = kahn(vertices, edges)
        self.assertEqual((len(vertices), len(edges), len(frames[0][1])), (8, 10, 2))
        self.assertFalse(remaining)
        self.assertTrue(all(order.index(a) < order.index(b) for a, b in edges))
        for failed, expected in [
            (None, ('Iniciado', 'Iniciado')),
            ('estoque', ('Iniciado', 'Bloqueado')),
            ('prescricoes', ('Bloqueado', 'Bloqueado')),
            (None, ('Iniciado', 'Iniciado')),
        ]:
            for key in vertices:
                vertices[key]['disponivel'] = key != failed
            states, _ = startup(vertices, order, parents, len(order), False)
            self.assertEqual((states['portal'], states['dispensacao']), expected)
        edges['portal', 'auth'] = {}
        order, _, remaining, parents = kahn(vertices, edges)
        self.assertIn('auth', remaining)
        self.assertIn('dispensacao', remaining)
        states, _ = startup(vertices, order, parents, len(order), True)
        self.assertNotIn('Iniciado', states.values())
        self.assertEqual(kahn({}, {})[0], [])
        self.assertEqual(set(kahn(vertices, {})[0]), set(vertices))

    def test_routes(self):
        vertices, edges = validate(*example(True), routing=True)
        for objective, minimum, expected in [
            ('latencia', 99, ['gateway', 'a', 'resposta']),
            ('custo', 99, ['gateway', 'b', 'resposta']),
            ('latencia', 94, ['gateway', 'c', 'resposta']),
            ('latencia', 95, ['gateway', 'c', 'resposta']),
            ('latencia', 100, []),
        ]:
            path, _, _ = dijkstra(vertices, edges, 'gateway', 'resposta', objective, Decimal(minimum))
            self.assertEqual(path, expected)
        edges['gateway', 'a']['ativa'] = False
        vertices['b']['disponivel'] = False
        path, _, excluded = dijkstra(vertices, edges, 'gateway', 'resposta', 'latencia', Decimal(99))
        self.assertFalse(path)
        self.assertEqual(excluded['gateway', 'a'], ['Ligação desativada'])
        self.assertEqual(excluded['gateway', 'b'], ['Vértice indisponível'])
        self.assertEqual(excluded['c', 'resposta'], ['Taxa abaixo do limite'])

    def test_editor_and_availability(self):
        nodes, links = edit_graph([], [], dict(action='add', name='Origem', available=True))
        source = nodes[0]['id']
        nodes, links = edit_graph(nodes, links, dict(action='add', name='Destino',
                                                     parent=source, available=True))
        target = nodes[1]['id']
        with self.assertRaises(ValueError):
            edit_graph(nodes, links, dict(action='link', source=source, target=target))
        self.assertEqual(len(links), 1)
        vertices, _ = validate(nodes, links)
        failed = outage_round(vertices, {source}, 2, set())
        self.assertEqual(failed, {target})
        self.assertFalse(apply_outages(vertices, failed)[target]['disponivel'])
        self.assertTrue(vertices[target]['disponivel'])
        self.assertEqual(outage_round(vertices, set(), 1, {target}), {source})
        edited, remaining = edit_graph(nodes, links, dict(action='remove', id=source))
        self.assertEqual([node['id'] for node in edited], [target])
        self.assertFalse(remaining)

    def test_replica_failover(self):
        nodes, links = example(False)
        auth = next(node for node in nodes if node['id'] == 'auth')
        auth['disponivel'] = False
        nodes.append(dict(id='emergency', nome='API Emergencial', disponivel=True, replica_of='auth'))
        links.extend([dict(origem='operacional', destino='emergency'),
                      dict(origem='emergency', destino='prontuario')])
        vertices, edges = validate(nodes, links)
        order, _, remaining, parents = kahn(vertices, edges)
        states, _, providers, sequence = initialization_state(vertices, order, parents, len(order), bool(remaining))
        self.assertEqual(states['auth'], 'Indisponível')
        self.assertEqual(states['portal'], 'Iniciado')
        self.assertEqual(states['estoque'], 'Bloqueado')
        self.assertEqual(states['dispensacao'], 'Bloqueado')
        self.assertEqual(providers['auth', 'prontuario'], 'emergency')
        self.assertNotIn(('auth', 'estoque'), providers)

        edges['emergency', 'estoque'] = {}
        order, _, remaining, parents = kahn(vertices, edges)
        states, _, providers, sequence = initialization_state(vertices, order, parents, len(order), bool(remaining))
        self.assertEqual(states['estoque'], 'Iniciado')
        self.assertEqual(states['dispensacao'], 'Iniciado')
        self.assertEqual(providers['auth', 'estoque'], 'emergency')
        self.assertLess(sequence.index('emergency'), sequence.index('estoque'))
        primary_up = {**vertices, 'auth': dict(vertices['auth'], disponivel=True)}
        _, _, providers, _ = initialization_state(primary_up, order, parents, len(order), False)
        self.assertFalse(providers)
        down = apply_outages(vertices, {'operacional'})
        states, _, providers, _ = initialization_state(down, order, parents, len(order), False)
        self.assertEqual(states['portal'], 'Bloqueado')
        self.assertFalse(providers)
        with self.assertRaises(ValueError):
            edit_graph(nodes, links, dict(action='remove', id='auth'))

    def test_routing_diagram_edits(self):
        nodes, links = edit_graph([], [], dict(action='add', name='Origem', available=True), routing=True)
        source = nodes[0]['id']
        metrics = dict(latencia=7, custo=.001, sucesso=99, ativa=True)
        nodes, links = edit_graph(
            nodes, links, dict(action='add', name='Destino', available=True, parent=source, **metrics), routing=True
        )
        target = nodes[1]['id']
        pair = dict(source=source, target=target)
        with self.assertRaises(ValueError):
            edit_graph(nodes, links, dict(action='update_link', **pair, **dict(metrics, latencia=-1)), routing=True)
        self.assertEqual(links[0]['latencia'], 7)
        nodes, links = edit_graph(
            nodes, links, dict(action='update_link', **pair, **dict(metrics, ativa=False)), routing=True
        )
        vertices, edges = validate(nodes, links, routing=True)
        self.assertFalse(dijkstra(vertices, edges, source, target, 'latencia', Decimal(99))[0])
        _, links = edit_graph(nodes, links, dict(action='unlink', **pair), routing=True)
        self.assertFalse(links)

    def test_validation(self):
        nodes, links = example(True)
        for field, invalid in [('latencia', -1), ('custo', float('inf')), ('custo', 'x'), ('sucesso', 101)]:
            edited = deepcopy(links)
            edited[0][field] = invalid
            with self.assertRaises(ValueError):
                validate(nodes, edited, True)
        for edited_nodes, edited_links in [
            ([dict(nodes[0], nome=' ')] + nodes[1:], links),
            (nodes + nodes[:1], links),
            (nodes[1:], links),
            (nodes, links + links[:1]),
        ]:
            with self.assertRaises(ValueError):
                validate(edited_nodes, edited_links, True)


class AppTests(unittest.TestCase):
    def test_demonstration(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.metric)
        app.button(key='kahn_restore').click().run()
        app.button(key='kahn_end').click().run()
        self.assertEqual([metric.value for metric in app.tabs[0].metric], ['Iniciado', 'Iniciado'])
        app.button(key='dijkstra_restore').click().run()
        app.button(key='dijkstra_end').click().run()
        self.assertIn('Réplica A', app.success[0].value)
        app.selectbox(key='objetivo_1').set_value('custo').run()
        self.assertIn('Réplica B', app.success[0].value)
        app.selectbox(key='objetivo_1').set_value('latencia').run()
        app.number_input(key='limite_1').set_value(94.0).run()
        self.assertIn('Réplica C', app.success[0].value)
        app.button(key='kahn_restore').click().run()
        self.assertFalse(app.exception)
        self.assertEqual([metric.value for metric in app.tabs[0].metric], ['Pendente', 'Pendente'])
