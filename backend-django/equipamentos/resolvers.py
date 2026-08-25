"""
Resolver central de Equipamento — Solução 2 (identidade ISA-95).

Por que existe
--------------
Depois que PR 3 removeu a unicidade global de `Equipamento.codigo` (agora
único só dentro da Linha), endpoints que recebiam "equipamento_codigo"
podiam encontrar N equipamentos com o mesmo código em linhas diferentes.

Este módulo centraliza a resolução para que TODOS os endpoints usem a
mesma lógica + mesmas mensagens de erro.

Ordem de prioridade (de mais explícito para menos):
  1. `equipamento_id`  (PK Django)              — sempre exato
  2. `uuid`            (UUIDv4 imutável)         — exato, ideal pra integrações
  3. `slug`            ("L01.E001")              — exato, ideal pra coletor/APIs
  4. (`codigo`, `linha_codigo`)                  — desambiguação humana
  5. `codigo` sozinho                            — só se único globalmente

Casos de erro:
  - `Equipamento.DoesNotExist`  → 404
  - `EquipamentoAmbiguo`        → 409 com lista de opções
"""
from __future__ import annotations

import logging
import uuid as _uuid_module
from typing import Iterable, Optional

from django.core.exceptions import ObjectDoesNotExist

from .models import Equipamento

logger = logging.getLogger(__name__)


class EquipamentoAmbiguo(Exception):
    """Código existe em múltiplas linhas e a chamada não desambiguou.

    Carrega `opcoes` para o endpoint devolver ao cliente uma lista
    de candidatos — permitindo que o coletor (ou um admin) saiba
    exatamente quais escolhas existem.
    """
    def __init__(self, codigo: str, opcoes: list[dict]):
        self.codigo = codigo
        self.opcoes = opcoes
        descricao = ', '.join(f"{o['linha_codigo']}.{o['codigo']}" for o in opcoes)
        super().__init__(
            f"Código '{codigo}' existe em {len(opcoes)} linhas: {descricao}. "
            f"Use `equipamento_slug`, `equipamento_id` ou `linha_codigo` para desambiguar."
        )


class EquipamentoIdentityConflict(ValueError):
    """O payload trouxe identificadores que apontam para equipamentos distintos."""

    def __init__(self, *, slug: str, codigo: str, linha_codigo: str):
        super().__init__(
            "Identidade de equipamento inconsistente: "
            f"slug={slug!r} não corresponde a {linha_codigo}.{codigo}."
        )
        self.slug = slug
        self.codigo = codigo
        self.linha_codigo = linha_codigo


def _parse_uuid(value: object) -> Optional[_uuid_module.UUID]:
    if value is None:
        return None
    if isinstance(value, _uuid_module.UUID):
        return value
    try:
        return _uuid_module.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def resolver_equipamento(
    *,
    equipamento_id: Optional[int | str] = None,
    uuid: Optional[str | _uuid_module.UUID] = None,
    slug: Optional[str] = None,
    codigo: Optional[str] = None,
    linha_codigo: Optional[str] = None,
    queryset: Optional[Iterable[Equipamento]] = None,
) -> Equipamento:
    """Resolve um Equipamento a partir de identificadores opcionais.

    Args:
        equipamento_id: PK Django (mais barato e exato).
        uuid: UUIDv4 imutável (ideal pra integrações externas).
        slug: identificador legível "L01.E001" (preferido em APIs).
        codigo: código curto ("E001") — exige `linha_codigo` se duplicado.
        linha_codigo: desambigua quando `codigo` aparece em várias linhas.
        queryset: opcional — base de busca (default: Equipamento.objects.all()).

    Returns:
        O `Equipamento` resolvido.

    Raises:
        Equipamento.DoesNotExist: nenhuma combinação retornou registro.
        EquipamentoAmbiguo: `codigo` resolveu para >1 equipamento sem `linha_codigo`.
        ValueError: chamada sem nenhum identificador.
    """
    qs = queryset if queryset is not None else Equipamento.objects.all()

    # 1. PK — caminho rápido, ignora outras chaves
    if equipamento_id is not None:
        try:
            return qs.get(pk=int(equipamento_id))
        except (ValueError, TypeError):
            raise Equipamento.DoesNotExist(f"equipamento_id inválido: {equipamento_id!r}")

    # 2. UUID — caminho de integrações externas
    parsed_uuid = _parse_uuid(uuid)
    if parsed_uuid is not None:
        return qs.get(uuid=parsed_uuid)

    # 3. Slug — caminho preferencial para coletor/APIs novas
    if slug:
        return qs.get(slug=slug)

    # 4-5. Código com ou sem linha
    if not codigo:
        raise ValueError(
            "resolver_equipamento: forneça `equipamento_id`, `uuid`, `slug` ou `codigo`."
        )

    candidatos = qs.filter(codigo=codigo).select_related('linha')
    if linha_codigo:
        candidatos = candidatos.filter(linha__codigo=linha_codigo)

    candidatos_list = list(candidatos[:5])  # cap defensivo
    n = len(candidatos_list)
    if n == 0:
        raise Equipamento.DoesNotExist(
            f"Equipamento '{codigo}' não encontrado"
            + (f" na linha '{linha_codigo}'" if linha_codigo else '')
            + '.'
        )
    if n == 1:
        return candidatos_list[0]

    # >1 candidato — devolve as opções para o cliente desambiguar
    opcoes = [
        {
            'id': eq.id,
            'slug': eq.slug,
            'codigo': eq.codigo,
            'linha_codigo': eq.linha.codigo if eq.linha else None,
            'linha_nome': eq.linha.nome if eq.linha else None,
            'nome': eq.nome,
        }
        for eq in candidatos_list
    ]
    raise EquipamentoAmbiguo(codigo, opcoes)


def resolver_de_payload(payload: dict) -> Equipamento:
    """Helper para uso direto em endpoints DRF — extrai os identificadores
    aceitos do payload e chama `resolver_equipamento`.

    Aceita estas chaves no payload (em qualquer combinação):
      equipamento_id, equipamento_uuid, equipamento_slug,
      equipamento_codigo, linha_codigo.
    """
    slug = payload.get('equipamento_slug') or payload.get('slug')
    codigo = payload.get('equipamento_codigo') or payload.get('codigo')
    linha_codigo = payload.get('linha_codigo')

    # Nunca deixe a prioridade do slug esconder um conflito de identidade.
    # O coletor envia slug + código + linha; os três precisam apontar para a
    # mesma PK antes de qualquer escrita no InfluxDB.
    if slug and codigo and linha_codigo:
        por_slug = resolver_equipamento(slug=slug)
        por_codigo_linha = resolver_equipamento(
            codigo=codigo,
            linha_codigo=linha_codigo,
        )
        if por_slug.pk != por_codigo_linha.pk:
            raise EquipamentoIdentityConflict(
                slug=slug,
                codigo=codigo,
                linha_codigo=linha_codigo,
            )
        return por_slug

    return resolver_equipamento(
        equipamento_id=payload.get('equipamento_id'),
        uuid=payload.get('equipamento_uuid') or payload.get('uuid'),
        slug=slug,
        codigo=codigo,
        linha_codigo=linha_codigo,
    )
