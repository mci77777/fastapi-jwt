"""GymBro FastAPI 应用入口。"""
from app.core.application import create_app

app = create_app()

__all__ = ["app", "create_app"]