import React from 'react';
import { Link } from 'react-router-dom';

function LinhasDisponiveis() {
  // Simulando dados do backend (substitua por uma chamada API real)
  const linhas = ['L01', 'L02', 'L03', 'L04'];
  const flexiveis = ['L01', 'L02'];
  const cartucho = ['L03'];

  return (
    <div>
      <h1 className="mb-4 text-center">Linhas de Produção Disponíveis</h1>
      <div className="row">
        <div className="col-md-6">
          <h2 className="h4">Linhas Flexíveis</h2>
          <div className="list-group">
            {flexiveis.map((linha) => (
              <Link
                key={linha}
                to={`/linha-detalhes/${linha}`}
                className="list-group-item list-group-item-action"
              >
                Linha {linha}
              </Link>
            ))}
          </div>
        </div>
        <div className="col-md-6">
          <h2 className="h4">Linhas Cartucho</h2>
          <div className="list-group">
            {cartucho.map((linha) => (
              <Link
                key={linha}
                to={`/linha-detalhes/${linha}`}
                className="list-group-item list-group-item-action"
              >
                Linha {linha}
              </Link>
            ))}
          </div>
        </div>
      </div>
      <hr />
      <div className="row mt-4">
        <div className="col-12">
          <h2 className="h4">Outras Linhas</h2>
          <div className="list-group">
            {linhas
              .filter((linha) => !flexiveis.includes(linha) && !cartucho.includes(linha))
              .map((linha) => (
                <Link
                  key={linha}
                  to={`/linha-detalhes/${linha}`}
                  className="list-group-item list-group-item-action"
                >
                  Linha {linha}
                </Link>
              ))}
          </div>
        </div>
      </div>
      <div className="mt-5 text-center">
        <a href="/linha-detalhes/test" className="btn btn-info">
          Página de Teste de SKUs
        </a>
      </div>
    </div>
  );
}

export default LinhasDisponiveis;