import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Link } from '@tanstack/react-router'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { TopNav } from '@/components/layout/top-nav'
import { agentsApi } from '@/lib/api'
import { Agent, IOCMatch, SeverityLevel } from '@/types/agent'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { useState } from 'react'
import { Loader, MoreHorizontal } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { isAgentOnline } from '@/types/agent'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

// Add this function to get severity badge
function getSeverityBadge(severity: SeverityLevel | string) {
  const capitalized = typeof severity === 'string' 
    ? severity.charAt(0).toUpperCase() + severity.slice(1).toLowerCase()
    : severity;
    
  switch (severity.toLowerCase()) {
    case 'critical':
      return <Badge variant="black">Critical</Badge>
    case 'high':
      return <Badge variant="destructive">High</Badge>
    case 'medium':
      return <Badge variant="secondary">Medium</Badge>
    case 'low':
      return <Badge variant="outline">Low</Badge>
    default:
      return <Badge variant="outline">{capitalized}</Badge>
  }
}

export default function Agents() {
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  
  // No longer using searchQuery since it's not connected to UI
  const { data: agents = [], isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.getAgents(),
    refetchInterval: 60000, // Refresh every minute
  });
  
  // Add query for IOC match history when an agent is selected
  const { data: iocMatches = [], isLoading: isLoadingIOCMatches } = useQuery({
    queryKey: ['agent-ioc-matches', selectedAgent?.id],
    queryFn: () => selectedAgent ? agentsApi.getAgentIOCMatches(selectedAgent.id) : Promise.resolve([]),
    enabled: !!selectedAgent,
  });

  return (
    <>
      {/* ===== Top Heading ===== */}
      <Header>
        <TopNav links={topNav} />
        <div className='ml-auto flex items-center space-x-4'>
          <Search placeholder="Search agents..." />
          <ThemeSwitch />
        </div>
      </Header>

      {/* ===== Main ===== */}
      <Main>
        <div className='mb-4 flex items-center justify-between space-y-2'>
          <h1 className='text-2xl font-bold tracking-tight'>Agents</h1>
          <Button asChild>
            <Link to="/agents/register">Register New Agent</Link>
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Agent List</CardTitle>
            <CardDescription>View and manage all registered EDR agents</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">Loading agents...</div>
            ) : agents.length === 0 ? (
              <div className="flex justify-center py-8 flex-col items-center">
                <p className="mb-4">No agents found</p>
                <Button asChild>
                  <Link to="/agents/register">Register your first agent</Link>
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Hostname</TableHead>
                    <TableHead>IP Address</TableHead>
                    <TableHead>OS</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Seen</TableHead>
                    <TableHead>Agent ID</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agents.map((agent: Agent) => (
                    <TableRow key={agent.id}>
                      <TableCell className="font-medium">{agent.hostname}</TableCell>
                      <TableCell>{agent.ip_address}</TableCell>
                      <TableCell>{agent.os_info || agent.os}</TableCell>
                      <TableCell>{agent.version}</TableCell>
                      <TableCell>
                        <Badge variant={isAgentOnline(agent.last_seen) ? "green" : "black"}>
                          {isAgentOnline(agent.last_seen) ? "ONLINE" : "OFFLINE"}
                        </Badge>
                      </TableCell>
                      <TableCell>{new Date(agent.last_seen).toLocaleString()}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {agent.id.length > 10 ? `${agent.id.substring(0, 8)}...` : agent.id}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              className="h-8 w-8 p-0"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                              <span className="sr-only">Show options</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => {
                                setSelectedAgent(agent);
                                // Open the dialog programmatically by finding and clicking the button
                                const detailsButton = document.querySelector(`#details-dialog-${agent.id}`);
                                if (detailsButton instanceof HTMLButtonElement) {
                                  detailsButton.click();
                                }
                              }}
                            >
                              Details
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to="/commands" search={{ agent_id: agent.id }}>
                                Command
                              </Link>
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                        
                        {/* Hidden dialog trigger that the dropdown can activate */}
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button 
                              id={`details-dialog-${agent.id}`}
                              variant="outline" 
                              size="sm"
                              onClick={() => setSelectedAgent(agent)}
                              className="hidden"
                            >
                              Details
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                              <DialogTitle className="flex items-center gap-2 text-xl">
                                Agent Details
                                {selectedAgent && (
                                  <Badge variant={isAgentOnline(selectedAgent.last_seen) ? "green" : "destructive"} className="ml-2">
                                    {isAgentOnline(selectedAgent.last_seen) ? "Online" : "Offline"}
                                  </Badge>
                                )}
                              </DialogTitle>
                              {selectedAgent && (
                                <div className="text-sm text-muted-foreground mt-1">
                                  <span className="font-medium">ID:</span> <span className="font-mono">{selectedAgent.id}</span>
                                </div>
                              )}
                            </DialogHeader>
                            {selectedAgent && (
                              <div className="mt-4 space-y-6">
                                <Tabs defaultValue="info">
                                  <TabsList className="grid w-full grid-cols-2">
                                    <TabsTrigger value="info">Agent Information</TabsTrigger>
                                    <TabsTrigger value="ioc-history">IOC Response History</TabsTrigger>
                                  </TabsList>

                                  <TabsContent value="info" className="space-y-6">
                                    {/* Basic Information */}
                                    <div className="rounded-lg border p-4">
                                      <h3 className="mb-3 text-sm font-medium text-muted-foreground">Basic Information</h3>
                                      <div className="grid grid-cols-2 gap-4">
                                        <div>
                                          <h4 className="text-sm font-semibold">Hostname</h4>
                                          <p className="text-sm">{selectedAgent.hostname}</p>
                                        </div>
                                        <div>
                                          <h4 className="text-sm font-semibold">IP Address</h4>
                                          <p className="text-sm">{selectedAgent.ip_address}</p>
                                        </div>
                                        <div>
                                          <h4 className="text-sm font-semibold">MAC Address</h4>
                                          <p className="text-sm">{selectedAgent.mac_address || 'Not available'}</p>
                                        </div>
                                        <div>
                                          <h4 className="text-sm font-semibold">Username</h4>
                                          <p className="text-sm">{selectedAgent.username || 'Not available'}</p>
                                        </div>
                                        <div className="col-span-2">
                                          <h4 className="text-sm font-semibold">Agent ID</h4>
                                          <p className="text-sm font-mono">{selectedAgent.id}</p>
                                        </div>
                                      </div>
                                    </div>

                                    {/* System Information */}
                                    <div className="rounded-lg border p-4">
                                      <h3 className="mb-3 text-sm font-medium text-muted-foreground">System Information</h3>
                                      <div>
                                        <h4 className="text-sm font-semibold">Operating System</h4>
                                        <p className="text-sm mb-4">{selectedAgent.os_version_full || selectedAgent.os}</p>
                                      </div>
                                      <div className="grid grid-cols-3 gap-4 mt-2">
                                        <div className="bg-slate-50 dark:bg-slate-900 p-3 rounded-md">
                                          <h4 className="text-sm font-semibold text-muted-foreground">CPU Usage</h4>
                                          <p className="text-lg font-medium">{selectedAgent.cpu_usage !== undefined ? `${selectedAgent.cpu_usage.toFixed(1)}%` : 'N/A'}</p>
                                        </div>
                                        <div className="bg-slate-50 dark:bg-slate-900 p-3 rounded-md">
                                          <h4 className="text-sm font-semibold text-muted-foreground">Memory Usage</h4>
                                          <p className="text-lg font-medium">{selectedAgent.memory_usage !== undefined ? `${selectedAgent.memory_usage.toFixed(1)}%` : 'N/A'}</p>
                                        </div>
                                        <div className="bg-slate-50 dark:bg-slate-900 p-3 rounded-md">
                                          <h4 className="text-sm font-semibold text-muted-foreground">Uptime</h4>
                                          <p className="text-lg font-medium">{selectedAgent.uptime !== undefined 
                                            ? formatUptime(selectedAgent.uptime) 
                                            : 'N/A'}</p>
                                        </div>
                                      </div>
                                    </div>

                                    {/* Agent Status */}
                                    <div className="rounded-lg border p-4">
                                      <h3 className="mb-3 text-sm font-medium text-muted-foreground">Agent Status</h3>
                                      <div className="grid grid-cols-3 gap-4">
                                        <div>
                                          <h4 className="text-sm font-semibold">Agent Version</h4>
                                          <p className="text-sm">{selectedAgent.version}</p>
                                        </div>
                                        <div>
                                          <h4 className="text-sm font-semibold">Registered</h4>
                                          <p className="text-sm">{new Date(selectedAgent.registered_at).toLocaleString()}</p>
                                        </div>
                                        <div>
                                          <h4 className="text-sm font-semibold">Last Seen</h4>
                                          <p className="text-sm">{new Date(selectedAgent.last_seen).toLocaleString()}</p>
                                        </div>
                                      </div>
                                    </div>
                                  </TabsContent>

                                  <TabsContent value="ioc-history">
                                    <div className="rounded-lg border p-4">
                                      <h3 className="mb-3 text-sm font-medium">IOC Response History</h3>
                                      
                                      {isLoadingIOCMatches ? (
                                        <div className="flex justify-center py-8">
                                          <Loader className="h-8 w-8 animate-spin" />
                                          <span className="ml-2">Loading IOC history...</span>
                                        </div>
                                      ) : iocMatches.length === 0 ? (
                                        <div className="text-center py-8 text-muted-foreground">
                                          No IOC matches recorded for this agent
                                        </div>
                                      ) : (
                                        <Table>
                                          <TableHeader>
                                            <TableRow>
                                              <TableHead>Time</TableHead>
                                              <TableHead>IOC Type</TableHead>
                                              <TableHead>Matched Value</TableHead>
                                              <TableHead>Severity</TableHead>
                                              <TableHead>Action Taken</TableHead>
                                              <TableHead>Result</TableHead>
                                            </TableRow>
                                          </TableHeader>
                                          <TableBody>
                                            {iocMatches.map((match: IOCMatch) => (
                                              <TableRow key={match.report_id}>
                                                <TableCell>{new Date(match.timestamp * 1000).toLocaleString()}</TableCell>
                                                <TableCell>
                                                  {match.type === 'IOC_IP' ? 'IP Address' : 
                                                   match.type === 'IOC_HASH' ? 'File Hash' : 
                                                   match.type === 'IOC_URL' ? 'URL' : match.type}
                                                </TableCell>
                                                <TableCell className="font-mono text-xs">
                                                  {match.matched_value}
                                                </TableCell>
                                                <TableCell>{getSeverityBadge(match.severity)}</TableCell>
                                                <TableCell>
                                                  {match.action_taken ? formatActionName(match.action_taken) : 'None'}
                                                </TableCell>
                                                <TableCell>
                                                  {match.action_taken ? (
                                                    match.action_success ? (
                                                      <Badge variant="green">Success</Badge>
                                                    ) : (
                                                      <Badge variant="destructive">Failed</Badge>
                                                    )
                                                  ) : (
                                                    'N/A'
                                                  )}
                                                </TableCell>
                                              </TableRow>
                                            ))}
                                          </TableBody>
                                        </Table>
                                      )}
                                    </div>
                                  </TabsContent>
                                </Tabs>
                                
                                {/* Quick Actions */}
                                <div className="flex justify-end gap-2">
                                  <Button variant="outline" size="sm" asChild>
                                    <Link to="/commands" search={{ agent_id: selectedAgent.id }}>
                                      Send Command
                                    </Link>
                                  </Button>
                                </div>
                              </div>
                            )}
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </Main>
    </>
  )
}

// Helper function to format uptime
function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  } else if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else {
    return `${minutes}m`;
  }
}

// Helper function to format action names
function formatActionName(action: string): string {
  switch (action) {
    case 'DELETE_FILE':
      return 'Delete File';
    case 'KILL_PROCESS':
      return 'Kill Process';
    case 'KILL_PROCESS_TREE':
      return 'Kill Process Tree';
    case 'BLOCK_IP':
      return 'Block IP';
    case 'BLOCK_URL':
      return 'Block URL';
    case 'NETWORK_ISOLATE':
      return 'Network Isolation';
    case 'NETWORK_RESTORE':
      return 'Network Restore';
    default:
      return action;
  }
}

const topNav = [
  { title: 'Dashboard', href: '/', isActive: false },
  { title: 'Agents', href: '/agents', isActive: true },
  { title: 'Alerts', href: '/alerts', isActive: false },
  { title: 'Commands', href: '/commands', isActive: false },
  { title: 'IOCs', href: '/iocs', isActive: false },
] 