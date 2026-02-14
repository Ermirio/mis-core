import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Modal, Button } from 'react-bootstrap';

function LinhaDetalhes({ match }) {
  const [linhaNome] = useState(match.params.linhaNome);
  const [skus, setSkus] = useState([]);
  const [selectedSku, setSelectedSku] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [feedback, setFeedback] = useState({ message: '', type: '' });

  useEffect(() => {
    fetchSkus();
  }, [linhaNome]);

  const fetchSkus = () => {
    axios
      .get(`/sincronizar-skus/?linha=${linhaNome}`, {
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      })
      .then((response) => {
        setSkus(response.data.skus || []);
        setFeedback({ message: 'SKUs sincronizados com sucesso!', type: 'success' });
      })
      .catch((error) => {
        setFeedback({ message: `Erro ao sincronizar SKUs: ${error.message}`, type: 'danger' });
      });
  };

  const showConfirmModal = (sku) => {
    setSelectedSku(sku);
    setShowModal(true);
  };

  const handleConfirmSend = () => {
    if (!selectedSku) return;

    const payload = {
      linha: linhaNome,
      sku: selectedSku.codigo_sku,
      codigo_sku: selectedSku.codigo_sku,
      dun14: selectedSku.dun14,
      validade: selectedSku.validade,
      descricao: selectedSku.descricao_sku,
      dia: new Date().toLocaleDateString('pt-BR').split('/').join(''),
      hora: new Date().toLocaleTimeString('pt-BR', { hour12: false }).split(':').join(''),
    };

    axios
      .post('/api/trocar_sku/', payload, {
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      })
      .then((response) => {
        setFeedback({
          message: response.data.mensagem || 'Troca realizada com sucesso!',
          type: 'success',
        });
        setShowModal(false);
      })
      .catch((error) => {
        setFeedback({
          message: `Erro ao enviar troca: ${error.response?.data?.mensagem || error.message}`,
          type: 'danger',
        });
      });
  };

  const updateFeedback = (message, type) => {
    setFeedback({ message, type });
  };

  // Função para pegar CSRF token (simplificada)
  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  };

  return (
    <div>
      <h1 className="mb-4">Página de Teste de SKUs (Linha: {linhaNome})</h1>
      <p>Esta página utiliza dados de SKU de teste e não interage com o Aplipack real.</p>

      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h2 className="h5 mb-0">SKUs da Ordem de Produção (Dados de Teste)</h2>
          <Button variant="secondary" onClick={fetchSkus}>
            Carregar SKUs de Teste
          </Button>
        </div>
        <div className="card-body">
          <input
            type="text"
            id="search-bar-aplipack"
            className="form-control mb-3"
            placeholder="Buscar SKU, Descrição ou OP..."
            onChange={(e) => {
              const value = e.target.value.toLowerCase();
              const rows = document.querySelectorAll('#aplipack-tbody tr');
              rows.forEach((row) => {
                const sku = row.cells[0]?.textContent.toLowerCase() || '';
                const desc = row.cells[1]?.textContent.toLowerCase() || '';
                const op = row.cells[4]?.textContent.toLowerCase() || '';
                row.style.display = value && !(sku.includes(value) || desc.includes(value) || op.includes(value)) ? 'none' : '';
              });
            }}
          />
          <div className="table-container">
            {skus.length === 0 ? (
              <p className="text-muted">Clique em "Carregar SKUs de Teste" para ver os dados.</p>
            ) : (
              <table className="table table-bordered table-hover">
                <thead className="table-dark">
                  <tr>
                    <th>Cód. SKU</th>
                    <th>Descrição</th>
                    <th>Data OP</th>
                    <th>ID Ordem</th>
                    <th>Nº OP</th>
                    <th>DUN14</th>
                    <th>Validade</th>
                    <th>Qtd/Pallet</th>
                    <th>Status OP</th>
                    <th>Ação</th>
                  </tr>
                </thead>
                <tbody id="aplipack-tbody">
                  {skus.map((sku) => (
                    <tr key={sku.codigo_sku} className="clickable-row-aplipack">
                      <td>{sku.codigo_sku || ''}</td>
                      <td>{sku.descricao_sku || ''}</td>
                      <td>{sku.dataop || ''}</td>
                      <td>{sku.id_ordem_prod || ''}</td>
                      <td>{sku.numero_op || ''}</td>
                      <td>{sku.dun14 || ''}</td>
                      <td>{sku.validade || ''}</td>
                      <td>{sku.quantidade_por_pallet || ''}</td>
                      <td>{sku.status_op || ''}</td>
                      <td>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => showConfirmModal(sku)}
                        >
                          Enviar SKU
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      <div className="feedback-area">
        {feedback.message && (
          <div className={`alert alert-${feedback.type} alert-dismissible fade show`} role="alert">
            {feedback.message}
            <button
              type="button"
              className="btn-close"
              onClick={() => setFeedback({ message: '', type: '' })}
              aria-label="Close"
            ></button>
          </div>
        )}
      </div>

      <Modal show={showModal} onHide={() => setShowModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Confirmar Troca de SKU (Teste)</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            Você tem certeza que deseja enviar o seguinte SKU para a{' '}
            <strong>Linha {linhaNome}</strong>?
          </p>
          <table className="table table-bordered">
            <tbody>
              <tr>
                <th scope="row">Linha:</th>
                <td>{linhaNome}</td>
              </tr>
              <tr>
                <th scope="row">SKU:</th>
                <td>{selectedSku?.codigo_sku || ''}</td>
              </tr>
              <tr>
                <th scope="row">Descrição:</th>
                <td>{selectedSku?.descricao_sku || ''}</td>
              </tr>
              <tr>
                <th scope="row">DUN14:</th>
                <td>{selectedSku?.dun14 || ''}</td>
              </tr>
              <tr>
                <th scope="row">Validade:</th>
                <td>{selectedSku?.validade || ''}</td>
              </tr>
              <tr className="aplipack-info">
                <th scope="row">Data OP:</th>
                <td>{selectedSku?.dataop || ''}</td>
              </tr>
              <tr className="aplipack-info">
                <th scope="row">ID Ordem:</th>
                <td>{selectedSku?.id_ordem_prod || ''}</td>
              </tr>
              <tr className="aplipack-info">
                <th scope="row">Número OP:</th>
                <td>{selectedSku?.numero_op || ''}</td>
              </tr>
              <tr className="aplipack-info">
                <th scope="row">Qtd./Pallet:</th>
                <td>{selectedSku?.quantidade_por_pallet || ''}</td>
              </tr>
              <tr className="aplipack-info">
                <th scope="row">Status OP:</th>
                <td>{selectedSku?.status_op || ''}</td>
              </tr>
            </tbody>
          </table>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={handleConfirmSend}>
            Confirmar Envio (Teste)
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}

export default LinhaDetalhes;