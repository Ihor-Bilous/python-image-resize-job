from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_job_store, require_admin
from app.protocols import JobStoreProtocol
from app.templates import templates

router = APIRouter(dependencies=[Depends(require_admin)])

StoreDep = Annotated[JobStoreProtocol, Depends(get_job_store)]


@router.get("/admin")
def admin(request: Request, store: StoreDep):
    return templates.TemplateResponse(request, "pages/admin.html", {"jobs": store.list_recent()})
