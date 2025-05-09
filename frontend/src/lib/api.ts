import axios from 'axios'

// Create Axios instance with base URL pointing to Flask backend
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'
const API_KEY = import.meta.env.VITE_API_KEY || 'your-secret-api-key-here'

// Changed from export to const, since it's unused as an export
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  },
  timeout: 10000, // 10 seconds timeout
})

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log the error for debugging
    console.error('API Error:', error.message);
    
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      console.error('Error status:', error.response.status);
      console.error('Error data:', error.response.data);
    } else if (error.request) {
      // The request was made but no response was received
      console.error('No response received:', error.request);
    }
    
    // Forward the error to the caller
    return Promise.reject(error);
  }
);

// Mock data for development/testing
const MOCK_STATS = {
  total_alerts: 158,
  new_alerts: 24,
  resolved_alerts: 126,
  false_positives: 8,
  active_agents: 12,
  total_rules: 32,
  active_rules: 28,
}

const MOCK_ALERTS_BY_STATUS = [
  { status: 'new', count: 24 },
  { status: 'in_progress', count: 8 },
  { status: 'resolved', count: 126 },
  { status: 'false_positive', count: 8 },
]

const MOCK_ALERTS_BY_TIME_7D = Array.from({ length: 7 }, (_, i) => {
  const date = new Date();
  date.setDate(date.getDate() - (6 - i));
  return {
    date: date.toISOString().split('T')[0],
    count: Math.floor(Math.random() * 15) + 5,
  }
})

const MOCK_AGENTS = [
  {
    id: '1',
    hostname: 'PC1',
    ip_address: '192.168.1.101',
    os_info: 'Windows 10',
    version: '1.2.0',
    status: 'active',
    last_seen: new Date().toISOString(),
    registered_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '2',
    hostname: 'PC2',
    ip_address: '192.168.1.102',
    os_info: 'Windows 10',
    version: '1.2.0',
    status: 'active',
    last_seen: new Date().toISOString(),
    registered_at: new Date(Date.now() - 25 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '3',
    hostname: 'PC3',
    ip_address: '192.168.1.103',
    os_info: 'Windows 10',
    version: '1.2.0',
    status: 'inactive',
    last_seen: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    registered_at: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString(),
  },
]

// Dashboard API functions
export const dashboardApi = {
  getStats: async () => {
    try {
      const response = await api.get('/api/dashboard/stats')
      return response.data
    } catch (error) {
      console.warn('Error fetching dashboard stats, using mock data:', error)
      return MOCK_STATS
    }
  },
  
  getAlertsByStatus: async () => {
    try {
      const response = await api.get('/api/dashboard/alerts-by-status')
      return response.data
    } catch (error) {
      console.warn('Error fetching alerts by status, using mock data:', error)
      return MOCK_ALERTS_BY_STATUS
    }
  },
  
  getAlertsByTimeRange: async (range = '7d') => {
    try {
      const response = await api.get(`/api/dashboard/alerts-by-time?range=${range}`)
      return response.data
    } catch (error) {
      console.warn('Error fetching alerts by time, using mock data:', error)
      // For simplicity, always return the 7d mock data
      return MOCK_ALERTS_BY_TIME_7D
    }
  },
  
  getAgentStats: async () => {
    try {
      const response = await api.get('/api/dashboard/agents')
      return response.data
    } catch (error) {
      console.warn('Error fetching agent stats, using mock data:', error)
      return { agents: MOCK_AGENTS }
    }
  }
}

// Alert API functions
export const alertsApi = {
  getAlerts: async (limit = 100) => {
    const response = await api.get(`/api/alerts?limit=${limit}`)
    return response.data
  },
  
  updateAlert: async (alertId: string, data: { status: string, notes?: string, assigned_to?: string }) => {
    const response = await api.put(`/api/alerts/${alertId}`, data)
    return response.data
  }
}

// Rules API functions
export const rulesApi = {
  getRules: async () => {
    const response = await api.get('/api/rules')
    return response.data
  },
  
  getRule: async (filename: string) => {
    const response = await api.get(`/api/rules/${filename}`)
    return response.data
  },
  
  getRuleYaml: async (filename: string) => {
    const response = await api.get(`/api/rules/${filename}/yaml`)
    return response.data
  },
  
  createRule: async (ruleData: any) => {
    const response = await api.post('/api/rules', ruleData)
    return response.data
  },
  
  createRuleFromYaml: async (yamlContent: string) => {
    const response = await api.post('/api/rules/yaml', { content: yamlContent })
    return response.data
  },
  
  updateRule: async (filename: string, ruleData: any) => {
    const response = await api.put(`/api/rules/${filename}`, ruleData)
    return response.data
  },
  
  updateRuleYaml: async (filename: string, yamlContent: string) => {
    const response = await api.put(`/api/rules/${filename}/yaml`, { content: yamlContent })
    return response.data
  },
  
  deleteRule: async (filename: string) => {
    const response = await api.delete(`/api/rules/${filename}`)
    return response.data
  },
  
  restartElastAlert: async () => {
    const response = await api.post('/api/elastalert/restart')
    return response.data
  }
}

// Agents API functions
export const agentsApi = {
  getAgents: async () => {
    const response = await api.get('/api/agents')
    return response.data
  },
  
  registerAgent: async (agentData: any) => {
    const response = await api.post('/api/agents/register', agentData)
    return response.data
  },
  
  getAgentIOCMatches: async (agentId: string) => {
    const response = await api.get(`/api/agents/${agentId}/ioc-matches`)
    return response.data
  }
}

// IOCs API functions
export const iocsApi = {
  getAllIOCs: async () => {
    const response = await api.get('/api/iocs')
    return response.data
  },
  
  getIOCsByType: async (iocType: 'ip' | 'hash' | 'url') => {
    const response = await api.get(`/api/iocs/${iocType}`)
    return response.data
  },
  
  addIpIOC: async (data: { value: string, description?: string, severity?: string }) => {
    const response = await api.post('/api/iocs/ip', data)
    return response.data
  },
  
  addHashIOC: async (data: { value: string, hash_type: string, description?: string, severity?: string }) => {
    const response = await api.post('/api/iocs/hash', data)
    return response.data
  },
  
  addUrlIOC: async (data: { value: string, description?: string, severity?: string }) => {
    const response = await api.post('/api/iocs/url', data)
    return response.data
  },
  
  removeIOC: async (iocType: 'ip' | 'hash' | 'url', value: string) => {
    const response = await api.delete(`/api/iocs/${iocType}/${encodeURIComponent(value)}`)
    return response.data
  }
}

// Logs API functions
export const logsApi = {
  getLogTypes: async () => {
    try {
      const response = await api.get('/api/logs/types')
      return response.data
    } catch (error) {
      console.error('Error getting log types:', error)
      throw error
    }
  },
  
  getLogs: async (
    logType: string, 
    options?: { 
      lines?: number, 
      search?: string, 
      level?: string, 
      since?: string 
    }
  ) => {
    try {
      const params = new URLSearchParams()
      if (options?.lines) params.append('lines', options.lines.toString())
      if (options?.search) params.append('search', options.search)
      if (options?.level) params.append('level', options.level)
      if (options?.since) params.append('since', options.since)
      
      const queryString = params.toString()
      const url = `/api/logs/${logType}${queryString ? `?${queryString}` : ''}`
      
      const response = await api.get(url)
      return response.data
    } catch (error) {
      console.error(`Error getting logs for type ${logType}:`, error)
      throw error
    }
  }
} 