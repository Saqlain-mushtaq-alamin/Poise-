# Add this line to your existing backend/app/models/__init__.py
# so Alembic autogenerate / metadata creation picks up Phase 10's tables:
from app.models import motivation  # noqa: F401
