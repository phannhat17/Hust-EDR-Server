import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
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
import { useState } from 'react'

export const Route = createFileRoute('/_authenticated/alerts')({
  component: AlertsPage
})

function AlertsPage() {
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds default

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => alertsApi.getAlerts(),
    refetchInterval: refreshInterval,
  })

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

  const handleStatusChange = (alertId: string, status: string) => {
    updateMutation.mutate({ alertId, status })
  }

  const handleRefreshIntervalChange = (value: string) => {
    setRefreshInterval(parseInt(value))
    toast({
      title: 'Auto-refresh updated',
      description: `Alerts will now refresh every ${parseInt(value) / 1000} seconds.`,
    })
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Alerts</h1>
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
            View and manage all security alerts
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
                  <TableHead>Rule Name</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((alert: Alert) => (
                  <TableRow key={alert.id}>
                    <TableCell className="font-medium">{alert.rule_name}</TableCell>
                    <TableCell>{new Date(alert.created_at).toLocaleString()}</TableCell>
                    <TableCell>{getStatusBadge(alert.status)}</TableCell>
                    <TableCell>
                      <Select
                        value={alert.status}
                        onValueChange={(value) => handleStatusChange(alert.id, value)}
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
    </div>
  )
} 