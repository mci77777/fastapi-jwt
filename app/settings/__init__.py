from .config import get_settings

settings = get_settings()
TORTOISE_ORM = getattr(settings, 'TORTOISE_ORM', {})
