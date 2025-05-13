import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ThemeSwitch } from '@/components/theme-switch'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { toast } from '@/hooks/use-toast'
import { iocsApi } from '@/lib/api'
import { Loader2, Trash2, Plus, AlertTriangle } from 'lucide-react'
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogFooter, 
  DialogHeader, 
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

export const Route = createFileRoute('/_authenticated/iocs')({
  component: IOCsPage
})

type IOCType = 'ip' | 'hash' | 'url'
type SeverityType = 'low' | 'medium' | 'high' | 'critical'
type HashType = 'md5' | 'sha1' | 'sha256'

interface IOC {
  value: string
  added_at: number
  description: string
  severity: SeverityType
  hash_type?: HashType
}

function IOCsPage() {
  const [activeTab, setActiveTab] = useState<IOCType>('ip')
  const [searchQuery, setSearchQuery] = useState('')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showUploadDialog, setShowUploadDialog] = useState(false)
  const [isProcessingFile, setIsProcessingFile] = useState(false)
  const [uploadStats, setUploadStats] = useState<{ imported: number, failed: number, duplicates: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const queryClient = useQueryClient()
  
  // Fetch all IOCs
  const { data: iocsData, isLoading } = useQuery({
    queryKey: ['iocs'],
    queryFn: () => iocsApi.getAllIOCs()
  })
  
  // Add IOC mutation
  const addIOCMutation = useMutation({
    mutationFn: async (iocData: {
      type: IOCType
      value: string
      description: string
      severity: SeverityType
      hash_type?: HashType
    }) => {
      const { type, value, description, severity, hash_type } = iocData
      
      switch (type) {
        case 'ip':
          return iocsApi.addIpIOC({ value, description, severity })
        case 'hash':
          return iocsApi.addHashIOC({ value, hash_type: hash_type || 'sha256', description, severity })
        case 'url':
          return iocsApi.addUrlIOC({ value, description, severity })
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['iocs'] })
      setShowAddDialog(false)
      toast({
        title: 'IOC added',
        description: 'The indicator of compromise has been added successfully.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.message || 'Failed to add IOC',
        variant: 'destructive',
      })
    }
  })
  
  // Remove IOC mutation
  const removeIOCMutation = useMutation({
    mutationFn: ({ type, value }: { type: IOCType, value: string }) => {
      return iocsApi.removeIOC(type, value)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['iocs'] })
      toast({
        title: 'IOC removed',
        description: 'The indicator of compromise has been removed successfully.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.message || 'Failed to remove IOC',
        variant: 'destructive',
      })
    }
  })
  
  // Send IOC updates mutation
  const sendIOCUpdatesMutation = useMutation({
    mutationFn: () => iocsApi.sendIOCUpdates(),
    onSuccess: (data) => {
      toast({
        title: 'Updates sent',
        description: data.message || `IOC updates sent to ${data.agents_updated} agents.`,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.message || 'Failed to send IOC updates',
        variant: 'destructive',
      })
    }
  })
  
  const handleSendUpdates = () => {
    sendIOCUpdatesMutation.mutate()
  }
  
  const handleRemoveIOC = (type: IOCType, value: string) => {
    if (confirm(`Are you sure you want to remove this ${type} IOC?`)) {
      removeIOCMutation.mutate({ type, value })
    }
  }
  
  // Filter IOCs by search query
  const filterIOCs = (iocs: Record<string, IOC>, query: string) => {
    if (!query) return iocs
    
    const lowercaseQuery = query.toLowerCase()
    return Object.entries(iocs).reduce((filtered, [key, value]) => {
      if (key.toLowerCase().includes(lowercaseQuery) ||
          value.description.toLowerCase().includes(lowercaseQuery)) {
        filtered[key] = value
      }
      return filtered
    }, {} as Record<string, IOC>)
  }
  
  // Get IOCs for active tab
  const getActiveIOCs = () => {
    if (!iocsData || !iocsData.iocs) return {}
    
    const iocs = {
      ip: iocsData.iocs.ip_addresses || {},
      hash: iocsData.iocs.file_hashes || {},
      url: iocsData.iocs.urls || {}
    }
    
    return filterIOCs(iocs[activeTab], searchQuery)
  }
  
  // Count of IOCs per type
  const iocCounts = {
    ip: iocsData?.iocs?.ip_addresses ? Object.keys(iocsData.iocs.ip_addresses).length : 0,
    hash: iocsData?.iocs?.file_hashes ? Object.keys(iocsData.iocs.file_hashes).length : 0,
    url: iocsData?.iocs?.urls ? Object.keys(iocsData.iocs.urls).length : 0
  }
  
  // Format timestamp
  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString()
  }
  
  // Get severity badge
  const getSeverityBadge = (severity: SeverityType) => {
    const capitalized = typeof severity === 'string'
      ? severity.charAt(0).toUpperCase() + severity.slice(1).toLowerCase()
      : severity;
      
    switch (severity.toLowerCase()) {
      case 'low':
        return <Badge variant="outline">Low</Badge>
      case 'medium':
        return <Badge variant="secondary">Medium</Badge>
      case 'high':
        return <Badge variant="destructive">High</Badge>
      case 'critical':
        return <Badge variant="black">Critical</Badge>
      default:
        return <Badge variant="outline">{capitalized}</Badge>
    }
  }
  
  // Add handleFileUpload function to process uploaded files
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    try {
      setIsProcessingFile(true)
      setUploadStats(null)
      
      // Read the file as text
      const fileText = await readFileAsText(file)
      
      // Initialize counters
      let imported = 0
      let failed = 0
      let duplicates = 0
      
      // Process CSV file
      const rows = parseCSV(fileText)
      
      // Process each row
      for (let i = 1; i < rows.length; i++) { // Skip header row
        const row = rows[i]
        if (row.length < 3) continue // Skip incomplete rows
        
        const type = row[0]?.trim().toLowerCase()
        const value = row[1]?.trim()
        const description = row[2]?.trim() || ''
        const severity = (row[3]?.trim().toLowerCase() || 'medium') as SeverityType
        const hashType = (row[4]?.trim().toLowerCase() || 'sha256') as HashType
        
        if (!value) continue // Skip empty values
        
        try {
          // Add IOC based on type
          if (type === 'ip') {
            await iocsApi.addIpIOC({ value, description, severity })
            imported++
          } else if (type === 'hash') {
            await iocsApi.addHashIOC({ value, hash_type: hashType, description, severity })
            imported++
          } else if (type === 'url') {
            await iocsApi.addUrlIOC({ value, description, severity })
            imported++
          } else {
            failed++
            console.error(`Unknown IOC type: ${type}`)
          }
        } catch (error: any) {
          if (error.response?.data?.message?.includes('already exists')) {
            duplicates++
          } else {
            failed++
            console.error(`Failed to add ${type} ${value}:`, error)
          }
        }
      }
      
      // Update stats and UI
      setUploadStats({ imported, failed, duplicates })
      
      // Refresh the data
      queryClient.invalidateQueries({ queryKey: ['iocs'] })
      
      // Show success toast
      toast({
        title: 'File processed',
        description: `${imported} IOCs imported, ${duplicates} duplicates found, ${failed} failed.`,
      })
      
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (error) {
      console.error('Error processing file:', error)
      toast({
        title: 'Error',
        description: 'Failed to process the uploaded file. Make sure it is a valid CSV file.',
        variant: 'destructive',
      })
    } finally {
      setIsProcessingFile(false)
    }
  }
  
  // Helper function to read file as text
  const readFileAsText = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (event) => {
        if (event.target?.result) {
          resolve(event.target.result as string)
        } else {
          reject(new Error('Failed to read file'))
        }
      }
      reader.onerror = () => reject(reader.error)
      reader.readAsText(file)
    })
  }
  
  // Add CSV parsing function
  const parseCSV = (text: string): string[][] => {
    // Split by newlines
    const rows = text.split(/\r?\n/).filter(row => row.trim().length > 0)
    
    // Parse each row, handling quoted values
    return rows.map(row => {
      const result: string[] = []
      let inQuotes = false
      let currentValue = ''
      
      for (let i = 0; i < row.length; i++) {
        const char = row[i]
        
        if (char === '"') {
          inQuotes = !inQuotes
        } else if (char === ',' && !inQuotes) {
          result.push(currentValue)
          currentValue = ''
        } else {
          currentValue += char
        }
      }
      
      // Add the last value
      result.push(currentValue)
      return result
    })
  }
  
  return (
    <>
      <Header>
        <h1 className="text-lg font-semibold">Indicators of Compromise (IOCs)</h1>
        <div className="ml-auto flex items-center space-x-2">
          <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Plus className="h-4 w-4 mr-1" />
                Import from CSV
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Import IOCs from CSV File</DialogTitle>
                <DialogDescription>
                  Upload a CSV file containing IOCs to import.
                  <br />
                  <span className="font-semibold mt-2 block">File format:</span>
                </DialogDescription>
              </DialogHeader>
              <div className="py-2">
                <div className="font-medium mb-1">CSV Format:</div>
                <pre className="bg-slate-100 dark:bg-slate-800 p-4 rounded-md text-xs overflow-auto">
{`type,value,description,severity,hash_type
ip,192.168.1.1,Malicious IP,high
hash,44d88612fea8a8f36de82e1278abb02f,Malware hash,critical,md5
url,example.com/malware,Malicious URL,medium`}
                </pre>
              </div>
              <div className="space-y-4">
                <Label htmlFor="ioc-file">Select file</Label>
                <Input
                  ref={fileInputRef}
                  id="ioc-file" 
                  type="file" 
                  accept=".csv"
                  onChange={handleFileUpload}
                  disabled={isProcessingFile}
                />
                {isProcessingFile && (
                  <div className="flex items-center space-x-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Processing file...</span>
                  </div>
                )}
                {uploadStats && (
                  <div className="bg-slate-100 dark:bg-slate-800 p-3 rounded-md text-sm">
                    <div className="font-medium">Import results:</div>
                    <ul className="mt-1 space-y-1">
                      <li className="text-green-600 dark:text-green-400">Imported: {uploadStats.imported}</li>
                      <li className="text-yellow-600 dark:text-yellow-400">Duplicates: {uploadStats.duplicates}</li>
                      <li className="text-red-600 dark:text-red-400">Failed: {uploadStats.failed}</li>
                    </ul>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button 
                  variant="outline" 
                  onClick={() => setShowUploadDialog(false)}
                >
                  Close
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Button 
            variant="outline"
            onClick={handleSendUpdates}
            disabled={sendIOCUpdatesMutation.isPending}
          >
            {sendIOCUpdatesMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                Sending...
              </>
            ) : (
              <>
                Send Update
              </>
            )}
          </Button>
          <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-1" />
                Add IOC
              </Button>
            </DialogTrigger>
            <AddIOCDialog activeTab={activeTab} onSubmit={(data) => addIOCMutation.mutate(data)} />
          </Dialog>
          
          <form onSubmit={(e) => {
            e.preventDefault()
            // Just rerender with the current search query
          }} className="w-72">
            <Input 
              placeholder="Search IOCs..." 
              value={searchQuery} 
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </form>
          <ThemeSwitch />
        </div>
      </Header>
      
      <Main>
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as IOCType)}>
          <TabsList className="grid grid-cols-3 w-full max-w-2xl mb-8">
            <TabsTrigger value="ip" className="relative">
              IP Addresses
              <Badge className="ml-2 h-5 w-5 p-0 flex items-center justify-center text-xs rounded-full">
                {iocCounts.ip}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="hash">
              File Hashes
              <Badge className="ml-2 h-5 w-5 p-0 flex items-center justify-center text-xs rounded-full">
                {iocCounts.hash}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="url">
              URLs
              <Badge className="ml-2 h-5 w-5 p-0 flex items-center justify-center text-xs rounded-full">
                {iocCounts.url}
              </Badge>
            </TabsTrigger>
          </TabsList>
          
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>{getTabTitle(activeTab)}</CardTitle>
              <CardDescription>{getTabDescription(activeTab)}</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center h-48">
                  <Loader2 className="h-8 w-8 animate-spin" />
                  <span className="ml-2">Loading IOCs...</span>
                </div>
              ) : (
                <IOCsTable 
                  type={activeTab} 
                  iocs={getActiveIOCs()} 
                  onRemove={(value) => handleRemoveIOC(activeTab, value)} 
                  formatDate={formatDate}
                  getSeverityBadge={getSeverityBadge}
                />
              )}
            </CardContent>
          </Card>
        </Tabs>
      </Main>
    </>
  )
}

// Helper component for the IOCs table
function IOCsTable({ 
  type, 
  iocs, 
  onRemove,
  formatDate,
  getSeverityBadge
}: { 
  type: IOCType
  iocs: Record<string, IOC>
  onRemove: (value: string) => void
  formatDate: (timestamp: number) => string
  getSeverityBadge: (severity: SeverityType) => React.ReactNode
}) {
  if (!iocs || Object.keys(iocs).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-center">
        <AlertTriangle className="h-8 w-8 text-muted-foreground mb-2" />
        <h3 className="text-lg font-medium">No IOCs found</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Add a new IOC using the "Add IOC" button.
        </p>
      </div>
    )
  }
  
  return (
    <div className="border rounded-md">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-1/3">{getValueHeader(type)}</TableHead>
            {type === 'hash' && <TableHead>Hash Type</TableHead>}
            <TableHead>Description</TableHead>
            <TableHead>Severity</TableHead>
            <TableHead>Added</TableHead>
            <TableHead className="w-14"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(iocs).map(([value, data]) => (
            <TableRow key={value}>
              <TableCell className="font-mono text-sm break-all">
                {value}
              </TableCell>
              {type === 'hash' && (
                <TableCell>{data.hash_type || 'Unknown'}</TableCell>
              )}
              <TableCell>{data.description || 'No description'}</TableCell>
              <TableCell>{getSeverityBadge(data.severity)}</TableCell>
              <TableCell>{formatDate(data.added_at)}</TableCell>
              <TableCell>
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => onRemove(value)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// Add IOC Dialog Component
function AddIOCDialog({ 
  activeTab,
  onSubmit 
}: { 
  activeTab: IOCType
  onSubmit: (data: any) => void
}) {
  const [type, setType] = useState<IOCType>(activeTab)
  const [value, setValue] = useState('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<SeverityType>('medium')
  const [hashType, setHashType] = useState<HashType>('sha256')
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    const data: any = {
      type,
      value,
      description,
      severity
    }
    
    if (type === 'hash') {
      data.hash_type = hashType
    }
    
    onSubmit(data)
  }
  
  return (
    <DialogContent className="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>Add Indicator of Compromise</DialogTitle>
        <DialogDescription>
          Add a new IOC to the database for detection and blocking.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="ioc-type">IOC Type</Label>
            <Select value={type} onValueChange={(val) => setType(val as IOCType)}>
              <SelectTrigger>
                <SelectValue placeholder="Select IOC type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ip">IP Address</SelectItem>
                <SelectItem value="hash">File Hash</SelectItem>
                <SelectItem value="url">URL</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          {type === 'hash' && (
            <div className="grid gap-2">
              <Label htmlFor="hash-type">Hash Type</Label>
              <Select value={hashType} onValueChange={(val) => setHashType(val as HashType)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select hash type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="md5">MD5</SelectItem>
                  <SelectItem value="sha1">SHA1</SelectItem>
                  <SelectItem value="sha256">SHA256</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          
          <div className="grid gap-2">
            <Label htmlFor="value">{getValueLabel(type)}</Label>
            <Input
              id="value"
              placeholder={getValuePlaceholder(type)}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
            />
          </div>
          
          <div className="grid gap-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Describe this IOC and why it's being blocked"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          
          <div className="grid gap-2">
            <Label htmlFor="severity">Severity</Label>
            <Select value={severity} onValueChange={(val) => setSeverity(val as SeverityType)}>
              <SelectTrigger>
                <SelectValue placeholder="Select severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button type="submit">Add IOC</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  )
}

// Helper functions for UI text
function getTabTitle(type: IOCType): string {
  switch (type) {
    case 'ip':
      return 'IP Address IOCs'
    case 'hash':
      return 'File Hash IOCs'
    case 'url':
      return 'URL IOCs'
    default:
      return 'Unknown'
  }
}

function getTabDescription(type: IOCType): string {
  switch (type) {
    case 'ip':
      return 'Malicious IP addresses that are blocked from communication'
    case 'hash':
      return 'File hashes of known malicious files to be detected and blocked'
    case 'url':
      return 'Malicious URLs that are blocked from being accessed'
    default:
      return ''
  }
}

function getValueHeader(type: IOCType): string {
  switch (type) {
    case 'ip':
      return 'IP Address'
    case 'hash':
      return 'File Hash'
    case 'url':
      return 'URL'
    default:
      return 'Value'
  }
}

function getValueLabel(type: IOCType): string {
  switch (type) {
    case 'ip':
      return 'IP Address'
    case 'hash':
      return 'File Hash'
    case 'url':
      return 'URL'
    default:
      return 'Value'
  }
}

function getValuePlaceholder(type: IOCType): string {
  switch (type) {
    case 'ip':
      return 'e.g., 192.168.1.1'
    case 'hash':
      return 'e.g., a94a8fe5ccb19ba61c4c0873d391e987982fbbd3'
    case 'url':
      return 'e.g., https://malicious-site.com'
    default:
      return ''
  }
} 