import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Agent } from '@/types/agent';
import { apiClient } from '@/lib/api/client';

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

  // Set the first agent as selected by default ONLY if none is specified and no agent is currently selected
  useEffect(() => {
    if (!selectedAgentId && agents && agents.length > 0 && !document.location.search.includes('agent_id')) {
      onAgentChange(agents[0].id);
    }
  }, [agents, selectedAgentId, onAgentChange]);

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
    <Select onValueChange={handleChange} defaultValue={selectedAgentId || undefined}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select an agent" />
      </SelectTrigger>
      <SelectContent>
        {agents.map((agent: Agent) => (
          <SelectItem key={agent.id} value={agent.id}>
            {agent.hostname} ({agent.ip_address})
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
} 