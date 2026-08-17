import { useState, useEffect, useRef } from 'react'
import { velocidadesBase, metas } from '../data/mockData'
import { format } from 'date-fns'

const INTERVALO_MS = 8000 // simula leitura OPC a cada 8s (em produção: 1-10 min)
const VARIACAO_MAX = 0.04  // ±4% de flutuação por leitura

function flutuarVelocidade(atual, base, metaValor) {
  const variacao = atual * VARIACAO_MAX * (Math.random() * 2 - 1)
  // Mantém velocidade em torno da base com drift leve
  const drift = (base - atual) * 0.05
  const nova = atual + variacao + drift
  // Limita entre 50% e 110% da meta
  return Math.round(Math.max(metaValor * 0.50, Math.min(nova, metaValor * 1.10)))
}

export function useSimulatedSpeed(waveId) {
  const [velocidades, setVelocidades] = useState(() => ({ ...velocidadesBase }))
  const [ultimaLeitura, setUltimaLeitura] = useState(() => format(new Date(), 'HH:mm:ss'))
  const [atualizado, setAtualizado] = useState({})
  const intervalRef = useRef(null)

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setVelocidades(prev => {
        const novas = {}
        const marcados = {}
        Object.keys(prev).forEach(linhaId => {
          const id = Number(linhaId)
          const meta = metas.find(m => m.linhaId === id && m.waveId === waveId)
          if (!meta) { novas[id] = prev[id]; return }
          novas[id] = flutuarVelocidade(prev[id], velocidadesBase[id], meta.velocidadeMeta)
          marcados[id] = true
        })
        return novas
      })
      setAtualizado(prev => {
        const novo = {}
        Object.keys(velocidadesBase).forEach(id => { novo[id] = true })
        return novo
      })
      setUltimaLeitura(format(new Date(), 'HH:mm:ss'))

      // Remove o flash de "atualizado" após 1.2s
      setTimeout(() => setAtualizado({}), 1200)
    }, INTERVALO_MS)

    return () => clearInterval(intervalRef.current)
  }, [waveId])

  return { velocidades, ultimaLeitura, atualizado }
}
