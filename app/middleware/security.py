"""
app/middleware/security.py — Security headers middleware.
Подключается в main.py: add_security_headers(app)
"""
from fastapi import FastAPI, Request


def add_security_headers(app: FastAPI) -> None:
    """Добавляет security headers ко всем ответам."""

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS только на HTTPS (Render/AWS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
