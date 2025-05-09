import { apiClient } from './client';

export type CommandType = 
  | 'DELETE_FILE'
  | 'KILL_PROCESS'
  | 'KILL_PROCESS_TREE'
  | 'BLOCK_IP'
  | 'BLOCK_URL'
  | 'NETWORK_ISOLATE'
  | 'NETWORK_RESTORE';

export interface Command {
  id: string;
  agent_id: string;
  type: CommandType;
  success: boolean;
  message: string;
  execution_time: number;
  duration_ms: number;
}

export interface SendCommandParams {
  agent_id: string;
  type: CommandType;
  params: Record<string, string>;
  priority?: number;
  timeout?: number;
}

export const commandsApi = {
  // Get all commands
  getCommands: async (): Promise<Command[]> => {
    const response = await apiClient.get('/api/commands');
    return response.data;
  },

  // Get a specific command
  getCommand: async (commandId: string): Promise<Command> => {
    const response = await apiClient.get(`/api/commands/${commandId}`);
    return response.data;
  },

  // Send a command to an agent
  sendCommand: async (params: SendCommandParams) => {
    const response = await apiClient.post('/api/commands/send', params);
    return response.data;
  },

  // Helper functions for specific command types
  deleteFile: async (agentId: string, filePath: string) => {
    return commandsApi.sendCommand({
      agent_id: agentId,
      type: 'DELETE_FILE',
      params: { path: filePath }
    });
  },

  killProcess: async (agentId: string, pid: string) => {
    return commandsApi.sendCommand({
      agent_id: agentId,
      type: 'KILL_PROCESS',
      params: { pid }
    });
  },

  killProcessTree: async (agentId: string, pid: string) => {
    return commandsApi.sendCommand({
      agent_id: agentId,
      type: 'KILL_PROCESS_TREE',
      params: { pid }
    });
  },

  blockIp: async (agentId: string, ip: string) => {
    return commandsApi.sendCommand({
      agent_id: agentId,
      type: 'BLOCK_IP',
      params: { ip }
    });
  },

  blockUrl: async (agentId: string, url: string) => {
    return commandsApi.sendCommand({
      agent_id: agentId,
      type: 'BLOCK_URL',
      params: { url }
    });
  },

  isolateNetwork: async (agentId: string, allowedIps?: string) => {
    return commandsApi.sendCommand({
      agent_id: agentId,
      type: 'NETWORK_ISOLATE',
      params: allowedIps ? { allowed_ips: allowedIps } : {}
    });
  },

  restoreNetwork: async (agentId: string) => {
    return commandsApi.sendCommand({
      agent_id: agentId,
      type: 'NETWORK_RESTORE',
      params: {}
    });
  }
}; 