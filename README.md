# EduSafe

EduSafe es una aplicación académica local para explorar árboles binarios de decisión configurables. La interfaz HTML/CSS/JavaScript y la API FastAPI se sirven desde el mismo proceso en `http://127.0.0.1:8001`; no requiere hosting ni una base de datos. Las sesiones se guardan en memoria y se eliminan al cerrar el servidor.

> **Aviso de seguridad:** EduSafe es una herramienta complementaria de consulta y capacitación. No sustituye las alarmas oficiales, los servicios de emergencia ni las instrucciones del personal de emergencia designado. Ante una emergencia real, siga los canales oficiales de su institución y de los servicios de emergencia.
>
> Los escenarios del repositorio son ejemplos académicos. Los protocolos no aprobados se muestran con su estado y sin instrucciones operativas.

## Requisitos

- Windows 10 o posterior.
- Python 3.10 o posterior instalado y disponible como `py` en la terminal. La instalación de Python debe incluir `pip`.
- Navegador web moderno.
- Conexión a Internet solo durante la instalación inicial de dependencias. La aplicación ya instalada funciona sin servicios alojados.
- El puerto local `8001` debe estar disponible.

El entorno `.venv` es local y está excluido por `.gitignore`. Al copiar la carpeta para compartirla, omita `.venv`; `start.bat` creará un entorno nuevo en el otro computador.

## Instalación y ejecución rápida

1. Copie la carpeta completa del proyecto al computador local, por ejemplo, al Escritorio. No necesita acceso al computador original.
2. Haga doble clic en `start.bat`.
3. En el primer inicio, el archivo crea `.venv` e instala las dependencias de `requirements.txt`. Luego inicia FastAPI en `127.0.0.1:8001` y abre el navegador.
4. Si Windows pregunta por el acceso de red, permita solo acceso en redes privadas si resulta necesario. El servidor se enlaza a `127.0.0.1` y no se expone a la red.

También se puede instalar e iniciar desde PowerShell, en la carpeta del proyecto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Después abra `http://127.0.0.1:8001`. La documentación interactiva de la API está en `http://127.0.0.1:8001/docs`.

Si el puerto 8001 ya está ocupado, `start.bat` no termina ese otro proceso. Cierre manualmente la aplicación que lo usa y vuelva a ejecutar el archivo.

## Pruebas

Instale las dependencias como se indica arriba y ejecute desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas cubren la estructura y validación del árbol, la carga de escenarios, la API, las sesiones y las respuestas de protocolos.

## Cerrar la aplicación

Use `Ctrl+C` en la ventana titulada **EduSafe - servidor local** o cierre esa ventana. Esto detiene FastAPI; las sesiones activas se pierden al apagarlo. Cerrar la pestaña del navegador por sí sola no detiene el servidor.

## Uso de la API y del árbol

- `GET /api/scenarios`: lista los escenarios configurados.
- `GET /api/scenarios/{scenario_id}/tree`: devuelve los nodos y las ramas reales para dibujar el árbol.
- `POST /api/sessions` con `{"scenario_id":"fire-smoke"}`: crea una sesión.
- `GET /api/sessions/{session_id}`: obtiene el estado actual.
- `POST /api/sessions/{session_id}/answers` con `{"answer":true}`: responde sí o no.
- `POST /api/sessions/{session_id}/reset`: reinicia la sesión.

El navegador usa la ruta relativa `/api` en el mismo origen. Es el backend quien determina el siguiente nodo; el cliente no envía destinos. El recorrido resaltado usa el árbol y el estado recibidos desde la API.

## Estructura y configuración

- `app/tree/decision_tree.py`: nodos conectados por referencias, construcción, búsqueda, recorrido preorder, evaluación y validación.
- `app/services/`: lectura y validación de escenarios JSON y coordinación de sesiones en memoria.
- `app/api/`: endpoints FastAPI y validación de solicitudes.
- `config/scenarios/`: escenarios y protocolos en JSON.
- `frontend/`: interfaz adaptable con HTML, CSS y JavaScript sin frameworks.
- `tests/`: pruebas automatizadas con `pytest` y `TestClient`.
- `start.bat`: preparación del entorno virtual e inicio local en Windows.

Cada JSON de escenario declara `id`, `title`, `description`, `root_id`, `nodes` y `protocols`. Los nodos de decisión requieren referencias `yes` y `no`; cada terminal requiere un `protocol_id` configurado. Los identificadores deben ser únicos, las referencias válidas, todos los nodos alcanzables y no debe haber ciclos.

Para `n` nodos, construir y validar el árbol cuesta O(n) esperado y O(n) memoria auxiliar. Preorder visita cada nodo una vez en O(n) esperado y O(n) memoria. La búsqueda por índice cuesta O(1) esperado (O(n) en el peor caso teórico de colisiones). Evaluar `h` decisiones cuesta O(h) tiempo y O(1) memoria adicional.

## Aprobación institucional

Antes de usar la herramienta como guía operativa, el personal institucional competente debe revisar y aprobar cada escenario, pregunta, rama y protocolo, además de confirmar que refleje las condiciones de la sede. La configuración de demostración marca los protocolos como no aprobados y la aplicación no los presenta como instrucciones oficiales.
