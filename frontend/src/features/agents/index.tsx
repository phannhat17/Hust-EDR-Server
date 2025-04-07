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
import { Agent } from '@/lib/types'
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

export default function Agents() {
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  
  // No longer using searchQuery since it's not connected to UI
  const { data: agents = [], isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.getAgents(),
    refetchInterval: 60000, // Refresh every minute
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
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agents.map((agent: Agent) => (
                    <TableRow key={agent.id}>
                      <TableCell className="font-medium">{agent.hostname}</TableCell>
                      <TableCell>{agent.ip_address}</TableCell>
                      <TableCell>{agent.os_info}</TableCell>
                      <TableCell>{agent.version}</TableCell>
                      <TableCell>
                        <Badge variant={agent.status === 'ONLINE' ? "green" : "black"}>
                          {agent.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{new Date(agent.last_seen).toLocaleString()}</TableCell>
                      <TableCell>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => setSelectedAgent(agent)}
                              className="mr-2"
                            >
                              Details
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="sm:max-w-md">
                            <DialogHeader>
                              <DialogTitle>Agent Details</DialogTitle>
                            </DialogHeader>
                            {selectedAgent && (
                              <div className="grid gap-4">
                                <div className="grid grid-cols-2 gap-4">
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">Hostname</h4>
                                    <p className="text-sm">{selectedAgent.hostname}</p>
                                  </div>
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">IP Address</h4>
                                    <p className="text-sm">{selectedAgent.ip_address}</p>
                                  </div>
                                </div>
                                <div className="space-y-1">
                                  <h4 className="font-medium text-sm">Operating System</h4>
                                  <p className="text-sm">{selectedAgent.os_version_full}</p>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">MAC Address</h4>
                                    <p className="text-sm">{selectedAgent.mac_address || 'Not available'}</p>
                                  </div>
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">Username</h4>
                                    <p className="text-sm">{selectedAgent.username || 'Not available'}</p>
                                  </div>
                                </div>
                                <div className="grid grid-cols-3 gap-4">
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">CPU Usage</h4>
                                    <p className="text-sm">{selectedAgent.cpu_usage !== undefined ? `${selectedAgent.cpu_usage.toFixed(1)}%` : 'N/A'}</p>
                                  </div>
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">Memory Usage</h4>
                                    <p className="text-sm">{selectedAgent.memory_usage !== undefined ? `${selectedAgent.memory_usage.toFixed(1)}%` : 'N/A'}</p>
                                  </div>
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">Uptime</h4>
                                    <p className="text-sm">
                                      {selectedAgent.uptime !== undefined 
                                        ? formatUptime(selectedAgent.uptime) 
                                        : 'N/A'}
                                    </p>
                                  </div>
                                </div>
                                <div className="grid grid-cols-3 gap-4">
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">Status</h4>
                                    <p className="text-sm">
                                      <Badge variant={selectedAgent.status === 'ONLINE' ? "green" : "black"}>
                                        {selectedAgent.status}
                                      </Badge>
                                    </p>
                                  </div>
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">Agent Version</h4>
                                    <p className="text-sm">{selectedAgent.version}</p>
                                  </div>
                                  <div className="space-y-1">
                                    <h4 className="font-medium text-sm">Registered</h4>
                                    <p className="text-sm">{new Date(selectedAgent.registered_at).toLocaleString()}</p>
                                  </div>
                                </div>
                                <div className="space-y-1">
                                  <h4 className="font-medium text-sm">Last Seen</h4>
                                  <p className="text-sm">{new Date(selectedAgent.last_seen).toLocaleString()}</p>
                                </div>
                              </div>
                            )}
                          </DialogContent>
                        </Dialog>
                        <Button
                          variant="outline"
                          size="sm"
                          asChild
                        >
                          <Link to="/commands" search={{ agent_id: agent.id }}>
                            Command
                          </Link>
                        </Button>
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

// Helper function to format uptime in a human-readable format
function formatUptime(seconds: number): string {
  if (seconds < 60) {
    return `${seconds} seconds`;
  } else if (seconds < 3600) {
    return `${Math.floor(seconds / 60)} minutes`;
  } else if (seconds < 86400) { // less than a day
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours} ${hours === 1 ? 'hour' : 'hours'} ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
  } else {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    return `${days} ${days === 1 ? 'day' : 'days'} ${hours} ${hours === 1 ? 'hour' : 'hours'}`;
  }
}

const topNav = [
  {
    title: 'All Agents',
    href: '/agents',
    isActive: true,
    disabled: false,
  },
  {
    title: 'Active',
    href: '/agents?status=active',
    isActive: false,
    disabled: true,
  },
  {
    title: 'Inactive',
    href: '/agents?status=inactive',
    isActive: false,
    disabled: true,
  },
] 