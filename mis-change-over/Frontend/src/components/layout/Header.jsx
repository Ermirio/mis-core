/**
 * Header.jsx - Componente de cabeçalho (Versão Compatível)
 *
 * Versão conservadora que mantém a estrutura original com melhorias visuais sutis.
 * Mantém a estrutura original "MIS Developed By Process Engineer" com
 * melhorias mínimas de estilo.
 *
 * @author Process Engineer
 * @version 3.2.0 - Versão Compatível
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { Nav } from 'react-bootstrap';
import { 
  FaIndustry,
  FaChartBar,
  FaClipboardCheck,
  FaCog,
  FaHistory,
  FaChartLine,
  FaFileAlt,
  FaRobot
} from 'react-icons/fa';
import './Header.css';

const Header = () => {
  return (
    <header className="header-container">
      <div className="header-bar">
        <FaIndustry className="header-icon" />
        
        {/* ESTRUTURA DO TÍTULO MANTIDA */}
        <div className="title-container">
          <span className="title-main">MIS</span>
          <span className="title-subtitle">Manufacture Integrated System</span>
          <span className="title-developed">Developed By Process Engineer</span>
        </div>
      </div>

      {/* Navbar com abas de navegação (funcionalidades mantidas) */}
      <Nav justify variant="tabs" className="custom-nav-tabs">
        <Nav.Item>
          <NavLink to="/kpis" className="nav-link-custom">
            <FaChartBar className="nav-icon" />
            <span>KPIs</span>
          </NavLink>
        </Nav.Item>
        
        <Nav.Item>
          <NavLink to="/product-status" className="nav-link-custom">
            <FaClipboardCheck className="nav-icon" />
            <span>Status do Produto</span>
          </NavLink>
        </Nav.Item>
        
        <Nav.Item>
          <NavLink to="/process-variables" className="nav-link-custom new-feature">
            <FaChartLine className="nav-icon" />
            <span>Variáveis de Processo</span>
          </NavLink>
        </Nav.Item>
        
        <Nav.Item>
          <NavLink to="/reports" className="nav-link-custom new-feature">
            <FaFileAlt className="nav-icon" />
            <span>Relatórios</span>
          </NavLink>
        </Nav.Item>
        
        <Nav.Item>
          <NavLink to="/machine-chat" className="nav-link-custom new-feature">
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
{/*         
        <Nav.Item>
          <NavLink to="/trocas" className="nav-link-custom">
            <FaHistory className="nav-icon" />
            <span>Histórico de Trocas</span>
          </NavLink>
        </Nav.Item> */}
      </Nav>
    </header>
  );
};

export default Header;

