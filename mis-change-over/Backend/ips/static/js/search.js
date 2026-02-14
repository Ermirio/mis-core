document.addEventListener('DOMContentLoaded', function () {
    // Busca dinâmica para SKUs Cadastrados
    const searchBarCadastrados = document.getElementById('search-bar-cadastrados');
    if (searchBarCadastrados) {
        searchBarCadastrados.addEventListener('input', function () {
            const searchValue = this.value.toLowerCase();
            const productList = document.getElementById('product-list-cadastrados');
            if (productList) {
                const rows = productList.getElementsByTagName('tr');
                Array.from(rows).forEach(row => {
                    const sku = row.cells[0]?.textContent.toLowerCase() || "";
                    const descricao = row.cells[1]?.textContent.toLowerCase() || "";
                    if (sku.includes(searchValue) || descricao.includes(searchValue)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            }
        });
    }

    // Busca dinâmica para SKUs Aplipack (a tabela é carregada dinamicamente)
    const searchBarAplipack = document.getElementById('search-bar-aplipack');
    if (searchBarAplipack) {
        searchBarAplipack.addEventListener('input', function () {
            const searchValue = this.value.toLowerCase();
            const aplipackTbody = document.getElementById('aplipack-tbody'); // Busca pelo ID do tbody
            if (aplipackTbody) {
                const rows = aplipackTbody.getElementsByTagName('tr');
                Array.from(rows).forEach(row => {
                    const sku = row.cells[0]?.textContent.toLowerCase() || "";
                    const descricao = row.cells[1]?.textContent.toLowerCase() || "";
                    const numeroOP = row.cells[4]?.textContent.toLowerCase() || ""; // Adicionando busca por Número OP
                    if (sku.includes(searchValue) || descricao.includes(searchValue) || numeroOP.includes(searchValue)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            }
        });
    }

    // Busca dinâmica para as últimas trocas
    const searchSwapsInput = document.getElementById('search-swaps');
    if (searchSwapsInput) {
        searchSwapsInput.addEventListener('input', function () {
            const searchValue = this.value.toLowerCase();
            const swapsList = document.getElementById('swaps-list');
            if (swapsList) {
                const rows = swapsList.getElementsByTagName('tr');
                Array.from(rows).forEach(row => {
                    const skuTrocado = row.cells[0]?.textContent.toLowerCase() || "";
                    const descricao = row.cells[1]?.textContent.toLowerCase() || "";
                    // const linha = row.cells[0]?.textContent.toLowerCase() || ""; // Linha não está mais nessa tabela
                    if (skuTrocado.includes(searchValue) || descricao.includes(searchValue)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            }
        });
    }
});