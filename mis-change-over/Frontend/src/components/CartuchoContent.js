import ProgressBar from 'react-bootstrap/ProgressBar';
import { FaPlay, FaPause, FaRunning  } from 'react-icons/fa';

const CartuchoContent = () => { // Simula dados de linhas com progresso e status
  // Gerando dados fictícios para as linhas
  const linhas = Array.from({ length: 10 }, (_, index) => { // Cria 10 linhas com progresso aleatório
    // Formata o número da linha com dois dígitos
    // Exemplo: Linha 01, Linha 02, ..., Linha 10
    const linhaNumber = String(index + 1).padStart(2, '0'); // Garante que o número da linha tenha dois dígitos
    return {
      nome: `Linha ${linhaNumber}`, // Nome da linha formatado
      // Progresso aleatório entre 0 e 100
      progress: Math.floor(Math.random() * 100), // Gera um progresso aleatório
      // Status aleatório para simular se a linha está rodando ou parada
      isRunning: Math.random() > 0.5, // 50% de chance de estar rodando
      // Se estiver rodando, o progresso é maior que 0, caso contrário é 0
    };
  });

  return (
    <div className="tab-content">
      <h2>Cartucho</h2>
      <p>Conteúdo relacionado a cartuchos. Informações sobre os cartuchos, como tipos, especificações ou dados de produção.</p>
    
      <h3>Programa Andretti</h3>

      {linhas.map((linha, index) => (
        <div key={index} className="divLinhas"> 
          <p className="nomeLinha">{linha.nome}</p>
          <div className="progress-wrapper">
            <ProgressBar
              animated={linha.isRunning}
              now={linha.progress}
              label={`${linha.progress}%`}
              variant={linha.isRunning ? 'success' : 'warning'}
              className="speedLine"
            />
            <span className="status-icon">
              {linha.isRunning ? (
                <FaPlay className="running-icon" />
              ) : (
                <FaPause className="stopped-icon" />
              )}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default CartuchoContent;