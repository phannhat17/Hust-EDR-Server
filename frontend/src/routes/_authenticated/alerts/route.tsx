import { useQuery } from '@tanstack/react-query'
import { createFileRoute, useRouter } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { alertsApi } from '@/lib/api'
import { Alert } from '@/lib/types'
import { Badge } from '@/components/ui/badge'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/hooks/use-toast'
import { useState, useMemo } from 'react'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { TopNav } from '@/components/layout/top-nav'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Copy } from 'lucide-react'

export const Route = createFileRoute('/_authenticated/alerts')({
  component: AlertsPage
})

function AlertsPage() {
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds default
  const router = useRouter()
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  
  // Replace URL-based status filter with direct state approach
  const [activeFilter, setActiveFilter] = useState<string>('all');

  // Get all alerts and filter client-side to fix type issue
  const { data: allAlerts = [], isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => alertsApi.getAlerts(),
    refetchInterval: refreshInterval,
  })

  // Enhanced filtering logic for alerts based on selected filter
  const alerts = useMemo(() => {
    if (!allAlerts.length) return [];
    
    if (activeFilter !== 'all') {
      return allAlerts.filter((alert: Alert) => alert.status === activeFilter);
    }
    
    return allAlerts;
  }, [allAlerts, activeFilter]);

  const queryClient = useQueryClient()

  const updateMutation = useMutation({
    mutationFn: ({ alertId, status }: { alertId: string, status: string }) => 
      alertsApi.updateAlert(alertId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      toast({
        title: 'Alert updated',
        description: 'The alert status has been updated successfully.',
      })
    },
  })

  // Helper function to safely format dates
  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'Date not available';
    
    try {
      // Check if date is in ISO format with Z at the end (UTC)
      if (dateString.includes('T') && dateString.endsWith('Z')) {
        const date = new Date(dateString);
        return !isNaN(date.getTime()) ? date.toLocaleString() : 'Date not available';
      }
      
      // Handle other date formats
      const date = new Date(dateString);
      return !isNaN(date.getTime()) ? date.toLocaleString() : 'Date not available';
    } catch (e) {
      return 'Date not available';
    }
  };

  // Get the best available timestamp from the alert
  const getBestTimestamp = (alert: Alert) => {
    // First try alert_time which is usually more accurate
    if (alert.alert_time) {
      return formatDate(alert.alert_time);
    }
    
    // Then try created_at
    if (alert.created_at) {
      return formatDate(alert.created_at);
    }
    
    // If raw_data has timestamp info, use that
    if (alert.raw_data && alert.raw_data.alert_time) {
      return formatDate(alert.raw_data.alert_time);
    }
    
    return 'Date not available';
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'new':
        return <Badge variant="default">New</Badge>
      case 'in_progress':
        return <Badge variant="outline">In Progress</Badge>
      case 'resolved':
        return <Badge variant="secondary">Resolved</Badge>
      case 'false_positive':
        return <Badge variant="destructive">False Positive</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const handleStatusChange = (alertId: string, status: 'new' | 'in_progress' | 'resolved' | 'false_positive') => {
    updateMutation.mutate({ alertId, status })
  }

  const handleRefreshIntervalChange = (value: string) => {
    setRefreshInterval(parseInt(value))
    toast({
      title: 'Auto-refresh updated',
      description: `Alerts will now refresh every ${parseInt(value) / 1000} seconds.`,
    })
  }

  const showAlertDetails = (alert: Alert) => {
    setSelectedAlert(alert)
    setDetailsOpen(true)
  }

  const copyRawData = () => {
    if (!selectedAlert) return;
    
    try {
      // Copy raw data content to clipboard - try different fields that might contain the data
      let dataToUse = selectedAlert.raw_data || selectedAlert;
      const rawData = JSON.stringify(dataToUse, null, 2);
      navigator.clipboard.writeText(rawData).then(
        () => {
          toast({
            title: 'Copied',
            description: 'Raw data copied to clipboard',
          });
        },
        () => {
          toast({
            title: 'Failed to copy',
            description: 'Could not copy raw data to clipboard',
            variant: 'destructive',
          });
        }
      );
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Could not prepare data for copying',
        variant: 'destructive',
      });
    }
  };

  // Build filter tabs
  const filterTabs = [
    {
      id: 'all',
      label: 'All Alerts',
      count: allAlerts.length,
    },
    {
      id: 'new',
      label: 'New',
      count: allAlerts.filter((alert: Alert) => alert.status === 'new').length,
    },
    {
      id: 'in_progress',
      label: 'In Progress',
      count: allAlerts.filter((alert: Alert) => alert.status === 'in_progress').length,
    },
    {
      id: 'resolved',
      label: 'Resolved',
      count: allAlerts.filter((alert: Alert) => alert.status === 'resolved').length,
    },
    {
      id: 'false_positive',
      label: 'False Positive',
      count: allAlerts.filter((alert: Alert) => alert.status === 'false_positive').length,
    }
  ];

  return (
    <>
      {/* ===== Top Heading ===== */}
      <Header>
        <div className="flex items-center space-x-4">
          <div className="flex overflow-x-auto">
            {filterTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveFilter(tab.id)}
                className={`px-4 py-2 font-medium text-sm whitespace-nowrap ${
                  activeFilter === tab.id
                    ? 'border-b-2 border-primary text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                }`}
              >
                {tab.label}
                <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                  {tab.count}
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className='ml-auto flex items-center space-x-4'>
          <Search />
          <ThemeSwitch />
        </div>
      </Header>

      {/* ===== Main ===== */}
      <Main>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">
            {activeFilter !== 'all' 
              ? `${activeFilter === 'false_positive' 
                  ? 'False Positive' 
                  : activeFilter.charAt(0).toUpperCase() + activeFilter.slice(1).replace('_', ' ')
                } Alerts` 
              : 'All Alerts'}
          </h1>
          <div className="flex gap-2 items-center">
            <Select
              value={refreshInterval.toString()}
              onValueChange={handleRefreshIntervalChange}
            >
              <SelectTrigger className="w-52">
                <SelectValue placeholder="Auto-refresh interval" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="5000">Refresh every 5 seconds</SelectItem>
                <SelectItem value="15000">Refresh every 15 seconds</SelectItem>
                <SelectItem value="30000">Refresh every 30 seconds</SelectItem>
                <SelectItem value="60000">Refresh every minute</SelectItem>
                <SelectItem value="300000">Refresh every 5 minutes</SelectItem>
                <SelectItem value="0">Turn off auto-refresh</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ['alerts'] })}>
              Refresh Now
            </Button>
          </div>
        </div>
        
        <Card>
          <CardHeader>
            <CardTitle>Alert List</CardTitle>
            <CardDescription>
              {activeFilter !== 'all' 
                ? `Viewing ${activeFilter === 'false_positive' 
                    ? 'false positive' 
                    : activeFilter.replace('_', ' ')
                  } alerts (${alerts.length})`
                : `View and manage all security alerts (${alerts.length})`}
              {refreshInterval > 0 && ` • Auto-refreshes every ${refreshInterval / 1000} seconds`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">Loading alerts...</div>
            ) : alerts.length === 0 ? (
              <div className="flex justify-center py-8">No alerts found</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Rule Name</TableHead>
                    <TableHead>Created At</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {alerts.map((alert: Alert) => (
                    <TableRow 
                      key={alert.id} 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => showAlertDetails(alert)}
                    >
                      <TableCell className="font-mono text-xs">{alert.id}</TableCell>
                      <TableCell className="font-medium">{alert.rule_name}</TableCell>
                      <TableCell>{getBestTimestamp(alert)}</TableCell>
                      <TableCell>{getStatusBadge(alert.status)}</TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Select
                          value={alert.status}
                          onValueChange={(value) => handleStatusChange(alert.id, value as 'new' | 'in_progress' | 'resolved' | 'false_positive')}
                        >
                          <SelectTrigger className="w-32">
                            <SelectValue placeholder="Status" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="new">New</SelectItem>
                            <SelectItem value="in_progress">In Progress</SelectItem>
                            <SelectItem value="resolved">Resolved</SelectItem>
                            <SelectItem value="false_positive">False Positive</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Alert Details Dialog */}
        <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
          <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-hidden">
            <DialogHeader>
              <DialogTitle>Alert Details</DialogTitle>
              <DialogDescription>
                {selectedAlert && `Alert from rule "${selectedAlert.rule_name}" detected at ${getBestTimestamp(selectedAlert)}`}
              </DialogDescription>
            </DialogHeader>

            {selectedAlert && (
              <Tabs defaultValue="details" className="w-full">
                <TabsList className="grid grid-cols-3 w-full mb-2">
                  <TabsTrigger value="details">Details</TabsTrigger>
                  <TabsTrigger value="raw">Raw Data</TabsTrigger>
                  <TabsTrigger value="timeline">Timeline</TabsTrigger>
                </TabsList>
                
                <TabsContent value="details" className="space-y-4 mt-4 overflow-auto max-h-[60vh]">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h3 className="text-sm font-medium text-muted-foreground mb-1">Rule Name</h3>
                      <p>{selectedAlert.rule_name}</p>
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-muted-foreground mb-1">Status</h3>
                      <div>{getStatusBadge(selectedAlert.status)}</div>
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-muted-foreground mb-1">Created At</h3>
                      <p>{getBestTimestamp(selectedAlert)}</p>
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-muted-foreground mb-1">Alert ID</h3>
                      <p className="text-xs">{selectedAlert.id}</p>
                    </div>
                    <div className="col-span-2">
                      <h3 className="text-sm font-medium text-muted-foreground mb-1">Description</h3>
                      <p>{selectedAlert.description || "No description available"}</p>
                    </div>
                    
                    {selectedAlert.source && (
                      <div className="col-span-2">
                        <h3 className="text-sm font-medium text-muted-foreground mb-1">Source</h3>
                        <p>{selectedAlert.source}</p>
                      </div>
                    )}
                    
                    {selectedAlert.affected_host && (
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground mb-1">Affected Host</h3>
                        <p>{selectedAlert.affected_host}</p>
                      </div>
                    )}
                    
                    {selectedAlert.severity && (
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground mb-1">Severity</h3>
                        <Badge variant={
                          selectedAlert.severity === 'high' ? 'destructive' : 
                          selectedAlert.severity === 'medium' ? 'default' : 'outline'
                        }>
                          {selectedAlert.severity.toUpperCase()}
                        </Badge>
                      </div>
                    )}
                  </div>
                  
                  <div className="flex justify-end space-x-2 pt-4">
                    <Select
                      value={selectedAlert.status}
                      onValueChange={(value: 'new' | 'in_progress' | 'resolved' | 'false_positive') => {
                        handleStatusChange(selectedAlert.id, value)
                        setSelectedAlert({...selectedAlert, status: value})
                      }}
                    >
                      <SelectTrigger className="w-40">
                        <SelectValue placeholder="Update Status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="new">New</SelectItem>
                        <SelectItem value="in_progress">In Progress</SelectItem>
                        <SelectItem value="resolved">Resolved</SelectItem>
                        <SelectItem value="false_positive">False Positive</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </TabsContent>
                
                <TabsContent value="raw" className="mt-4 overflow-auto max-h-[60vh]">
                  <div className="flex justify-end mb-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={copyRawData}
                      className="flex items-center gap-1"
                    >
                      <Copy className="h-4 w-4" />
                      Copy
                    </Button>
                  </div>
                  <div className="border rounded-md border-border">
                    <ScrollArea className="h-[350px] w-full">
                      <pre className="text-xs p-4 bg-muted rounded-md overflow-hidden whitespace-pre-wrap break-all text-foreground">
                        {(() => {
                          try {
                            // Try to get raw_data first, if that doesn't exist or is empty, show the whole alert
                            const dataToDisplay = selectedAlert.raw_data || selectedAlert;
                            return JSON.stringify(dataToDisplay, null, 2);
                          } catch (error) {
                            return "Error displaying raw data";
                          }
                        })()}
                      </pre>
                    </ScrollArea>
                  </div>
                </TabsContent>
                
                <TabsContent value="timeline" className="mt-4 overflow-auto max-h-[60vh]">
                  <div className="relative pl-6 border-l border-border space-y-4 py-2">
                    <div>
                      <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-background bg-muted"></div>
                      <h3 className="text-sm font-medium">Alert Created</h3>
                      <time className="text-xs text-muted-foreground">
                        {getBestTimestamp(selectedAlert)}
                      </time>
                    </div>
                    
                    {selectedAlert.status !== 'new' && (
                      <div>
                        <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-background bg-muted"></div>
                        <h3 className="text-sm font-medium">Status Updated</h3>
                        <time className="text-xs text-muted-foreground">
                          {/* This would ideally come from a timeline field in the data */}
                          {new Date().toLocaleString()}
                        </time>
                        <p className="text-sm">Status changed to {selectedAlert.status.replace('_', ' ')}</p>
                      </div>
                    )}
                  </div>
                </TabsContent>
              </Tabs>
            )}
          </DialogContent>
        </Dialog>
      </Main>
    </>
  )
} 