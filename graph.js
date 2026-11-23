const views = new WeakMap();

function spreadEndpoints(ends, start, size) {
  for (const group of ends.values()) {
    group.forEach((end, index) => {
      end.offset = start + size * (index + 1) / (group.length + 1);
    });
  }
}

function trackEndpoint(groups, key, oppositeY) {
  if (!groups.has(key)) groups.set(key, []);
  const end = {oppositeY};
  groups.get(key).push(end);
  return end;
}

function element(tag, className, text) {
  const result = document.createElement(tag);
  result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}

function action(text, handler, className = '') {
  const button = element('button', className, text);
  button.type = 'button';
  button.onclick = handler;
  return button;
}

export default function ({parentElement, data, setTriggerValue}) {
  const shell = parentElement.querySelector('.graph-shell');
  const toolbar = shell.querySelector('.graph-toolbar');
  const board = shell.querySelector('.graph-board');
  const inspector = shell.querySelector('.graph-inspector');
  const {nodes, edges, editable, revision} = data;
  const byId = new Map(nodes.map(node => [node.id, node]));
  let view = views.get(shell);
  if (!view || view.revision !== revision) {
    view = {revision, selection: null, connecting: null, pending: false};
    views.set(shell, view);
    inspector.replaceChildren();
  }
  view.pending = false;
  const manual = new Map(Object.entries(data.positions));
  if (view.drag?.moved) manual.set(view.drag.id, view.drag.position);

  board.onpointermove = event => {
    const drag = view.drag;
    if (!drag || event.pointerId !== drag.pointer) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    if (!drag.moved) {
      drag.moved = true;
      board.setPointerCapture(event.pointerId);
      board.dataset.dragging = 'true';
    }
    drag.position = {
      x: Math.max(8, Math.round(drag.start.x + dx)),
      y: Math.max(8, Math.round(drag.start.y + dy)),
    };
    manual.set(drag.id, drag.position);
    draw();
  };

  function finishDrag(event) {
    const drag = view.drag;
    if (!drag || event.pointerId !== drag.pointer) return;
    view.drag = null;
    delete board.dataset.dragging;
    if (drag.moved) setTriggerValue('move', {id: drag.id, ...drag.position, revision});
  }
  board.onpointerup = finishDrag;
  board.onpointercancel = finishDrag;

  function submit(command) {
    if (view.pending) return;
    view.pending = true;
    setTriggerValue('edit', {...command, revision});
  }

  function clearSelection() {
    view.selection = null;
    view.connecting = null;
    inspector.replaceChildren();
  }

  function routeFields(form, metrics = {}) {
    if (data.dependencies) return () => ({});
    const fields = {};
    for (const [key, title, value] of [
      ['latencia', 'Latência (ms)', 0],
      ['custo', 'Custo (R$)', 0],
      ['sucesso', 'Taxa de sucesso (%)', 100],
    ]) {
      const label = element('label', '', title + ' ');
      const input = element('input', '');
      input.type = 'number';
      input.min = '0';
      input.step = 'any';
      input.required = true;
      if (key === 'sucesso') input.max = '100';
      input.value = metrics[key] ?? value;
      fields[key] = input;
      label.append(input);
      form.append(label);
    }
    const label = element('label', '');
    const active = element('input', '');
    active.type = 'checkbox';
    active.checked = metrics.ativa ?? true;
    label.append(active, ' Ligação ativa');
    form.append(label);
    return () => ({...Object.fromEntries(Object.entries(fields).map(([key, input]) =>
      [key, input.valueAsNumber])), ativa: active.checked});
  }

  function beginConnection(id) {
    view.selection = id;
    view.connecting = id;
    inspector.replaceChildren();
    draw();
    toolbar.querySelector('.graph-cancel')?.focus();
  }

  function openNode(id, parent, primary) {
    const node = byId.get(id);
    view.selection = id;
    view.connecting = null;
    const form = element('form', '');
    form.setAttribute('aria-label', node ? 'Editar vértice' : 'Criar vértice');
    if (parent) form.append(element('strong', '', 'Novo vértice ligado a ' + byId.get(parent).nome));
    if (primary) form.append(element('strong', '', 'Nova réplica de ' + byId.get(primary).nome));
    const label = element('label', '', 'Nome do vértice ');
    const name = element('input', '');
    name.type = 'text';
    name.required = true;
    name.value = node?.nome ?? '';
    label.append(name);
    const availability = element('label', '');
    const available = element('input', '');
    available.type = 'checkbox';
    available.checked = node?.disponivel ?? true;
    availability.append(available, ' Disponível manualmente');
    const save = element('button', '', node ? 'Salvar' : 'Criar vértice');
    save.type = 'submit';
    const replicaLabel = element('label', '', 'Réplica de ');
    const replica = element('select', '');
    const standalone = element('option', '', 'Serviço independente');
    standalone.value = '';
    replica.append(standalone);
    for (const candidate of nodes.filter(item => item.id !== id && !item.replica_of)) {
      const option = element('option', '', candidate.nome);
      option.value = candidate.id;
      replica.append(option);
    }
    replica.value = node?.replica_of ?? primary ?? '';
    replicaLabel.append(replica);
    form.append(label, availability, replicaLabel);
    const metrics = parent ? routeFields(form) : () => ({});
    form.append(save);
    form.onsubmit = event => {
      event.preventDefault();
      if (!name.value.trim()) {
        name.focus();
        return;
      }
      submit({action: node ? 'update' : 'add', id, parent, name: name.value,
        available: available.checked, replica_of: replica.value, ...metrics()});
    };
    if (node) {
      form.append(
        action('Ligar a outro vértice', () => beginConnection(id)),
        action('Criar réplica', () => openNode(undefined, undefined, node.replica_of ?? id)),
        action('Remover vértice e ligações', () => {
          inspector.replaceChildren();
          const confirmation = element('form', '');
          confirmation.append(element('span', '', 'Remover este vértice e todas as suas ligações?'),
            action('Confirmar remoção', () => submit({action: 'remove', id})),
            action('Cancelar', () => openNode(id)));
          inspector.append(confirmation);
        }),
      );
    }
    form.append(action('Fechar', () => { clearSelection(); draw(); }));
    inspector.replaceChildren(form);
    draw();
    name.focus({preventScroll: true});
    inspector.scrollIntoView({block: 'nearest'});
  }

  function openEdge(edge, creating = false) {
    clearSelection();
    const form = element('form', '');
    const {source, target} = edge;
    form.append(element('strong', '', byId.get(source).nome + ' → ' + byId.get(target).nome));
    if (!data.dependencies) {
      const metrics = routeFields(form, edge.metrics);
      const save = element('button', '', creating ? 'Criar ligação' : 'Salvar ligação');
      save.type = 'submit';
      form.append(save);
      form.onsubmit = event => {
        event.preventDefault();
        submit({action: creating ? 'link' : 'update_link', source, target, ...metrics()});
      };
    }
    if (!creating) form.append(action('Remover ligação', () => submit({action: 'unlink', source, target})));
    form.append(action('Fechar', () => { clearSelection(); draw(); }));
    inspector.append(form);
    inspector.scrollIntoView({block: 'nearest'});
    draw();
  }

  function selectNode(id) {
    if (view.connecting === null) return openNode(id);
    const source = view.connecting;
    if (source === id) return;
    const existing = edges.find(edge => edge.source === source && edge.target === id);
    if (existing) openEdge(existing);
    else if (data.dependencies) submit({action: 'link', source, target: id});
    else openEdge({source, target: id}, true);
  }

  function draw() {
    toolbar.replaceChildren();
    toolbar.hidden = !editable;
    if (editable) {
      toolbar.append(action('+ Novo vértice', () => openNode()));
      if (view.connecting !== null) {
        toolbar.append(element('span', '', 'Origem: ' + byId.get(view.connecting).nome + '. Selecione o destino.'),
          action('Cancelar ligação', () => { clearSelection(); draw(); }, 'graph-cancel'));
      } else if (nodes.length) {
        toolbar.append(element('span', '', 'Arraste para organizar. Clique para editar. Use + para criar um vértice ligado ou → para escolher um destino.'));
      }
    }
    const legend = shell.querySelector('.graph-legend');
    legend.hidden = !data.dependencies || !nodes.length;
    board.replaceChildren();
    if (!nodes.length) {
      board.style.cssText = '';
      board.append(element('div', 'graph-empty', 'Grafo vazio. Crie um vértice ou aplique o cenário de exemplo.'));
      return;
    }

    const advance = 236;
    const positions = new Map();
    const counts = new Map();
    for (const node of nodes) {
      const row = counts.get(node.rank) ?? 0;
      counts.set(node.rank, row + 1);
      positions.set(node.id, manual.get(node.id) ?? {x: 18 + node.rank * advance, y: 20 + row * 100});
    }
    const cardWidth = 172;
    const width = Math.max(...[...positions.values()].map(point => point.x)) + 224;
    const cardArea = Math.max(...[...positions.values()].map(point => point.y)) + 82;
    const longEdges = edges.filter(edge =>
      !manual.has(edge.source) && !manual.has(edge.target)
      && Math.abs(byId.get(edge.source).rank - byId.get(edge.target).rank) > 1);
    const lanes = new Map(longEdges.map((edge, index) => [edge, cardArea + 12 + index * 24]));
    // Give each connection its own port and each long segment its own column in the gap.
    const ports = new Map();
    const channels = new Map();
    const geometry = new Map();
    for (const edge of edges) {
      const sourceRank = byId.get(edge.source).rank;
      const targetRank = byId.get(edge.target).rank;
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      const moved = manual.has(edge.source) || manual.has(edge.target);
      const horizontalGap = target.x - source.x;
      const sourceRight = moved ? horizontalGap >= -cardWidth : sourceRank <= targetRank;
      const targetRight = moved ? horizontalGap <= cardWidth : sourceRank >= targetRank;
      const from = trackEndpoint(ports, JSON.stringify([edge.source, sourceRight]), target.y);
      const to = trackEndpoint(ports, JSON.stringify([edge.target, targetRight]), source.y);
      let exit;
      let entry;
      if (lanes.has(edge)) {
        exit = trackEndpoint(channels, sourceRight ? sourceRank : sourceRank - 1);
        entry = trackEndpoint(channels, targetRight ? targetRank : targetRank - 1);
      }
      geometry.set(edge, {from, to, exit, entry, sourceRight, targetRight});
    }
    for (const group of ports.values()) {
      group.sort((a, b) => a.oppositeY - b.oppositeY);
    }
    spreadEndpoints(ports, 8, 46);
    spreadEndpoints(channels, 8, advance - cardWidth - 16);
    const height = cardArea + (longEdges.length ? longEdges.length * 24 + 12 : 0);
    board.style.minWidth = width + 'px';
    board.style.height = height + 'px';
    const canvas = element('canvas', '');
    canvas.setAttribute('aria-hidden', 'true');
    const dpi = window.devicePixelRatio || 1;
    canvas.width = width * dpi;
    canvas.height = height * dpi;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    board.append(canvas);
    const ctx = canvas.getContext('2d');
    ctx.scale(dpi, dpi);
    const theme = getComputedStyle(shell);
    const neutral = theme.color;
    const green = theme.getPropertyValue('--graph-available').trim();
    const red = theme.getPropertyValue('--graph-unavailable').trim();
    for (const edge of edges) {
      const a = positions.get(edge.source);
      const b = positions.get(edge.target);

      const {from, to, exit, entry, sourceRight, targetRight} = geometry.get(edge);
      const x1 = a.x + (sourceRight ? cardWidth : 0);
      const x2 = b.x + (targetRight ? cardWidth : 0);
      const y1 = a.y + from.offset;
      const y2 = b.y + to.offset;
      const sameSide = sourceRight === targetRight;
      const bend = sameSide ? Math.abs(x2 - x1) + 40 : Math.abs(x2 - x1) * .5;
      const dependency = data.dependencies;
      const unavailable = dependency &&
        ['Bloqueado', 'Indisponível'].includes(byId.get(edge.source).estado);
      const color = dependency ? (unavailable ? red : green)
        : edge.active ? '#28a269' : edge.excluded ? '#d89539' : neutral;
      ctx.globalAlpha = dependency || edge.active || edge.excluded ? 1 : .43;
      ctx.strokeStyle = ctx.fillStyle = color;
      ctx.lineWidth = edge.active ? 3 : dependency ? 1.8 : 1.5;
      ctx.setLineDash(edge.excluded || unavailable ? [5, 4] : []);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      const direction = targetRight ? -1 : 1;
      const lane = lanes.get(edge);
      const badgeX = (x1 + x2) / 2 + (sameSide ? bend * .75 : 0);
      let badgeY = (y1 + y2) / 2;
      if (lane !== undefined) {
        const firstGap = Math.min(a.x, a.x + (sourceRight ? advance : -advance));
        const lastGap = Math.min(b.x, b.x + (targetRight ? advance : -advance));
        const exitX = firstGap + cardWidth + exit.offset;
        const entryX = lastGap + cardWidth + entry.offset;
        ctx.lineTo(exitX, y1);
        ctx.lineTo(exitX, lane);
        ctx.lineTo(entryX, lane);
        ctx.lineTo(entryX, y2);
        ctx.lineTo(x2, y2);
        badgeY = lane;
      } else {
        ctx.bezierCurveTo(x1 + (sourceRight ? bend : -bend), y1,
          x2 + (targetRight ? bend : -bend), y2, x2, y2);
        if (sameSide && edge.source !== edge.target && edges.some(other =>
          other.source === edge.target && other.target === edge.source)) {
          badgeY += edge.source < edge.target ? -10 : 10;
        }
      }
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - direction * 7, y2 - 4);
      ctx.lineTo(x2 - direction * 7, y2 + 4);
      ctx.fill();

      if (editable || edge.provider) {
        const badge = editable
          ? action(edge.provider ? '↪' : '→', () => openEdge(edge), 'graph-edge')
          : element('span', 'graph-edge', '↪');
        badge.title = byId.get(edge.source).nome + ' → ' + byId.get(edge.target).nome;
        badge.setAttribute('aria-label', 'Ligação ' + badge.title);
        if (edge.provider) badge.title += ' · Atendida por ' + byId.get(edge.provider).nome;
        if (!dependency) {
          const {latencia, custo, sucesso} = edge.metrics;
          badge.title += ' · ' + latencia + ' ms · R$ ' + custo + ' · ' + sucesso + '%';
        }
        badge.dataset.active = edge.active;
        if (dependency) badge.dataset.availability = unavailable ? 'unavailable' : 'available';
        badge.style.left = badgeX + 'px';
        badge.style.top = badgeY + 'px';
        board.append(badge);
      }
    }
    for (const node of nodes) {
      const point = positions.get(node.id);
      const card = element('div', 'graph-card');
      card.dataset.state = node.estado;
      card.dataset.selected = node.id === view.selection;
      card.style.left = point.x + 'px';
      card.style.top = point.y + 'px';
      const body = editable ? action('', () => selectNode(node.id), 'graph-node') : element('div', 'graph-node');
      body.title = node.nome;
      const name = element('strong', 'graph-name', node.nome);
      const status = element('span', 'graph-status');
      const dot = element('span', 'graph-dot');
      dot.style.color = {
        'Apto': 'var(--st-blue-text-color, #4285d0)',
        'Iniciado': 'var(--st-green-text-color, #16864c)',
        'Indisponível': 'var(--st-red-text-color, #da5252)',
        'Bloqueado': 'var(--st-orange-text-color, #c07822)',
      }[node.estado] ?? 'currentColor';
      status.append(dot, node.estado);
      body.append(name, status);
      if (node.replica_of) {
        const replica = element('span', 'graph-replica', 'Réplica');
        replica.title = 'Réplica de ' + byId.get(node.replica_of).nome;
        replica.setAttribute('aria-label', replica.title);
        body.append(replica);
      }
      card.append(body);
      if (editable) {
        body.dataset.draggable = 'true';
        body.onpointerdown = event => {
          if (event.button !== 0 || view.connecting !== null || view.drag) return;
          body.setPointerCapture(event.pointerId);
          view.drag = {id: node.id, pointer: event.pointerId,
            x: event.clientX, y: event.clientY, start: point, moved: false};
        };
        const add = action('+', () => openNode(undefined, node.id), 'graph-add');
        add.title = add.ariaLabel = 'Criar vértice ligado a ' + node.nome;
        const connect = action('→', () => beginConnection(node.id), 'graph-add');
        connect.title = connect.ariaLabel = 'Criar ligação a partir de ' + node.nome;
        const actions = element('div', 'graph-actions');
        actions.append(add, connect);
        card.append(actions);
      }
      board.append(card);
    }
  }

  draw();
}
