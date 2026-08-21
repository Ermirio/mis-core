import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DJANGO_API_URL } from '../config/api';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            // A rota de auth fica no IdP central (Django do Hub)
            const res = await axios.post(`${DJANGO_API_URL}/auth/login/`, {
                username,
                password,
            }, {
                // Importante pra capturar os Cookies na resposta Set-Cookie
                withCredentials: true
            });

            if (res.status === 200) {
                // Verifica se há um destino de retorno (ex: ?next=/mis-ai/)
                const nextUrl = searchParams.get('next');
                if (nextUrl && nextUrl.startsWith('/')) {
                    // Redireciona para o app de origem (navegação absoluta, fora do React Router)
                    window.location.href = nextUrl;
                } else {
                    // Fallback: redireciona para o painel principal do MIS Core
                    navigate('/');
                }
            }
        } catch (err: any) {
            console.error(err);
            setError('Credenciais inválidas. Tente novamente.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 border-t-4 border-t-blue-600">
            <Card className="w-full max-w-sm">
                <CardHeader className="text-center space-y-2">
                    <CardTitle className="text-2xl font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                        MIS HUB SSO
                    </CardTitle>
                    <CardDescription>Entre com suas credenciais de acesso</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleLogin} className="space-y-4">
                        {error && (
                            <div className="p-3 text-sm text-red-600 bg-red-100 rounded-md text-center font-medium">
                                {error}
                            </div>
                        )}

                        <div className="space-y-2">
                            <label className="text-sm font-medium leading-none text-gray-700 dark:text-gray-300">
                                Usuário
                            </label>
                            <Input
                                type="text"
                                placeholder="Seu usuário"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                className="w-full"
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium leading-none text-gray-700 dark:text-gray-300">
                                Senha
                            </label>
                            <Input
                                type="password"
                                placeholder="Sua senha"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                className="w-full"
                            />
                        </div>

                        <Button type="submit" className="w-full" disabled={loading}>
                            {loading ? 'Autenticando...' : 'Entrar'}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
};

export default Login;
