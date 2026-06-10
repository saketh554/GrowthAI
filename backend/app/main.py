from fastapi import FastAPI

from backend.app.bootstrap import init_persistence
from backend.app.settings import Settings, ensure_data_dirs


def create_app() -> FastAPI:
    settings = Settings()
    ensure_data_dirs(settings)
    engine, session_factory, retrieval = init_persistence(settings)

    app = FastAPI(title="Northwind Expense Pre-Review API")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.retrieval = retrieval

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "northwind-backend"}

    @app.get("/api/retrieval/test")
    def retrieval_test(query: str, k: int = 5) -> list[dict[str, object]]:
        results = app.state.retrieval.retrieve(query=query, k=k)
        return [result.model_dump() for result in results]

    return app


app = create_app()
