"""Cenários fictícios e motores de grafos, sem dependências da interface."""

from collections import deque
from decimal import Decimal
from heapq import heappop, heappush
from math import isfinite
from random import sample
from uuid import uuid4


def example(routing):
    if routing:
        names = {"gateway": "Gateway", "a": "Réplica A", "b": "Réplica B",
                 "c": "Réplica C", "resposta": "Resposta"}
        rows = [
            ("gateway", "a", 5, .001, 99.9), ("a", "resposta", 15, .003, 99.8),
            ("gateway", "b", 10, .001, 99.9), ("b", "resposta", 25, .001, 99.9),
            ("gateway", "c", 3, .001, 99.9), ("c", "resposta", 7, .002, 95),
        ]
        links = [dict(origem=a, destino=b, latencia=ms, custo=cost, sucesso=rate, ativa=True)
                 for a, b, ms, cost, rate in rows]
    else:
        names = {"clinico": "Banco clínico", "operacional": "Banco operacional",
                 "auth": "Autenticação", "prontuario": "Prontuário", "estoque": "Estoque",
                 "prescricoes": "Prescrições", "portal": "Portal assistencial",
                 "dispensacao": "Dispensação"}
        pairs = [
            ("operacional", "auth"), ("clinico", "prontuario"), ("auth", "prontuario"),
            ("operacional", "estoque"), ("auth", "estoque"), ("prontuario", "prescricoes"),
            ("prontuario", "portal"), ("prescricoes", "portal"),
            ("prescricoes", "dispensacao"), ("estoque", "dispensacao"),
        ]
        links = [dict(origem=a, destino=b) for a, b in pairs]
    nodes = [dict(id=key, nome=name, disponivel=True) for key, name in names.items()]
    return nodes, links


def number(value, label, minimum=0, maximum=None):
    try:
        valid = not isinstance(value, bool) and isfinite(value)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid or value < minimum or (maximum is not None and value > maximum):
        interval = f"entre {minimum} e {maximum}" if maximum is not None else f"a partir de {minimum}"
        raise ValueError(f"{label} deve ser um número finito {interval}.")
    return Decimal(str(value))


def clean_text(value):
    return value.strip() if isinstance(value, str) else ""


def validate(nodes, links, routing=False):
    vertices = {}
    edges = {}
    for node in nodes:
        key = clean_text(node.get("id"))
        name = clean_text(node.get("nome"))
        if not key or not name:
            raise ValueError("Preencha o ID e o nome de cada vértice.")
        if key in vertices:
            raise ValueError(f"ID repetido: {key}.")
        vertices[key] = dict(nome=name, disponivel=bool(node.get("disponivel")))
        replica = clean_text(node.get("replica_of"))
        if replica:
            vertices[key]["replica_of"] = replica
    for key, node in vertices.items():
        primary = node.get("replica_of")
        if primary and (primary == key or primary not in vertices or vertices[primary].get("replica_of")):
            raise ValueError("A réplica deve apontar para outro vértice que seja um serviço principal.")
    for link in links:
        pair = tuple(clean_text(link.get(field)) for field in ("origem", "destino"))
        if any(key not in vertices for key in pair):
            raise ValueError(f"Ligação {pair[0]} → {pair[1]}: use IDs existentes. "
                             "Para remover um vértice, remova também suas ligações antes de aplicar.")
        if pair in edges:
            raise ValueError(f"Ligação repetida: {pair[0]} → {pair[1]}.")
        edges[pair] = {}
        if routing:
            label = f"{pair[0]} → {pair[1]}"
            edges[pair] = dict(
                latencia=number(link.get("latencia"), f"Latência de {label}"),
                custo=number(link.get("custo"), f"Custo de {label}"),
                sucesso=number(link.get("sucesso"), f"Taxa de sucesso de {label}", maximum=100),
                ativa=bool(link.get("ativa")),
            )
    return vertices, edges


def kahn(vertices, edges):
    successors = {key: [] for key in vertices}
    parents = {key: [] for key in vertices}
    for a, b in edges:
        successors[a].append(b)
        parents[b].append(a)
    degrees = {key: len(items) for key, items in parents.items()}
    queue = deque(key for key in vertices if degrees[key] == 0)
    order = []
    frames = [(None, list(queue), degrees.copy())]
    while queue:
        current = queue.popleft()
        order.append(current)
        for target in successors[current]:
            degrees[target] -= 1
            if degrees[target] == 0:
                queue.append(target)
        frames.append((current, list(queue), degrees.copy()))
    remaining = [key for key in vertices if degrees[key]]
    return order, frames, remaining, parents


def startup(vertices, order, parents, step, invalid):
    states = {}
    blockers = {}
    for key in vertices:
        states[key] = "Pendente" if vertices[key]["disponivel"] else "Indisponível"
    if invalid:
        return states, blockers
    for key in order:
        blockers[key] = [parent for parent in parents[key]
                         if states[parent] in ("Indisponível", "Bloqueado")]
        if states[key] != "Indisponível" and blockers[key]:
            states[key] = "Bloqueado"
    for key in order[:step]:
        if states[key] == "Pendente":
            states[key] = "Iniciado"
    for key in order[step:]:
        if states[key] == "Pendente" and all(states[p] == "Iniciado" for p in parents[key]):
            states[key] = "Apto"
    return states, blockers


def replica_startup(vertices, order, parents):
    """Find which instances can start, with OR within each dependency group."""
    primary = {key: node.get("replica_of", key) for key, node in vertices.items()}
    required = {}
    for key in vertices:
        groups = {}
        for parent in parents[key]:
            groups.setdefault(primary[parent], []).append(parent)
        for root, connected in groups.items():
            if root in connected:
                connected.remove(root)
                connected.insert(0, root)
        required[key] = groups
    started = set()
    sequence = []
    while True:
        ready = [key for key in order if key not in started and vertices[key]["disponivel"]
                 and all(started.intersection(connected) for connected in required[key].values())]
        if not ready:
            break
        sequence.extend(ready)
        started.update(ready)
    return sequence, required


def initialization_state(vertices, order, parents, step, invalid):
    if invalid or not any(node.get("replica_of") for node in vertices.values()):
        states, blockers = startup(vertices, order, parents, step, invalid)
        return states, blockers, {}, order
    sequence, required = replica_startup(vertices, order, parents)
    started = set(sequence[:step])
    possible = set(sequence)
    states = {}
    blockers = {}
    providers = {}
    for key in vertices:
        blockers[key] = [root for root, connected in required[key].items() if not possible.intersection(connected)]
        if not vertices[key]["disponivel"]:
            states[key] = "Indisponível"
        elif blockers[key]:
            states[key] = "Bloqueado"
        elif key in started:
            states[key] = "Iniciado"
        else:
            states[key] = "Apto" if all(started.intersection(connected) for connected in required[key].values()) else "Pendente"
        for root, connected in required[key].items():
            provider = next((member for member in connected if member in started and member != key), None)
            if provider and provider != root:
                providers[root if root in connected else provider, key] = provider
    return states, blockers, providers, sequence


def dijkstra(vertices, edges, source, target, objective, minimum):
    neighbors = {key: [] for key in vertices}
    excluded = {}
    for (a, b), link in edges.items():
        reasons = []
        if not vertices[a]["disponivel"] or not vertices[b]["disponivel"]:
            reasons.append("Vértice indisponível")
        if not link["ativa"]:
            reasons.append("Ligação desativada")
        if link["sucesso"] < minimum:
            reasons.append("Taxa abaixo do limite")
        if reasons:
            excluded[a, b] = reasons
        else:
            neighbors[a].append((b, link[objective]))

    distances = {}
    previous = {}
    ready = (source in vertices and target in vertices
             and vertices[source]["disponivel"] and vertices[target]["disponivel"])
    queue = [(Decimal(0), source)] if ready else []
    if ready:
        distances[source] = Decimal(0)
    frames = [(None, distances.copy(), previous.copy())]
    path = []
    while queue:
        distance, current = heappop(queue)
        if distance != distances[current]:
            continue
        if current != target:
            for neighbor, weight in neighbors[current]:
                candidate = distance + weight
                if neighbor not in distances or candidate < distances[neighbor]:
                    distances[neighbor] = candidate
                    previous[neighbor] = current
                    heappush(queue, (candidate, neighbor))
        frames.append((current, distances.copy(), previous.copy()))
        if current == target:
            path = [target]
            while path[-1] != source:
                path.append(previous[path[-1]])
            path.reverse()
            break
    return path, frames, excluded


def edit_graph(nodes, links, command, routing=False):
    """Return a validated draft, leaving the current graph intact on error."""
    nodes = [node.copy() for node in nodes]
    links = [link.copy() for link in links]
    by_id = {node["id"]: node for node in nodes}
    action = command.get("action")
    metrics = {}
    if routing and (action in ("link", "update_link") or command.get("parent") is not None):
        metrics = {field: command.get(field) for field in ("latencia", "custo", "sucesso", "ativa")}
    key = command.get("id")
    if action in ("add", "update"):
        values = dict(nome=command.get("name"), disponivel=command.get("available") is True,
                      replica_of=command.get('replica_of'))
        if action == "add":
            key = uuid4().hex
            nodes.append(dict(id=key, **values))
            if command.get("parent") is not None:
                links.append(dict(origem=command["parent"], destino=key, **metrics))
        elif key in by_id:
            by_id[key].update(values)
        else:
            raise ValueError("Vértice não encontrado.")
    elif action == "remove" and key in by_id:
        if any(node.get("replica_of") == key for node in nodes):
            raise ValueError("Desvincule as réplicas antes de remover o serviço principal.")
        nodes = [node for node in nodes if node["id"] != key]
        links = [link for link in links if key not in (link["origem"], link["destino"])]
    elif action == "link":
        links.append(dict(origem=command.get("source"), destino=command.get("target"), **metrics))
    elif action == "update_link" and routing:
        pair = command.get("source"), command.get("target")
        link = next((link for link in links if (link["origem"], link["destino"]) == pair), None)
        if link is None:
            raise ValueError("Ligação não encontrada.")
        link.update(metrics)
    elif action == "unlink":
        links = [link for link in links if (link["origem"], link["destino"])
                 != (command.get("source"), command.get("target"))]
    else:
        raise ValueError("Edição inválida.")
    validate(nodes, links, routing)
    return nodes, links


def outage_round(vertices, protected, count, previous):
    """Select available, unprotected vertices for the next interval."""
    eligible = [key for key, node in vertices.items()
                if node["disponivel"] and key not in protected]
    chosen = set(sample(eligible, min(count, len(eligible))))
    if chosen == previous and chosen and len(eligible) > len(chosen):
        chosen.remove(next(key for key in eligible if key in chosen))
        chosen.add(next(key for key in eligible if key not in previous))
    return chosen


def apply_outages(vertices, failed):
    return {key: dict(node, disponivel=node["disponivel"] and key not in failed)
            for key, node in vertices.items()}
