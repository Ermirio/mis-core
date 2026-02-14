        // Executar função no Django
        document.getElementById('execute-django').addEventListener('click', () => {
            fetch(`/executar-funcao/?linha={{ linha.nome }}`, { // URL definida no Django
                method: 'GET',
            })
            .then(response => response.json())
            .then(data => updateFeedback(data.mensagem)) // Atualiza feedback
            .catch(error => {
                console.error('Erro:', error);
                updateFeedback('Erro ao executar a função no Django.', 'danger');
            });
        });