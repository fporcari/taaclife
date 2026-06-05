from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.foods.router import router as foods_router


def create_app() -> FastAPI:
    app = FastAPI(title="NutriCoach", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(foods_router)
    return app


app = create_app()
