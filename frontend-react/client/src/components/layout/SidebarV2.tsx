import React, { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Search, Factory, Container } from "lucide-react";
import { useSystemHealth } from "../../hooks/useSystemHealth";
import { DJANGO_API_URL, FLASK_API_URL, FASTAPI_V2_URL } from "@/config/api";
import { normalizeState } from "@/utils/equipmentStateUtils";
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
  // Campos hierarquicos novos (PR 13): vindos do LinhaProducaoSerializer
  // permitem agrupar por fabrica e localizacao sem recorrer a regex.
  localizacao?: string | null;
  fabrica_id?: number | null;
  fabrica_codigo?: string | null;
  fabrica_nome?: string | null;
  equipamentos?: Array<{
    id: number | string;
    codigo?: string;
    nome?: string;
    status?: string;
  }>;
}

type LineState = 'ok' | 'warn' | 'bad' | 'off';
type RealtimeEquipment = {
  medicoes?: Record<string, unknown>;
  linha?: string | number | null;
  linha_codigo?: string | null;
  linha_id?: string | number | null;
};

type CurrentUser = {
  username: string;
  is_admin: boolean;
  is_staff: boolean;
  is_superuser: boolean;
};

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

// PR 13: agrupamento por Fabrica -> Localizacao -> Linha. Substitui buckets
// por regex que ignoravam a hierarquia real de cadastro (item 16 do plano).
interface LocalizacaoGroup {
  nome: string;
  linhas: Linha[];
}
interface FabricaGroup {
  fabrica_codigo: string;
  fabrica_nome: string;
  localizacoes: LocalizacaoGroup[];
}

function groupByFabricaLocalizacao(linhas: Linha[]): FabricaGroup[] {
  const fabricas = new Map<string, { codigo: string; nome: string; locs: Map<string, Linha[]> }>();
  for (const l of linhas) {
    const fabCodigo = (l.fabrica_codigo || '').trim() || 'SEM-FABRICA';
    const fabNome = (l.fabrica_nome || '').trim() || 'Sem fábrica';
    const loc = (l.localizacao || '').trim() || 'Sem localização';
    if (!fabricas.has(fabCodigo)) {
      fabricas.set(fabCodigo, { codigo: fabCodigo, nome: fabNome, locs: new Map() });
    }
    const fab = fabricas.get(fabCodigo)!;
    if (!fab.locs.has(loc)) fab.locs.set(loc, []);
    fab.locs.get(loc)!.push(l);
  }
  return Array.from(fabricas.values())
    .sort((a, b) => a.codigo.localeCompare(b.codigo))
    .map(fab => ({
      fabrica_codigo: fab.codigo,
      fabrica_nome: fab.nome,
      localizacoes: Array.from(fab.locs.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([nome, linhasLoc]) => ({
          nome,
          linhas: linhasLoc.sort((a, b) =>
            (a.codigo || a.nome).localeCompare(b.codigo || b.nome)
          ),
        })),
    }));
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

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function normalizeOee(value: unknown): number | null {
  const n = toNumber(value);
  if (n === null) return null;
  return Math.round(n <= 1 ? n * 100 : n);
}

function stateFromEquipment(eq: RealtimeEquipment): LineState | null {
  const medicoes = eq.medicoes || {};
  const rawState = medicoes.estado_maquina ?? medicoes.estado ?? medicoes.status ?? eq.medicoes?.state;
  if (rawState === null || rawState === undefined || rawState === "") return null;

  const normalized = normalizeState(rawState as string | number);
  if (normalized === "PRODUZINDO" || normalized === "PARTINDO") return "ok";
  if (normalized === "PARADO" || normalized === "MANUTENCAO" || normalized === "OFFLINE") return normalized === "OFFLINE" ? "off" : "bad";
  if (normalized === "DEFAULT") return null;
  return "warn";
}

function stateFromLineStatus(status: unknown): LineState | null {
  const text = String(status || "").toUpperCase();
  if (!text) return null;
  if (text.includes("OFFLINE") || text.includes("SEM COMUNICA")) return "off";
  if (text.includes("FALHA") || text.includes("QUEBRA") || text.includes("MANUTEN")) return "bad";
  if (text.includes("SETUP") || text.includes("AGUARD") || text.includes("BLOQUE")) return "warn";
  if (text.includes("PRODUZ") || text.includes("RUN")) return "ok";
  if (text.includes("PARAD")) return "bad";
  return null;
}

function aggregateLineStates(
  linhas: Linha[],
  realtime: Record<string, RealtimeEquipment>,
): Record<string, { state: LineState; oee: number | null }> {
  const equipmentToLine = new Map<string, string>();

  for (const linha of linhas) {
    const lineKey = linha.codigo || String(linha.id);
    for (const eq of linha.equipamentos || []) {
      if (eq.codigo) equipmentToLine.set(eq.codigo, lineKey);
    }
  }

  const buckets = new Map<string, Array<{ state: LineState | null; oee: number | null }>>();

  Object.entries(realtime).forEach(([equipmentCode, eq]) => {
    const explicitLine = eq.linha_codigo || eq.linha || eq.linha_id;
    const lineKey = equipmentToLine.get(equipmentCode) || (explicitLine !== null && explicitLine !== undefined ? String(explicitLine) : null);
    if (!lineKey) return;

    const medicoes = eq.medicoes || {};
    const oee = normalizeOee(medicoes.oee ?? medicoes.oee_realtime);
    const state = stateFromEquipment(eq) ?? oeeToState(oee);

    if (!buckets.has(lineKey)) buckets.set(lineKey, []);
    buckets.get(lineKey)!.push({ state, oee });
  });

  const result: Record<string, { state: LineState; oee: number | null }> = {};

  buckets.forEach((items, lineKey) => {
    const oeEs = items.map(item => item.oee).filter((oee): oee is number => oee !== null);
    const oee = oeEs.length ? Math.round(oeEs.reduce((sum, value) => sum + value, 0) / oeEs.length) : null;
    const states = items.map(item => item.state).filter((state): state is LineState => state !== null);

    let state: LineState = "off";
    if (states.includes("bad")) state = "bad";
    else if (states.includes("ok")) state = "ok";
    else if (states.includes("warn")) state = "warn";
    else if (oee !== null) state = oeeToState(oee);

    result[lineKey] = { state, oee };
  });

  return result;
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
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  // lineStates: maps codigo → { state, oee }. Starts with mock, gets overwritten by real data.
  // IMPORTANTE: NAO inicializar com MOCK_LINE_STATES — quando o backend nao
  // retorna nada, queremos refletir isso na UI (sem dados ficticios).
  const [lineStates, setLineStates] = useState<Record<string, { state: LineState; oee: number | null }>>({});
  const searchRef = useRef<HTMLInputElement>(null);
  const { health } = useSystemHealth();

  useEffect(() => {
    let alive = true;
    fetch(`${DJANGO_API_URL}/auth/me/`, { credentials: 'include' })
      .then(response => response.ok ? response.json() : null)
      .then(data => { if (alive) setCurrentUser(data); })
      .catch(() => { if (alive) setCurrentUser(null); });
    return () => { alive = false; };
  }, []);

  // ---- fetch linhas from Django ----
  // Sem fallback para MOCK: se a API responde vazio (modo producao limpo) a
  // sidebar fica vazia mesmo. Mocks so iriam confundir o usuario em demos
  // de conectividade real.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const resp = await fetch(`${DJANGO_API_URL}/linhas/`);
        const data = await resp.json();
        const list: Linha[] = data.results || data || [];
        if (alive) setLinhas(list);
      } catch {
        if (alive) setLinhas([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  // ---- fetch real-time line state/OLE. FastAPI is the canonical source; Flask is fallback. ----
  useEffect(() => {
    if (collapsed || linhas.length === 0) return;
    let alive = true;
    const load = async () => {
      let fallback: Record<string, { state: LineState; oee: number | null }> = {};
      try {
        // Flask-out completo: /realtime/all migrado para Django.
        const resp = await fetch(`${DJANGO_API_URL}/realtime/all`);
        if (resp.ok) {
          const data: Record<string, RealtimeEquipment> = await resp.json();
          fallback = aggregateLineStates(linhas, data);
        }
      } catch {
        // keep mock states
      }

      const next: Record<string, { state: LineState; oee: number | null }> = { ...fallback };
      await Promise.all(
        linhas
          .filter((linha) => linha.ativa !== false)
          .map(async (linha) => {
            const code = linha.codigo || String(linha.id);
            try {
              const [statusResp, oleResp] = await Promise.all([
                fetch(`${FASTAPI_V2_URL}/linha/${encodeURIComponent(code)}/overview-status`),
                fetch(`${FASTAPI_V2_URL}/linha/${encodeURIComponent(code)}/ole-realtime`),
              ]);
              const statusData = statusResp.ok ? await statusResp.json() : null;
              const oleData = oleResp.ok ? await oleResp.json() : null;
              const canonicalState = stateFromLineStatus(statusData?.status);
              const canonicalOle = normalizeOee(oleData?.ole);
              next[code] = {
                state: canonicalState ?? next[code]?.state ?? oeeToState(canonicalOle),
                oee: canonicalOle ?? next[code]?.oee ?? null,
              };
            } catch {
              // keep fallback for this line
            }
          })
      );

      if (alive && Object.keys(next).length > 0) setLineStates(next);
    };
    load();
    const iv = setInterval(load, 15000);
    return () => { alive = false; clearInterval(iv); };
  }, [collapsed, linhas]);

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

  // ---- filter + group por Fabrica -> Localizacao ----
  const grupos = useMemo(() => {
    const q = query.trim().toLowerCase();
    const active = linhas.filter((l) => l.ativa !== false);
    const filtered = q
      ? active.filter(
          (l) =>
            (l.codigo || "").toLowerCase().includes(q) ||
            (l.nome || "").toLowerCase().includes(q) ||
            (l.localizacao || "").toLowerCase().includes(q) ||
            (l.fabrica_nome || "").toLowerCase().includes(q) ||
            (l.fabrica_codigo || "").toLowerCase().includes(q) ||
            extractArea(l).toLowerCase().includes(q),
        )
      : active;
    return groupByFabricaLocalizacao(filtered);
  }, [linhas, query]);

  const totalLinhas = linhas.filter((l) => l.ativa !== false).length;
  const linhasVisiveis = grupos.reduce(
    (n, fab) => n + fab.localizacoes.reduce((m, loc) => m + loc.linhas.length, 0),
    0,
  );
  // Quando existe apenas uma fabrica cadastrada, simplifica a UI exibindo
  // direto as localizacoes (evita um nivel de '<details>' redundante).
  const fabricaUnica = grupos.length === 1;

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

          {grupos.map((fab) => {
            const totalNoFab = fab.localizacoes.reduce((n, loc) => n + loc.linhas.length, 0);
            const renderLinhas = (linhasLoc: Linha[]) => (
              <ul className="sbv2__group-list">
                {linhasLoc.map((linha) => {
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
            );

            const renderLocalizacoes = (
              fab.localizacoes.map((loc) => (
                <details
                  key={`${fab.fabrica_codigo}|${loc.nome}`}
                  className="sbv2__group"
                  open={!!query || loc.linhas.length <= 6}
                  style={{ marginLeft: fabricaUnica ? 0 : 10 }}
                >
                  <summary
                    className="sbv2__group-summary"
                    title={`${loc.nome} (${loc.linhas.length})`}
                  >
                    <span className="sbv2__group-chev">▸</span>
                    <span className="sbv2__group-emoji" aria-hidden="true">📍</span>
                    {!collapsed && (
                      <>
                        <span className="sbv2__group-label">{loc.nome}</span>
                        <span className="sbv2__group-count">{loc.linhas.length}</span>
                      </>
                    )}
                  </summary>
                  {renderLinhas(loc.linhas)}
                </details>
              ))
            );

            // Quando ha apenas uma fabrica cadastrada, mostra direto as
            // localizacoes (evita header redundante de 'F001 - Unica').
            if (fabricaUnica) {
              return (
                <React.Fragment key={fab.fabrica_codigo}>
                  {renderLocalizacoes}
                </React.Fragment>
              );
            }

            return (
              <details
                key={fab.fabrica_codigo}
                className="sbv2__group"
                open={!!query || totalNoFab <= 10}
              >
                <summary
                  className="sbv2__group-summary"
                  title={`${fab.fabrica_codigo} · ${fab.fabrica_nome}`}
                >
                  <span className="sbv2__group-chev">▸</span>
                  <span className="sbv2__group-emoji" aria-hidden="true">🏭</span>
                  {!collapsed && (
                    <>
                      <span className="sbv2__group-label">
                        {fab.fabrica_codigo} · {fab.fabrica_nome}
                      </span>
                      <span className="sbv2__group-count">{totalNoFab}</span>
                    </>
                  )}
                </summary>
                <div style={{ paddingLeft: 4 }}>{renderLocalizacoes}</div>
              </details>
            );
          })}
        </div>
      </section>

      {/* ---- Ferramentas externas ----
          Logica:
            - Acesso DIRETO (rede OT, hostname IP da .160 ou localhost):
              usa porta nativa - Grafana em :3001, Chronograf em :8888.
            - Acesso via PROXY (qualquer outro hostname, ex.: hub.mis.local,
              IP do proxy central): usa subpath /mc-... que o proxy reverso
              encaminha para a maquina .160. Critico para Node-RED, senao
              cai no Node-RED ANTIGO da maquina .71 pelo /nodered/.
       */}
      {currentUser?.is_admin && (
        <nav className="sbv2__tools" aria-label="Ferramentas administrativas">
          {!collapsed && <p className="sbv2__section-title">Ferramentas</p>}
          <SmartToolLink kind="grafana"    icon="📈" label="Grafana"    collapsed={collapsed} />
          <SmartToolLink kind="chronograf" icon="⏱️" label="Chronograf" collapsed={collapsed} />
          <SmartToolLink kind="nodered"    icon="🔌" label="Node-RED"   collapsed={collapsed} />
          <SmartToolLink kind="emqx"       icon="📡" label="EMQX"       collapsed={collapsed} />
          <SmartToolLink kind="kepserver"  icon="🏭" label="Kepserver"  collapsed={collapsed} />
          <SmartToolLink
            kind="portainer"
            icon={<Container size={17} strokeWidth={1.8} />}
            label="Portainer"
            collapsed={collapsed}
          />
        </nav>
      )}

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

// ToolLink — aponta para uma porta nativa do mesmo host onde a aplicação
// está sendo acessada. Em localhost usa localhost:PORT; em uma fábrica
// acessada via IP/hostname, usa o mesmo host:PORT — sem dependência de
// proxy reverso.
// MANTIDO para compatibilidade. Para novas rotas, prefira SmartToolLink.
const ToolLink: React.FC<{
  port: number;
  icon: string;
  label: string;
  collapsed: boolean;
}> = ({ port, icon, label, collapsed }) => {
  const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  const href = `http://${host}:${port}/`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="sbv2__link"
      title={`${label} — abre em nova aba (${href})`}
    >
      <span aria-hidden="true">{icon}</span>
      {!collapsed && <span>{label}</span>}
    </a>
  );
};

// SmartToolLink — escolhe automaticamente entre porta nativa e subpath
// do proxy central, baseado no hostname onde o usuário está acessando.
//
// Regra:
//   - hostname é IP privado (192.168.x, 10.x, localhost): rede OT direta →
//     usa porta nativa (Grafana :3001, Chronograf :8888, EMQX :18083).
//     Node-RED usa auth Django; Portainer usa sua autenticacao nativa.
//
//   - qualquer outro hostname (proxy central, ex.: hub.mis.local ou
//     192.168.30.71): usa subpath /mc-*/ do proxy reverso, que aponta
//     para a máquina .160 (NÃO confunde com /grafana/, /nodered/ etc.
//     do proxy que apontam para os legados na máquina .71).
//
// É o que evita o bug "cliquei em Node-RED e abriu o do .71 em vez do .160".
type ToolKind = 'grafana' | 'chronograf' | 'nodered' | 'emqx' | 'portainer' | 'kepserver';

const TOOL_PROXY_PATHS: Record<ToolKind, string> = {
  grafana: '/mc-grafana/',
  chronograf: '/mc-chronograf/',
  nodered: '/mc-nodered/',
  emqx: '/mc-emqx/',
  portainer: '/mc-portainer/',
  kepserver: '/kepserver-manager/',
};

const SmartToolLink: React.FC<{
  kind: ToolKind;
  icon: React.ReactNode;
  label: string;
  collapsed: boolean;
}> = ({ kind, icon, label, collapsed }) => {
  // Toda ferramenta passa pelo gateway Django; não há exceção por IP/porta.
  const href = TOOL_PROXY_PATHS[kind];
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="sbv2__link"
      title={`${label} — abre em nova aba (${href})`}
    >
      <span aria-hidden="true">{icon}</span>
      {!collapsed && <span>{label}</span>}
    </a>
  );
};

export default SidebarV2;
