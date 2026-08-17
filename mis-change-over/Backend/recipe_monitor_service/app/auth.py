"""
Extração do JWT do operador a partir do header Authorization.

Não validamos o JWT aqui — quem valida é o Django (na hora do PATCH).
A nossa única responsabilidade é capturar o token e repassar adiante.

Por que não validar localmente? Para evitar acoplamento à chave secreta
do Django (SIMPLE_JWT.SIGNING_KEY) e impedir drift de configuração.
Se o token estiver expirado/inválido, o Django retorna 401 e nós
propagamos para o frontend.

(Em uma fase posterior podemos cachear a validação via JWKS, mas não
é necessário no MVP.)
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status


async def get_operator_jwt(authorization: str | None = Header(default=None)) -> str:
    """
    Dependency do FastAPI: extrai o JWT do header Authorization.

    Usado nas rotas que escrevem (POST /sincronizar).
    Para as rotas só-leitura (GET /snapshot) o JWT é opcional —
    use `get_operator_jwt_optional` lá.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization ausente. Envie 'Bearer <jwt>'.",
        )
    token = _strip_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization malformado.",
        )
    return token


async def get_operator_jwt_optional(
    authorization: str | None = Header(default=None),
) -> str | None:
    if not authorization:
        return None
    return _strip_bearer(authorization) or None


def _strip_bearer(authorization: str) -> str:
    s = authorization.strip()
    if s.lower().startswith("bearer "):
        return s[7:].strip()
    return s
