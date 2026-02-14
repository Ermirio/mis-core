import React, { useState, useEffect } from 'react';

const FindLines = () => {
  const [linhas, setLinhas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;

    const fetchLinhas = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch('/api/linhas-disponiveis/', {
          signal,
          method: 'GET', // Explicitly set method
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error(`Erro ao buscar as linhas: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Resposta da API:', data); // Depuração

        // Verifica se a API retorna um array diretamente ou um objeto com chave 'linhas'
        const linhaData = Array.isArray(data) ? data : data.linhas || [];
        const formattedLinhas = linhaData.map((nome) => `Linha ${nome.padStart(2, '0')}`);
        setLinhas(formattedLinhas);
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.error('Erro na requisição:', err); // Depuração
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchLinhas();

    return () => controller.abort();
  }, []);

  if (loading) {
    return <div>Carregando...</div>;
  }

  if (error) {
    return <div>Erro: {error}</div>;
  }

  return (
    <>
      <h2>Lista de Linhas</h2>
      <ul>
        {linhas.map((linha, index) => (
          <li key={index}>{linha}</li> // Usando index como key, já que linha pode não ser único
        ))}
      </ul>
    </>
  );
};

export default FindLines;