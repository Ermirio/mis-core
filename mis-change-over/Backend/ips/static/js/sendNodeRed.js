// Obter o valor da linha do atributo data
const linha = document.getElementById('linha-info').getAttribute('data-linha');

// Enviar ao Node-RED pelo Frontend
document.getElementById('send-node-red-frontend').addEventListener('click', () => {
    fetch('http://127.0.0.1:1880/execute', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message: 'Informação enviada pelo Frontend',
            linha: linha // Usando o valor extraído
        })
    })
    .then(response => {
        if (response.ok) {
            updateFeedback('Informação enviada ao Node-RED pelo Frontend com sucesso!');
        } else {
            updateFeedback('Erro ao enviar para o Node-RED pelo Frontend.', 'danger');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        updateFeedback('Erro ao enviar para o Node-RED pelo Frontend.', 'danger');
    });
});
