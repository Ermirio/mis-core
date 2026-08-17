/**
 * ComunicacaoContent.js — Central de Comunicação v9.2.1
 *
 * Melhorias:
 *   - Grupo/função do usuário exibido junto ao nome
 *   - Turno removido da frente do nome (aparece só no separador)
 *   - #hashtags coloridas e exibidas como chips
 *   - Botão "Resumir Turno" → chama LM Studio e exibe resultado no chat
 *   - Polling automático a cada 10s
 */
import React, {
  useState, useEffect, useRef, useCallback, useMemo
} from 'react';
import {
  Card, Form, Button, Spinner, Alert, Badge, InputGroup
} from 'react-bootstrap';
import {
  FaComments, FaPaperPlane, FaAt, FaCalendarAlt,
  FaChevronLeft, FaChevronRight, FaSyncAlt, FaIndustry,
  FaMagic, FaTag, FaRobot
} from 'react-icons/fa';
import useAxios from '../hooks/useAxios';

// ─── Paleta de cores por inicial ────────────────────────────────────────────
const AVATAR_COLORS = [
  '#0d6efd','#198754','#dc3545','#fd7e14','#6610f2',
  '#20c997','#ffc107','#0dcaf0','#d63384','#6f42c1',
];
function corAvatar(username = '') {
  let h = 0;
  for (let i = 0; i < username.length; i++) h = username.charCodeAt(i) + ((h << 5) - h);
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

// ─── Cor de hashtag por palavra (consistente) ────────────────────────────────
const TAG_COLORS = ['#198754','#0dcaf0','#fd7e14','#6610f2','#d63384','#20c997'];
function corTag(tag = '') {
  let h = 0;
  for (let i = 0; i < tag.length; i++) h = tag.charCodeAt(i) + ((h << 5) - h);
  return TAG_COLORS[Math.abs(h) % TAG_COLORS.length];
}

// ─── Avatar com iniciais ─────────────────────────────────────────────────────
const Avatar = ({ nome, username, size = 36 }) => {
  const iniciais = nome
    ? nome.split(' ').slice(0, 2).map(p => p[0]).join('').toUpperCase()
    : (username || '?')[0].toUpperCase();
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      backgroundColor: corAvatar(username),
      color: '#fff', fontWeight: 700,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.38, flexShrink: 0,
    }}>
      {iniciais}
    </div>
  );
};

// ─── Formata hora local ──────────────────────────────────────────────────────
function fmtHora(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

// ─── Renderiza texto com @menções e #hashtags coloridas ──────────────────────
function TextoMensagem({ texto }) {
  const partes = texto.split(/([@#]\w+)/g);
  return (
    <span>
      {partes.map((p, i) => {
        if (p.startsWith('@')) return <strong key={i} style={{ color: '#6610f2' }}>{p}</strong>;
        if (p.startsWith('#')) return (
          <strong key={i} style={{ color: corTag(p.slice(1)), cursor: 'default' }}>{p}</strong>
        );
        return <span key={i}>{p}</span>;
      })}
    </span>
  );
}

// ─── Chip de hashtag ─────────────────────────────────────────────────────────
const TagChip = ({ tag }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 3,
    background: corTag(tag) + '18',
    color: corTag(tag),
    borderRadius: 99, padding: '1px 8px',
    fontSize: '0.68rem', fontWeight: 600,
    border: `1px solid ${corTag(tag)}40`,
    marginRight: 4,
  }}>
    <FaTag size={8} />{tag}
  </span>
);

// ─── Bolha de mensagem normal ────────────────────────────────────────────────
const Bolha = ({ msg, minha }) => {
  const grupo = msg.autor_grupos?.[0];
  return (
    <div style={{
      display: 'flex',
      flexDirection: minha ? 'row-reverse' : 'row',
      alignItems: 'flex-end',
      gap: 8,
      marginBottom: 12,
    }}>
      {!minha && <Avatar nome={msg.autor_nome} username={msg.autor} />}
      <div style={{ maxWidth: '72%' }}>
        {!minha && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, paddingLeft: 4 }}>
            <strong style={{ fontSize: '0.78rem', color: '#343a40' }}>
              {msg.autor_nome || msg.autor}
            </strong>
            {grupo && (
              <span style={{
                fontSize: '0.65rem', fontWeight: 600,
                background: '#e9ecef', color: '#495057',
                borderRadius: 99, padding: '1px 7px',
              }}>
                {grupo}
              </span>
            )}
          </div>
        )}
        <div style={{
          background: minha ? '#0d6efd' : '#f1f3f5',
          color: minha ? '#fff' : '#212529',
          borderRadius: minha ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          padding: '8px 14px',
          fontSize: '0.9rem',
          lineHeight: 1.45,
          wordBreak: 'break-word',
        }}>
          <TextoMensagem texto={msg.texto} />
        </div>
        {/* Chips de hashtag abaixo da bolha */}
        {msg.tags?.length > 0 && (
          <div style={{ marginTop: 4, paddingLeft: 4 }}>
            {msg.tags.map(t => <TagChip key={t} tag={t} />)}
          </div>
        )}
        <div style={{
          fontSize: '0.68rem', color: '#adb5bd',
          textAlign: minha ? 'right' : 'left',
          marginTop: 2, paddingInline: 4,
        }}>
          {fmtHora(msg.criada_em)}
          {msg.editada && ' · editada'}
          {msg.mencoes?.length > 0 && (
            <span style={{ marginLeft: 6, color: '#6610f2' }}>
              @ {msg.mencoes.map(m => m.username).join(', ')}
            </span>
          )}
        </div>
      </div>
      {minha && <Avatar nome={msg.autor_nome} username={msg.autor} />}
    </div>
  );
};

// ─── Bolha de resumo (IA) ─────────────────────────────────────────────────────
const BolhaResumo = ({ resumo, turnoLabel, nMensagens }) => (
  <div style={{
    margin: '16px 0',
    background: 'linear-gradient(135deg, #f8f9ff 0%, #eff1ff 100%)',
    border: '1px solid #c5ceff',
    borderRadius: 12,
    padding: '14px 16px',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
      <div style={{
        width: 32, height: 32, borderRadius: '50%',
        background: '#6610f2', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <FaRobot color="#fff" size={14} />
      </div>
      <div>
        <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#3d2c8d' }}>
          Resumo do {turnoLabel}
        </div>
        <div style={{ fontSize: '0.68rem', color: '#6c757d' }}>
          {nMensagens} mensagens analisadas · LM Studio
        </div>
      </div>
    </div>
    <div style={{
      fontSize: '0.88rem', lineHeight: 1.6, color: '#212529',
      whiteSpace: 'pre-wrap',
    }}>
      {resumo}
    </div>
  </div>
);

// ─── Separador de turno ──────────────────────────────────────────────────────
const SeparadorTurno = ({ turno }) => {
  const labels = { A: 'Turno A — 06h às 14h', B: 'Turno B — 14h às 22h', C: 'Turno C — 22h às 06h' };
  const cores  = { A: '#198754', B: '#0d6efd', C: '#6610f2' };
  return (
    <div style={{ display: 'flex', alignItems: 'center', margin: '16px 0' }}>
      <hr style={{ flex: 1, borderColor: cores[turno], opacity: 0.3 }} />
      <Badge style={{ background: cores[turno], margin: '0 10px', fontSize: '0.72rem' }}>
        {labels[turno] || turno}
      </Badge>
      <hr style={{ flex: 1, borderColor: cores[turno], opacity: 0.3 }} />
    </div>
  );
};

// ─── Utilitário: data para string YYYY-MM-DD ─────────────────────────────────
function toDateStr(d) { return d.toISOString().slice(0, 10); }

// ════════════════════════════════════════════════════════════════════════════════
//  ComunicacaoContent
// ════════════════════════════════════════════════════════════════════════════════
const ComunicacaoContent = ({ selectedLine, onMarkRead }) => {
  const api    = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;

  // ── estados ────────────────────────────────────────────────────────────────
  const [mensagens,    setMensagens]    = useState([]);
  const [resumoItem,   setResumoItem]   = useState(null);   // resumo IA exibido no chat
  const [loading,      setLoading]      = useState(false);
  const [erro,         setErro]         = useState(null);
  const [texto,        setTexto]        = useState('');
  const [enviando,     setEnviando]     = useState(false);
  const [resumindo,    setResumindo]    = useState(false);
  const [data,         setData]         = useState(toDateStr(new Date()));
  const [turno,        setTurno]        = useState('');
  const [usuarios,     setUsuarios]     = useState([]);
  const [mention,      setMention]      = useState(null);
  const [sugestoes,    setSugestoes]    = useState([]);
  const [meuUsername,  setMeuUsername]  = useState('');
  const [turnoAtual,   setTurnoAtual]   = useState('A');    // turno corrente para o botão resumir

  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);
  const pollingRef = useRef(null);

  // ── usuário logado e turno atual ───────────────────────────────────────────
  useEffect(() => {
    try {
      const token = localStorage.getItem('access') || localStorage.getItem('token');
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setMeuUsername(payload.username || '');
      }
    } catch { /* ignore */ }

    // Turno local
    const hora = new Date().getHours();
    if (hora >= 6 && hora < 14)       setTurnoAtual('A');
    else if (hora >= 14 && hora < 22) setTurnoAtual('B');
    else                               setTurnoAtual('C');
  }, []);

  // ── carregar usuários (autocomplete) ───────────────────────────────────────
  useEffect(() => {
    apiRef.current.get('/api/chat/usuarios/').then(r => setUsuarios(r.data)).catch(() => {});
  }, []);

  // ── buscar mensagens ───────────────────────────────────────────────────────
  const buscarMensagens = useCallback(async (silencioso = false) => {
    if (!selectedLine) return;
    if (!silencioso) setLoading(true);
    setErro(null);
    try {
      const params = new URLSearchParams({ data });
      if (turno) params.set('turno', turno);
      const res = await apiRef.current.get(`/api/chat/${selectedLine}/?${params}`);
      setMensagens(res.data.mensagens || []);
    } catch (e) {
      if (!silencioso) setErro(e.response?.data?.detail || 'Erro ao carregar mensagens.');
    } finally {
      if (!silencioso) setLoading(false);
    }
  }, [selectedLine, data, turno]);

  useEffect(() => { buscarMensagens(); }, [buscarMensagens]);

  // ── polling 10s ───────────────────────────────────────────────────────────
  useEffect(() => {
    clearInterval(pollingRef.current);
    if (!selectedLine) return;
    pollingRef.current = setInterval(() => buscarMensagens(true), 10000);
    return () => clearInterval(pollingRef.current);
  }, [buscarMensagens, selectedLine]);

  // Marca chat da linha como visualizado ao abrir (zera badge no sidebar)
  useEffect(() => {
    if (!selectedLine) return;
    apiRef.current.post(`/api/chat/${selectedLine}/visualizar/`, {})
      .then(() => { if (onMarkRead) onMarkRead(selectedLine); })
      .catch(() => {});
  }, [selectedLine]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── scroll para o fim ──────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensagens, resumoItem]);

  // ── agrupar por turno ──────────────────────────────────────────────────────
  const grupos = useMemo(() => {
    const g = [];
    let turnoAtualGrupo = null;
    for (const m of mensagens) {
      if (m.turno !== turnoAtualGrupo) {
        g.push({ tipo: 'separador', turno: m.turno });
        turnoAtualGrupo = m.turno;
      }
      g.push({ tipo: 'msg', msg: m });
    }
    return g;
  }, [mensagens]);

  // ── navegação de data ──────────────────────────────────────────────────────
  function alterarData(delta) {
    const d = new Date(data + 'T00:00:00');
    d.setDate(d.getDate() + delta);
    setData(toDateStr(d));
    setResumoItem(null);
  }

  // ── autocomplete @menção ───────────────────────────────────────────────────
  function handleTextoChange(e) {
    const val = e.target.value;
    setTexto(val);
    const pos = e.target.selectionStart;
    const antes = val.slice(0, pos);
    const matchAt = antes.match(/@(\w*)$/);
    if (matchAt) {
      const query = matchAt[1].toLowerCase();
      setMention({ start: pos - matchAt[0].length, query });
      setSugestoes(
        usuarios.filter(u =>
          u.username.toLowerCase().includes(query) || u.nome.toLowerCase().includes(query)
        ).slice(0, 6)
      );
    } else {
      setMention(null);
      setSugestoes([]);
    }
  }

  function selecionarMencao(u) {
    if (!mention) return;
    const antes  = texto.slice(0, mention.start);
    const depois = texto.slice(inputRef.current?.selectionStart || texto.length);
    setTexto(`${antes}@${u.username} ${depois}`);
    setMention(null);
    setSugestoes([]);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  // ── enviar mensagem ────────────────────────────────────────────────────────
  async function handleEnviar(e) {
    e?.preventDefault();
    if (!texto.trim() || !selectedLine || enviando) return;
    setEnviando(true);
    try {
      const res = await apiRef.current.post(`/api/chat/${selectedLine}/enviar/`, { texto: texto.trim() });
      setTexto('');
      setMensagens(prev =>
        prev.some(m => m.id === res.data.id) ? prev : [...prev, res.data]
      );
    } catch (e) {
      setErro(e.response?.data?.detail || 'Erro ao enviar mensagem.');
    } finally {
      setEnviando(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (sugestoes.length > 0 && mention) selecionarMencao(sugestoes[0]);
      else handleEnviar();
    }
    if (e.key === 'Escape') { setMention(null); setSugestoes([]); }
  }

  // ── resumir turno ──────────────────────────────────────────────────────────
  async function handleResumir() {
    if (!selectedLine || resumindo) return;
    setResumindo(true);
    setErro(null);
    try {
      const turnoParaResumir = turno || turnoAtual;
      const res = await apiRef.current.post(`/api/chat/${selectedLine}/resumir/`, {
        turno: turnoParaResumir,
        data,
      });
      setResumoItem(res.data);
    } catch (e) {
      setErro(e.response?.data?.detail || 'Erro ao resumir turno. Verifique se o LM Studio está ativo.');
    } finally {
      setResumindo(false);
    }
  }

  // ── sem linha selecionada ──────────────────────────────────────────────────
  if (!selectedLine) {
    return (
      <div className="text-center py-5 text-muted">
        <FaIndustry size={48} className="mb-3 opacity-50" />
        <h5>Selecione uma linha para ver o chat</h5>
      </div>
    );
  }

  // ── renderização ───────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 180px)', minHeight: 400 }}>

      {/* ── Cabeçalho ────────────────────────────────────────────────────── */}
      <Card className="mb-2 shadow-sm flex-shrink-0">
        <Card.Body className="py-2 px-3">
          <div className="d-flex align-items-center gap-3 flex-wrap">
            <FaComments className="text-primary" size={20} />
            <span className="fw-semibold">Comunicação — {selectedLine}</span>

            {/* Filtro turno */}
            <div className="d-flex gap-1">
              {['', 'A', 'B', 'C'].map(t => (
                <Button
                  key={t}
                  size="sm"
                  variant={turno === t ? 'primary' : 'outline-secondary'}
                  onClick={() => setTurno(t)}
                  style={{ minWidth: 42 }}
                >
                  {t || 'Todos'}
                </Button>
              ))}
            </div>

            {/* Botão resumir turno */}
            <Button
              size="sm"
              variant="outline-purple"
              onClick={handleResumir}
              disabled={resumindo || mensagens.length === 0}
              style={{
                borderColor: '#6610f2', color: '#6610f2',
                display: 'flex', alignItems: 'center', gap: 5,
              }}
              title="Resumir turno com LM Studio"
            >
              {resumindo
                ? <><Spinner size="sm" animation="border" style={{ width: 14, height: 14 }} /> Resumindo…</>
                : <><FaMagic size={12} /> Resumir turno</>
              }
            </Button>

            {/* Navegação de data */}
            <div className="d-flex align-items-center gap-1 ms-auto">
              <Button size="sm" variant="outline-secondary" onClick={() => alterarData(-1)}>
                <FaChevronLeft />
              </Button>
              <div className="d-flex align-items-center gap-1">
                <FaCalendarAlt className="text-muted" size={13} />
                <input
                  type="date"
                  value={data}
                  onChange={e => { setData(e.target.value); setResumoItem(null); }}
                  className="form-control form-control-sm"
                  style={{ width: 130 }}
                  max={toDateStr(new Date())}
                />
              </div>
              <Button
                size="sm" variant="outline-secondary"
                onClick={() => alterarData(1)}
                disabled={data >= toDateStr(new Date())}
              >
                <FaChevronRight />
              </Button>
              <Button size="sm" variant="outline-secondary" onClick={() => buscarMensagens()} disabled={loading}>
                <FaSyncAlt className={loading ? 'spin' : ''} />
              </Button>
            </div>
          </div>
        </Card.Body>
      </Card>

      {/* ── Área de mensagens ─────────────────────────────────────────────── */}
      <div style={{
        flex: 1, overflowY: 'auto',
        background: '#f8f9fa',
        borderRadius: 8,
        padding: '12px 16px',
        marginBottom: 8,
        border: '1px solid #dee2e6',
      }}>
        {loading && mensagens.length === 0 && (
          <div className="text-center py-5">
            <Spinner animation="border" variant="primary" size="sm" />
            <p className="mt-2 text-muted small">Carregando mensagens…</p>
          </div>
        )}

        {erro && <Alert variant="danger" className="py-2" dismissible onClose={() => setErro(null)}>{erro}</Alert>}

        {!loading && mensagens.length === 0 && !erro && (
          <div className="text-center py-5 text-muted">
            <FaComments size={36} className="mb-2 opacity-25" />
            <p className="small">Nenhuma mensagem nesta data{turno ? ` · Turno ${turno}` : ''}.</p>
          </div>
        )}

        {grupos.map((item, idx) =>
          item.tipo === 'separador'
            ? <SeparadorTurno key={`sep-${idx}`} turno={item.turno} />
            : (
              <Bolha
                key={item.msg.id}
                msg={item.msg}
                minha={item.msg.autor === meuUsername}
              />
            )
        )}

        {/* Resumo da IA exibido após as mensagens */}
        {resumoItem && (
          <BolhaResumo
            resumo={resumoItem.resumo}
            turnoLabel={resumoItem.turno_label}
            nMensagens={resumoItem.n_mensagens}
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input de mensagem ─────────────────────────────────────────────── */}
      <div style={{ position: 'relative', flexShrink: 0 }}>
        {/* Dropdown autocomplete @menção */}
        {sugestoes.length > 0 && (
          <div style={{
            position: 'absolute', bottom: '100%', left: 0, right: 0,
            background: '#fff', border: '1px solid #dee2e6',
            borderRadius: 8, boxShadow: '0 -4px 16px rgba(0,0,0,0.1)',
            zIndex: 100, maxHeight: 240, overflowY: 'auto',
          }}>
            {sugestoes.map(u => (
              <button
                key={u.id}
                className="w-100 text-start px-3 py-2 border-0 bg-transparent"
                style={{ cursor: 'pointer' }}
                onMouseDown={e => { e.preventDefault(); selecionarMencao(u); }}
              >
                <div className="d-flex align-items-center gap-2">
                  <Avatar nome={u.nome} username={u.username} size={28} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{u.nome}</div>
                    <div style={{ fontSize: '0.72rem', color: '#6c757d' }}>
                      @{u.username}
                      {u.grupos?.[0] && (
                        <span style={{
                          marginLeft: 6, background: '#e9ecef',
                          borderRadius: 99, padding: '1px 6px', fontSize: '0.65rem',
                        }}>
                          {u.grupos[0]}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleEnviar}>
          <InputGroup>
            <Button
              variant="outline-secondary"
              size="sm"
              type="button"
              title="Mencionar usuário"
              onClick={() => {
                setTexto(prev => prev + '@');
                setTimeout(() => inputRef.current?.focus(), 0);
              }}
            >
              <FaAt />
            </Button>
            <Form.Control
              as="textarea"
              ref={inputRef}
              rows={2}
              placeholder="Digite uma mensagem… @username para mencionar · #tag para categorizar"
              value={texto}
              onChange={handleTextoChange}
              onKeyDown={handleKeyDown}
              disabled={enviando}
              style={{ resize: 'none', fontSize: '0.9rem' }}
            />
            <Button
              type="submit"
              variant="primary"
              disabled={!texto.trim() || enviando}
            >
              {enviando
                ? <Spinner size="sm" animation="border" />
                : <FaPaperPlane />
              }
            </Button>
          </InputGroup>
          <div style={{ fontSize: '0.7rem', color: '#adb5bd', marginTop: 3, textAlign: 'right' }}>
            Enter para enviar · Shift+Enter para nova linha · #manutenção #qualidade #segurança para categorizar
          </div>
        </form>
      </div>

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default ComunicacaoContent;
