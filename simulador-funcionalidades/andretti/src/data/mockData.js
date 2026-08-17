import { subHours, format } from 'date-fns'

// ─── WAVES ────────────────────────────────────────────────────────────────────
export const waves = [
  { id: 1, nome: 'Wave 1 — Q1 2026', dataInicio: '2026-01-01', dataFim: '2026-03-31', ativa: false },
  { id: 2, nome: 'Wave 2 — Q2 2026', dataInicio: '2026-04-01', dataFim: '2026-06-30', ativa: true },
]

// ─── LINHAS ───────────────────────────────────────────────────────────────────
export const linhas = [
  { id: 1, nome: 'Linha 1', descricao: 'Enchedora A — 400g', formato: '400g', cor: '#6366f1' },
  { id: 2, nome: 'Linha 2', descricao: 'Enchedora B — 800g', formato: '800g', cor: '#f97316' },
  { id: 3, nome: 'Linha 3', descricao: 'Enchedora C — 1600g', formato: '1600g', cor: '#22c55e' },
  { id: 4, nome: 'Linha 4', descricao: 'Viscadora — Multiformato', formato: 'Multi', cor: '#a78bfa' },
]

// ─── METAS POR LINHA × WAVE ───────────────────────────────────────────────────
export const metas = [
  // Wave 1
  { id: 1, linhaId: 1, waveId: 1, velocidadePadrao: 120, velocidadeMeta: 145, unidade: 'ppm' },
  { id: 2, linhaId: 2, waveId: 1, velocidadePadrao: 85,  velocidadeMeta: 100, unidade: 'ppm' },
  { id: 3, linhaId: 3, waveId: 1, velocidadePadrao: 60,  velocidadeMeta: 72,  unidade: 'ppm' },
  { id: 4, linhaId: 4, waveId: 1, velocidadePadrao: 200, velocidadeMeta: 240, unidade: 'ppm' },
  // Wave 2
  { id: 5, linhaId: 1, waveId: 2, velocidadePadrao: 145, velocidadeMeta: 168, unidade: 'ppm' },
  { id: 6, linhaId: 2, waveId: 2, velocidadePadrao: 100, velocidadeMeta: 118, unidade: 'ppm' },
  { id: 7, linhaId: 3, waveId: 2, velocidadePadrao: 72,  velocidadeMeta: 85,  unidade: 'ppm' },
  { id: 8, linhaId: 4, waveId: 2, velocidadePadrao: 240, velocidadeMeta: 275, unidade: 'ppm' },
]

// ─── VELOCIDADES ATUAIS INICIAIS (base para simulação) ────────────────────────
// Wave 2 values
export const velocidadesBase = {
  1: 158, // 94% da meta (168) — quase lá
  2: 79,  // 67% da meta (118) — longe
  3: 84,  // 99% da meta (85)  — batendo meta!
  4: 182, // 66% da meta (275) — longe
}

// ─── GERADOR DE TREND (24h de leituras horárias) ─────────────────────────────
function gerarTrend(baseSpeed, meta, horas = 24) {
  const agora = new Date()
  return Array.from({ length: horas }, (_, i) => {
    const hora = subHours(agora, horas - 1 - i)
    const h = hora.getHours()
    // Simula padrão de turno: dips na troca de turno (06h, 14h, 22h)
    const trocaTurno = [6, 14, 22].includes(h)
    const base = trocaTurno
      ? baseSpeed * 0.72
      : h < 6 || h >= 22
      ? baseSpeed * 0.88
      : baseSpeed * (0.90 + Math.random() * 0.12)
    return {
      hora: format(hora, 'HH:mm'),
      velocidade: Math.round(Math.min(base + (Math.random() - 0.5) * 8, meta * 1.05)),
      meta,
      padrao: Math.round(baseSpeed),
    }
  })
}

export const trendsIniciais = {
  1: gerarTrend(158, 168),
  2: gerarTrend(79, 118),
  3: gerarTrend(84, 85),
  4: gerarTrend(182, 275),
}

// ─── CATEGORIAS POR ÁREA ──────────────────────────────────────────────────────
export const categoriasPorArea = {
  manutencao: [
    'Restauração de Condição Básica',
    'Manutenção Preventiva',
    'Melhoria de Equipamento',
    'Lubrificação e Ajuste',
  ],
  qualidade: [
    'Redução de Rejeição',
    'Controle de Processo',
    'Calibração de Equipamento',
    'Melhoria de Inspeção',
  ],
  eng_projetos: [
    'Automação',
    'Retrofit',
    'Novo Equipamento',
    'Infraestrutura',
  ],
  eng_processos: [
    'Otimização de Parâmetros',
    'Troca Rápida (SMED)',
    'Padronização',
    'Análise de Perdas',
  ],
}

export const areaConfig = {
  manutencao:   { label: 'Manutenção',          icon: '🔧', cor: '#f59e0b', corFundo: '#f59e0b18' },
  qualidade:    { label: 'Qualidade',            icon: '🔬', cor: '#8b5cf6', corFundo: '#8b5cf618' },
  eng_projetos: { label: 'Engenharia Projetos',  icon: '🏗️',  cor: '#3b82f6', corFundo: '#3b82f618' },
  eng_processos:{ label: 'Engenharia Processos', icon: '⚙️',  cor: '#10b981', corFundo: '#10b98118' },
}

// ─── AÇÕES ────────────────────────────────────────────────────────────────────
export const acoesIniciais = [
  {
    id: 1, linhaId: 1, waveId: 2,
    area: 'manutencao', categoria: 'Restauração de Condição Básica',
    descricao: 'Troca do motor da esteira de saída — desgaste avançado detectado',
    status: 'em_andamento', responsavel: 'João Silva',
    dataInsercao: '2026-04-01', prazoExecucao: '2026-04-10', dataRealizada: null,
  },
  {
    id: 2, linhaId: 2, waveId: 2,
    area: 'manutencao', categoria: 'Lubrificação e Ajuste',
    descricao: 'Lubrificação do sistema de dosagem e ajuste de folgas',
    status: 'concluida', responsavel: 'Carlos Matos',
    dataInsercao: '2026-04-01', prazoExecucao: '2026-04-05', dataRealizada: '2026-04-04',
  },
  {
    id: 3, linhaId: 3, waveId: 2,
    area: 'manutencao', categoria: 'Restauração de Condição Básica',
    descricao: 'Ajuste do tensor da correia transportadora principal',
    status: 'aberta', responsavel: 'Marcos Lima',
    dataInsercao: '2026-04-02', prazoExecucao: '2026-04-15', dataRealizada: null,
  },
  {
    id: 4, linhaId: 4, waveId: 2,
    area: 'manutencao', categoria: 'Melhoria de Equipamento',
    descricao: 'Instalação de encoder digital no eixo principal para controle de velocidade mais preciso',
    status: 'em_andamento', responsavel: 'Roberto Nunes',
    dataInsercao: '2026-04-01', prazoExecucao: '2026-04-30', dataRealizada: null,
  },
  {
    id: 5, linhaId: 1, waveId: 2,
    area: 'qualidade', categoria: 'Calibração de Equipamento',
    descricao: 'Calibração do sensor de nível de produto — leituras fora de spec a alta velocidade',
    status: 'em_andamento', responsavel: 'Ana Paula',
    dataInsercao: '2026-04-01', prazoExecucao: '2026-04-08', dataRealizada: null,
  },
  {
    id: 6, linhaId: 2, waveId: 2,
    area: 'qualidade', categoria: 'Redução de Rejeição',
    descricao: 'Análise da causa raiz de rejeitos na seladora automática acima de 85 ppm',
    status: 'aberta', responsavel: 'Fernanda Costa',
    dataInsercao: '2026-04-02', prazoExecucao: '2026-04-20', dataRealizada: null,
  },
  {
    id: 7, linhaId: 3, waveId: 2,
    area: 'qualidade', categoria: 'Controle de Processo',
    descricao: 'Revisão dos limites de controle de qualidade validados para a nova velocidade alvo',
    status: 'aberta', responsavel: 'Fernanda Costa',
    dataInsercao: '2026-04-03', prazoExecucao: '2026-04-25', dataRealizada: null,
  },
  {
    id: 8, linhaId: 1, waveId: 2,
    area: 'eng_projetos', categoria: 'Automação',
    descricao: 'Retrofit do sistema de alimentação de tampas com servomotor — eliminar gargalo',
    status: 'aberta', responsavel: 'Diego Henrique',
    dataInsercao: '2026-04-01', prazoExecucao: '2026-05-30', dataRealizada: null,
  },
  {
    id: 9, linhaId: 4, waveId: 2,
    area: 'eng_projetos', categoria: 'Novo Equipamento',
    descricao: 'Implantação de inspetor de nível por visão computacional — 100% de cobertura',
    status: 'em_andamento', responsavel: 'Diego Henrique',
    dataInsercao: '2026-04-01', prazoExecucao: '2026-06-15', dataRealizada: null,
  },
  {
    id: 10, linhaId: 2, waveId: 2,
    area: 'eng_processos', categoria: 'Otimização de Parâmetros',
    descricao: 'Otimização da temperatura e pressão de selagem para formato 800g em velocidade aumentada',
    status: 'em_andamento', responsavel: 'Priscila Ramos',
    dataInsercao: '2026-04-01', prazoExecucao: '2026-04-12', dataRealizada: null,
  },
  {
    id: 11, linhaId: 3, waveId: 2,
    area: 'eng_processos', categoria: 'Padronização',
    descricao: 'Padronização do tempo e critérios de aquecimento na virada de turno',
    status: 'concluida', responsavel: 'Priscila Ramos',
    dataInsercao: '2026-03-25', prazoExecucao: '2026-03-31', dataRealizada: '2026-03-28',
  },
  {
    id: 12, linhaId: 1, waveId: 2,
    area: 'eng_processos', categoria: 'Troca Rápida (SMED)',
    descricao: 'Redução do tempo de setup na troca de formato — meta: -40% vs atual',
    status: 'aberta', responsavel: 'Priscila Ramos',
    dataInsercao: '2026-04-02', prazoExecucao: '2026-04-30', dataRealizada: null,
  },
]

export const statusConfig = {
  aberta:       { label: 'Aberta',       cor: '#3b82f6', corFundo: '#3b82f620' },
  em_andamento: { label: 'Em Andamento', cor: '#f59e0b', corFundo: '#f59e0b20' },
  concluida:    { label: 'Concluída',    cor: '#22c55e', corFundo: '#22c55e20' },
  cancelada:    { label: 'Cancelada',    cor: '#6b7280', corFundo: '#6b728020' },
}
