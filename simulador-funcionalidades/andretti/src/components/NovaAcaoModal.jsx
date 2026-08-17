import React, { useState, useEffect } from 'react'
import { X, Plus } from 'lucide-react'
import { linhas, categoriasPorArea, areaConfig, waves } from '../data/mockData'

const AREAS = Object.keys(areaConfig)

export default function NovaAcaoModal({ areaInicial, waveId, onSalvar, onFechar }) {
  const [form, setForm] = useState({
    area:           areaInicial || 'manutencao',
    linhaId:        1,
    categoria:      '',
    descricao:      '',
    responsavel:    '',
    prazoExecucao:  '',
    status:         'aberta',
  })

  useEffect(() => {
    setForm(prev => ({ ...prev, area: areaInicial || 'manutencao', categoria: '' }))
  }, [areaInicial])

  const categorias = categoriasPorArea[form.area] || []

  function handle(field, value) {
    setForm(prev => ({
      ...prev,
      [field]: value,
      ...(field === 'area' ? { categoria: '' } : {}),
    }))
  }

  function salvar(e) {
    e.preventDefault()
    if (!form.descricao || !form.responsavel || !form.prazoExecucao || !form.categoria) return
    onSalvar({
      ...form,
      linhaId: Number(form.linhaId),
      waveId,
      dataInsercao: new Date().toISOString().split('T')[0],
      dataRealizada: null,
    })
  }

  const cfg = areaConfig[form.area]

  return (
    <div className="modal-overlay" onClick={onFechar}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ borderBottom: `2px solid ${cfg.cor}40` }}>
          <div>
            <h3 className="modal-title">
              <span>{cfg.icon}</span> Nova Ação
            </h3>
            <p className="modal-subtitle" style={{ color: cfg.cor }}>
              {cfg.label}
            </p>
          </div>
          <button className="modal-close" onClick={onFechar}>
            <X size={18} />
          </button>
        </div>

        <form className="modal-form" onSubmit={salvar}>
          {/* Área */}
          <div className="form-group">
            <label className="form-label">Área Responsável</label>
            <div className="area-selector">
              {AREAS.map(a => {
                const c = areaConfig[a]
                return (
                  <button
                    key={a}
                    type="button"
                    className={`area-btn ${form.area === a ? 'active' : ''}`}
                    style={form.area === a
                      ? { background: c.cor, color: '#fff', borderColor: c.cor }
                      : { borderColor: c.cor + '50', color: c.cor }
                    }
                    onClick={() => handle('area', a)}
                  >
                    {c.icon} {c.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Linha + Categoria */}
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Linha</label>
              <select className="form-select" value={form.linhaId} onChange={e => handle('linhaId', e.target.value)}>
                {linhas.map(l => (
                  <option key={l.id} value={l.id}>{l.nome} — {l.descricao}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Categoria</label>
              <select className="form-select" value={form.categoria} onChange={e => handle('categoria', e.target.value)} required>
                <option value="">Selecione...</option>
                {categorias.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          {/* Descrição */}
          <div className="form-group">
            <label className="form-label">Descrição da Ação</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="Descreva a ação necessária para aumentar a velocidade..."
              value={form.descricao}
              onChange={e => handle('descricao', e.target.value)}
              required
            />
          </div>

          {/* Responsável + Prazo */}
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Responsável</label>
              <input
                className="form-input"
                type="text"
                placeholder="Nome do responsável"
                value={form.responsavel}
                onChange={e => handle('responsavel', e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Prazo de Execução</label>
              <input
                className="form-input"
                type="date"
                value={form.prazoExecucao}
                onChange={e => handle('prazoExecucao', e.target.value)}
                required
              />
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-cancelar" onClick={onFechar}>
              Cancelar
            </button>
            <button type="submit" className="btn-salvar" style={{ background: cfg.cor }}>
              <Plus size={15} /> Adicionar Ação
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
