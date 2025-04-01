import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
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
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Copy, ChevronsRight, ArrowLeft, Terminal, Server, Check } from 'lucide-react'
import { toast } from '@/hooks/use-toast'

export default function AgentRegistration() {
  const navigate = useNavigate();
  const [agentName, setAgentName] = useState('');
  const [agentToken, setAgentToken] = useState(generateToken());
  const [activeTab, setActiveTab] = useState('generate');
  const apiHost = import.meta.env.VITE_API_URL || 'http://localhost:5000';

  function generateToken() {
    return Array.from({ length: 32 }, () => 
      Math.floor(Math.random() * 16).toString(16)
    ).join('');
  }

  function regenerateToken() {
    setAgentToken(generateToken());
    toast({
      title: 'New token generated',
      description: 'A new agent registration token has been generated.',
    });
  }

  function copyToClipboard(text: string, message: string) {
    navigator.clipboard.writeText(text).then(() => {
      toast({
        title: 'Copied!',
        description: message,
      });
    });
  }

  const linuxCommand = `curl -L "${apiHost}/api/agents/installer?token=${agentToken}&name=${agentName || 'edr-agent'}" | sudo bash`;
  const windowsCommand = `powershell -Command "& {Invoke-WebRequest -Uri '${apiHost}/api/agents/installer?token=${agentToken}&name=${agentName || 'edr-agent'}&platform=windows' -OutFile $env:TEMP\\edr-installer.ps1; Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File $env:TEMP\\edr-installer.ps1'}"`;

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
        <div className='mb-4 flex items-center justify-between space-y-2'>
          <div className="flex items-center">
            <Button variant="ghost" size="sm" className="mr-2" asChild>
              <Link to="/agents"><ArrowLeft className="mr-2 h-4 w-4" /> Back to Agents</Link>
            </Button>
            <h1 className='text-2xl font-bold tracking-tight'>Register New Agent</h1>
          </div>
        </div>

        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Agent Registration</CardTitle>
            <CardDescription>Follow these steps to register and install a new EDR agent</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="generate" value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="generate">1. Generate Token</TabsTrigger>
                <TabsTrigger value="install">2. Install Agent</TabsTrigger>
                <TabsTrigger value="verify" disabled={!agentToken}>3. Verify Connection</TabsTrigger>
              </TabsList>
              
              <TabsContent value="generate" className="space-y-4 py-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="agent-name">Agent Name (Optional)</Label>
                    <Input 
                      id="agent-name" 
                      placeholder="e.g. web-server-01" 
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="agent-token">Registration Token</Label>
                    <div className="flex space-x-2">
                      <Input 
                        id="agent-token" 
                        value={agentToken} 
                        readOnly
                      />
                      <Button onClick={regenerateToken} variant="outline" size="icon">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="h-4 w-4"
                        >
                          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                          <path d="M3 3v5h5" />
                        </svg>
                        <span className="sr-only">Regenerate</span>
                      </Button>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      This token will be used to authenticate the agent during installation.
                    </p>
                  </div>
                </div>
                
                <div className="flex justify-end">
                  <Button onClick={() => setActiveTab('install')}>
                    Next Step <ChevronsRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </TabsContent>
              
              <TabsContent value="install" className="space-y-4 py-4">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-lg font-medium">Choose your platform</h3>
                    <p className="text-sm text-muted-foreground">
                      Run the appropriate command on the system where you want to install the agent.
                    </p>
                  </div>
                  
                  <div className="space-y-4">
                    <Card>
                      <CardHeader>
                        <div className="flex items-center">
                          <Terminal className="mr-2 h-5 w-5" />
                          <CardTitle>Linux / macOS</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="relative">
                          <pre className="bg-muted rounded-md p-4 overflow-x-auto text-sm">
                            {linuxCommand}
                          </pre>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="absolute top-2 right-2" 
                            onClick={() => copyToClipboard(linuxCommand, "Linux installation command copied to clipboard")}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                    
                    <Card>
                      <CardHeader>
                        <div className="flex items-center">
                          <Server className="mr-2 h-5 w-5" />
                          <CardTitle>Windows</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="relative">
                          <pre className="bg-muted rounded-md p-4 overflow-x-auto text-sm">
                            {windowsCommand}
                          </pre>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="absolute top-2 right-2" 
                            onClick={() => copyToClipboard(windowsCommand, "Windows installation command copied to clipboard")}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
                
                <div className="flex justify-between">
                  <Button variant="outline" onClick={() => setActiveTab('generate')}>
                    <ArrowLeft className="mr-2 h-4 w-4" /> Previous Step
                  </Button>
                  <Button onClick={() => setActiveTab('verify')}>
                    Next Step <ChevronsRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </TabsContent>
              
              <TabsContent value="verify" className="space-y-4 py-4">
                <div className="space-y-4">
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <div className="mb-4 rounded-full bg-muted p-3">
                      <Check className="h-8 w-8 text-primary" />
                    </div>
                    <h3 className="text-lg font-medium">Waiting for agent to connect</h3>
                    <p className="text-sm text-muted-foreground max-w-md">
                      After installation, it may take a few moments for the agent to register with the server.
                      You can check the status on the agents page.
                    </p>
                  </div>
                </div>
                
                <div className="flex justify-between">
                  <Button variant="outline" onClick={() => setActiveTab('install')}>
                    <ArrowLeft className="mr-2 h-4 w-4" /> Previous Step
                  </Button>
                  <Button onClick={() => navigate({ to: '/agents' })}>
                    Go to Agents List <ChevronsRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </Main>
    </>
  )
}

const topNav = [
  {
    title: 'Register Agent',
    href: '/agents/register',
    isActive: true,
    disabled: false,
  },
] 