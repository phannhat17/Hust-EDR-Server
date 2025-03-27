import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { rulesApi } from '@/lib/api'
import { Rule } from '@/lib/types'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/hooks/use-toast'
import { Trash2, Edit, Play } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

export const Route = createFileRoute('/_authenticated/rules')({
  component: RulesPage
})

function RulesPage() {
  const { data: rules = [], isLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: () => rulesApi.getRules(),
  })

  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (filename: string) => rulesApi.deleteRule(filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      toast({
        title: 'Rule deleted',
        description: 'The rule has been deleted successfully.',
      })
    },
  })

  const restartMutation = useMutation({
    mutationFn: () => rulesApi.restartElastAlert(),
    onSuccess: () => {
      toast({
        title: 'ElastAlert restarted',
        description: 'ElastAlert has been restarted successfully. New rules will be applied.',
      })
    },
  })

  const handleDelete = (filename: string) => {
    deleteMutation.mutate(filename)
  }

  const handleRestart = () => {
    restartMutation.mutate()
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Rules</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ['rules'] })}>
            Refresh
          </Button>
          <Button onClick={handleRestart}>
            <Play className="mr-2 h-4 w-4" /> Restart ElastAlert
          </Button>
        </div>
      </div>
      
      <Card>
        <CardHeader>
          <CardTitle>Rule List</CardTitle>
          <CardDescription>View and manage all ElastAlert rules</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">Loading rules...</div>
          ) : rules.length === 0 ? (
            <div className="flex justify-center py-8">No rules found</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Index</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule: Rule) => (
                  <TableRow key={rule.filename}>
                    <TableCell className="font-medium">{rule.name}</TableCell>
                    <TableCell>{rule.type}</TableCell>
                    <TableCell>{rule.index}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button variant="outline" size="icon">
                              <Edit className="h-4 w-4" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="sm:max-w-2xl">
                            <DialogHeader>
                              <DialogTitle>Edit Rule: {rule.name}</DialogTitle>
                              <DialogDescription>
                                Modify the rule configuration
                              </DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                              {/* Form content would go here */}
                              <pre className="bg-slate-100 p-4 rounded text-xs overflow-auto max-h-96">
                                {JSON.stringify(rule, null, 2)}
                              </pre>
                            </div>
                          </DialogContent>
                        </Dialog>
                        
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="outline" size="icon">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This will permanently delete the rule "{rule.name}".
                                You won't be able to recover it.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(rule.filename)}>
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
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