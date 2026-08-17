import React, { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Search, Factory } from "lucide-react";
import { useSystemHealth } from "../../hooks/useSystemHealth";
import { DJANGO_API_URL, FLASK_API_URL } from "@/config/api";
import "./SidebarV2.css";

// ----------------------------------------------------------------------------
// Tipos
// ----------------------------------------------------------------------------
interface Linha {
  id: number | string;
  codigo?: string;
  nome: string;
  ativa?: boolean;
  area?: { id: number | string; nome: string } | string | null;
  area_nome?: string;
}

type LineState = 'ok' | 'warn' | 'bad' | 'off';

// Mock status/OEE per line — shown when Flask /realtime/all is unavailable
const MOCK_LINE_STATES: Record<string, { state: LineState; oee: number | null }> = {
  "ENV-01": { state: 'ok',   oee: 87 },
  "ENV-02": { state: 'warn', oee: 72 },
  "ENV-03": { state: 'bad',  oee: 48 },
  "EMP-01": { state: 'ok',   oee: 91 },
  "EMP-02": { state: 'warn', oee: 68 },
  "EMP-03": { state: 'bad',  oee: 55 },
  "PAL-01": { state: 'ok',   oee: 83 },
  "PAL-02": { state: 'off',  oee: null },
  "ROT-01": { state: 'ok',   oee: 79 },
  "ROT-02": { state: 'bad',  oee: 41 },
};

// Mock lines — active when Django returns empty
const MOCK_LINHAS_SIDEBAR: Linha[] = [
  { id: 1,  codigo: "ENV-01", nome: "Envase 01",        ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 2,  codigo: "ENV-02", nome: "Envase 02",        ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 3,  codigo: "ENV-03", nome: "Envase 03",        ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 4,  codigo: "EMP-01", nome: "Empacotamento 01", ativa: true, area: { id: 2, nome: "Empacotamento" } },
  { id: 5,  codigo: "EMP-02", nome: "Empacotamento 02", ativa: true, area: { id: 2, nome: "Empacotamento" } },
  { id: 6,  codigo: "EMP-03", nome: "Empacotamento 03", ativa: true, area: { id: 2, nome: "Empacotamento" } },
  { id: 7,  codigo: "PAL-01", nome: "Paletização 01",   ativa: true, area: { id: 3, nome: "Paletização" } },
  { id: 8,  codigo: "PAL-02", nome: "Paletização 02",   ativa: true, area: { id: 3, nome: "Paletização" } },
  { id: 9,  codigo: "ROT-01", nome: "Rotulagem 01",     ativa: true, area: { id: 4, nome: "Rotulagem" } },
  { id: 10, codigo: "ROT-02", nome: "Rotulagem 02",     ativa: true, area: { id: 4, nome: "Rotulagem" } },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------
function extractArea(l: Linha): string {
  if (typeof l.area === "string" && l.area) return l.area;
  if (l.area && typeof l.area === "object" && "nome" in l.area) return l.area.nome;
  if (l.area_nome) return l.area_nome;
  return "Outras linhas";
}

const AREA_BUCKETS: { match: RegExp; label: string; emoji: string }[] = [
  { match: /envas/i,      label: "Envase",         emoji: "🧴" },
  { match: /empac|pack/i, label: "Empacotamento",  emoji: "📦" },
  { match: /palet/i,      label: "Paletização",    emoji: "🧱" },
  { match: /rotul/i,      label: "Rotulagem",      emoji: "🏷️" },
  { match: /util|utilid/i,label: "Utilidades",     emoji: "🔧" },
];

function bucketOf(areaName: string): { label: string; emoji: string } {
  for (const b of AREA_BUCKETS) {
    if (b.match.test(areaName)) return { label: b.label, emoji: b.emoji };
  }
  return { label: areaName || "Outras linhas", emoji: "🏭" };
}

function groupLinhas(linhas: Linha[]): Array<{ label: string; emoji: string; items: Linha[] }> {
  const map = new Map<string, { label: string; emoji: string; items: Linha[] }>();
  for (const l of linhas) {
    const { label, emoji } = bucketOf(extractArea(l));
    if (!map.has(label)) map.set(label, { label, emoji, items: [] });
    map.get(label)!.items.push(l);
  }
  return Array.from(map.values())
    .map((g) => ({ ...g, items: g.items.sort((a, b) => (a.codigo || a.nome).localeCompare(b.codigo || b.nome)) }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

/** Derives line state from OEE value (fallback when no real-time data) */
function oeeToState(oee: number | null): LineState {
  if (oee === null) return 'off';
  if (oee >= 80) return 'ok';
  if (oee >= 65) return 'warn';
  return 'bad';
}

/** Returns CSS modifier for dot/badge based on state */
function stateMod(state: LineState): string {
  return `--${state}`;
}

// ----------------------------------------------------------------------------
// Sub-componentes visuais
// ----------------------------------------------------------------------------
const StatusDot: React.FC<{ state: LineState }> = ({ state }) => (
  <span className={`sbv2__dot sbv2__dot${stateMod(state)}`} title={state} />
);

const OeeBadge: React.FC<{ oee: number | null; state: LineState }> = ({ oee, state }) => {
  if (state === 'off') return <span className="sbv2__oee">OFF</span>;
  if (oee === null) return null;
  return (
    <span className={`sbv2__oee sbv2__oee${stateMod(state)}`}>
      {oee}
    </span>
  );
};

// ----------------------------------------------------------------------------
// Componente principal
// ----------------------------------------------------------------------------
const SidebarV2: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  // lineStates: maps codigo → { state, oee }. Starts with mock, gets overwritten by real data.
  const [lineStates, setLineStates] = useState<Record<string, { state: LineState; oee: number | null }>>(MOCK_LINE_STATES);
  const searchRef = useRef<HTMLInputElement>(null);
  const { health } = useSystemHealth();

  // ---- fetch linhas from Django ----
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const resp = await fetch(`${DJANGO_API_URL}/linhas/`);
        const data = await resp.json();
        const list: Linha[] = data.results || data || [];
        if (alive) setLinhas(list.length > 0 ? list : MOCK_LINHAS_SIDEBAR);
      } catch {
        if (alive) setLinhas(MOCK_LINHAS_SIDEBAR);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  // ---- fetch real-time OEE from Flask (best-effort) ----
  useEffect(() => {
    if (collapsed) return;
    let alive = true;
    const load = async () => {
      try {
        const resp = await fetch(`${FLASK_API_URL}/realtime/all`);
        if (!resp.ok) return;
        const data: Record<string, any> = await resp.json();
        const next: Record<string, { state: LineState; oee: number | null }> = {};
        Object.entries(data).forEach(([code, eq]: [string, any]) => {
          const oee = typeof eq?.medicoes?.oee === 'number' ? Math.round(eq.medicoes.oee * 100) : null;
          next[code] = { oee, state: oeeToState(oee) };
        });
        if (alive && Object.keys(next).length > 0) setLineStates(next);
      } catch {
        // keep mock states
      }
    };
    load();
    const iv = setInterval(load, 15000);
    return () => { alive = false; clearInterval(iv); };
  }, [collapsed]);

  // ---- "/" shortcut for search ----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA";
      if (e.key === "/" && !typing && !collapsed) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [collapsed]);

  // ---- filter + group ----
  const grupos = useMemo(() => {
    const q = query.trim().toLowerCase();
    const active = linhas.filter((l) => l.ativa !== false);
    const filtered = q
      ? active.filter(
          (l) =>
            (l.codigo || "").toLowerCase().includes(q) ||
            (l.nome || "").toLowerCase().includes(q) ||
            extractArea(l).toLowerCase().includes(q),
        )
      : active;
    return groupLinhas(filtered);
  }, [linhas, query]);

  const totalLinhas = linhas.filter((l) => l.ativa !== false).length;
  const linhasVisiveis = grupos.reduce((n, g) => n + g.items.length, 0);

  return (
    <aside className={`sbv2 ${collapsed ? "sbv2--collapsed" : ""}`} aria-label="Menu principal">

      {/* ---- Header ---- */}
      <header className="sbv2__header">
        <button
          type="button"
          className="sbv2__toggle"
          onClick={onToggle}
          title={collapsed ? "Expandir menu" : "Recolher menu"}
          aria-expanded={!collapsed}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        {!collapsed && (
          <Link to="/" className="sbv2__brand" title="Home">
            <img
              src={`${import.meta.env.BASE_URL}mis-core-logo-v2.png`}
              alt="MIS-CORE"
              className="sbv2__logo"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <span className="sbv2__brand-sub">Monitoramento Industrial</span>
          </Link>
        )}
      </header>

      {/* ---- Navegação principal ---- */}
      <nav className="sbv2__primary" aria-label="Navegação">
        <SideLink to="/"              icon="🏠" label="Home"           collapsed={collapsed} end />
        <SideLink to="/factory-panel" icon="🏢" label="Gestão Fabril"  collapsed={collapsed} />
        <SideLink to="/analytics"     icon="📊" label="Analytics"      collapsed={collapsed} />
        <SideLink to="/descartes"     icon="🗑️" label="Descartes"      collapsed={collapsed} />
        <SideLink to="/giveaway"      icon="⚖️" label="Give Away"      collapsed={collapsed} />
      </nav>

      {/* ---- Linhas de produção (scrollável) ---- */}
      <section className="sbv2__lines" aria-label="Linhas de produção">
        {!collapsed && (
          <>
            <p className="sbv2__section-title">
              <Factory size={11} />
              Fábrica — Unidade Norte
            </p>
            <div className="sbv2__lines-header">
              <span style={{ fontSize: 11, color: 'var(--sb-fg-muted)' }}>Linhas ativas</span>
              <span className="sbv2__badge" title="visíveis / total">
                {linhasVisiveis}/{totalLinhas}
              </span>
            </div>
            <div className="sbv2__search">
              <Search size={13} aria-hidden="true" />
              <input
                ref={searchRef}
                type="search"
                placeholder="Buscar… (tecla /)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Buscar linha"
              />
            </div>
          </>
        )}

        <div className="sbv2__scroll">
          {loading && !collapsed && <p className="sbv2__hint">Carregando…</p>}
          {!loading && grupos.length === 0 && !collapsed && (
            <p className="sbv2__hint">Nenhuma linha encontrada.</p>
          )}

          {grupos.map((g) => (
            <details
              key={g.label}
              className="sbv2__group"
              open={!!query || g.items.length <= 6}
            >
              <summary className="sbv2__group-summary" title={`${g.label} (${g.items.length})`}>
                <span className="sbv2__group-chev">▸</span>
                <span className="sbv2__group-emoji" aria-hidden="true">{g.emoji}</span>
                {!collapsed && (
                  <>
                    <span className="sbv2__group-label">{g.label}</span>
                    <span className="sbv2__group-count">{g.items.length}</span>
                  </>
                )}
              </summary>

              <ul className="sbv2__group-list">
                {g.items.map((linha) => {
                  const code = linha.codigo || String(linha.id);
                  const ls = lineStates[code] ?? { state: 'off' as LineState, oee: null };
                  return (
                    <li key={linha.id}>
                      <NavLink
                        to={`/linha/${code}/detalhes`}
                        className={({ isActive }) =>
                          `sbv2__line ${isActive ? "sbv2__line--active" : ""}`
                        }
                        title={`${linha.nome} — OEE ${ls.oee ?? 'OFF'}`}
                      >
                        <StatusDot state={ls.state} />
                        {!collapsed && (
                          <>
                            <span className="sbv2__line-code">{code}</span>
                            <span className="sbv2__line-name">{linha.nome}</span>
                            <OeeBadge oee={ls.oee} state={ls.state} />
                          </>
                        )}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </details>
          ))}
        </div>
      </section>

      {/* ---- Ferramentas externas ---- */}
      <nav className="sbv2__tools" aria-label="Ferramentas">
        {!collapsed && <p className="sbv2__section-title">Ferramentas</p>}
        <ExternalLink href="/grafana/"    icon="📈" label="Grafana"    collapsed={collapsed} />
        <ExternalLink href="/chronograf/" icon="⏱️" label="Chronograf" collapsed={collapsed} />
        <ExternalLink href="/nodered/"    icon="🔌" label="Node-RED"   collapsed={collapsed} />
      </nav>

      {/* ---- Footer ---- */}
      <footer className="sbv2__footer">
        <SideLink to="/admin"       icon="⚙️" label="Configurações" collapsed={collapsed} />
        <NavLink
          to="/diagnosticos"
          className={({ isActive }) =>
            `sbv2__link ${isActive ? "sbv2__link--active" : ""} ${
              health === "critical" ? "sbv2__link--critical" : health === "warning" ? "sbv2__link--warn" : ""
            }`
          }
          title={health === "critical" ? "Erro no Sistema" : health === "warning" ? "Alertas Ativos" : "Diagnósticos"}
        >
          <span aria-hidden="true">
            {health === "critical" ? "🚨" : health === "warning" ? "⚠️" : "🔧"}
          </span>
          {!collapsed && <span>Diagnósticos</span>}
        </NavLink>

        {!collapsed && (
          <div className="sbv2__health-row">
            <span className="sbv2__health-dot">
              <span className={`sbv2__dot sbv2__dot--${health === 'ok' ? 'ok' : health === 'warning' ? 'warn' : 'bad'}`} />
              {health === 'ok' ? 'Sistema OK' : health === 'warning' ? 'Alertas ativos' : 'Erro no sistema'}
            </span>
            <span style={{ fontSize: 10, color: 'var(--sb-fg-weak)' }}>v2.0</span>
          </div>
        )}
      </footer>
    </aside>
  );
};

// ----------------------------------------------------------------------------
// Sub-componentes de navegação
// ----------------------------------------------------------------------------
const SideLink: React.FC<{
  to: string;
  icon: string;
  label: string;
  collapsed: boolean;
  end?: boolean;
}> = ({ to, icon, label, collapsed, end }) => (
  <NavLink
    to={to}
    end={end}
    className={({ isActive }) => `sbv2__link ${isActive ? "sbv2__link--active" : ""}`}
    title={label}
  >
    <span aria-hidden="true">{icon}</span>
    {!collapsed && <span>{label}</span>}
  </NavLink>
);

const ExternalLink: React.FC<{
  href: string;
  icon: string;
  label: string;
  collapsed: boolean;
}> = ({ href, icon, label, collapsed }) => (
  <a
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    className="sbv2__link"
    title={label}
  >
    <span aria-hidden="true">{icon}</span>
    {!collapsed && <span>{label}</span>}
  </a>
);

export default SidebarV2;
