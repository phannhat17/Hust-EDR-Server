import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { TopNav } from '@/components/layout/top-nav'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Overview } from './components/overview'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'
import { RefreshCw, ShieldAlert, Server, Book } from 'lucide-react'
import { useState } from 'react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Agent } from '@/lib/types'
import { Badge } from '@/components/ui/badge'

export default function Dashboard() {
  const [timeRange, setTimeRange] = useState('7d');

  const { data: dashboardStats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.getStats(),
    refetchInterval: 60000, // Refresh every minute
  });

  const { data: alertsByTime, isLoading: alertsTimeLoading } = useQuery({
    queryKey: ['alerts-by-time', timeRange],
    queryFn: () => dashboardApi.getAlertsByTimeRange(timeRange),
    refetchInterval: 60000,
  });
  
  const { data: agentStats, isLoading: agentsLoading } = useQuery({
    queryKey: ['agent-stats'],
    queryFn: () => dashboardApi.getAgentStats(),
    refetchInterval: 60000,
  });

  return (
    <>
      {/* ===== Top Heading ===== */}
      <Header>
        <TopNav links={topNav} />
        <div className='ml-auto flex items-center space-x-4'>
          <Search />
          <ThemeSwitch />
        </div>
      </Header>

      {/* ===== Main ===== */}
      <Main>
        <div className='mb-2 flex items-center justify-between space-y-2'>
          <h1 className='text-2xl font-bold tracking-tight'>EDR Dashboard</h1>
          <div className='flex items-center space-x-2'>
            <Select 
              value={timeRange} 
              onValueChange={setTimeRange}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Time Range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1d">Last 24 hours</SelectItem>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="90d">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </div>
        <Tabs
          orientation='vertical'
          defaultValue='overview'
          className='space-y-4'
        >
          <div className='w-full overflow-x-auto pb-2'>
          </div>
          <TabsContent value='overview' className='space-y-4'>
            <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
              <Card>
                <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                  <CardTitle className='text-sm font-medium'>
                    Total Alerts
                  </CardTitle>
                  <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold'>
                    {statsLoading ? "Loading..." : dashboardStats?.total_alerts || 0}
                  </div>
                  <p className='text-xs text-muted-foreground'>
                    {statsLoading ? "" : `${dashboardStats?.new_alerts || 0} new alerts`}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                  <CardTitle className='text-sm font-medium'>
                    Active Agents
                  </CardTitle>
                  <Server className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold'>
                    {statsLoading ? "Loading..." : dashboardStats?.active_agents || 0}
                  </div>
                  <p className='text-xs text-muted-foreground'>
                    {agentsLoading ? "" : `${agentStats?.agents?.length || 0} total agents`}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                  <CardTitle className='text-sm font-medium'>Active Rules</CardTitle>
                  <Book className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold'>
                    {statsLoading ? "Loading..." : dashboardStats?.active_rules || 0}
                  </div>
                  <p className='text-xs text-muted-foreground'>
                    {statsLoading ? "" : `${dashboardStats?.total_rules || 0} total rules`}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                  <CardTitle className='text-sm font-medium'>
                    Success Rate
                  </CardTitle>
                  <svg
                    xmlns='http://www.w3.org/2000/svg'
                    viewBox='0 0 24 24'
                    fill='none'
                    stroke='currentColor'
                    strokeLinecap='round'
                    strokeLinejoin='round'
                    strokeWidth='2'
                    className='h-4 w-4 text-muted-foreground'
                  >
                    <path d='M22 12h-4l-3 9L9 3l-3 9H2' />
                  </svg>
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold'>
                    {statsLoading ? "Loading..." : 
                      `${dashboardStats?.total_alerts ? 
                        Math.round(((dashboardStats.total_alerts - (dashboardStats.false_positives || 0)) / 
                        dashboardStats.total_alerts) * 100) : 0}%`}
                  </div>
                  <p className='text-xs text-muted-foreground'>
                    {statsLoading ? "" : `${dashboardStats?.false_positives || 0} false positives`}
                  </p>
                </CardContent>
              </Card>
            </div>
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-7'>
              <Card className='col-span-1 lg:col-span-4'>
                <CardHeader>
                  <CardTitle>Alert Trend</CardTitle>
                  <CardDescription>
                    {`Alert activity over the ${timeRange === '1d' ? 'last 24 hours' : 
                      timeRange === '7d' ? 'last 7 days' : 
                      timeRange === '30d' ? 'last 30 days' : 'last 90 days'}`}
                  </CardDescription>
                </CardHeader>
                <CardContent className='pl-2'>
                  {alertsTimeLoading ? (
                    <div className="flex justify-center py-8">Loading data...</div>
                  ) : alertsByTime ? (
                    <Overview chartData={alertsByTime} />
                  ) : (
                    <div className="flex justify-center py-8">No data available</div>
                  )}
                </CardContent>
              </Card>
              <Card className='col-span-1 lg:col-span-3'>
                <CardHeader>
                  <CardTitle>Active Agents</CardTitle>
                  <CardDescription>
                    {agentsLoading ? "Loading..." : `${dashboardStats?.active_agents || 0} active agents out of ${agentStats?.agents?.length || 0} total`}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {agentsLoading ? (
                    <div className="flex justify-center py-8">Loading agents...</div>
                  ) : agentStats?.agents?.length > 0 ? (
                    <div className="space-y-4">
                      {agentStats.agents.slice(0, 5).map((agent: Agent) => (
                        <div key={agent.id} className="flex items-center">
                          <div className="space-y-1">
                            <p className="text-sm font-medium leading-none">{agent.hostname}</p>
                            <p className="text-sm text-muted-foreground">{agent.ip_address}</p>
                          </div>
                          <div className="ml-auto">
                            <Badge variant={agent.status === 'ONLINE' ? "green" : "black"}>
                              {agent.status}
                            </Badge>
                          </div>
                        </div>
                      ))}
                      {agentStats.agents.length > 5 && (
                        <Button variant="link" className="text-sm">
                          View all {agentStats.agents.length} agents
                        </Button>
                      )}
                    </div>
                  ) : (
                    <div className="flex justify-center py-8">No agents registered</div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </Main>
    </>
  )
}

const topNav = [
  {
    title: 'Overview',
    href: '/',
    isActive: true,
    disabled: false,
  },
]
