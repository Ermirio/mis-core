// Enviar ao Node-RED pelo Django
document.getElementById('send-node-red-django').addEventListener('click', () => {
    // Obter o valor da linha do atributo data no momento do clique
    const linha = document.getElementById('linha-info').getAttribute('data-linha');

    // Verificar se o valor da linha foi recuperado corretamente
    if (!linha) {
        console.error('Erro: O valor da linha não foi encontrado.');
        updateFeedback('Erro: O valor da linha não foi encontrado.', 'danger');
        return;
    }

    // Fazer a requisição ao Django com a linha correta
    fetch(`/enviar-para-node-red/?linha=${linha}`, { // Substituir o valor dinamicamente
        method: 'GET',
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Erro na resposta do servidor');
        }
    })
    .then(data => updateFeedback(data.mensagem)) // Atualiza feedback
    .catch(error => {
        console.error('Erro:', error);
        updateFeedback('Erro ao enviar para o Node-RED via Django.', 'danger');
    });
});
