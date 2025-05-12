import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { commandsApi, Command } from '@/lib/api/commands';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { AgentSelector } from '@/components/agent-selector';
import { CommandForm } from './command-form';
import { formatDistanceToNow } from 'date-fns';
import { useRouter, useSearch } from '@tanstack/react-router';
import { apiClient } from '@/lib/api/client';
import { isAgentOnline, formatAgentMetric } from '@/types/agent';

export default function Commands() {
  const [selectedTab, setSelectedTab] = useState('send');
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentHostname, setAgentHostname] = useState<string | null>(null);
  const { agent_id } = useSearch({ from: '/_authenticated/commands/' });
  const router = useRouter();

  // Fetch command history
  const { data: commands, isLoading, error, refetch } = useQuery({
    queryKey: ['commands'],
    queryFn: () => commandsApi.getCommands(),
  });

  // Fetch agent details when agent_id is available
  const { data: agentDetails } = useQuery({
    queryKey: ['agent', selectedAgentId],
    queryFn: async () => {
      if (!selectedAgentId) return null;
      const response = await apiClient.get(`/api/agents/${selectedAgentId}`);
      return response.data;
    },
    enabled: !!selectedAgentId,
  });

  // Update agent hostname when agent details change
  useEffect(() => {
    if (agentDetails) {
      setAgentHostname(agentDetails.hostname);
    }
  }, [agentDetails]);

  // Execute command mutation
  const executeMutation = useMutation({
    mutationFn: commandsApi.sendCommand,
    onSuccess: () => {
      // Refetch commands after successful execution
      refetch();
    },
  });

  // Set agent from URL parameters if provided
  useEffect(() => {
    if (agent_id) {
      setSelectedAgentId(agent_id);
      setSelectedTab('send');
    }
  }, [agent_id]);

  // Handle agent selection
  const handleAgentChange = (agentId: string) => {
    setSelectedAgentId(agentId);
    
    // Update URL with selected agent
    router.navigate({
      to: '/commands',
      search: agentId ? { agent_id: agentId } : { agent_id: undefined },
      replace: true
    });
  };

  // Clear agent selection
  const clearAgentSelection = () => {
    setSelectedAgentId(null);
    setAgentHostname(null);
    router.navigate({
      to: '/commands',
      search: { agent_id: undefined },
      replace: true
    });
  };

  // Filter commands by agent_id if provided
  const filteredCommands = agent_id 
    ? commands?.filter(command => command.agent_id === agent_id)
    : commands;

  return (
    <>
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-tight">Commands</h1>
        </div>

        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Send Commands</CardTitle>
            <CardDescription>Send commands to agents and view command history</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue={selectedTab} value={selectedTab} onValueChange={setSelectedTab} className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-4">
                <TabsTrigger value="send">Send Command</TabsTrigger>
                <TabsTrigger value="history">Command History</TabsTrigger>
              </TabsList>
              
              <TabsContent value="send" className="space-y-4">
                <div className="space-y-4">
                  {!agent_id ? (
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Select Agent</label>
                      <AgentSelector onAgentChange={handleAgentChange} selectedAgentId={selectedAgentId || undefined} />
                    </div>
                  ) : agentDetails ? (
                    <div className="rounded-md bg-muted p-4 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-sm font-medium">{agentDetails.hostname}</h3>
                            <Badge variant={isAgentOnline(agentDetails.last_seen) ? "green" : "black"}>
                              {isAgentOnline(agentDetails.last_seen) ? "Online" : "Offline"}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{agentDetails.os}</p>
                        </div>
                        <Button variant="ghost" size="sm" onClick={clearAgentSelection}>
                          Change Agent
                        </Button>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-4 pt-2">
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">System Stats</p>
                          <div className="text-sm">
                            CPU: {formatAgentMetric(agentDetails.cpu_usage).toFixed(1)}% • Memory: {formatAgentMetric(agentDetails.memory_usage).toFixed(1)}%
                          </div>
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">Network</p>
                          <div className="text-sm">
                            {agentDetails.ip_address} • {agentDetails.mac_address}
                          </div>
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">Uptime</p>
                          <div className="text-sm">
                            {formatDistanceToNow(Date.now() - (agentDetails.uptime * 1000))}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-md bg-muted p-4">
                      <p className="text-sm text-muted-foreground">Loading agent details...</p>
                    </div>
                  )}
                  
                  {selectedAgentId ? (
                    <CommandForm 
                      agentId={selectedAgentId} 
                      onSubmit={(data) => {
                        executeMutation.mutate(data);
                      }} 
                      isSubmitting={executeMutation.isPending}
                      error={executeMutation.error ? String(executeMutation.error) : undefined}
                      success={executeMutation.isSuccess}
                    />
                  ) : (
                    <div className="rounded-md bg-muted p-8 text-center">
                      <p className="text-sm text-muted-foreground">
                        Please select an agent to send commands
                      </p>
                    </div>
                  )}
                </div>
              </TabsContent>
              
              <TabsContent value="history" className="space-y-4">
                <div className="space-y-4">
                  {agentHostname && agent_id ? (
                    <div className="rounded-md bg-muted p-4 flex items-center justify-between">
                      <p className="text-sm">
                        Showing commands for agent: <span className="font-medium">{agentHostname}</span>
                      </p>
                      <Button variant="ghost" size="sm" onClick={clearAgentSelection}>
                        Show All Commands
                      </Button>
                    </div>
                  ) : (
                    <div className="rounded-md bg-muted p-4">
                      <p className="text-sm">
                        Showing all commands across all agents
                      </p>
                    </div>
                  )}

                  {isLoading ? (
                    <div className="rounded-md bg-muted p-8 text-center">
                      <p className="text-sm text-muted-foreground">Loading commands...</p>
                    </div>
                  ) : error ? (
                    <div className="rounded-md bg-destructive/10 p-8 text-center text-destructive">
                      <p className="text-sm">Error loading commands: {String(error)}</p>
                    </div>
                  ) : filteredCommands?.length === 0 ? (
                    <div className="rounded-md bg-muted p-8 text-center">
                      <p className="text-sm text-muted-foreground">
                        No commands have been executed yet {agent_id && "for this agent"}
                      </p>
                    </div>
                  ) : (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            {!agent_id && <TableHead>Agent ID</TableHead>}
                            <TableHead>Status</TableHead>
                            <TableHead>Execution Time</TableHead>
                            <TableHead>Duration</TableHead>
                            <TableHead className="w-[50%]">Message</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredCommands?.map((command: Command) => (
                            <TableRow key={command.id}>
                              {!agent_id && <TableCell className="font-mono text-xs">{command.agent_id}</TableCell>}
                              <TableCell>
                                <Badge variant={command.success ? "green" : "destructive"}>
                                  {command.success ? "Success" : "Failed"}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                {command.execution_time ? formatDistanceToNow(command.execution_time, { addSuffix: true }) : 'Unknown'}
                              </TableCell>
                              <TableCell>{command.duration_ms}ms</TableCell>
                              <TableCell className="break-all">{command.message}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </>
  );
} 