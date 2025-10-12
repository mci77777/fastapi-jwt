"""检查路由注册情况。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api.v1 import v1_router

print(f"Total routes in v1_router: {len(v1_router.routes)}")
print("\nDashboard/Stats/Logs routes:")
for route in v1_router.routes:
    if "dashboard" in route.path or "stats" in route.path or "logs" in route.path:
        methods = getattr(route, "methods", ["WebSocket"])
        print(f"  - {route.path} ({methods})")

print("\nAll routes:")
for route in v1_router.routes:
    print(f"  - {route.path}")

