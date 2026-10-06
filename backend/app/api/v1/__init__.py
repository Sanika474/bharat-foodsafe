from fastapi import APIRouter
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.equipment import router as equipment_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.safety_rules import router as safety_rules_router
from app.api.v1.task_templates import router as task_templates_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.uploads import router as uploads_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(audit_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(equipment_router)
api_v1_router.include_router(incidents_router)
api_v1_router.include_router(safety_rules_router)
api_v1_router.include_router(task_templates_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(uploads_router)



