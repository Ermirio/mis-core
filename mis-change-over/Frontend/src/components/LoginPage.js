import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Container, Form, Button, Card, Alert } from 'react-bootstrap';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const { loginUser, loading } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const result = await loginUser(username, password);

    if (result.success) {
      // Redireciona para a página inicial após o login
      navigate('/', { replace: true });
    } else {
      setError(result.error);
    }
  };

  return (
    <Container 
      className="d-flex align-items-center justify-content-center" 
      style={{ minHeight: '100vh', backgroundColor: '#f8f9fa' }}
    >
      <div className="w-100" style={{ maxWidth: '400px' }}>
        <Card className="shadow-lg">
          <Card.Body>
            <h2 className="text-center mb-4">MIS - Login</h2>
            {error && <Alert variant="danger">{error}</Alert>}
            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3" controlId="formBasicUsername">
                <Form.Label>Usuário</Form.Label>
                <Form.Control
                  type="text"
                  placeholder="Digite seu usuário"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </Form.Group>

              <Form.Group className="mb-3" controlId="formBasicPassword">
                <Form.Label>Senha</Form.Label>
                <Form.Control
                  type="password"
                  placeholder="Senha"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </Form.Group>

              <Button 
                variant="primary" 
                type="submit" 
                className="w-100"
                disabled={loading}
              >
                {loading ? 'Entrando...' : 'Entrar'}
              </Button>
            </Form>
          </Card.Body>
        </Card>
        <div className="w-100 text-center mt-2">
          <small className="text-muted">MIS Developed By Process Engineer</small>
        </div>
      </div>
    </Container>
  );
};

export default LoginPage;
