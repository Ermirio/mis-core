/**
 * Header.jsx — v9.6
 * - NEW badges removidos
 * - Aba Comunicação mostra total de mensagens não lidas (todas as linhas)
 * - Badge com sino animado mantido para @menções diretas
 */

import React, { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { Nav, Badge } from 'react-bootstrap';
import {
  FaIndustry,
  FaChartBar,
  FaClipboardCheck,
  FaCog,
  FaHistory,
  FaChartLine,
  FaRobot,
  FaShieldAlt,
  FaFlagCheckered,
  FaFlask,
  FaComments,
  FaBell,
  FaWaveSquare,
  FaUsersCog,
} from 'react-icons/fa';
import useAxios from '../../hooks/useAxios';
import { useAuth } from '../../context/AuthContext';
import './Header.css';

const Header = ({ unreadCounts = {} }) => {
  const api    = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;
  const { user } = useAuth();
  const isSuperuser = !!(user && user.is_superuser);
  const [mencoes, setMencoes] = useState(0);

  // Total de mensagens não lidas em todas as linhas (do App.js)
  const totalNaoLidas = Object.values(unreadCounts).reduce((s, n) => s + (n || 0), 0);

  // Menções @diretas ao usuário (endpoint existente)
  useEffect(() => {
    let mounted = true;
    const buscar = () => {
      apiRef.current.get('/api/chat/mencoes/nao-lidas/')
        .then(r => { if (mounted) setMencoes(r.data.nao_lidas || 0); })
        .catch(() => {});
    };
    buscar();
    const id = setInterval(buscar, 30000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  const temNotif = totalNaoLidas > 0 || mencoes > 0;
  const contadorExibido = totalNaoLidas > 0 ? totalNaoLidas : mencoes;

  return (
    <header className="header-container">
      <div className="header-bar">
        <FaIndustry className="header-icon" />
        <div className="title-container">
          <span className="title-main">MIS</span>
          <span className="title-subtitle">Manufacture Integrated System</span>
          <span className="title-developed">Developed By Process Engineer</span>
        </div>
      </div>

      <Nav justify variant="tabs" className="custom-nav-tabs">
        {/* [v10.2] Status do Produto desativado temporariamente.
            O worker do Django (OPCValidacaoQualidadeWorker) continua rodando
            para preservar a Validacao de Qualidade. So' a tela foi escondida.
            Para REATIVAR: descomente este bloco + a rota em App.js + o import.
        <Nav.Item>
          <NavLink to="/product-status" className="nav-link-custom">
            <FaClipboardCheck className="nav-icon" />
            <span>Status do Produto</span>
          </NavLink>
        </Nav.Item>
        */}

        <Nav.Item>
          <NavLink to="/intertravamentos" className="nav-link-custom">
            <FaShieldAlt className="nav-icon" />
            <span>Intertravamentos</span>
          </NavLink>
        </Nav.Item>

        <Nav.Item>
          <NavLink to="/validacoes" className="nav-link-custom">
            <FaFlask className="nav-icon" />
            <span>Validações</span>
          </NavLink>
        </Nav.Item>

        <Nav.Item>
          <NavLink to="/andretti" className="nav-link-custom">
            <FaFlagCheckered className="nav-icon" />
            <span>Andretti</span>
          </NavLink>
        </Nav.Item>

        {/* ── Comunicação — badge de não lidas ── */}
        <Nav.Item>
          <NavLink
            to="/comunicacao"
            className={`nav-link-custom${temNotif ? ' nav-link-notif' : ''}`}
            style={{ position: 'relative' }}
          >
            <span style={{ position: 'relative', display: 'inline-flex' }}>
              <FaComments className="nav-icon" />
              {mencoes > 0 && (
                <FaBell
                  className="bell-shake"
                  style={{
                    position: 'absolute', top: -6, right: -8,
                    color: '#dc3545', fontSize: '0.75rem',
                  }}
                />
              )}
            </span>
            <span>Comunicação</span>
            {temNotif && (
              <Badge
                bg="danger"
                pill
                style={{
                  position: 'absolute', top: 2, right: 2,
                  fontSize: '0.6rem', padding: '2px 5px',
                  minWidth: 18, textAlign: 'center',
                }}
              >
                {contadorExibido > 99 ? '99+' : contadorExibido}
              </Badge>
            )}
          </NavLink>
        </Nav.Item>

        <style>{`
          .nav-link-notif {
            background: linear-gradient(135deg, #fff3cd 0%, #ffe8e8 100%) !important;
            border-color: #dc3545 !important;
          }
          .bell-shake {
            animation: bell-shake 1.2s ease infinite;
            transform-origin: top center;
          }
          @keyframes bell-shake {
            0%,100% { transform: rotate(0deg); }
            10%      { transform: rotate(15deg); }
            20%      { transform: rotate(-13deg); }
            30%      { transform: rotate(10deg); }
            40%      { transform: rotate(-8deg); }
            50%      { transform: rotate(5deg); }
            60%      { transform: rotate(0deg); }
          }
        `}</style>

        <Nav.Item>
          <NavLink to="/machine-chat" className="nav-link-custom">
            <FaRobot className="nav-icon" />
            <span>Chat IA</span>
          </NavLink>
        </Nav.Item>

        <Nav.Item>
          <NavLink to="/troca-automatica" className="nav-link-custom">
            <FaCog className="nav-icon" />
            <span>Troca Automática</span>
          </NavLink>
        </Nav.Item>

        <Nav.Item>
          <NavLink to="/receita-monitor" className="nav-link-custom">
            <FaWaveSquare className="nav-icon" />
            <span>Monitor de Receita</span>
          </NavLink>
        </Nav.Item>

        <Nav.Item>
          <NavLink to="/trocas" className="nav-link-custom">
            <FaHistory className="nav-icon" />
            <span>Histórico de Trocas</span>
          </NavLink>
        </Nav.Item>

        {/* Gestão de Usuários — só aparece para superusuário */}
        {isSuperuser && (
          <Nav.Item>
            <NavLink to="/gestao-usuarios" className="nav-link-custom">
              <FaUsersCog className="nav-icon" />
              <span>Gestão de Usuários</span>
            </NavLink>
          </Nav.Item>
        )}
      </Nav>
    </header>
  );
};

export default Header;
