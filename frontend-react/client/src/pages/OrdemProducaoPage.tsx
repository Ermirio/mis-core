/**
 * OrdemProducaoPage — Visão operacional das Ordens de Produção
 *
 * Propósito: dashboard de produção centrado em OPs — diferente do
 * ProductionOrdersAdmin (cadastro CRUD), esta página foca na execução:
 * - Status ao vivo (% concluída, TPH necessário)
 * - Filtros rápidos por linha / status
 * - Ação de abrir OP em produção direto
 *
 * ISA-101: cores saturadas apenas em desvio (atrasado, cancelado).
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  PlayCircle, PauseCircle, CheckCircle, XCircle,
  Calendar, Search, RefreshCw, ClipboardList, TrendingUp,
  AlertTriangle
} from "lucide-react";
import { DJANGO_API_URL } from "@/config/api";

// ── Paleta ISA-101 ──────────────────────────────────────────────────────────
const C = {
  bg: "#f4f5f7", bgPanel: "#ffffff", border: "#d7dbe0",
  text: "#2c3138", muted: "#657384", weak: "#9ba3ad",
  accent: "#3f5b7c", ok: "#2d8659", warn: "#c9932d", bad: "#b53a2b",
  okBg: "#e3efe7", warnBg: "#f4e8cf", badBg: "#f4dad6", mutedBg: "#e9ecef",
};

// ── Tipos ───────────────────────────────────────────────────────────────────
interface OP {
  id: number;
  codigo: string;
  linha: number;
  linha_nome: string;
  linha_codigo: string;
  produto: number;
  produto_codigo: string;
  produto_descricao: string;
  meta_total: number;
  formato_gramas: string;
  eficiencia_planejada: number;
  status: "PLANEJADA" | "PRODUZINDO" | "PAUSADA" | "CONCLUIDA" | "CANCELADA";
  data_planejada_inicio: string;
  data_inicio_real: string | null;
  data_fim_real: string | null;
  producao_realizada: string;
  producao_total: string;
  percentual_conclusao: number;
  cuc?: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function toN(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function statusMeta(s: OP["status"]): {
  label: string; color: string; bg: string; Icon: React.ElementType;
} {
  switch (s) {
    case "PRODUZINDO": return { label: "Produzindo", color: C.ok, bg: C.okBg, Icon: PlayCircle };
    case "PLANEJADA":  return { label: "Planejada",  color: C.accent, bg: "#eaf0f7", Icon: Calendar };
    case "PAUSADA":    return { label: "Pausada",    color: C.warn, bg: C.warnBg, Icon: PauseCircle };
    case "CONCLUIDA":  return { label: "Concluída",  color: C.muted, bg: C.mutedBg, Icon: CheckCircle };
    case "CANCELADA":  return { label: "Cancelada",  color: C.bad, bg: C.badBg, Icon: XCircle };
  }
}

// Tempo estimado restante a TPH planejado
function etaHoras(op: OP): string {
  const saldo = op.meta_total - toN(op.producao_total);
  if (saldo <= 0) return "0h";
  const vel = op.eficiencia_planejada > 0 ? op.meta_total * (op.eficiencia_planejada / 100) : op.meta_total;
  const h = saldo / (vel / 8); // estimativa grosseira a 8h/turno
  if (!Number.isFinite(h)) return "—";
  return h > 24 ? `${(h / 24).toFixed(1)}d` : `${h.toFixed(1)}h`;
}

// ── Barra de progresso ───────────────────────────────────────────────────────
const ProgressBar: React.FC<{ pct: number; status: OP["status"] }> = ({ pct, status }) => {
  const color =
    status === "CONCLUIDA" ? C.ok :
    status === "CANCELADA" ? C.bad :
    pct >= 100 ? C.ok : pct >= 75 ? C.accent : pct >= 40 ? C.warn : C.bad;
  const safe = Math.min(100, Math.max(0, pct));
  return (
    <div style={{ background: C.mutedBg, borderRadius: 3, height: 6, width: "100%" }}>
      <div style={{
        height: "100%", borderRadius: 3,
        width: `${safe}%`, background: color,
        transition: "width .4s ease",
      }} />
    </div>
  );
};

// ── Card de uma OP ──────────────────────────────────────────────────────────
const OPCard: React.FC<{ op: OP; onClick: () => void }> = ({ op, onClick }) => {
  const sm = statusMeta(op.status);
  const pct = toN(op.percentual_conclusao);
  const prod = toN(op.producao_total);
  const isAtiva = op.status === "PRODUZINDO";

  return (
    <div
      onClick={onClick}
      style={{
        background: C.bgPanel,
        border: `1px solid ${isAtiva ? C.ok : C.border}`,
        borderLeft: `3px solid ${sm.color}`,
        borderRadius: 6,
        padding: "12px 14px",
        cursor: "pointer",
        transition: "box-shadow .12s, transform .12s",
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 2px 8px rgba(0,0,0,.08)";
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(-1px)";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
        (e.currentTarget as HTMLDivElement).style.transform = "none";
      }}
    >
      {/* Cabeçalho */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div>
          <div style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 13, color: C.text }}>
            {op.codigo}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 1 }}>
            {op.linha_codigo} · {op.linha_nome}
          </div>
        </div>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 10,
          background: sm.bg, color: sm.color,
        }}>
          <sm.Icon size={11} />
          {sm.label}
        </span>
      </div>

      {/* Produto */}
      <div style={{ marginTop: 8, fontSize: 12 }}>
        <span style={{ color: C.muted }}>SKU </span>
        <span style={{ fontWeight: 600, color: C.text }}>{op.produto_codigo}</span>
        {" · "}
        <span style={{ color: C.muted, fontSize: 11 }}>{op.produto_descricao}</span>
      </div>

      {/* Progresso */}
      <div style={{ marginTop: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4, color: C.muted }}>
          <span>{prod.toLocaleString("pt-BR")} un</span>
          <span style={{ fontWeight: 600, color: C.text, fontVariantNumeric: "tabular-nums" }}>
            {pct.toFixed(1)}% / {op.meta_total.toLocaleString("pt-BR")} un
          </span>
        </div>
        <ProgressBar pct={pct} status={op.status} />
      </div>

      {/* Rodapé com datas e ETA */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: C.weak }}>
        <span>Início: {fmtDate(op.data_inicio_real || op.data_planejada_inicio)}</span>
        {op.status === "PRODUZINDO" && (
          <span style={{ color: C.accent, fontWeight: 600 }}>
            ≈ {etaHoras(op)} restantes
          </span>
        )}
        {op.status === "CONCLUIDA" && op.data_fim_real && (
          <span>Fim: {fmtDate(op.data_fim_real)}</span>
        )}
      </div>
    </div>
  );
};

// ── Painel de resumo ─────────────────────────────────────────────────────────
const SummaryCard: React.FC<{ label: string; value: string | number; color?: string; icon?: React.ReactNode }> = ({
  label, value, color = C.text, icon
}) => (
  <div style={{ background: C.bgPanel, border: `1px solid ${C.border}`, borderRadius: 6, padding: "10px 14px" }}>
    <div style={{ fontSize: 10, textTransform: "uppercase", color: C.muted, letterSpacing: "0.05em", display: "flex", alignItems: "center", gap: 4 }}>
      {icon}{label}
    </div>
    <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4, fontVariantNumeric: "tabular-nums" }}>
      {value}
    </div>
  </div>
);

// ── Componente principal ────────────────────────────────────────────────────
const OrdemProducaoPage: React.FC = () => {
  const navigate = useNavigate();
  const [ops, setOps] = useState<OP[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("TODOS");
  const [filterLinha, setFilterLinha] = useState<string>("TODAS");
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const load = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${DJANGO_API_URL}/ordens-producao/?limit=500&ordering=-data_planejada_inicio`);
      const data = await resp.json();
      const list: OP[] = data.results || data || [];
      setOps(list);
      setLastRefresh(new Date());
    } catch {
      setOps([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // Polling a cada 30s para OPs em produção
  useEffect(() => {
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, []);

  // Opções de linha disponíveis nos dados
  const linhaOptions = useMemo(() => {
    const map = new Map<string, string>();
    ops.forEach(op => { if (op.linha_codigo) map.set(op.linha_codigo, op.linha_nome); });
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [ops]);

  // Filtros aplicados
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return ops.filter(op => {
      if (filterStatus !== "TODOS" && op.status !== filterStatus) return false;
      if (filterLinha !== "TODAS" && op.linha_codigo !== filterLinha) return false;
      if (q && ![op.codigo, op.produto_codigo, op.produto_descricao, op.linha_nome, op.linha_codigo]
        .some(v => v?.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [ops, search, filterStatus, filterLinha]);

  // KPIs de resumo
  const summary = useMemo(() => {
    const all = filtered;
    return {
      total: all.length,
      emProducao: all.filter(o => o.status === "PRODUZINDO").length,
      planejadas: all.filter(o => o.status === "PLANEJADA").length,
      concluidas: all.filter(o => o.status === "CONCLUIDA").length,
      canceladas: all.filter(o => o.status === "CANCELADA").length,
      avgPct: all.length
        ? (all.reduce((sum, o) => sum + toN(o.percentual_conclusao), 0) / all.length).toFixed(1)
        : "—",
    };
  }, [filtered]);

  const STATUS_TABS = [
    { value: "TODOS", label: "Todas" },
    { value: "PRODUZINDO", label: "Em Produção" },
    { value: "PLANEJADA", label: "Planejadas" },
    { value: "PAUSADA", label: "Pausadas" },
    { value: "CONCLUIDA", label: "Concluídas" },
    { value: "CANCELADA", label: "Canceladas" },
  ];

  return (
    <div style={{ padding: "20px", background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "system-ui,-apple-system,sans-serif", fontSize: 14 }}>
      {/* Cabeçalho */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
            <ClipboardList size={20} color={C.accent} />
            Ordens de Produção
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: C.muted }}>
            Acompanhamento de execução · Atualizado às {lastRefresh.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {/* Busca */}
          <div style={{ position: "relative" }}>
            <Search size={13} style={{ position: "absolute", left: 8, top: "50%", transform: "translateY(-50%)", color: C.weak }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Buscar OP, SKU, linha…"
              style={{
                paddingLeft: 26, paddingRight: 8, paddingTop: 6, paddingBottom: 6,
                border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12,
                background: C.bgPanel, color: C.text, outline: "none", width: 200,
              }}
            />
          </div>
          {/* Filtro linha */}
          <select
            value={filterLinha}
            onChange={e => setFilterLinha(e.target.value)}
            style={{ border: `1px solid ${C.border}`, borderRadius: 6, padding: "6px 8px", fontSize: 12, background: C.bgPanel, color: C.text }}
          >
            <option value="TODAS">Todas as linhas</option>
            {linhaOptions.map(([cod, nome]) => (
              <option key={cod} value={cod}>{cod} — {nome}</option>
            ))}
          </select>
          {/* Refresh */}
          <button
            onClick={load}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 4,
              padding: "6px 12px", border: `1px solid ${C.border}`, borderRadius: 6,
              background: C.bgPanel, color: C.muted, cursor: "pointer", fontSize: 12,
            }}
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            {loading ? "Atualizando…" : "Atualizar"}
          </button>
          {/* Link para admin */}
          <button
            onClick={() => navigate("/admin/ordens")}
            style={{
              padding: "6px 12px", border: `1px solid ${C.accent}`, borderRadius: 6,
              background: C.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 500,
            }}
          >
            + Nova OP
          </button>
        </div>
      </div>
