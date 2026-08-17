"""
Cliente HTTP assíncrono para o Django (mis-change-over).

Apenas dois "modos" de chamada:
  1. **Service-level reads** — leitura de configuração OPC e listas
     (linhas, formatos). Não exigem JWT do operador, mas vamos sempre
     repassar o JWT do request original se disponível (audit trail).
  2. **User-level writes** — sincronismo de receita. SEMPRE repassa o JWT
     do operador para o Django validar grupo (PodeSincronizarReceita).

Erros do Django são propagados como `DjangoAPIError` — quem chama decide
se retorna 502, 401, etc.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from .config import get_settings
from .schemas import DjangoOPCConfigsResponse, SincronizarResponse

logger = logging.getLogger(__name__)


class DjangoAPIError(Exception):
    """Erro genérico ao falar com o Django."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class DjangoClient:
    """
    Cliente reutilizável. Mantém um httpx.AsyncClient com pool de conexões.
    Instância única por processo (ver `get_django_client` em main.py).
    """

    def __init__(self, base_url: str, timeout_s: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_s,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── Helpers internos ──────────────────────────────────────────────

    def _auth_headers(self, jwt: Optional[str]) -> dict[str, str]:
        if not jwt:
            return {}
        # Aceita tanto "Bearer xxx" quanto só "xxx"
        token = jwt[7:] if jwt.lower().startswith("bearer ") else jwt
        return {"Authorization": f"Bearer {token}"}

    async def _get_json(self, path: str, jwt: Optional[str] = None) -> Any:
        try:
            resp = await self._client.get(path, headers=self._auth_headers(jwt))
        except httpx.RequestError as e:
            raise DjangoAPIError(f"Falha de rede ao chamar Django: {e}") from e

        if resp.status_code >= 400:
            raise DjangoAPIError(
                f"Django retornou {resp.status_code} em GET {path}",
                status_code=resp.status_code,
                body=_safe_json(resp),
            )
        return resp.json()

    async def _patch_json(self, path: str, *, json: dict, jwt: str) -> Any:
        try:
            resp = await self._client.patch(
                path, json=json, headers=self._auth_headers(jwt)
            )
        except httpx.RequestError as e:
            raise DjangoAPIError(f"Falha de rede ao chamar Django: {e}") from e

        if resp.status_code >= 400:
            raise DjangoAPIError(
                f"Django retornou {resp.status_code} em PATCH {path}",
                status_code=resp.status_code,
                body=_safe_json(resp),
            )
        return resp.json()

    # ── Endpoints consumidos ──────────────────────────────────────────

    async def get_opc_configs(self, jwt: Optional[str] = None) -> DjangoOPCConfigsResponse:
        """
        GET /api/opc-configs/
        Retorna todas linhas ativas com seus equipamentos e tags configuradas.
        """
        data = await self._get_json("/api/opc-configs/", jwt=jwt)
        return DjangoOPCConfigsResponse.model_validate(data)

    async def get_linhas_disponiveis(self, jwt: Optional[str] = None) -> dict[str, Any]:
        """GET /api/linhas-disponiveis/ — usado para validar nome de linha."""
        return await self._get_json("/api/linhas-disponiveis/", jwt=jwt)

    async def patch_sincronizar(
        self,
        *,
        formato_id: int,
        linha_nome: str,
        observacao: str,
        variaveis: list[dict],
        jwt: str,
    ) -> SincronizarResponse:
        """
        PATCH /api/recipe-monitor/formato/<formato_id>/sincronizar/

        Body:
            {
                "linha_nome": "L21",
                "observacao": "...",
                "variaveis": [{"variavel_id": 12, "valor": "1.004"}, ...]
            }
        """
        path = f"/api/recipe-monitor/formato/{formato_id}/sincronizar/"
        payload = {
            "linha_nome": linha_nome,
            "observacao": observacao,
            "variaveis": variaveis,
        }
        data = await self._patch_json(path, json=payload, jwt=jwt)
        return SincronizarResponse.model_validate(data)


# ── Singleton helpers ─────────────────────────────────────────────────

_client: DjangoClient | None = None


def get_django_client() -> DjangoClient:
    """Acessor singleton — inicializado em app startup."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = DjangoClient(base_url=settings.django_base_url_clean)
    return _client


async def close_django_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text[:500]
