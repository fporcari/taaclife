from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.coach.router import router as coach_router
from app.diary.router import router as diary_router
from app.disclaimer import DISCLAIMER_TEXT_IT, DISCLAIMER_VERSION
from app.foods.router import router as foods_router
from app.middleware import MedicalDisclaimerHeaderMiddleware
from app.profile.router import router as profile_router
from app.summary.router import router as summary_router
from app.weights.router import router as weights_router


def create_app() -> FastAPI:
    app = FastAPI(title="NutriCoach", version="0.1.0")
    app.add_middleware(MedicalDisclaimerHeaderMiddleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/disclaimer", tags=["public"])
    def disclaimer() -> dict[str, str]:
        """Disclaimer medico-legale (PROJECT.md §3). Pubblico, no JWT."""
        return {"version": DISCLAIMER_VERSION, "text": DISCLAIMER_TEXT_IT}

    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(foods_router)
    app.include_router(diary_router)
    app.include_router(summary_router)
    app.include_router(weights_router)
    app.include_router(coach_router)
    return app


app = create_app()
