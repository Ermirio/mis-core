/**
 * Navbar.js - Componente de barra superior (Versão Compatível)
 * 
 * Versão conservadora que mantém toda a funcionalidade original
 * com melhorias visuais mínimas e compatibilidade total.
 * Renderiza a barra com notificações e informações do usuário.
 *
 * @author Process Engineer
 * @version 2.5.0 - Versão Compatível
 */
import { useAuth } from '../../context/AuthContext';
import React, { useState, useEffect, useCallback } from 'react';
import {
  Navbar as BootstrapNavbar,
  Dropdown,
  Badge,
  Button
} from 'react-bootstrap';
import {
  FaBell,
  FaUser,
  FaCog,
  FaSignOutAlt,
  FaExclamationTriangle,
  FaInfoCircle,
  FaCheckCircle,
  FaTimes
} from 'react-icons/fa';
import './Navbar.css';

// --- Nome da IA ---
const AI_NAME = "LIIA";

const Navbar = ({ selectedLine, isMachineChatActive }) => {
  // Estados para notificações
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Estado para informações do usuário
  const { user, logoutUser } = useAuth();
  console.log("### DEBUG: Objeto USER do AuthContext:", user); // <-- ADICIONE ESTA LINHA

  const generateNotifications = useCallback((lineId) => {
    if (!lineId) return [];

    const now = new Date();
    const notificationTypes = [
      { type: 'warning', icon: FaExclamationTriangle, title: 'Eficiência Baixa', message: `Linha ${lineId}: Eficiência abaixo de 75%` },
      { type: 'info', icon: FaInfoCircle, title: 'Troca de Turno', message: `Linha ${lineId}: Próxima troca em 30 min` },
      { type: 'success', icon: FaCheckCircle, title: 'Meta Atingida', message: `Linha ${lineId}: Meta de produção atingida` },
      { type: 'danger', icon: FaExclamationTriangle, title: 'Defeito Crítico', message: `Linha ${lineId}: Taxa de defeitos elevada` },
    ];

    const numNotifications = Math.floor(Math.random() * 2) + 2;
    return Array.from({ length: numNotifications }, (_, i) => {
        const notifType = notificationTypes[i % notificationTypes.length];
        const timestamp = new Date(now);
        timestamp.setMinutes(timestamp.getMinutes() - (i * 15 + Math.random() * 10));
        return {
            id: `notif_${i}`,
            ...notifType,
            timestamp: timestamp.toISOString(),
            read: Math.random() > 0.5,
        };
    });
  }, []);

  useEffect(() => {
    const newNotifications = generateNotifications(selectedLine);
    setNotifications(newNotifications);
    setUnreadCount(newNotifications.filter(n => !n.read).length);
  }, [selectedLine, generateNotifications]);

  const markAsRead = (notificationId) => {
    setNotifications(prev =>
      prev.map(notif =>
        notif.id === notificationId
          ? { ...notif, read: true }
          : notif
      )
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
  };

  const removeNotification = (notificationId) => {
    setNotifications(prev => prev.filter(notif => notif.id !== notificationId));
  };

  const formatNotificationTime = (timestamp) => {
    const now = new Date();
    const notifTime = new Date(timestamp);
    const diffMinutes = Math.floor((now - notifTime) / (1000 * 60));

    if (diffMinutes < 1) return 'Agora';
    if (diffMinutes < 60) return `${diffMinutes}m atrás`;

    const diffHours = Math.floor(diffMinutes / 60);
    return `${diffHours}h atrás`;
  };

  return (
    <BootstrapNavbar
      bg="white"
      variant="light"
      className="navbar-custom shadow-sm"
    >
      <div className="navbar-container">
        {/* Espaço para o título/info à esquerda */}
        <div className="navbar-left">
          {/* Lógica condicional para exibir LIIA ou Linha Ativa */}
          {isMachineChatActive ? (
            <div className="liia-info">
              <div className="liia-icon-wrapper">
                {/* Ícone de Cérebro Eletrônico (SVG) */}
                <svg className="liia-brain-icon" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-3.1 0-5.75-1.64-7.17-4H4v-1.17c0-1.04.84-1.87 1.87-1.87H12c1.38 0 2.5-1.12 2.5-2.5S13.38 8 12 8H5.87C4.84 8 4 7.16 4 6.13V5c0-1.1.9-2 2-2h4v1.17c0 1.04.84 1.87 1.87 1.87h7.13c1.03 0 1.87.84 1.87 1.87V12c0 3.87-3.13 7-7 7z"/>
                </svg>
              </div>
              <span className="liia-name">{AI_NAME}</span>
            </div>
          ) : (
            selectedLine && (
              <div className="selected-line-info">
                <span className="line-label">Linha Ativa:</span>
                <Badge bg="primary" className="line-badge">{selectedLine}</Badge>
              </div>
            )
          )}
        </div>

        {/* Seção direita - Notificações e usuário */}
        <div className="navbar-right">
          {/* Dropdown de notificações */}
          <Dropdown>
            <Dropdown.Toggle as={Button} variant="link" className="notification-btn">
              <FaBell />
              {unreadCount > 0 && (
                <Badge bg="danger" className="notification-badge" pill>{unreadCount}</Badge>
              )}
            </Dropdown.Toggle>
            <Dropdown.Menu className="notifications-menu" align="end">
                <div className="notifications-header">
                    <h6>Notificações</h6>
                </div>
                <div className="notifications-list">
                    {notifications.length > 0 ? (
                        notifications.map(n => (
                            <div key={n.id} className={`notification-item ${!n.read ? 'unread' : ''}`} onClick={() => markAsRead(n.id)}>
                                <div className="notification-icon">
                                    <n.icon className={`icon-${n.type}`} />
                                </div>
                                <div className="notification-info">
                                    <h6 className="notification-title">{n.title}</h6>
                                    <p className="notification-message">{n.message}</p>
                                    <small className="notification-time">{formatNotificationTime(n.timestamp)}</small>
                                </div>
                                <Button variant="link" size="sm" className="remove-notification-btn" onClick={(e) => { e.stopPropagation(); removeNotification(n.id); }}>
                                    <FaTimes />
                                </Button>
                            </div>
                        ))
                    ) : (
                        <div className="no-notifications">Nenhuma notificação</div>
                    )}
                </div>
            </Dropdown.Menu>
          </Dropdown>

          {/* Dropdown do usuário */}
          <Dropdown>
            <Dropdown.Toggle as={Button} variant="link" className="user-btn">
              <FaUser />
              <span className="user-name d-none d-md-inline">
                {user ? user.username : 'Usuário'}
              </span>
            </Dropdown.Toggle>
            <Dropdown.Menu className="user-menu" align="end">
                <Dropdown.Header>
                  {/* Agora 'user.username' deve funcionar */}
                  <strong>{user ? user.username : 'Carregando...'}</strong>

                  <br />

                  {/* E 'user.group' também */}
                  <small className="text-muted">
                    {user && user.group ? user.group : 'Sem Grupo'}
                  </small>
                </Dropdown.Header>

                <Dropdown.Divider />

                <Dropdown.Item className="text-danger" onClick={logoutUser}>
                  <FaSignOutAlt className="me-2" />Sair
                </Dropdown.Item>
              </Dropdown.Menu>
          </Dropdown>
        </div>
      </div>
    </BootstrapNavbar>
  );
};

export default Navbar;

