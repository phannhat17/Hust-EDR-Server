import { useQuery } from '@tanstack/react-query';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Agent, isAgentOnline, formatAgentMetric } from '@/types/agent';
import { apiClient } from '@/lib/api/client';
import { Badge } from '@/components/ui/badge';

interface AgentSelectorProps {
  onAgentChange: (agentId: string) => void;
  selectedAgentId?: string;
}

export function AgentSelector({ onAgentChange, selectedAgentId }: AgentSelectorProps) {
  // Fetch agents from API
  const { data: agents, isLoading, error } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await apiClient.get('/api/agents');
      return response.data;
    },
  });

  // Handle agent selection
  const handleChange = (value: string) => {
    onAgentChange(value);
  };

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Loading agents...</div>;
  }

  if (error) {
    return <div className="text-sm text-destructive">Error: {String(error)}</div>;
  }

  if (!agents || agents.length === 0) {
    return <div className="text-sm text-muted-foreground">No agents found</div>;
  }

  return (
    <Select onValueChange={handleChange} value={selectedAgentId}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select an agent">
          {selectedAgentId && agents?.find((a: Agent) => a.id === selectedAgentId)?.hostname}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {agents.map((agent: Agent) => {
          const isOnline = isAgentOnline(agent.last_seen);
          return (
            <SelectItem key={agent.id} value={agent.id} className="py-2">
              <div className="flex flex-col space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{agent.hostname}</span>
                  <Badge variant={isOnline ? "green" : "destructive"} className="ml-2">
                    {isOnline ? "Online" : "Offline"}
                  </Badge>
                </div>
                <div className="flex items-center space-x-2 text-xs text-muted-foreground">
                  <span>{agent.ip_address}</span>
                  <span>•</span>
                  <span>CPU: {formatAgentMetric(agent.cpu_usage).toFixed(1)}%</span>
                  <span>•</span>
                  <span>Memory: {formatAgentMetric(agent.memory_usage).toFixed(1)}%</span>
                </div>
              </div>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
} 