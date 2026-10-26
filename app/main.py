"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.services.decision_service import DecisionService, ScenarioService

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(scenario_directory: Path | None = None) -> FastAPI:
    scenarios = ScenarioService.from_directory(scenario_directory or BASE_DIR / "config" / "scenarios")
    application = FastAPI(title="EduSafe API", version="1.0.0",
                          description="API de demostración para árboles de decisión EduSafe.")
    application.state.decision_service = DecisionService(scenarios)
    application.add_middleware(CORSMiddleware,
        allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
        allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    application.include_router(router)
    # Serve the plain HTML/CSS/JavaScript client from the same local origin as the API.
    application.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
    return application


app = create_app()
