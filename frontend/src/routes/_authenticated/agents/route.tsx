import { useQuery } from '@tanstack/react-query'
import { createFileRoute, useRouter } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { agentsApi } from '@/lib/api'
import { Agent } from '@/lib/types'
import { Badge } from '@/components/ui/badge'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from '@/hooks/use-toast'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { TopNav } from '@/components/layout/top-nav'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'

export const Route = createFileRoute('/_authenticated/agents')({
  component: AgentsPage
})

function AgentsPage() {
  const router = useRouter()
  
  // Get the current status filter from URL
  const { status: statusFilter } = router.state.location.search as { status?: string }

  // Filter agents client-side since the API doesn't support server-side filtering
  const { data: allAgents = [], isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.getAgents(),
    refetchInterval: 60000, // Refresh every minute
  })

  // Filter agents based on status
  const agents = statusFilter
    ? allAgents.filter((agent: Agent) => agent.status === statusFilter)
    : allAgents;

  const queryClient = useQueryClient()

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge>Active</Badge>
      case 'inactive':
        return <Badge variant="outline">Inactive</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  // Generate topNav with proper active states based on current URL params
  const getTopNav = () => {
    return [
      {
        title: 'All Agents',
        href: '/agents',
        isActive: !statusFilter,
        disabled: false,
      },
      {
        title: 'Active',
        href: '/agents?status=active',
        isActive: statusFilter === 'active',
        disabled: false,
      },
      {
        title: 'Inactive',
        href: '/agents?status=inactive',
        isActive: statusFilter === 'inactive',
        disabled: false,
      },
    ];
  };

  return (
    <>
      {/* ===== Top Heading ===== */}
      <Header>
        <TopNav links={getTopNav()} />
        <div className='ml-auto flex items-center space-x-4'>
          <Search />
          <ThemeSwitch />
        </div>
      </Header>

      {/* ===== Main ===== */}
      <Main>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">
            {statusFilter ? `${statusFilter.charAt(0).toUpperCase() + statusFilter.slice(1)} Agents` : 'All Agents'}
          </h1>
          <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ['agents'] })}>
            Refresh
          </Button>
        </div>
        
        <Card>
          <CardHeader>
            <CardTitle>Agent List</CardTitle>
            <CardDescription>
              {statusFilter 
                ? `Viewing ${statusFilter} agents` 
                : 'View and manage all monitoring agents'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">Loading agents...</div>
            ) : agents.length === 0 ? (
              <div className="flex justify-center py-8">No agents found</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Hostname</TableHead>
                    <TableHead>IP Address</TableHead>
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
                      <TableCell>{getStatusBadge(agent.status)}</TableCell>
                      <TableCell>{new Date(agent.last_seen).toLocaleString()}</TableCell>
                      <TableCell>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => {
                            toast({
                              title: 'Feature not implemented',
                              description: 'Agent restart functionality is not yet implemented.',
                            })
                          }}
                        >
                          Restart
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