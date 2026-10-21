from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import JobError
from app.routers.admin_router import router as admin_router
from app.routers.job_router import router as job_router

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def create_app() -> FastAPI:
    app = FastAPI(title="Image Resize Job")

    @app.exception_handler(JobError)
    async def job_error_handler(request: Request, exc: JobError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(_SECURITY_HEADERS)
        return response

    app.include_router(job_router)
    app.include_router(admin_router)
    return app
