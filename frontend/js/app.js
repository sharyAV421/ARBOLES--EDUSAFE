import { ApiError, api } from './api.js';

const elements = {
  status: document.getElementById('status'),
  statusActions: document.getElementById('status-actions'),
  scenarioList: document.getElementById('scenario-list'),
  questionPanel: document.getElementById('question-panel'),
  question: document.getElementById('question'),
  answerButtons: document.getElementById('answer-buttons'),
  protocolPanel: document.getElementById('protocol-panel'),
  restart: document.getElementById('restart'),
  changeScenario: document.getElementById('change-scenario'),
  tree: document.getElementById('tree'),
  stepChip: document.getElementById('step-chip'),
};

let session = null;
let tree = null;

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function validateScenarioList(payload) {
  if (!Array.isArray(payload.scenarios)) throw new Error('La lista de escenarios no tiene el formato esperado.');
  const identifiers = new Set();
  for (const scenario of payload.scenarios) {
    if (!isRecord(scenario) || typeof scenario.id !== 'string' || !scenario.id ||
        typeof scenario.title !== 'string' || typeof scenario.description !== 'string') {
      throw new Error('Uno de los escenarios recibidos no tiene datos válidos.');
    }
    if (identifiers.has(scenario.id)) throw new Error('La lista de escenarios contiene identificadores repetidos.');
    identifiers.add(scenario.id);
  }
  return payload.scenarios;
}

function validateTree(payload, scenarioId) {
  if (payload.scenario_id !== scenarioId || typeof payload.root_id !== 'string' || !Array.isArray(payload.nodes)) {
    throw new Error('El árbol de decisiones no está disponible en un formato válido.');
  }
  const nodes = new Map();
  for (const node of payload.nodes) {
    if (!isRecord(node) || typeof node.id !== 'string' || !node.id ||
        !['decision', 'terminal'].includes(node.type) || typeof node.label !== 'string') {
      throw new Error('El árbol de decisiones contiene un nodo no válido.');
    }
    if (nodes.has(node.id)) throw new Error('El árbol de decisiones contiene identificadores repetidos.');
    if (node.type === 'decision' && (typeof node.yes !== 'string' || typeof node.no !== 'string')) {
      throw new Error('El árbol de decisiones tiene una rama incompleta.');
    }
    nodes.set(node.id, node);
  }
  if (!nodes.has(payload.root_id)) throw new Error('El árbol de decisiones no tiene un inicio válido.');
  for (const node of nodes.values()) {
    if (node.type === 'decision' && (!nodes.has(node.yes) || !nodes.has(node.no))) {
      throw new Error('El árbol de decisiones apunta a una rama que no existe.');
    }
  }
  return { ...payload, nodes: [...nodes.values()] };
}

function validateProtocol(protocol, scenarioId) {
  if (!isRecord(protocol) || typeof protocol.id !== 'string' || typeof protocol.title !== 'string' ||
      protocol.scenario_id !== scenarioId || typeof protocol.version !== 'string' ||
      !Array.isArray(protocol.instructions) || !protocol.instructions.every((item) => typeof item === 'string')) {
    return false;
  }
  if (protocol.approval_status === 'unapproved') return true;
  return protocol.approval_status === 'approved' &&
    typeof protocol.approving_authority === 'string' && protocol.approving_authority.trim().length > 0 &&
    typeof protocol.review_date === 'string' && protocol.review_date.trim().length > 0 &&
    protocol.instructions.length > 0;
}

function validateSession(state, activeTree) {
  if (!isRecord(state) || typeof state.session_id !== 'string' || !state.session_id ||
      state.scenario_id !== activeTree.scenario_id || typeof state.current_node_id !== 'string' ||
      typeof state.completed !== 'boolean' || !Array.isArray(state.path) ||
      !state.path.every((id) => typeof id === 'string')) {
    throw new Error('El servicio devolvió un estado de consulta no válido.');
  }
  const nodes = new Map(activeTree.nodes.map((node) => [node.id, node]));
  const currentNode = nodes.get(state.current_node_id);
  if (!currentNode || (state.path.length && state.path[state.path.length - 1] !== state.current_node_id) ||
      state.path.some((id) => !nodes.has(id)) || (state.path.length && state.path[0] !== activeTree.root_id)) {
    throw new Error('El recorrido recibido no coincide con el árbol de decisiones.');
  }
  for (let index = 1; index < state.path.length; index += 1) {
    const previous = state.path[index - 1];
    const next = state.path[index];
    if (previous === next) continue;
    const parent = nodes.get(previous);
    if (parent.type !== 'decision' || (parent.yes !== next && parent.no !== next)) {
      throw new Error('El recorrido recibido no coincide con las ramas del árbol.');
    }
  }
  if (!state.path.length && currentNode.id !== activeTree.root_id) {
    throw new Error('La consulta comenzó en un nodo inesperado.');
  }
  if (state.completed) {
    if (currentNode.type !== 'terminal' || !validateProtocol(state.protocol, state.scenario_id)) {
      return { ...state, protocol: null, protocolUnavailable: true };
    }
  } else {
    if (currentNode.type !== 'decision' || typeof state.question !== 'string' || !state.question.trim() ||
        !Array.isArray(state.answers) || state.answers.length !== 2 ||
        !state.answers.every((option) => isRecord(option) && typeof option.value === 'boolean' && typeof option.label === 'string') ||
        new Set(state.answers.map((option) => option.value)).size !== 2) {
      throw new Error('La pregunta recibida no tiene respuestas válidas.');
    }
  }
  return state;
}

function setStatus(message, { kind = 'info', actions = [] } = {}) {
  elements.status.textContent = message;
  elements.status.className = `status${kind === 'error' ? ' error' : ''}${kind === 'success' ? ' success' : ''}`;
  elements.status.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  elements.statusActions.replaceChildren();
  for (const action of actions) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'status-action';
    button.textContent = action.label;
    button.addEventListener('click', action.onClick);
    elements.statusActions.append(button);
  }
}

function clearTree(message = 'Elige un escenario para visualizar su recorrido.') {
  elements.tree.replaceChildren();
  const empty = document.createElement('p');
  empty.className = 'tree-empty';
  empty.textContent = message;
  elements.tree.append(empty);
}

function showError(error, actions = []) {
  const message = error instanceof Error ? error.message : 'Ocurrió un error inesperado.';
  setStatus(message, { kind: 'error', actions });
}

function pathEdges(path) {
  const edges = new Set();
  for (let index = 1; index < path.length; index += 1) {
    if (path[index - 1] !== path[index]) edges.add(`${path[index - 1]}:${path[index]}`);
  }
  return edges;
}

function renderTree() {
  if (!tree) return;
  const visited = new Set(session?.path || []);
  if (session) visited.add(session.current_node_id);
  const takenEdges = pathEdges(session?.path || []);
  const lookup = new Map(tree.nodes.map((node) => [node.id, node]));
  elements.tree.replaceChildren();
  const list = document.createElement('ol');
  list.className = 'tree-list';
  for (const node of tree.nodes) {
    const item = document.createElement('li');
    item.className = `tree-node${node.type === 'terminal' ? ' terminal' : ''}${visited.has(node.id) ? ' visited' : ''}${session?.current_node_id === node.id ? ' current' : ''}`;
    if (session?.current_node_id === node.id) item.setAttribute('aria-current', 'step');
    const type = document.createElement('span');
    type.className = 'node-type';
    const currentLabel = session?.current_node_id === node.id ? ' · Recorrido actual' : visited.has(node.id) ? ' · Recorrido' : '';
    type.textContent = `${node.id === tree.root_id ? 'Inicio' : node.type === 'decision' ? 'Decisión' : 'Resultado'}${currentLabel}`;
    const label = document.createElement('span');
    label.className = 'node-label';
    label.textContent = node.label;
    item.append(type, label);
    if (node.type === 'decision') {
      const branches = document.createElement('ul');
      branches.className = 'node-branches';
      for (const [answer, target] of [['Sí', node.yes], ['No', node.no]]) {
        const branch = document.createElement('li');
        branch.className = 'branch-line';
        const nextNode = lookup.get(target);
        const taken = takenEdges.has(`${node.id}:${target}`);
        branch.textContent = `${answer} → ${nextNode.label}${taken ? ' · Recorrido realizado' : ''}`;
        if (taken) branch.classList.add('branch-visited');
        branches.append(branch);
      }
      item.append(branches);
    }
    list.append(item);
  }
  elements.tree.append(list);
}

function focusAfterUpdate(target) {
  target?.focus({ preventScroll: false });
}

function renderProtocol(protocol) {
  const panel = elements.protocolPanel;
  panel.replaceChildren();
  const badge = document.createElement('span');
  badge.className = `protocol-badge${protocol.approval_status === 'approved' ? ' approved' : ' unapproved'}`;
  badge.textContent = protocol.approval_status === 'approved'
    ? 'PROTOCOLO APROBADO'
    : 'DATOS DE DEMOSTRACIÓN · NO APROBADO PARA EMERGENCIAS REALES';
  const title = document.createElement('h3');
  title.tabIndex = -1;
  title.textContent = protocol.title;
  const metadata = document.createElement('p');
  metadata.className = 'protocol-meta';
  metadata.textContent = protocol.approval_status === 'approved'
    ? `Versión ${protocol.version} · Autoridad: ${protocol.approving_authority} · Revisión: ${protocol.review_date}`
    : `Versión ${protocol.version} · Sin autoridad aprobadora ni fecha de revisión.`;
  panel.append(badge, title, metadata);
  if (protocol.approval_status === 'approved') {
    const heading = document.createElement('p');
    heading.className = 'instructions-heading';
    heading.textContent = 'Instrucciones del protocolo institucional';
    const instructions = document.createElement('ul');
    for (const instruction of protocol.instructions) {
      const item = document.createElement('li');
      item.textContent = instruction;
      instructions.append(item);
    }
    panel.append(heading, instructions);
  } else {
    const notice = document.createElement('p');
    notice.className = 'unapproved-notice';
    notice.textContent = 'Este contenido es solo una demostración y no contiene instrucciones para actuar. Consulta el protocolo institucional vigente y sigue las indicaciones del personal de emergencia designado.';
    panel.append(notice);
  }
  return title;
}

function renderProtocolUnavailable() {
  const panel = elements.protocolPanel;
  panel.replaceChildren();
  const heading = document.createElement('h3');
  heading.tabIndex = -1;
  heading.textContent = 'Protocolo no disponible';
  const explanation = document.createElement('p');
  explanation.textContent = 'El árbol llegó a un resultado, pero el servicio no entregó un protocolo válido para consultarlo. No se mostrarán instrucciones alternativas.';
  panel.append(heading, explanation);
  return heading;
}

function renderSession(rawState, { focus = true } = {}) {
  const state = validateSession(rawState, tree);
  session = state;
  elements.statusActions.replaceChildren();
  elements.status.textContent = '';
  elements.status.className = 'status';
  elements.status.setAttribute('role', 'status');
  elements.questionPanel.hidden = state.completed;
  elements.protocolPanel.hidden = !state.completed;
  elements.restart.hidden = false;
  elements.changeScenario.hidden = false;
  elements.stepChip.textContent = state.completed ? 'FINALIZADO' : `PASO ${Math.floor(state.path.length / 2) + 1}`;
  let focusTarget;
  if (!state.completed) {
    elements.question.textContent = state.question;
    elements.answerButtons.replaceChildren();
    for (const option of state.answers) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'answer-button';
      button.textContent = option.label;
      button.addEventListener('click', () => submitAnswer(option.value));
      elements.answerButtons.append(button);
    }
    focusTarget = elements.question;
  } else if (state.protocolUnavailable) {
    focusTarget = renderProtocolUnavailable();
  } else {
    focusTarget = renderProtocol(state.protocol);
  }
  renderTree();
  if (focus) focusAfterUpdate(focusTarget);
}

async function loadScenarios({ focus = false } = {}) {
  setStatus('Cargando escenarios…');
  elements.scenarioList.replaceChildren();
  elements.scenarioList.hidden = false;
  try {
    const scenarios = validateScenarioList(await api.scenarios());
    if (!scenarios.length) {
      setStatus('No hay escenarios configurados para consulta.');
      clearTree();
      return;
    }
    setStatus('Selecciona un escenario para iniciar la consulta.');
    const icons = ['◈', '⌁', '＋', '◇'];
    scenarios.forEach((scenario, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'scenario-card';
      const icon = document.createElement('span');
      icon.className = 'scenario-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = icons[index % icons.length];
      const text = document.createElement('span');
      text.className = 'scenario-text';
      const title = document.createElement('span');
      title.className = 'scenario-title';
      title.textContent = scenario.title;
      const description = document.createElement('span');
      description.className = 'scenario-description';
      description.textContent = scenario.description;
      text.append(title, description);
      const arrow = document.createElement('span');
      arrow.className = 'scenario-arrow';
      arrow.setAttribute('aria-hidden', 'true');
      arrow.textContent = '›';
      button.append(icon, text, arrow);
      button.addEventListener('click', () => startSession(scenario.id, button));
      elements.scenarioList.append(button);
    });
    if (focus) focusAfterUpdate(elements.scenarioList.querySelector('button'));
  } catch (error) {
    showError(error, [{ label: 'Volver a cargar escenarios', onClick: () => loadScenarios() }]);
  }
}

async function startSession(scenarioId, sourceButton) {
  elements.scenarioList.querySelectorAll('button').forEach((button) => { button.disabled = true; });
  setStatus('Cargando el árbol y preparando la consulta…');
  try {
    const loadedTree = validateTree(await api.tree(scenarioId), scenarioId);
    const started = await api.start(scenarioId);
    tree = loadedTree;
    elements.scenarioList.hidden = true;
    renderSession(started);
  } catch (error) {
    tree = null;
    elements.scenarioList.querySelectorAll('button').forEach((button) => { button.disabled = false; });
    const message = error instanceof ApiError && error.status === 404
      ? 'El escenario o su árbol no están disponibles. Elige otro escenario o inténtalo más tarde.'
      : error.message;
    showError(new Error(message), [{ label: 'Actualizar escenarios', onClick: () => loadScenarios() }]);
    focusAfterUpdate(sourceButton);
  }
}

function showExpiredSession() {
  session = null;
  tree = null;
  elements.scenarioList.hidden = false;
  elements.scenarioList.querySelectorAll('button').forEach((button) => { button.disabled = false; });
  elements.questionPanel.hidden = true;
  elements.protocolPanel.hidden = true;
  elements.restart.hidden = true;
  elements.changeScenario.hidden = true;
  elements.stepChip.textContent = 'PASO 1';
  clearTree('La sesión terminó. Inicia una nueva consulta para ver el árbol.');
  setStatus('La sesión ya no está disponible. Inicia una consulta nueva; el estado anterior no se ha conservado.', {
    kind: 'error',
    actions: [{ label: 'Actualizar escenarios', onClick: () => loadScenarios({ focus: true }) }],
  });
  focusAfterUpdate(elements.statusActions.querySelector('button') || elements.scenarioList.querySelector('button'));
}

async function synchronizeSession() {
  if (!session) return;
  setStatus('Comprobando el estado de la consulta…');
  try {
    renderSession(await api.state(session.session_id));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      showExpiredSession();
      return;
    }
    showError(error, [{ label: 'Comprobar de nuevo', onClick: synchronizeSession }]);
  }
}

async function submitAnswer(answer) {
  if (!session) return;
  elements.answerButtons.querySelectorAll('button').forEach((button) => { button.disabled = true; });
  setStatus('Registrando la respuesta…');
  try {
    renderSession(await api.answer(session.session_id, answer));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      showExpiredSession();
      return;
    }
    if (error instanceof ApiError && error.status === 409) {
      await synchronizeSession();
      return;
    }
    showError(error, [{ label: 'Comprobar el estado de la consulta', onClick: synchronizeSession }]);
  }
}

async function resetSession() {
  if (!session) return;
  elements.restart.disabled = true;
  setStatus('Reiniciando la consulta…');
  try {
    renderSession(await api.reset(session.session_id));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      showExpiredSession();
      return;
    }
    showError(error, [{ label: 'Comprobar el estado de la consulta', onClick: synchronizeSession }]);
  } finally {
    elements.restart.disabled = false;
  }
}

function changeScenario() {
  session = null;
  tree = null;
  elements.questionPanel.hidden = true;
  elements.protocolPanel.hidden = true;
  elements.restart.hidden = true;
  elements.changeScenario.hidden = true;
  elements.stepChip.textContent = 'PASO 1';
  clearTree();
  loadScenarios({ focus: true });
}

elements.restart.addEventListener('click', resetSession);
elements.changeScenario.addEventListener('click', changeScenario);
loadScenarios();
