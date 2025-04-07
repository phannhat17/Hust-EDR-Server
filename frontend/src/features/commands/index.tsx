import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { commandsApi, Command } from '@/lib/api/commands';
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { AgentSelector } from '@/components/agent-selector';
import { CommandForm } from './command-form';
import { formatDistanceToNow } from 'date-fns';
import { apiClient } from '@/lib/api/client';

export default function Commands() {
  const [selectedTab, setSelectedTab] = useState('send');
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  // Fetch command history
  const { data: commands, isLoading, error, refetch } = useQuery({
    queryKey: ['commands'],
    queryFn: () => commandsApi.getCommands(),
  });

  // Execute command mutation
  const executeMutation = useMutation({
    mutationFn: commandsApi.sendCommand,
    onSuccess: () => {
      // Refetch commands after successful execution
      refetch();
    },
  });

  // Handle agent selection
  const handleAgentChange = (agentId: string) => {
    setSelectedAgentId(agentId);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Commands</h1>
          <p className="text-muted-foreground">Send commands to agents and view command history</p>
        </div>
      </div>

      <Tabs value={selectedTab} onValueChange={setSelectedTab} className="w-full">
        <TabsList className="grid w-full md:w-auto grid-cols-2">
          <TabsTrigger value="send">Send Command</TabsTrigger>
          <TabsTrigger value="history">Command History</TabsTrigger>
        </TabsList>
        
        <TabsContent value="send" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Send Command</CardTitle>
              <CardDescription>Execute commands on remote agents</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-6">
                <label className="text-sm font-medium">Select Agent</label>
                <AgentSelector onAgentChange={handleAgentChange} />
              </div>
              
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
                <div className="py-8 text-center text-muted-foreground">
                  Please select an agent to send commands
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="history" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Command History</CardTitle>
              <CardDescription>View the results of previously executed commands</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="py-8 text-center">Loading commands...</div>
              ) : error ? (
                <div className="py-8 text-center text-destructive">
                  Error loading commands: {String(error)}
                </div>
              ) : commands?.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  No commands have been executed yet
                </div>
              ) : (
                <Table>
                  <TableCaption>A list of all executed commands</TableCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Command Type</TableHead>
                      <TableHead>Agent ID</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Execution Time</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Message</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {commands?.map((command: Command) => (
                      <TableRow key={command.id}>
                        <TableCell>
                          <Badge variant="outline">{command.type}</Badge>
                        </TableCell>
                        <TableCell className="font-mono text-xs">{command.agent_id}</TableCell>
                        <TableCell>
                          <Badge variant={command.success ? "green" : "destructive"}>
                            {command.success ? "Success" : "Failed"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {command.execution_time ? formatDistanceToNow(command.execution_time, { addSuffix: true }) : 'Unknown'}
                        </TableCell>
                        <TableCell>{command.duration_ms}ms</TableCell>
                        <TableCell className="max-w-xs truncate">{command.message}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
} 