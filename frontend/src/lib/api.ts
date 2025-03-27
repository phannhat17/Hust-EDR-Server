import axios from 'axios'

// Create Axios instance with base URL pointing to Flask backend
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

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
    hostname: 'web-server-01',
    ip_address: '192.168.1.101',
    os_info: 'Ubuntu 22.04 LTS',
    version: '1.2.0',
    status: 'active',
    last_seen: new Date().toISOString(),
    registered_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '2',
    hostname: 'db-server-01',
    ip_address: '192.168.1.102',
    os_info: 'CentOS 8',
    version: '1.2.0',
    status: 'active',
    last_seen: new Date().toISOString(),
    registered_at: new Date(Date.now() - 25 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '3',
    hostname: 'app-server-01',
    ip_address: '192.168.1.103',
    os_info: 'Windows Server 2019',
    version: '1.1.5',
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
  
  createRule: async (ruleData: any) => {
    const response = await api.post('/api/rules', ruleData)
    return response.data
  },
  
  updateRule: async (filename: string, ruleData: any) => {
    const response = await api.put(`/api/rules/${filename}`, ruleData)
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
    try {
      const response = await api.get('/api/agents')
      return response.data
    } catch (error) {
      console.warn('Error fetching agents, using mock data:', error)
      return MOCK_AGENTS
    }
  },
  
  registerAgent: async (agentData: any) => {
    const response = await api.post('/api/agents/register', agentData)
    return response.data
  }
} 