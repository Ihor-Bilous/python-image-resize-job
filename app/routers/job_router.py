import secrets
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.config import get_settings
from app.dependencies import get_image_service, get_job_store, get_mailer, get_rate_limiter
from app.exceptions import JobError
from app.protocols import ImageServiceProtocol, JobStoreProtocol, MailerProtocol, RateLimiterProtocol
from app.schemas import JobFormSchema
from app.services.image_service import MAX_UPLOAD_BYTES
from app.templates import templates
from app.use_cases.send_download_link import send_download_link

router = APIRouter()

ImageServiceDep = Annotated[ImageServiceProtocol, Depends(get_image_service)]
StoreDep = Annotated[JobStoreProtocol, Depends(get_job_store)]
RateLimiterDep = Annotated[RateLimiterProtocol, Depends(get_rate_limiter)]
MailerDep = Annotated[MailerProtocol, Depends(get_mailer)]


def _field_errors(exc: ValidationError) -> dict[str, str]:
    return {str(err["loc"][0]): err["msg"] for err in exc.errors() if err["loc"]}


def _render_form(
    request: Request,
    values: dict | None = None,
    field_errors: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request,
        "pages/index.html",
        {"values": values or {}, "field_errors": field_errors or {}, "error": error},
        status_code=status_code,
    )


@router.get("/")
def index(request: Request):
    return _render_form(request)


@router.post("/jobs")
async def create_job(
    request: Request,
    background_tasks: BackgroundTasks,
    image_service: ImageServiceDep,
    store: StoreDep,
    rate_limiter: RateLimiterDep,
    mailer: MailerDep,
):
    form = await request.form()
    raw = {"email": form.get("email", ""), "width": form.get("width", "")}
    try:
        data = JobFormSchema.model_validate(raw)
    except ValidationError as e:
        return _render_form(request, raw, _field_errors(e), status_code=422)

    upload = form.get("image")
    if not isinstance(upload, UploadFile) or not upload.filename:
        return _render_form(request, raw, {"image": "Choose a JPEG or PNG file."}, status_code=422)

    try:
        client_id = request.client.host if request.client else "shared-client"
        rate_limiter.check(client_id, data.email)
        contents = await upload.read(MAX_UPLOAD_BYTES + 1)
        resized = await run_in_threadpool(image_service.resize, contents, data.width)
        preview = await run_in_threadpool(image_service.preview, resized.data)
    except JobError as e:
        return _render_form(request, raw, error=str(e), status_code=e.status_code)

    token = secrets.token_urlsafe(32)
    job = store.create(resized, token)
    download_url = f"{get_settings().app_url.rstrip('/')}/images/{token}"
    background_tasks.add_task(
        send_download_link, job.id, data.email, resized, preview, download_url, mailer, store
    )
    return RedirectResponse("/success", status_code=303)


@router.get("/success")
def success(request: Request):
    return templates.TemplateResponse(request, "pages/success.html", {})


@router.get("/images/{token}", include_in_schema=False)
def download_image(token: str, store: StoreDep):
    return Response(
        store.get_image(token),
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="resized.png"'},
    )
