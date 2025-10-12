"""检查应用路由。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.application import create_app

app = create_app()

print(f"Total app routes: {len(app.routes)}")
print("\nDashboard/Stats routes:")
for route in app.routes:
    if hasattr(route, "path"):
        if "dashboard" in route.path or "stats" in route.path or "logs" in route.path:
            print(f"  - {route.path}")

