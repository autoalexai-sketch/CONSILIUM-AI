"""
app/middleware/security.py — Security headers middleware.
Подключается в main.py: add_security_headers(app)
"""
from fastapi import FastAPI, Request


# Content-Security-Policy.
#
# NOTE on 'unsafe-inline': frontend/index.html is a single-file SPA -- all
# JS lives in one inline <script> block and all CSS in one inline <style>
# block, with onclick="..." attributes used throughout. A strict CSP without
# 'unsafe-inline' for script-src/style-src would break the app outright, so
# this is NOT a substitute for escaping user-controlled content before
# inserting it into the DOM (see frontend/index.html's escapeHtml() usage in
# renderWiki/renderDecisions/renderPrinciples/renderHistoryItems/
# renderSessionDetail -- that's the actual XSS fix; this header is
# defense-in-depth on top of it).
#
# What this DOES still meaningfully block even with 'unsafe-inline' on
# script-src: connect-src 'self' means an injected/XSS'd script cannot
# fetch() or exfiltrate the JWT token to an attacker-controlled domain --
# only same-origin requests succeed. object-src/frame-ancestors block
# embedding/clickjacking and plugin-based attacks regardless of script-src.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


def add_security_headers(app: FastAPI) -> None:
    """Добавляет security headers ко всем ответам."""

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CSP
        # HSTS только на HTTPS (Render/AWS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
