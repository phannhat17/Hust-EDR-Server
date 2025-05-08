import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { toast } from '@/hooks/use-toast'
import { logsApi } from '@/lib/api'
import { Loader2, RefreshCcw, Download } from 'lucide-react'

export const Route = createFileRoute('/_authenticated/logs')({
  component: LogsPage
})

function LogsPage() {
  const [selectedLogType, setSelectedLogType] = useState('app')
  const [searchQuery, setSearchQuery] = useState('')
  const [logLevel, setLogLevel] = useState('any')
  const [lines, setLines] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds
  
  // Fetch log types
  const { 
    data: logTypes = [], 
    error: logTypesError,
    isError: isLogTypesError 
  } = useQuery({
    queryKey: ['logTypes'],
    queryFn: async () => {
      try {
        return await logsApi.getLogTypes();
      } catch (error) {
        console.error('Error fetching log types:', error);
        toast({
          title: 'Error',
          description: 'Failed to fetch log types. Please try again later.',
          variant: 'destructive',
        });
        return [];
      }
    }
  })
  
  // Fetch logs for the selected type with filters
  const { 
    data: logs = { content: [], log_type: selectedLogType, count: 0, lines: 0 },
    isLoading,
    error: logsError,
    isError: isLogsError,
    refetch,
    isRefetching
  } = useQuery({
    queryKey: ['logs', selectedLogType, searchQuery, logLevel, lines],
    queryFn: async () => {
      try {
        return await logsApi.getLogs(selectedLogType, {
          lines,
          search: searchQuery || undefined,
          level: logLevel === "any" ? undefined : logLevel || undefined
        });
      } catch (error) {
        console.error('Error fetching logs:', error);
        toast({
          title: 'Error',
          description: 'Failed to fetch logs. Please try again later.',
          variant: 'destructive',
        });
        return { content: [], log_type: selectedLogType, count: 0, lines: 0 };
      }
    },
    refetchInterval: autoRefresh ? refreshInterval : false,
  })
  
  // Auto scroll to bottom of logs when new logs are loaded
  useEffect(() => {
    const scrollArea = document.getElementById('logs-scroll-area')
    if (scrollArea) {
      scrollArea.scrollTop = scrollArea.scrollHeight
    }
  }, [logs])

  // Display error notification if API fails
  useEffect(() => {
    if (isLogsError && logsError) {
      toast({
        title: 'Error',
        description: 'There was a problem loading the logs. Please try again.',
        variant: 'destructive',
      });
    }
  }, [isLogsError, logsError]);
  
  const handleRefresh = () => {
    refetch()
    toast({
      title: 'Refreshed',
      description: 'Logs have been refreshed.',
    })
  }
  
  const handleAutoRefreshChange = (enabled: boolean) => {
    setAutoRefresh(enabled)
    toast({
      title: enabled ? 'Auto-refresh enabled' : 'Auto-refresh disabled',
      description: enabled ? `Logs will refresh every ${refreshInterval / 1000} seconds` : 'Logs will not refresh automatically',
    })
  }
  
  const handleRefreshIntervalChange = (value: string) => {
    const interval = parseInt(value)
    setRefreshInterval(interval)
    toast({
      title: 'Refresh interval updated',
      description: `Logs will refresh every ${interval / 1000} seconds`,
    })
  }
  
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    refetch()
  }
  
  const downloadLogs = () => {
    try {
      if (!logs || !logs.content || logs.content.length === 0) {
        toast({
          title: 'No logs to download',
          description: 'There are no logs available to download.',
          variant: 'destructive',
        });
        return;
      }
      
      const content = logs.content.join('')
      const blob = new Blob([content], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${selectedLogType}_logs_${new Date().toISOString().slice(0, 10)}.log`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      
      toast({
        title: 'Downloaded',
        description: `Logs have been downloaded as ${selectedLogType}_logs.log`,
      })
    } catch (error) {
      console.error('Error downloading logs:', error);
      toast({
        title: 'Download failed',
        description: 'There was a problem downloading the logs.',
        variant: 'destructive',
      });
    }
  }
  
  // Helper to highlight log levels with colors
  const highlightLogLevel = (line: string) => {
    if (line.includes('[DEBUG]')) {
      return <span><Badge variant="outline" className="mr-2 font-mono">DEBUG</Badge>{line.replace(/\[DEBUG\]/, '')}</span>
    } else if (line.includes('[INFO]')) {
      return <span><Badge variant="outline" className="mr-2 font-mono bg-blue-50">INFO</Badge>{line.replace(/\[INFO\]/, '')}</span>
    } else if (line.includes('[WARNING]')) {
      return <span><Badge variant="outline" className="mr-2 font-mono bg-yellow-50">WARNING</Badge>{line.replace(/\[WARNING\]/, '')}</span>
    } else if (line.includes('[ERROR]')) {
      return <span><Badge variant="destructive" className="mr-2 font-mono">ERROR</Badge>{line.replace(/\[ERROR\]/, '')}</span>
    } else if (line.includes('[CRITICAL]')) {
      return <span><Badge variant="destructive" className="mr-2 font-mono bg-red-700">CRITICAL</Badge>{line.replace(/\[CRITICAL\]/, '')}</span>
    }
    return line
  }
  
  return (
    <>
      <Header>
        <h1 className="text-lg font-semibold">System Logs</h1>
        <div className="ml-auto flex items-center space-x-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={handleRefresh}
            disabled={isRefetching}
          >
            {isRefetching ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <RefreshCcw className="h-4 w-4 mr-1" />
            )}
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={downloadLogs}
            disabled={!logs}
          >
            <Download className="h-4 w-4 mr-1" />
            Download
          </Button>
          <Search />
          <ThemeSwitch />
        </div>
      </Header>
      
      <Main>
        <div className="grid grid-cols-1 gap-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Log Viewer</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col space-y-4">
                <div className="flex flex-wrap gap-4">
                  <div className="flex-1 min-w-[200px]">
                    <label className="block text-sm font-medium mb-1">Log Type</label>
                    <Select
                      value={selectedLogType}
                      onValueChange={setSelectedLogType}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select log type" />
                      </SelectTrigger>
                      <SelectContent>
                        {logTypes.map((type: string) => (
                          <SelectItem key={type} value={type}>
                            {type}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="flex-1 min-w-[200px]">
                    <label className="block text-sm font-medium mb-1">Log Level</label>
                    <Select
                      value={logLevel}
                      onValueChange={setLogLevel}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Any level" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="any">Any level</SelectItem>
                        <SelectItem value="debug">DEBUG</SelectItem>
                        <SelectItem value="info">INFO</SelectItem>
                        <SelectItem value="warning">WARNING</SelectItem>
                        <SelectItem value="error">ERROR</SelectItem>
                        <SelectItem value="critical">CRITICAL</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="flex-1 min-w-[200px]">
                    <label className="block text-sm font-medium mb-1">Lines to Show</label>
                    <Select
                      value={lines.toString()}
                      onValueChange={(value) => setLines(parseInt(value))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="50">50 lines</SelectItem>
                        <SelectItem value="100">100 lines</SelectItem>
                        <SelectItem value="250">250 lines</SelectItem>
                        <SelectItem value="500">500 lines</SelectItem>
                        <SelectItem value="1000">1000 lines</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="flex-1 min-w-[200px]">
                    <label className="block text-sm font-medium mb-1">Auto-refresh</label>
                    <div className="flex space-x-2">
                      <Select
                        value={refreshInterval.toString()}
                        onValueChange={handleRefreshIntervalChange}
                        disabled={!autoRefresh}
                      >
                        <SelectTrigger className="flex-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="5000">5 seconds</SelectItem>
                          <SelectItem value="10000">10 seconds</SelectItem>
                          <SelectItem value="30000">30 seconds</SelectItem>
                          <SelectItem value="60000">1 minute</SelectItem>
                          <SelectItem value="300000">5 minutes</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button
                        variant={autoRefresh ? "default" : "outline"}
                        onClick={() => handleAutoRefreshChange(!autoRefresh)}
                      >
                        {autoRefresh ? "On" : "Off"}
                      </Button>
                    </div>
                  </div>
                </div>
                
                <form onSubmit={handleSearch} className="flex space-x-2">
                  <Input 
                    placeholder="Search logs..." 
                    value={searchQuery} 
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="flex-1"
                  />
                  <Button type="submit">Search</Button>
                </form>
                
                <div className="border rounded-md">
                  <ScrollArea id="logs-scroll-area" className="h-[60vh] w-full font-mono text-sm">
                    {isLoading ? (
                      <div className="flex items-center justify-center h-full">
                        <Loader2 className="h-8 w-8 animate-spin" />
                        <span className="ml-2">Loading logs...</span>
                      </div>
                    ) : logs && logs.content && logs.content.length > 0 ? (
                      <pre className="p-4 whitespace-pre-wrap">
                        {logs.content.map((line: string, index: number) => (
                          <div key={index} className="py-1 border-b border-dashed border-gray-200 last:border-0">
                            {highlightLogLevel(line)}
                          </div>
                        ))}
                      </pre>
                    ) : (
                      <div className="flex items-center justify-center h-full text-muted-foreground">
                        {isLogsError ? 'Error loading logs. Please try again.' : 'No logs available'}
                      </div>
                    )}
                  </ScrollArea>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </Main>
    </>
  )
} 