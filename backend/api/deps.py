"""Dependências FastAPI compartilhadas: autenticação por API key e por sessão."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from backend.core import security


def require_api_key(scope: str):
    """Factory de dependency que exige uma API key válida com o escopo dado."""

    async def _dep(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
        info = security.validate_api_key(x_api_key or "", scope)
        if not info:
            raise HTTPException(status_code=401, detail="API key inválida ou sem escopo")
        return info

    return _dep


async def require_session(request: Request) -> dict:
    """Exige cookie de sessão assinado (portais Auditor/Supervisor)."""
    token = request.cookies.get("valbot_session")
    sess = security.verify_session(token)
    if not sess:
        raise HTTPException(status_code=401, detail="sessão ausente ou expirada")
    return sess


def require_role(*roles: str):
    async def _dep(request: Request) -> dict:
        sess = await require_session(request)
        if sess.get("role") not in roles and "admin" not in roles:
            if sess.get("role") != "admin":
                raise HTTPException(status_code=403, detail=f"requer papel: {roles}")
        return sess

    return _dep
