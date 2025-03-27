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

export default function Agents() {
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
                        <Badge variant={agent.status === 'active' ? "default" : "outline"}>
                          {agent.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{new Date(agent.last_seen).toLocaleString()}</TableCell>
                      <TableCell>
                        <Button variant="outline" size="sm">Details</Button>
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