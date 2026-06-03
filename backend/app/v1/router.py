from fastapi import APIRouter

from app.v1.routes.health import router as health_router
from app.v1.routes.massing_options import router as massing_options_router
from app.v1.routes.polygons import router as polygons_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(polygons_router)
router.include_router(massing_options_router)
