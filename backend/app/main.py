from fastapi import FastAPI

from backend.app.settings import Settings, ensure_data_dirs


def create_app() -> FastAPI:
    settings = Settings()
    ensure_data_dirs(settings)

    app = FastAPI(title="Northwind Expense Pre-Review API")
    app.state.settings = settings

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "northwind-backend"}

    return app


app = create_app()
