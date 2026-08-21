/**
 * Centralized mock / demo data for all pages.
 * Activated automatically when backends return empty or fail.
 * Remove this module when production data is available.
 */
// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function seededRandom(seed) {
    let s = seed;
    return () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return (s >>> 0) / 0xffffffff; };
}
function genTimestamps(n, hoursBack = 8) {
    const now = Date.now();
    const step = (hoursBack * 3600000) / n;
    return Array.from({ length: n }, (_, i) => new Date(now - (n - i) * step).toISOString());
}
function genValues(n, mean, std, seed = 42) {
    const rand = seededRandom(seed);
    return Array.from({ length: n }, () => {
        const u1 = Math.max(1e-10, rand());
        const u2 = rand();
        const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
        return Math.round((mean + z * std) * 100) / 100;
    });
}
// ---------------------------------------------------------------------------
// LineAnalytics — Flask /analyze/* mock responses
// ---------------------------------------------------------------------------
export function mockAnalyzeTimeseries(variables) {
    const n = 120;
    const timestamps = genTimestamps(n, 8);
    const result = {};
    variables.forEach((v, idx) => {
        const mean = v.nominal ?? (v.lsl != null && v.usl != null ? (v.lsl + v.usl) / 2 : 50);
        const std = v.usl != null && v.lsl != null ? (v.usl - v.lsl) / 8 : mean * 0.05;
        const values = genValues(n, mean, std, idx * 17 + 7);
        result[v.alias] = {
            timestamps,
            values,
            stats: {
                mean: parseFloat((values.reduce((a, b) => a + b, 0) / n).toFixed(3)),
                ucl: parseFloat((mean + 3 * std).toFixed(3)),
                lcl: parseFloat((mean - 3 * std).toFixed(3)),
            },
        };
    });
    return result;
}
export function mockAnalyzeStats(variables) {
    return variables.map((v, idx) => {
        const mean = v.nominal ?? (v.lsl != null && v.usl != null ? (v.lsl + v.usl) / 2 : 50);
        const std = v.usl != null && v.lsl != null ? (v.usl - v.lsl) / 8 : mean * 0.05;
        const count = 480;
        const cp = v.lsl != null && v.usl != null ? (v.usl - v.lsl) / (6 * std) : 1.33;
        const cpk = Math.min(cp, cp * 0.95);
        const nBins = 10;
        const binW = std * 0.6;
        const bins = Array.from({ length: nBins + 1 }, (_, i) => parseFloat((mean - nBins / 2 * binW + i * binW).toFixed(3)));
        const rand = seededRandom(idx * 31 + 13);
        const rawCounts = Array.from({ length: nBins }, (_, i) => {
            const x = (bins[i] + bins[i + 1]) / 2;
            const z = (x - mean) / std;
            return Math.max(1, Math.round(count * 0.4 * Math.exp(-0.5 * z * z) + rand() * 5));
        });
        return {
            variable: v.alias,
            stats: { mean: parseFloat(mean.toFixed(3)), std: parseFloat(std.toFixed(3)), count, cpk: parseFloat(cpk.toFixed(2)), cp: parseFloat(cp.toFixed(2)) },
            histogram: { bins, counts: rawCounts },
        };
    });
}
export function mockAnalyzeCorrelation(variables) {
    const n = variables.length;
    const rand = seededRandom(77);
    const matrix = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => {
        if (i === j)
            return 1.0;
        const v = parseFloat((rand() * 1.6 - 0.8).toFixed(4));
        return v;
    }));
    // make symmetric
    for (let i = 0; i < n; i++)
        for (let j = 0; j < i; j++)
            matrix[j][i] = matrix[i][j];
    const pValues = matrix.map(row => row.map(v => v === 1 ? 0 : parseFloat((Math.abs(1 - Math.abs(v)) * 0.05).toFixed(4))));
    return {
        correlation_matrix: {
            columns: variables.map(v => v.alias.split(' - ').slice(-1)[0]),
            values: matrix,
            p_values: pValues,
            method: 'pearson',
            n_points: 480,
            resample_rule: '5T',
        },
    };
}
// ---------------------------------------------------------------------------
// LineDeepView — Flask endpoint mocks
// ---------------------------------------------------------------------------
export const MOCK_LINE_OVERVIEW_STATUS = {
    status: 'running',
    state_code: 1,
    equipamentos: [
        { codigo: 'ENV-01-ENCR', nome: 'Enchedora', status: 'running', velocidade_atual: 108, oee: 0.82, contagem_saida: 4791, descarte: 29 },
        { codigo: 'ENV-01-TAMP', nome: 'Tampadora', status: 'warning', velocidade_atual: 98, oee: 0.61, contagem_saida: 4650, descarte: 141 },
        { codigo: 'ENV-01-ROT', nome: 'Rotuladora', status: 'running', velocidade_atual: 105, oee: 0.78, contagem_saida: 4650, descarte: 0 },
    ],
};
export const MOCK_LINE_KPIS = {
    oee: 0.72, availability: 0.88, performance: 0.81, quality: 0.98,
    velocidade_atual: 108, producao_turno: 4791, meta_hora: 600,
    descarte_perc: 0.6,
};
export const MOCK_LINE_OLE = {
    ole: 0.72, oee: 0.72,
    throughput: 4791,
    descarte_tons: 0.029,
};
export const MOCK_EQUIPMENT_DADOS = (code) => ({
    equipamento: code,
    timestamp: new Date().toISOString(),
    status: 'online',
    medicoes: {
        velocidade_atual: 108, contagem_entrada: 4820, contagem_saida: 4791,
        descarte: 29, percentual_descarte: 0.6,
        temperatura: 20.4, pressao: 2.6,
        estado: 'Produzindo', estado_code: 1,
        oee: 0.82, oee_realtime: 0.82,
    },
});
export const MOCK_DIAGNOSTICS_ALERTS = [
    { codigo: 'WARN-001', descricao: 'Velocidade abaixo da meta por 12 min', nivel: 'warning', timestamp: new Date(Date.now() - 720000).toISOString() },
    { codigo: 'INFO-001', descricao: 'Troca de SKU concluída', nivel: 'info', timestamp: new Date(Date.now() - 3600000).toISOString() },
];
// ---------------------------------------------------------------------------
// FactoryManagementPanel — Flask /fabrica/* mocks
// ---------------------------------------------------------------------------
export const MOCK_FABRICA_KPIS = {
    oee_fabril_real: 73,
    oee_fabril_planejado: 80,
    producao_real_t: 48.2,
    producao_planejada_t: 56.0,
    vazao_total_tph: 6.1,
    vazao_necessaria_tph: 7.0,
    linhas: [
        { linha: 'ENV-01', status: 'Rodando', oee_real: 82, oee_planejado: 80, producao_real_t: 9.6, producao_planejada_t: 10.0, tph_real: 1.2 },
        { linha: 'ENV-02', status: 'Rodando', oee_real: 58, oee_planejado: 80, producao_real_t: 6.4, producao_planejada_t: 10.0, tph_real: 0.8 },
        { linha: 'ENV-03', status: 'Parado', oee_real: 31, oee_planejado: 80, producao_real_t: 2.2, producao_planejada_t: 10.0, tph_real: 0.3 },
        { linha: 'EMP-01', status: 'Rodando', oee_real: 79, oee_planejado: 80, producao_real_t: 7.6, producao_planejada_t: 8.0, tph_real: 1.0 },
        { linha: 'EMP-02', status: 'Offline', oee_real: 0, oee_planejado: 80, producao_real_t: 0.0, producao_planejada_t: 8.0, tph_real: 0.0 },
        { linha: 'EMP-03', status: 'Rodando', oee_real: 88, oee_planejado: 80, producao_real_t: 8.8, producao_planejada_t: 8.0, tph_real: 1.1 },
        { linha: 'PAL-01', status: 'Rodando', oee_real: 75, oee_planejado: 80, producao_real_t: 7.2, producao_planejada_t: 8.0, tph_real: 0.9 },
        { linha: 'PAL-02', status: 'Offline', oee_real: 0, oee_planejado: 80, producao_real_t: 0.0, producao_planejada_t: 8.0, tph_real: 0.0 },
        { linha: 'ROT-01', status: 'Rodando', oee_real: 61, oee_planejado: 80, producao_real_t: 3.6, producao_planejada_t: 4.0, tph_real: 0.5 },
        { linha: 'ROT-02', status: 'Rodando', oee_real: 91, oee_planejado: 80, producao_real_t: 2.8, producao_planejada_t: 4.0, tph_real: 0.4 },
    ],
};
export const MOCK_FABRICA_MAPA = [
    { linha: 'ENV-01', status: 'Rodando', ole: 82, layout: { pos_x: 0, pos_y: 0, w: 1, h: 1 } },
    { linha: 'ENV-02', status: 'Rodando', ole: 58, layout: { pos_x: 1, pos_y: 0, w: 1, h: 1 } },
    { linha: 'ENV-03', status: 'Parado', ole: 31, layout: { pos_x: 2, pos_y: 0, w: 1, h: 1 } },
    { linha: 'EMP-01', status: 'Rodando', ole: 79, layout: { pos_x: 3, pos_y: 0, w: 1, h: 1 } },
    { linha: 'EMP-02', status: 'Offline', ole: 0, layout: { pos_x: 4, pos_y: 0, w: 1, h: 1 } },
    { linha: 'EMP-03', status: 'Rodando', ole: 88, layout: { pos_x: 5, pos_y: 0, w: 1, h: 1 } },
    { linha: 'PAL-01', status: 'Rodando', ole: 75, layout: { pos_x: 0, pos_y: 1, w: 1, h: 1 } },
    { linha: 'PAL-02', status: 'Offline', ole: 0, layout: { pos_x: 1, pos_y: 1, w: 1, h: 1 } },
    { linha: 'ROT-01', status: 'Rodando', ole: 61, layout: { pos_x: 2, pos_y: 1, w: 1, h: 1 } },
    { linha: 'ROT-02', status: 'Rodando', ole: 91, layout: { pos_x: 3, pos_y: 1, w: 1, h: 1 } },
];
// ---------------------------------------------------------------------------
// WasteAnalysisDashboard — Django /descartes/* mocks
// ---------------------------------------------------------------------------
export const MOCK_DESCARTES_LINHAS = [
    { id: 1, codigo: 'ENV-01', nome: 'Envase 01' },
    { id: 2, codigo: 'ENV-02', nome: 'Envase 02' },
    { id: 3, codigo: 'ENV-03', nome: 'Envase 03' },
    { id: 4, codigo: 'EMP-01', nome: 'Empacotamento 01' },
    { id: 5, codigo: 'EMP-02', nome: 'Empacotamento 02' },
    { id: 6, codigo: 'EMP-03', nome: 'Empacotamento 03' },
    { id: 7, codigo: 'PAL-01', nome: 'Paletização 01' },
    { id: 9, codigo: 'ROT-01', nome: 'Rotulagem 01' },
    { id: 10, codigo: 'ROT-02', nome: 'Rotulagem 02' },
];
export const MOCK_DESCARTES_RESUMO = {
    periodo: 'turno',
    periodo_label: 'Turno Atual',
    consolidado: {
        descarte_tons: 0.42,
        descarte_percentual: 0.87,
        producao_tons: 48.2,
        total_unidades: 420,
    },
    por_linha: [
        { linha: 'Envase 01', codigo: 'ENV-01', descarte_tons: 0.029, descarte_percentual: 0.60, producao_tons: 4.8, unidades_ruins: 29 },
        { linha: 'Envase 02', codigo: 'ENV-02', descarte_tons: 0.141, descarte_percentual: 2.20, producao_tons: 6.4, unidades_ruins: 141 },
        { linha: 'Envase 03', codigo: 'ENV-03', descarte_tons: 0.088, descarte_percentual: 4.00, producao_tons: 2.2, unidades_ruins: 88 },
        { linha: 'Empacotamento 01', codigo: 'EMP-01', descarte_tons: 0.062, descarte_percentual: 0.82, producao_tons: 7.6, unidades_ruins: 62 },
        { linha: 'Empacotamento 03', codigo: 'EMP-03', descarte_tons: 0.019, descarte_percentual: 0.22, producao_tons: 8.8, unidades_ruins: 19 },
        { linha: 'Paletização 01', codigo: 'PAL-01', descarte_tons: 0.008, descarte_percentual: 0.11, producao_tons: 7.2, unidades_ruins: 8 },
        { linha: 'Rotulagem 01', codigo: 'ROT-01', descarte_tons: 0.051, descarte_percentual: 1.42, producao_tons: 3.6, unidades_ruins: 51 },
        { linha: 'Rotulagem 02', codigo: 'ROT-02', descarte_tons: 0.022, descarte_percentual: 0.79, producao_tons: 2.8, unidades_ruins: 22 },
    ],
    top_equipamentos: [
        { equipamento: 'Enchedora ENV-02', linha: 'ENV-02', unidades: 141, tons: 0.141, percentual: 2.20 },
        { equipamento: 'Enchedora ENV-03', linha: 'ENV-03', unidades: 88, tons: 0.088, percentual: 4.00 },
        { equipamento: 'Formadora EMP-01', linha: 'EMP-01', unidades: 62, tons: 0.062, percentual: 0.82 },
        { equipamento: 'Rotuladora ROT-01', linha: 'ROT-01', unidades: 51, tons: 0.051, percentual: 1.42 },
        { equipamento: 'Tampadora ENV-01', linha: 'ENV-01', unidades: 29, tons: 0.029, percentual: 0.60 },
    ],
    linha_maior_descarte: {
        linha: 'Envase 03',
        descarte_tons: 0.088,
        descarte_percentual: 4.00,
    },
    evolucao_temporal: Array.from({ length: 8 }, (_, i) => ({
        hora: `${(6 + i).toString().padStart(2, '0')}:00`,
        descarte: parseFloat((0.04 + Math.sin(i * 0.8) * 0.02).toFixed(3)),
        producao: parseFloat((5.8 + Math.cos(i * 0.5) * 0.4).toFixed(2)),
    })),
    descarte_por_estado: [
        { estado_code: 4, estado_label: 'Produzindo', tons: 0.22, percentual: 52 },
        { estado_code: 5, estado_label: 'Parado', tons: 0.09, percentual: 21 },
        { estado_code: 9, estado_label: 'Manutenção', tons: 0.07, percentual: 17 },
        { estado_code: 1, estado_label: 'Aguardando', tons: 0.04, percentual: 10 },
    ],
};
// ---------------------------------------------------------------------------
// GiveAwayDashboard — Django /giveaway/* mocks
// ---------------------------------------------------------------------------
export const MOCK_GIVEAWAY_RESUMO = {
    consolidado: { giveaway_kg: 186.4, giveaway_percent: 0.39, producao_ref_kg: 48200 },
    por_linha: [
        { linha: 'Envase 01', codigo: 'ENV-01', equipamento_leitura: 'ENV-01-BAL', giveaway_kg: 38.2, giveaway_percent: 0.40, producao_unidades: 4791, producao_nominal_kg: 9582 },
        { linha: 'Envase 02', codigo: 'ENV-02', equipamento_leitura: 'ENV-02-BAL', giveaway_kg: 29.1, giveaway_percent: 0.45, producao_unidades: 3200, producao_nominal_kg: 6400 },
        { linha: 'Empacotamento 01', codigo: 'EMP-01', equipamento_leitura: 'EMP-01-BAL', giveaway_kg: 42.8, giveaway_percent: 0.56, producao_unidades: 3800, producao_nominal_kg: 7600 },
        { linha: 'Empacotamento 03', codigo: 'EMP-03', equipamento_leitura: 'EMP-03-BAL', giveaway_kg: 19.3, giveaway_percent: 0.22, producao_unidades: 4400, producao_nominal_kg: 8800 },
        { linha: 'Paletização 01', codigo: 'PAL-01', equipamento_leitura: 'PAL-01-BAL', giveaway_kg: 28.6, giveaway_percent: 0.40, producao_unidades: 1200, producao_nominal_kg: 3600 },
        { linha: 'Rotulagem 01', codigo: 'ROT-01', equipamento_leitura: 'ROT-01-BAL', giveaway_kg: 14.1, giveaway_percent: 0.20, producao_unidades: 7200, producao_nominal_kg: 7200 },
        { linha: 'Rotulagem 02', codigo: 'ROT-02', equipamento_leitura: 'ROT-02-BAL', giveaway_kg: 14.3, giveaway_percent: 0.16, producao_unidades: 8800, producao_nominal_kg: 8800 },
    ],
};
// ---------------------------------------------------------------------------
// DiagnosticosLogs — Flask /health/system + /realtime/all mocks
// ---------------------------------------------------------------------------
export const MOCK_SYSTEM_HEALTH = {
    influxdb: true, django: true, coletor: true,
    details: {
        influxdb: { latency_ms: 12, version: '1.8.10' },
        django: { latency_ms: 18, version: '4.2' },
        coletor: { last_write: new Date(Date.now() - 8000).toISOString(), tags_active: 47 },
    },
};
export const MOCK_REALTIME_ALL = Object.fromEntries(['ENV-01-ENCR', 'ENV-01-TAMP', 'ENV-01-ROT', 'EMP-01-FORM', 'PAL-01-ROBO'].map((code) => [
    code,
    {
        timestamp: new Date().toISOString(),
        status: 'online',
        medicoes: { velocidade_atual: 100 + Math.random() * 20, estado: 1, oee: 0.78 },
    },
]));
// ---------------------------------------------------------------------------
// LineManagement — Flask /linha/{id}/status mock
// ---------------------------------------------------------------------------
export function mockLinhaStatus(linhaId) {
    const makeEquip = (sufixo, nome, saida, vel, descarte, oee, disponibilidade, performance, qualidade, temp, pressao) => ({
        equipamento: `${linhaId}-${sufixo}`,
        nome,
        medicoes: {
            contagem_entrada: saida + descarte,
            contagem_saida: saida,
            velocidade_atual: vel,
            descarte,
            percentual_descarte: parseFloat(((descarte / (saida + descarte)) * 100).toFixed(2)),
            oee,
            disponibilidade,
            performance,
            qualidade,
            temperatura: temp,
            pressao,
            planejado_op: 120,
            formato_gramas: 500,
            descricao: 'SKU-DEMO-001',
            sku_codigo: 'SKU-001',
            ordem_producao: 'OP-2026-001',
        },
    });
    return {
        linha: linhaId,
        timestamp: new Date().toISOString(),
        status: 'running',
        equipamentos: [
            makeEquip('ENCR', 'Enchedora', 4791, 108, 29, 82.0, 91.0, 89.0, 99.4, 20.4, 2.6),
            makeEquip('TAMP', 'Tampadora', 4650, 98, 141, 61.0, 78.0, 77.0, 97.0, 22.1, 2.2),
            makeEquip('ROT', 'Rotuladora', 4650, 105, 0, 78.0, 92.0, 84.0, 100, 19.8, 0.0),
        ],
        agregados: {
            total_equipamentos: 3,
            total_contagem_saida: 4650,
            total_descarte: 170,
            media_oee: 73.7,
            media_velocidade: 103.7,
        },
    };
}
