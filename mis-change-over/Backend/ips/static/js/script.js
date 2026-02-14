console.log("script.js carregado - Versão atualizada em: ", new Date().toISOString());

document.addEventListener('DOMContentLoaded', function () {
    const confirmModalElement = document.getElementById('confirmModal');
    const confirmModal = confirmModalElement ? new bootstrap.Modal(confirmModalElement) : null;

    // Função para mostrar o modal de confirmação
    window.showConfirmModal = function(dataSourceElement, sourceType) {
        if (!confirmModal) {
            console.error("Modal de confirmação não encontrado.");
            return;
        }

        const linha = dataSourceElement.getAttribute('data-linha');
        const sku = dataSourceElement.getAttribute('data-sku');
        const descricao = dataSourceElement.getAttribute('data-descricao');
        const dun14 = dataSourceElement.getAttribute('data-dun14');
        const validade = dataSourceElement.getAttribute('data-validade');

        document.getElementById('modal-linha').innerText = linha;
        document.getElementById('modal-sku').innerText = sku;
        document.getElementById('modal-descricao').innerText = descricao;
        document.getElementById('modal-dun14').innerText = dun14;
        document.getElementById('modal-validade').innerText = validade;

        // Mostrar/ocultar campos específicos do Aplipack
        const aplipackInfoRows = document.querySelectorAll('.aplipack-info');
        if (sourceType === 'aplipack') {
            document.getElementById('modal-dataop').innerText = dataSourceElement.getAttribute('data-dataop');
            document.getElementById('modal-idordem').innerText = dataSourceElement.getAttribute('data-idordem');
            document.getElementById('modal-numeroop').innerText = dataSourceElement.getAttribute('data-numeroop');
            document.getElementById('modal-quantidade').innerText = dataSourceElement.getAttribute('data-quantidade');
            document.getElementById('modal-status').innerText = dataSourceElement.getAttribute('data-status');
            aplipackInfoRows.forEach(row => row.classList.remove('d-none'));
        } else {
            aplipackInfoRows.forEach(row => row.classList.add('d-none'));
             // Limpar campos se não for aplipack
            document.getElementById('modal-dataop').innerText = '';
            document.getElementById('modal-idordem').innerText = '';
            document.getElementById('modal-numeroop').innerText = '';
            document.getElementById('modal-quantidade').innerText = '';
            document.getElementById('modal-status').innerText = '';
        }
        confirmModal.show();
    }

    // Adiciona o evento de clique às linhas da tabela de SKUs Cadastrados
    document.querySelectorAll('.clickable-row-cadastrado').forEach(row => {
        row.addEventListener('click', function () {
            window.showConfirmModal(this, 'cadastrado');
        });
    });

    // Evento para o botão de confirmação no modal
    const confirmSendButton = document.getElementById('confirm-send');
    if (confirmSendButton) {
        confirmSendButton.addEventListener('click', function () {
            var linha = document.getElementById('modal-linha').textContent.trim();
            var sku = document.getElementById('modal-sku').textContent.trim();
            var codigo_sku = document.getElementById('modal-sku').textContent.trim(); 
            var dun14 = document.getElementById('modal-dun14').textContent.trim();
            var validade = document.getElementById('modal-validade').textContent.trim();
            var descricao = document.getElementById('modal-descricao').textContent.trim();

            const now = new Date();
            const dia = now.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }).split('/').join('');
            const hora = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).split(':').join('');

            const payload = {
                linha: linha,
                sku: sku,
                codigo_sku: codigo_sku,
                dun14: dun14,
                validade: validade,
                descricao: descricao,
                dia: dia,
                hora: hora
            };

            console.log("Enviando dados para /trocar_sku/:", payload);

            fetch('/trocar_sku/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // 'X-CSRFToken': getCookie('csrftoken') // Necessário se não usar @csrf_exempt
                },
                body: JSON.stringify(payload),
            })
            .then(response => response.json().then(data => ({
                status: response.status,
                body: data
            })))
            .then(({ status, body }) => {
                let feedbackMessage = body.mensagem || 'Ocorreu um erro desconhecido.';
                let feedbackType = 'danger';

                if (status >= 200 && status < 300) {
                    feedbackType = 'success';
                    if (body.erros && body.erros.length > 0) {
                        feedbackMessage += "<br><strong>Atenção - Erros parciais:</strong><br>" + body.erros.join("<br>");
                        feedbackType = 'warning'; // Pode ser warning se a operação principal foi ok, mas houve erros secundários
                    }
                } else {
                     if (body.erros && body.erros.length > 0) {
                        feedbackMessage += "<br><strong>Detalhes do Erro:</strong><br>" + body.erros.join("<br>");
                    }
                }
                updateFeedback(feedbackMessage, feedbackType);
            })
            .catch(error => {
                console.error('Erro ao enviar para o Django:', error);
                updateFeedback('Erro crítico ao enviar a troca de SKU: ' + error.message, 'danger');
            });

            if(confirmModal) confirmModal.hide();
        });
    }

    // Atualizar feedback na página
    window.updateFeedback = function(message, type = 'success') {
        const feedbackArea = document.getElementById('feedback-area');
        if (feedbackArea) {
            feedbackArea.innerHTML = `
                <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
             // Scroll para a área de feedback para que o usuário veja a mensagem
            feedbackArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // Função para pegar o CSRF token (se necessário)
    // function getCookie(name) {
    //     let cookieValue = null;
    //     if (document.cookie && document.cookie !== '') {
    //         const cookies = document.cookie.split(';');
    //         for (let i = 0; i < cookies.length; i++) {
    //             const cookie = cookies[i].trim();
    //             if (cookie.substring(0, name.length + 1) === (name + '=')) {
    //                 cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
    //                 break;
    //             }
    //         }
    //     }
    //     return cookieValue;
    // }
});