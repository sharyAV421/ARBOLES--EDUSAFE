// The frontend is served by FastAPI, so use the same local origin and port.
const API_BASE = '/api';

export class ApiError extends Error {
  constructor(message, { status = 0, kind = 'network' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
  }
}

async function request(path, options = {}) {
  let response;
  const headers = { Accept: 'application/json', ...options.headers };
  if (options.body) headers['Content-Type'] = 'application/json';
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers,
      ...options,
    });
  } catch {
    throw new ApiError('No se pudo conectar con EduSafe. Comprueba que el servicio esté activo e inténtalo de nuevo.');
  }

  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError('El servicio devolvió una respuesta que no se pudo leer.', {
      status: response.status,
      kind: 'invalid-response',
    });
  }

  if (!response.ok) {
    const messages = {
      404: 'La sesión, el escenario o el árbol solicitado ya no está disponible.',
      409: 'La consulta cambió de estado. Vamos a comprobarla.',
      422: 'La solicitud no coincide con el formato esperado.',
      500: 'El servicio encontró un problema. Inténtalo de nuevo más tarde.',
    };
    throw new ApiError(messages[response.status] || 'No fue posible completar la solicitud.', {
      status: response.status,
      kind: 'http',
    });
  }

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new ApiError('El servicio devolvió datos con un formato inesperado.', {
      status: response.status,
      kind: 'invalid-response',
    });
  }
  return payload;
}

export const api = {
  scenarios: () => request('/scenarios'),
  tree: (scenarioId) => request(`/scenarios/${encodeURIComponent(scenarioId)}/tree`),
  start: (scenarioId) => request('/sessions', {
    method: 'POST',
    body: JSON.stringify({ scenario_id: scenarioId }),
  }),
  state: (sessionId) => request(`/sessions/${encodeURIComponent(sessionId)}`),
  answer: (sessionId, answer) => request(`/sessions/${encodeURIComponent(sessionId)}/answers`, {
    method: 'POST',
    body: JSON.stringify({ answer }),
  }),
  reset: (sessionId) => request(`/sessions/${encodeURIComponent(sessionId)}/reset`, { method: 'POST' }),
};
