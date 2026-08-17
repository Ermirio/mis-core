/**
 * GestaoUsuariosContent — gestão de validade de contas de usuários.
 *
 * ACESSO RESTRITO A SUPERUSER. A rota em App.js já bloqueia, mas este
 * componente também verifica user.is_superuser e mostra aviso se não for.
 *
 * Mostra: lista de usuários, último login, dias de inatividade, validade,
 * dias até expirar, status, e botão "Renovar" (+5 meses) por usuário.
 *
 * Backend:
 *   GET  /api/gestao-usuarios/
 *   POST /api/gestao-usuarios/<id>/renovar/
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Table, Button, Spinner, Alert, Badge } from 'react-bootstrap';
import {
  FaUsersCog, FaSyncAlt, FaCheckCircle, FaExclamationTriangle,
  FaUserClock, FaUserSlash, FaCrown, FaUserCheck,
} from 'react-icons/fa';
import useAxios from '../hooks/useAxios';
import { useAuth } from '../context/AuthContext';

// cor = texto (escuro, legível) · bg = fundo suave. Contraste garantido.
const STATUS_META = {
  ativo:        { label: 'Ativo',            cor: '#1a7e34', bg: '#d1e7dd' },
  a_vencer:     { label: 'A vencer',         cor: '#7a5c00', bg: '#fff3cd' },
  expirado:     { label: 'Expirado',         cor: '#b02a37', bg: '#f8d7da' },
  bloqueado:    { label: 'Bloqueado',        cor: '#495057', bg: '#e9ecef' },
  superuser:    { label: 'Superusuário',     cor: '#0a58ca', bg: '#cfe2ff' },
  sem_controle: { label: 'Sem prazo definido', cor: '#664d03', bg: '#fff3cd' },
};

function fmtData(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch { return '—'; }
}

function GestaoUsuariosContent() {
  const api = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;
  const { user } = useAuth();
  const isSuperuser = !!(user && user.is_superuser);

  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(null);
  const [usuarios, setUsuarios] = useState([]);
  const [resumo, setResumo] = useState({});
  const [renovandoId, setRenovandoId] = useState(null);
  const [toast, setToast] = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    try {
      const res = await apiRef.current.get('/api/gestao-usuarios/');
      setUsuarios(res.data.usuarios || []);
      setResumo(res.data.resumo || {});
    } catch (e) {
      const detail = e.response?.data?.detail || e.message;
      setErro(detail);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isSuperuser) carregar();
    else setLoading(false);
  }, [isSuperuser, carregar]);

  const renovar = useCallback(async (u) => {
    setRenovandoId(u.id);
    try {
      const res = await apiRef.current.post(`/api/gestao-usuarios/${u.id}/renovar/`);
      setToast({ tipo: 'success', msg: res.data.mensagem || `Conta de ${u.username} renovada.` });
      await carregar();
    } catch (e) {
      const detail = e.response?.data?.detail || e.message;
      setToast({ tipo: 'danger', msg: `Falha ao renovar: ${detail}` });
    } finally {
      setRenovandoId(null);
    }
  }, [carregar]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  if (!isSuperuser) {
    return (
      <div style={{ padding: 24 }}>
        <Alert variant="danger">
          <Alert.Heading><FaUserSlash /> Acesso restrito</Alert.Heading>
          Esta tela é exclusiva para superusuários.
        </Alert>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Spinner animation="border" variant="primary" />
        <div style={{ marginTop: 12, color: '#6c757d' }}>Carregando usuários…</div>
      </div>
    );
  }

  if (erro) {
    return (
      <div style={{ padding: 24 }}>
        <Alert variant="danger">Erro ao carregar: {erro}</Alert>
        <Button variant="outline-primary" onClick={carregar}><FaSyncAlt /> Tentar novamente</Button>
      </div>
    );
  }

  return (
    <div style={{ padding: '18px 22px 40px', fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ width: 42, height: 42, borderRadius: 9, background: '#e7f0ff', color: '#0d6efd',
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <FaUsersCog size={22} />
        </span>
        <div>
          <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Gestão de Usuários</h1>
          <div style={{ fontSize: 12, color: '#6c757d' }}>
            Validade de contas · expiração por inatividade (60 dias) ou validade (5 meses)
          </div>
        </div>
        <Button variant="outline-secondary" size="sm" style={{ marginLeft: 'auto' }} onClick={carregar}>
          <FaSyncAlt /> Atualizar
        </Button>
      </div>

      {toast && (
        <Alert variant={toast.tipo} dismissible onClose={() => setToast(null)}>
          {toast.tipo === 'success' ? <FaCheckCircle /> : <FaExclamationTriangle />} {toast.msg}
        </Alert>
      )}

      {/* Cards de resumo */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: 16 }}>
        {[
          { k: 'total', label: 'Total', icon: <FaUserCheck />, cor: '#0d6efd' },
          { k: 'ativos', label: 'Ativos', icon: <FaUserCheck />, cor: '#28a745' },
          { k: 'a_vencer', label: 'A vencer (≤7d)', icon: <FaUserClock />, cor: '#fd7e14' },
          { k: 'bloqueados', label: 'Bloqueados', icon: <FaUserSlash />, cor: '#6c757d' },
        ].map((c) => (
          <Card key={c.k} body style={{ borderRadius: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ color: c.cor, fontSize: 20 }}>{c.icon}</span>
              <div>
                <div style={{ fontSize: 23, fontWeight: 800, color: c.cor }}>{resumo[c.k] ?? 0}</div>
                <div style={{ fontSize: 11, color: '#6c757d' }}>{c.label}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card style={{ borderRadius: 10, overflow: 'hidden' }}>
        <Table hover responsive style={{ margin: 0, fontSize: 13 }}>
          <thead style={{ background: '#f1f3f5' }}>
            <tr>
              <th>Usuário</th>
              <th>Grupos</th>
              <th>Último login</th>
              <th>Inatividade</th>
              <th>Validade até</th>
              <th>Dias restantes</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => {
              const meta = STATUS_META[u.status] || STATUS_META.sem_controle;
              return (
                <tr key={u.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>
                      {u.is_superuser && <FaCrown color="#0d6efd" style={{ marginRight: 5 }} title="Superusuário" />}
                      {u.username}
                    </div>
                    <div style={{ fontSize: 11, color: '#6c757d' }}>{u.nome_completo}</div>
                  </td>
                  <td style={{ fontSize: 11 }}>{u.grupos.length ? u.grupos.join(', ') : '—'}</td>
                  <td>{fmtData(u.ultimo_login)}</td>
                  <td>{u.dias_inativo === null ? '—' : `${u.dias_inativo}d`}</td>
                  <td>{fmtData(u.validade_ate)}</td>
                  <td style={{ fontWeight: 600,
                    color: u.dias_ate_validade !== null && u.dias_ate_validade <= 7 ? '#fd7e14' : '#212529' }}>
                    {u.dias_ate_validade === null ? '—' : `${u.dias_ate_validade}d`}
                  </td>
                  <td>
                    <span style={{
                      display: 'inline-block',
                      padding: '3px 10px',
                      borderRadius: 20,
                      fontSize: 11.5,
                      fontWeight: 700,
                      lineHeight: 1.4,
                      whiteSpace: 'nowrap',
                      color: meta.cor,
                      background: meta.bg,
                      border: `1px solid ${meta.cor}55`,
                    }}>
                      {meta.label}
                    </span>
                  </td>
                  <td>
                    {/* Botão aparece para qualquer usuário comum (não-superuser).
                        "Definir prazo" cria o registro inicial; "Renovar" estende. */}
                    {!u.is_superuser && (
                      <Button size="sm" variant={u.tem_expiracao ? 'outline-primary' : 'primary'}
                        disabled={renovandoId === u.id}
                        onClick={() => renovar(u)}>
                        {renovandoId === u.id
                          ? <Spinner size="sm" animation="border" />
                          : <><FaSyncAlt size={11} /> {u.tem_expiracao ? 'Renovar' : 'Definir prazo'}</>}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
            {usuarios.length === 0 && (
              <tr><td colSpan={8} style={{ textAlign: 'center', padding: 30, color: '#6c757d' }}>
                Nenhum usuário.
              </td></tr>
            )}
          </tbody>
        </Table>
      </Card>

      <div style={{ marginTop: 12, fontSize: 11.5, color: '#6c757d', lineHeight: 1.6 }}>
        <FaExclamationTriangle /> Contas comuns são bloqueadas automaticamente após 60 dias sem login
        ou ao atingir 5 meses de validade. Superusuários nunca expiram.<br />
        <b>Definir prazo</b> cria a validade inicial (+5 meses) para um usuário que ainda não tem.
        &nbsp;<b>Renovar</b> estende por mais 5 meses e reativa uma conta bloqueada.
      </div>
    </div>
  );
}

export default GestaoUsuariosContent;
