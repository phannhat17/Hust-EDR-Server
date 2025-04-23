import { useState, useEffect } from 'react'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Copy, ChevronsRight, ArrowLeft, Server, Check } from 'lucide-react'
import { toast } from '@/hooks/use-toast'
import axios from 'axios'

export default function AgentRegistration() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('install');
  const [installCommand, setInstallCommand] = useState('');
  const apiHost = import.meta.env.VITE_API_URL || 'http://localhost:5000';
  
  useEffect(() => {
    fetchInstallCommand();
  }, []);
  
  async function fetchInstallCommand() {
    try {
      const response = await axios.get(`${apiHost}/api/install`);
      setInstallCommand(response.data);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to fetch installation command.',
        variant: 'destructive'
      });
      console.error('Failed to fetch install command:', error);
    }
  }

  function copyToClipboard(text: string, message: string) {
    navigator.clipboard.writeText(text).then(() => {
      toast({
        title: 'Copied!',
        description: message,
      });
    });
  }

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
            <Tabs defaultValue="install" value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="install">1. Install Agent</TabsTrigger>
                <TabsTrigger value="verify">2. Verify Connection</TabsTrigger>
              </TabsList>
              
              <TabsContent value="install" className="space-y-4 py-4">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-lg font-medium">Installation Command</h3>
                    <p className="text-sm text-muted-foreground">
                      Run the following command on the system where you want to install the agent.
                    </p>
                  </div>
                  
                  <div className="space-y-4">
                    <Card>
                      <CardHeader>
                        <div className="flex items-center">
                          <Server className="mr-2 h-5 w-5" />
                          <CardTitle>Installation Command</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="relative">
                          <pre className="bg-muted rounded-md p-4 overflow-x-auto text-sm">
                            {installCommand}
                          </pre>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="absolute top-2 right-2" 
                            onClick={() => copyToClipboard(installCommand, "Installation command copied to clipboard")}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
                
                <div className="flex justify-end">
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