// Serviço para buscar dados de análise da linha
import axios from 'axios';
import { DJANGO_API_URL } from '../config/api';
export const fetchAnaliseProducao = async (linhaId, dataInicio, dataFim, granularidade = 'turno') => {
    const params = new URLSearchParams();
    if (dataInicio)
        params.append('data_inicio', dataInicio);
    if (dataFim)
        params.append('data_fim', dataFim);
    params.append('granularidade', granularidade);
    const response = await axios.get(`${DJANGO_API_URL}/linhas/${linhaId}/analise/producao/?${params.toString()}`);
    return response.data;
};
export const fetchAnaliseVelocidade = async (linhaId, dataInicio, dataFim, granularidade = 'turno') => {
    const params = new URLSearchParams();
    if (dataInicio)
        params.append('data_inicio', dataInicio);
    if (dataFim)
        params.append('data_fim', dataFim);
    params.append('granularidade', granularidade);
    const response = await axios.get(`${DJANGO_API_URL}/linhas/${linhaId}/analise/velocidade/?${params.toString()}`);
    return response.data;
};
export const fetchAnaliseSKU = async (linhaId, dataInicio, dataFim) => {
    const params = new URLSearchParams();
    if (dataInicio)
        params.append('data_inicio', dataInicio);
    if (dataFim)
        params.append('data_fim', dataFim);
    const response = await axios.get(`${DJANGO_API_URL}/linhas/${linhaId}/analise/sku/?${params.toString()}`);
    return response.data;
};
// Função auxiliar para calcular período rápido
export const calcularPeriodoRapido = (tipo) => {
    const agora = new Date();
    const dataFim = agora.toISOString();
    let dataInicio;
    switch (tipo) {
        case 'ultima_hora':
            dataInicio = new Date(agora.getTime() - 60 * 60 * 1000);
            break;
        case 'hoje':
            dataInicio = new Date(agora.setHours(0, 0, 0, 0));
            break;
        case 'ontem':
            const ontem = new Date(agora);
            ontem.setDate(ontem.getDate() - 1);
            ontem.setHours(0, 0, 0, 0);
            dataInicio = ontem;
            break;
        case 'ultimos_7_dias':
            dataInicio = new Date(agora.getTime() - 7 * 24 * 60 * 60 * 1000);
            break;
        case 'ultimos_30_dias':
            dataInicio = new Date(agora.getTime() - 30 * 24 * 60 * 60 * 1000);
            break;
        default:
            // turno_atual ou turno_anterior - deixar backend calcular
            return { dataInicio: '', dataFim: '' };
    }
    return {
        dataInicio: dataInicio.toISOString(),
        dataFim
    };
};
