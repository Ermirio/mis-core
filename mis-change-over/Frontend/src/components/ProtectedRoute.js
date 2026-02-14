import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * Componente para proteger rotas.
 * Redireciona para a página de login se o usuário não estiver autenticado.
 */
const ProtectedRoute = () => {
  const { user } = useAuth();

  // Se o usuário estiver autenticado (user não é null), renderiza o conteúdo da rota.
  // Caso contrário, redireciona para a página de login.
  return user ? <Outlet /> : <Navigate to="/login" replace />;
};

export default ProtectedRoute;
