/**
 * TrocasContent.js - Componente para Histórico de Trocas de Produtos
 * * ATUALIZAÇÃO: Agora busca dados reais da API com base na linha selecionada,
 * * utilizando variáveis de ambiente para as URLs da API.
 * * @author Manus AI
 * @version 2.2.1 (Ajustes para variáveis de ambiente e consistência)
 */

import React, { useState, useEffect } from 'react';
import { Card, Table, Badge, Spinner, Alert } from 'react-bootstrap';
import { FaHistory, FaInfoCircle, FaExclamationTriangle } from 'react-icons/fa';

// Use as variáveis de ambiente diretamente.
// São as mesmas que configuramos para o `TrocaAutomaticaContent` para manter a consistência.
const API_BASE_URL = process.env.REACT_APP_TROCA_AUTOMATICA_BASE_URL || '/api';
const HISTORICO_TROCAS_ENDPOINT = process.env.REACT_APP_HISTORICO_TROCAS_ENDPOINT || '/linha/{line}';

// A URL antiga era 'http://127.0.0.1:8000/linha/{selectedLine}/'
// A nova será, por exemplo: 'http://localhost:8000/api/linha/L01/'

const TrocasContent = ({ selectedLine }) => {
  // Estados para gerenciar os dados, carregamento e erros
  const [historico, setHistorico] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // useEffect para buscar os dados sempre que a linha selecionada mudar
  useEffect(() => {
    // Se nenhuma linha estiver selecionada, limpa os dados e não faz a busca
    if (!selectedLine) {
      setHistorico([]);
      setError(null);
      return;
    }

    const fetchHistoricoTrocas = async () => {
      setIsLoading(true); // Inicia o carregamento
      setError(null); // Limpa erros anteriores

      try {
        // Constrói a URL para o endpoint de histórico de trocas.
        // Substitui o placeholder '{line}' pela linha selecionada.
        // Adicionando parâmetros de paginação padrão (mesmo que este componente não tenha controle de UI para isso)
        // para garantir que o endpoint do backend receba o que espera.
        const page = 1; // Podemos fixar a página para este componente se ele não tiver UI de paginação
        const perPage = 10; // E um número de itens por página, ou usar o REACT_APP_DEFAULT_PAGE_SIZE

        // Combinando a BASE_URL com o ENDPOINT, substituindo '{line}' e adicionando parâmetros de paginação
        const url = `${HISTORICO_TROCAS_ENDPOINT.replace('{line}', selectedLine)}?page=${page}&per_page=${perPage}`;

        console.log('Fetching historical data from:', url); // Para debug

        const response = await fetch(url);

        if (!response.ok) {
          throw new Error(`Erro na rede: ${response.status} - ${response.statusText}`);
        }

        const data = await response.json();

        // Verifica se a resposta contém a chave esperada e se é um array
        // O backend do Django para histórico geralmente retorna 'ultimas_trocas' dentro de um objeto,
        // assim como no TrocaAutomaticaContent.
        if (data && Array.isArray(data.ultimas_trocas)) {
          setHistorico(data.ultimas_trocas);
        } else {
          console.warn("API não retornou a estrutura esperada 'ultimas_trocas'.", data);
          setHistorico([]); // Define como vazio se a chave não existir ou não for um array
        }

      } catch (err) {
        setError(err.message);
        setHistorico([]); // Limpa o histórico em caso de erro
        console.error("Falha ao buscar histórico de trocas:", err);
      } finally {
        setIsLoading(false); // Finaliza o carregamento
      }
    };

    fetchHistoricoTrocas();
  }, [selectedLine]); // A dependência é a linha selecionada. API_BASE_URL e HISTORICO_TROCAS_ENDPOINT
  // são constantes, então não precisam ser adicionadas aqui.

  // Função para formatar a data para um formato legível
  const formatarData = (dataIso) => {
    if (!dataIso) return 'Data inválida';
    try {
      return new Date(dataIso).toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (e) {
      console.error("Erro ao formatar data:", dataIso, e);
      return dataIso; // Retorna a string original se for inválida
    }
  };

  const renderContent = () => {
    // 1. Mensagem para selecionar uma linha
    if (!selectedLine) {
      return (
        <Alert variant="info" className="mt-3 text-center">
          <FaInfoCircle size={24} className="mb-2" />
          <br />
          Selecione uma linha no menu lateral para ver o histórico de trocas.
        </Alert>
      );
    }

    // 2. Indicador de carregamento
    if (isLoading) {
      return (
        <div className="text-center p-5">
          <Spinner animation="border" variant="primary" />
          <p className="mt-2">Carregando histórico para a linha <strong>{selectedLine}</strong>...</p>
        </div>
      );
    }

    // 3. Mensagem de erro
    if (error) {
      return (
        <Alert variant="danger" className="mt-3 text-center">
          <FaExclamationTriangle size={24} className="mb-2" />
          <br />
          <strong>Erro ao carregar dados:</strong> {error}
        </Alert>
      );
    }

    // 4. Mensagem para histórico vazio
    if (historico.length === 0) {
      return (
        <Alert variant="secondary" className="mt-3 text-center">
          Nenhum histórico de troca encontrado para a linha <strong>{selectedLine}</strong>.
        </Alert>
      );
    }

    // 5. Tabela com os dados
    return (
      <Table striped bordered hover responsive className="mt-3">
        <thead className="table-dark">
          <tr>
            <th>SKU Trocado</th>
            <th>Descrição</th>
            <th>Data/Hora da Troca</th>
          </tr>
        </thead>
        <tbody>
          {historico.map((item, index) => (
            <tr key={item.data_hora || index}> {/* Usar um ID único do item se disponível */}
              <td><Badge bg="secondary">{item.sku_trocado}</Badge></td>
              <td>{item.descricao}</td>
              <td>{formatarData(item.data_hora)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  };

  return (
    <div className="p-4">
      <Card>
        <Card.Header>
          <h2 className="h5 mb-0 d-flex align-items-center">
            <FaHistory className="me-2" />
            Histórico de Troca de Produtos
            {selectedLine && <Badge bg="primary" className="ms-2 fs-6">{selectedLine}</Badge>}
          </h2>
        </Card.Header>
        <Card.Body>
          {renderContent()}
        </Card.Body>
      </Card>
    </div>
  );
};

export default TrocasContent;