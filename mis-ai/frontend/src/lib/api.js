// api.js - Corrigido para usar padrão de URLs correto (/opc/ ao invés de /opc-)
// IMPORTANTE: Este arquivo deve substituir o src/lib/api.js do frontend

// Detecta automaticamente se está em desenvolvimento ou produção
const API_BASE_URL = process.env.NODE_ENV === 'production'
  ? '/predicao-api'  // Em produção, usa o proxy do Nginx
  : 'http://localhost:5004/api'  // Em desenvolvimento, acessa diretamente

class ApiClient {
  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
      }

      if (response.status === 204) { // Handle "No Content" responses
        return null;
      }

      return await response.json()
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error)
      throw error
    }
  }

  // Health check
  async healthCheck() {
    return this.request('/health')
  }

  // Lines
  async getLines() {
    return this.request('/lines')
  }

  async createLine(data) {
    return this.request('/lines', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateLine(lineId, data) {
    return this.request(`/lines/${lineId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteLine(lineId) {
    return this.request(`/lines/${lineId}`, {
      method: 'DELETE',
    })
  }

  // Targets
  async getTargets(line) {
    return this.request(`/targets?line=${encodeURIComponent(line)}`)
  }

  async createTarget(data) {
    return this.request('/targets', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateTarget(targetId, data) {
    return this.request(`/targets/${targetId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteTarget(targetId) {
    return this.request(`/targets/${targetId}`, {
      method: 'DELETE',
    })
  }

  // Models
  async getModels(targetId) {
    return this.request(`/models?target_id=${targetId}`)
  }

  async createModel(data) {
    return this.request('/models', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateModel(modelId, data) {
    return this.request(`/models/${modelId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteModel(modelId) {
    return this.request(`/models/${modelId}`, {
      method: 'DELETE',
    })
  }

  async trainModel(modelId) {
    return this.request(`/models/${modelId}/train`, {
      method: 'POST',
    })
  }

  async getModelStatus(modelId) {
    return this.request(`/models/${modelId}/status`)
  }

  // ADICIONE ESTE NOVO MÉTODO
  async getLastPrediction(modelId) {
    return this.request(`/models/${modelId}/last_prediction`)
}

  async predictWithModel(modelId) {
    return this.request(`/models/${modelId}/predict`, {
      method: 'POST',
    })
  }

  // Continuous Predictions
  async startContinuousPredictions(data) {
    return this.request('/predictions/continuous/start', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async stopContinuousPredictions(data) {
    return this.request('/predictions/continuous/stop', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getContinuousPredictionsStatus(modelId) {
    return this.request(`/predictions/continuous/status?model_id=${modelId}`)
  }

  // Data
  async saveManualData(data) {
    return this.request('/data/manual', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getData(params) {
    const queryParams = new URLSearchParams(params)
    return this.request(`/data?${queryParams.toString()}`)
  }
  
  // ==================== OPC - CORRIGIDO ====================
  // Mudado de /opc-variables para /opc/variables (padrão com barra)
  
  async getOPCVariables(line) {
    return this.request(`/opc/variables?line=${encodeURIComponent(line)}`)
  }

  async createOPCVariable(data) {
    return this.request('/opc/variables', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateOPCVariable(variableId, data) {
    return this.request(`/opc/variables/${variableId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteOPCVariable(variableId) {
    return this.request(`/opc/variables/${variableId}`, {
      method: 'DELETE',
    })
  }

  async startOPCLogging(line) {
    return this.request('/opc/logging/start', {
      method: 'POST',
      body: JSON.stringify({ line }),
    })
  }

  async stopOPCLogging(line) {
    return this.request('/opc/logging/stop', {
      method: 'POST',
      body: JSON.stringify({ line }),
    })
  }

  async getOPCLoggingStatus(line) {
    return this.request(`/opc/logging/status?line=${encodeURIComponent(line)}`)
  }

  async getOPCStatus() {
    return this.request('/opc/status')
  }

  async connectOPC() {
    return this.request('/opc/connect', {
      method: 'POST',
    })
  }

  async disconnectOPC() {
    return this.request('/opc/disconnect', {
      method: 'POST',
    })
  }

  async writeOPCVariable(nodeId, value) {
    return this.request('/opc/write', {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId, value }),
    })
  }

  async readOPCVariable(nodeId) {
    return this.request(`/opc/read?node_id=${encodeURIComponent(nodeId)}`)
  }

  async getOPCLogsByDate(line, date) {
    return this.request(`/opc/logs/by-date?line=${encodeURIComponent(line)}&date=${date}`)
  }

  async getOPCHistory(params) {
    const queryParams = new URLSearchParams(params)
    return this.request(`/opc/history?${queryParams.toString()}`)
  }
  
  // ==================== FIM OPC ====================
  
  // Compatibility methods (legacy API)
  async saveDensity(data) {
    return this.request('/density', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async predictDensity(data) {
    return this.request('/predict', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async trainDensityModel(data) {
    return this.request('/train', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getDensityModelStatus(line) {
    return this.request(`/model_status?line=${encodeURIComponent(line)}`)
  }
}


  

export const api = new ApiClient()

