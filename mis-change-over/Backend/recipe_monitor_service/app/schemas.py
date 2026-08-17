"""
Schemas Pydantic compartilhados pelo serviço.

Modelam:
  - O retorno de /api/opc-configs/ do Django (DjangoLinhaConfig)
  - O estado interno (Leitura, HistoricoPonto)
  - As respostas REST/WS para o frontend (SnapshotVariavel, Snapshot, Update)

Mantenha os nomes de campo iguais aos do mock ReceitaMonitorContent.jsx
para minimizar adaptação no frontend.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ╔════════════════════════════════════════════════════════════════════╗
# ║ Django responses                                                   ║
# ╚════════════════════════════════════════════════════════════════════╝

TipoVariavel = Literal["REAL", "DINT", "UDINT", "INT", "UINT", "BOOL", "STRING"]


class DjangoVariavelConfig(BaseModel):
    """Um item de `configuracoes_variaveis` em /api/opc-configs/."""
    variavel_mestra_id: int
    nome_variavel_mestra: str
    tipo_variavel_mestra: TipoVariavel
    unidade_variavel_mestra: Optional[str] = ""
    tolerancia_variavel_mestra: Optional[float] = None
    tag_plc: str


class DjangoEquipamentoConfig(BaseModel):
    nome: str
    tipo_equipamento: Optional[str] = ""
    conexao_opcua_nome: Optional[str] = None
    conexao_opcua_url: Optional[str] = None
    conexao_opcua_caminho_plc: Optional[str] = ""
    configuracoes_variaveis: list[DjangoVariavelConfig] = Field(default_factory=list)


class DjangoLinhaConfig(BaseModel):
    nome: str
    equipamentos: list[DjangoEquipamentoConfig] = Field(default_factory=list)


class DjangoOPCConfigsResponse(BaseModel):
    linhas_configuracoes: list[DjangoLinhaConfig] = Field(default_factory=list)


# ╔════════════════════════════════════════════════════════════════════╗
# ║ Estado interno                                                     ║
# ╚════════════════════════════════════════════════════════════════════╝

StatusClassificacao = Literal["normal", "atencao", "alarme", "semleitura"]


class HistoricoPonto(BaseModel):
    """Um ponto no buffer circular de histórico (para sparkline / tendência)."""
    t: int  # timestamp em ms (igual ao mock JS)
    valor: Optional[int | float | bool | str] = None


class Leitura(BaseModel):
    """Estado atual de uma variável em uma linha."""
    variavel_id: int
    valor: Optional[int | float | bool | str] = None
    timestamp_ms: int
    qualidade: str = "GOOD"  # GOOD / BAD / UNCERTAIN
    status_opc_ok: bool = True


# ╔════════════════════════════════════════════════════════════════════╗
# ║ Respostas para o frontend (formato espelhado do mock JSX)          ║
# ╚════════════════════════════════════════════════════════════════════╝

class SnapshotVariavel(BaseModel):
    """
    Estrutura esperada por ReceitaMonitorContent.jsx (campos do mock):
      id, nome, equip, clp, tipo, unidade, receita, tolerancia, atual,
      historico[], _status, ultimaLeitura
    """
    id: int                                    # variavel_mestra_id
    nome: str                                  # nome_variavel_mestra
    equip: str                                 # nome do equipamento
    clp: str                                   # conexao_opcua_nome
    tipo: TipoVariavel
    unidade: str = ""
    receita: Optional[int | float | bool | str] = None    # vem do frontend (formato escolhido) — pode ser None aqui
    tolerancia: Optional[float] = None
    atual: Optional[int | float | bool | str] = None
    historico: list[HistoricoPonto] = Field(default_factory=list)
    ultima_leitura_ms: Optional[int] = None
    status: StatusClassificacao = "semleitura"
    tag_plc: str


class Snapshot(BaseModel):
    """Resposta do GET /linhas/{nome}/snapshot."""
    linha: str
    opc_online: bool
    ultima_atualizacao_ms: Optional[int] = None
    variaveis: list[SnapshotVariavel]


class Update(BaseModel):
    """Mensagem push enviada pelo WS quando uma variável muda."""
    tipo: Literal["update"] = "update"
    linha: str
    variavel_id: int
    valor: Optional[int | float | bool | str] = None
    timestamp_ms: int
    status: StatusClassificacao = "semleitura"


class StatusOPCMessage(BaseModel):
    """Mensagem push quando a conexão OPC da linha muda de estado."""
    tipo: Literal["opc_status"] = "opc_status"
    linha: str
    online: bool
    timestamp_ms: int


# ╔════════════════════════════════════════════════════════════════════╗
# ║ Sincronismo (POST /linhas/{nome}/sincronizar)                      ║
# ╚════════════════════════════════════════════════════════════════════╝

class SincronizarVariavelItem(BaseModel):
    variavel_id: int
    # Opcional: se o frontend não mandar, o serviço usa o último valor lido do Redis.
    valor: Optional[int | float | bool | str] = None


class SincronizarRequest(BaseModel):
    formato_id: int
    observacao: str = ""
    variaveis: list[SincronizarVariavelItem]


class SincronizarResponse(BaseModel):
    """Repasse fiel da resposta do Django (recipe_monitor_sincronizar)."""
    lote_uuid: str
    formato_id: int
    formato_nome: str
    atualizadas: list[dict]
    ignoradas: list[dict]
    total_atualizadas: int
    total_ignoradas: int
    usuario: str
    data_hora: str
