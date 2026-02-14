document.addEventListener('DOMContentLoaded', function() {
  var syncButton = document.getElementById('sync-skus-aplipack');
  if (syncButton) {
      syncButton.addEventListener('click', function() {
          var linhaElement = document.getElementById('linha-info');
          if (!linhaElement) {
              console.error("Elemento #linha-info não encontrado.");
              updateFeedback("Erro interno: Informação da linha não encontrada.", "danger");
              return;
          }
          var linha = linhaElement.getAttribute('data-linha');
          if (!linha) {
              console.error("Atributo data-linha não encontrado em #linha-info.");
              updateFeedback("Erro interno: Atributo da linha não configurado.", "danger");
              return;
          }
          
          // Mostra um indicador de loading
          var container = document.getElementById('aplipack-skus-container');
          container.innerHTML = '<div class="d-flex justify-content-center align-items-center p-3"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Carregando...</span></div><span class="ms-2">Sincronizando com Aplipack...</span></div>';


          fetch(`/sincronizar-skus/?linha=${linha}`)
              .then(response => {
                  if (!response.ok) {
                      return response.json().then(err => { throw new Error(err.mensagem || `Erro ${response.status} ao sincronizar.`); });
                  }
                  return response.json();
              })
              .then(data => {
                  console.log("Dados recebidos do sincronizar-skus:", data.skus);
                  if (data.skus && data.skus.length > 0) {
                      var html = '<table class="table table-bordered table-hover">'; // Adicionado table-hover
                      html += '<thead class="table-dark"><tr>';
                      html += '<th>Cód. SKU</th><th>Descrição</th><th>Data OP</th><th>ID Ordem</th>';
                      html += '<th>Nº OP</th><th>DUN14</th><th>Validade</th><th>Qtd/Pallet</th>';
                      html += '<th>Status OP</th><th>Ação</th>';
                      html += '</tr></thead>';
                      html += '<tbody id="aplipack-tbody">'; // ID para a busca
                      data.skus.forEach(function(item) {
                          html += `<tr class="clickable-row-aplipack">
                              <td>${item.codigo_sku || ''}</td>
                              <td>${item.descricao_sku || ''}</td>
                              <td>${item.dataop || ''}</td>
                              <td>${item.id_ordem_prod || ''}</td>
                              <td>${item.numero_op || ''}</td>
                              <td>${item.dun14 || ''}</td>
                              <td>${item.validade || ''}</td>
                              <td>${item.quantidade_por_pallet || ''}</td>
                              <td>${item.status_op || ''}</td>
                              <td>
                                  <button class="btn btn-sm btn-primary enviar-sku-btn" 
                                          data-source="aplipack"
                                          data-linha="${linha}"
                                          data-sku="${item.codigo_sku || ''}" 
                                          data-descricao="${item.descricao_sku || ''}"
                                          data-dataop="${item.dataop || ''}"
                                          data-idordem="${item.id_ordem_prod || ''}"
                                          data-numeroop="${item.numero_op || ''}"
                                          data-dun14="${item.dun14 || ''}"
                                          data-validade="${item.validade || ''}"
                                          data-quantidade="${item.quantidade_por_pallet || ''}"
                                          data-status="${item.status_op || ''}">
                                      Enviar SKU
                                  </button>
                              </td>
                          </tr>`;
                      });
                      html += '</tbody></table>';
                      container.innerHTML = html;
                      
                      document.querySelectorAll('#aplipack-skus-container .enviar-sku-btn').forEach(btn => {
                          btn.addEventListener('click', function () {
                              window.showConfirmModal(this, 'aplipack');
                          });
                      });
                      updateFeedback("SKUs do Aplipack sincronizados com sucesso!", "success");
                  } else {
                      container.innerHTML = `<p class="text-muted">${data.mensagem || 'Nenhum SKU encontrado no Aplipack para esta linha.'}</p>`;
                      updateFeedback(data.mensagem || "Nenhum SKU encontrado no Aplipack para esta linha.", "info");
                  }
              })
              .catch(error => {
                  console.error('Erro ao sincronizar SKUs:', error);
                  container.innerHTML = `<div class="alert alert-danger">Erro ao sincronizar com Aplipack: ${error.message}</div>`;
                  updateFeedback(`Erro ao sincronizar SKUs: ${error.message}`, "danger");
              });
      });
  }
});