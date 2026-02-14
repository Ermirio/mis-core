import React, { createContext, useState, useContext, useCallback } from 'react';
import axios from 'axios';
import { jwtDecode } from 'jwt-decode';

// Criação do Contexto
const AuthContext = createContext();

// Hook customizado para usar o contexto
export const useAuth = () => {
  return useContext(AuthContext);
};

// Provedor de Autenticação
export const AuthProvider = ({ children }) => {
  // Estado inicial: tenta carregar o token e o usuário do localStorage
  const [authTokens, setAuthTokens] = useState(() =>
    localStorage.getItem('authTokens')
      ? JSON.parse(localStorage.getItem('authTokens'))
      : null
  );
  const [user, setUser] = useState(() =>
    localStorage.getItem('authTokens')
      ? jwtDecode(JSON.parse(localStorage.getItem('authTokens')).access)
      : null
  );
  const [loading, setLoading] = useState(false);

  // URL base da API - usa variável de ambiente para suportar proxy do hub
  const API_URL = process.env.REACT_APP_SIDEBAR_API_BASE_URL || '/api';

  /**
   * Função de Login
   */
  const loginUser = useCallback(async (username, password) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_URL}/token/`, {
        username,
        password,
      });

      if (response.status === 200) {
        const data = response.data;
        setAuthTokens(data);
        setUser(jwtDecode(data.access));
        localStorage.setItem('authTokens', JSON.stringify(data));
        setLoading(false);
        return { success: true };
      } else {
        setLoading(false);
        return { success: false, error: 'Credenciais inválidas.' };
      }
    } catch (error) {
      setLoading(false);
      const errorMessage = error.response?.data?.detail || 'Erro de conexão ou credenciais inválidas.';
      return { success: false, error: errorMessage };
    }
  }, [API_URL]);

  /**
   * Função de Logout
   */
  const logoutUser = useCallback(() => {
    setAuthTokens(null);
    setUser(null);
    localStorage.removeItem('authTokens');
  }, []);

  /**
   * Função para verificar se o usuário pertence a um grupo
   */
  const isOperator = useCallback(() => {
    if (!user) return false;
    // O JWT do simplejwt não inclui grupos por padrão.
    // Para simplificar, vamos assumir que o backend pode ser configurado para incluir grupos no payload do token
    // OU que a verificação de grupo será feita apenas no backend (como no trocar_sku).
    // Por enquanto, o frontend só precisa saber se está logado.
    return true;
  }, [user]);

  /**
   * Função para atualizar o token (chamada em intervalos regulares)
   */
  const updateToken = useCallback(async () => {
    if (!authTokens?.refresh) {
      logoutUser();
      return;
    }

    try {
      const response = await axios.post(`${API_URL}/token/refresh/`, {
        refresh: authTokens.refresh,
      });

      if (response.status === 200) {
        const data = response.data;
        setAuthTokens(data);
        setUser(jwtDecode(data.access));
        localStorage.setItem('authTokens', JSON.stringify(data));
      } else {
        logoutUser();
      }
    } catch (error) {
      logoutUser();
    }
  }, [authTokens, logoutUser, API_URL]);

  // Efeito para atualizar o token a cada 4 minutos (240000 ms)
  React.useEffect(() => {
    const fourMinutes = 1000 * 60 * 4;
    const interval = setInterval(() => {
      if (authTokens) {
        updateToken();
      }
    }, fourMinutes);
    return () => clearInterval(interval);
  }, [authTokens, updateToken]);

  const contextData = {
    user,
    authTokens,
    loginUser,
    logoutUser,
    loading,
    isOperator,
  };

  return (
    <AuthContext.Provider value={contextData}>
      {children}
    </AuthContext.Provider>
  );
};

// Exportar jwtDecode para uso em outros lugares, se necessário
export { jwtDecode };
