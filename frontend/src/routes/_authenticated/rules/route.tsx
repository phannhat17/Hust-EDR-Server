import { useQuery } from '@tanstack/react-query'
import { createFileRoute, useRouter } from '@tanstack/react-router'
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
import { Trash2, Edit, Play, Plus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { TopNav } from '@/components/layout/top-nav'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { useState, useEffect, useRef, useMemo } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

// Rule form schema for validation
const ruleFormSchema = z.object({
  name: z.string().min(2, { message: 'Name must be at least 2 characters' }),
  type: z.string().min(1, { message: 'Type is required' }),
  index: z.string().min(1, { message: 'Index pattern is required' }),
  alert: z.array(z.string()).min(1, { message: 'At least one alert type is required' }),
  description: z.string().optional(),
  is_enabled: z.boolean().default(true),
  filter: z.array(z.record(z.any())).optional(),
  alert_subject: z.string().optional(),
  alert_text: z.string().optional(),
  alert_text_type: z.string().optional(),
  timestamp_field: z.string().optional(),
  extra_settings: z.record(z.any()).optional(),
});

type RuleFormValues = z.infer<typeof ruleFormSchema>;

// Rule form component
function RuleForm({ 
  rule, 
  onSubmit, 
  onCancel 
}: { 
  rule?: Rule; 
  onSubmit: (data: any) => Promise<any>;
  onCancel: () => void;
}) {
  const isEdit = !!rule;
  const [submitting, setSubmitting] = useState(false);
  
  // Extract alert types from the rule.alert array
  const alertTypes = rule?.alert || [];
  
  // Set default values or use provided rule
  const defaultValues = rule ? {
    ...rule,
    alert: alertTypes,
    is_enabled: rule.is_enabled !== false, // Default to true if not specified
    filter: rule.filter || [],
  } : {
    name: '',
    type: 'any',
    index: 'logs-*',
    alert: ['email'],
    is_enabled: true,
    description: '',
    alert_subject: '',
    alert_text: '',
    alert_text_type: 'plain',
    timestamp_field: '@timestamp',
    filter: [],
    extra_settings: {},
  };
  
  // Setup form with validation
  const form = useForm<RuleFormValues>({
    resolver: zodResolver(ruleFormSchema),
    defaultValues,
  });
  
  // Handle form submission
  const handleSubmit = (data: RuleFormValues) => {
    setSubmitting(true);
    onSubmit({
      ...data,
      // Merge the form data with any additional data needed
    })
      .then(() => {
        // Handle successful submission
      })
      .catch((error) => {
        // Handle error
        console.error("Error submitting form:", error);
      })
      .finally(() => {
        setSubmitting(false);
      });
  };

  // Handle alert tag deletion
  const handleDeleteTag = (index: number) => {
    const currentAlerts = form.getValues("alert");
    const newAlerts = [...currentAlerts];
    newAlerts.splice(index, 1);
    form.setValue("alert", newAlerts, { shouldValidate: true });
  };

  // Handle adding new alert tag
  const [newAlertType, setNewAlertType] = useState("");
  const handleAddTag = () => {
    if (!newAlertType.trim()) return;
    
    const currentAlerts = form.getValues("alert");
    form.setValue("alert", [...currentAlerts, newAlertType.trim()], { shouldValidate: true });
    setNewAlertType("");
  };
  
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 gap-6">
          {/* Section: Basic Information */}
          <div className="rounded-lg border p-4 bg-accent/10">
            <h3 className="text-lg font-medium mb-4">Basic Information</h3>
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center">
                      Rule Name
                      <span className="text-destructive ml-1">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="My Rule" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              
              <FormField
                control={form.control}
                name="is_enabled"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3 shadow-sm">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">Enabled</FormLabel>
                      <FormDescription>
                        Enable or disable this rule
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <div className="grid grid-cols-2 gap-4 mt-4">
              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center">
                      Rule Type
                      <span className="text-destructive ml-1">*</span>
                    </FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select rule type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="any">Any</SelectItem>
                        <SelectItem value="blacklist">Blacklist</SelectItem>
                        <SelectItem value="whitelist">Whitelist</SelectItem>
                        <SelectItem value="change">Change</SelectItem>
                        <SelectItem value="frequency">Frequency</SelectItem>
                        <SelectItem value="spike">Spike</SelectItem>
                        <SelectItem value="flatline">Flatline</SelectItem>
                        <SelectItem value="new_term">New Term</SelectItem>
                        <SelectItem value="cardinality">Cardinality</SelectItem>
                        <SelectItem value="metric_aggregation">Metric Aggregation</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      The type of rule determines how ElastAlert processes events
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              
              <FormField
                control={form.control}
                name="index"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center">
                      Index Pattern
                      <span className="text-destructive ml-1">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="logs-*" {...field} />
                    </FormControl>
                    <FormDescription>
                      Elasticsearch index pattern to search
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            
            <div className="mt-4">
              <FormField
                control={form.control}
                name="timestamp_field"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Timestamp Field</FormLabel>
                    <FormControl>
                      <Input placeholder="@timestamp" {...field} />
                    </FormControl>
                    <FormDescription>
                      Field containing the timestamp in your documents
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            
            <div className="mt-4">
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Enter a description for this rule"
                        className="resize-none min-h-[100px]"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      Detailed description of what this rule detects
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </div>
          
          {/* Section: Alert Configuration */}
          <div className="rounded-lg border p-4 bg-accent/10">
            <h3 className="text-lg font-medium mb-4">Alert Configuration</h3>
            
            <FormField
              control={form.control}
              name="alert"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="flex items-center">
                    Alert Types
                    <span className="text-destructive ml-1">*</span>
                  </FormLabel>
                  <FormDescription className="mt-0 mb-2">
                    Specify where alerts should be sent (email, slack, discord, etc.)
                  </FormDescription>
                  
                  <div className="flex flex-wrap gap-2 mb-2">
                    {field.value.map((tag, index) => (
                      <span 
                        key={index}
                        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/20 text-primary-foreground"
                      >
                        {tag}
                        <button
                          type="button"
                          onClick={() => handleDeleteTag(index)}
                          className="ml-1 h-4 w-4 rounded-full inline-flex items-center justify-center text-primary-foreground hover:bg-primary/30"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  
                  <div className="flex">
                    <Input 
                      className="rounded-r-none"
                      placeholder="Add alert type (e.g., email, slack)"
                      value={newAlertType}
                      onChange={(e) => setNewAlertType(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag();
                        }
                      }}
                    />
                    <Button 
                      type="button"
                      onClick={handleAddTag}
                      className="rounded-l-none"
                    >
                      Add
                    </Button>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <div className="grid grid-cols-2 gap-4 mt-4">
              <FormField
                control={form.control}
                name="alert_subject"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Alert Subject</FormLabel>
                    <FormControl>
                      <Input placeholder="EDR Alert: Potential Threat Detected" {...field} />
                    </FormControl>
                    <FormDescription>
                      Subject line for email alerts
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              
              <FormField
                control={form.control}
                name="alert_text_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Alert Text Type</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select text type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="plain">Plain</SelectItem>
                        <SelectItem value="alert_text_only">Alert Text Only</SelectItem>
                        <SelectItem value="exclude_fields">Exclude Fields</SelectItem>
                        <SelectItem value="aggregation_summary_only">Aggregation Summary</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Format of the alert content
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            
            <div className="mt-4">
              <FormField
                control={form.control}
                name="alert_text"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Alert Text</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Enter the text for the alert notification"
                        className="resize-none min-h-[100px]"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      Text body of the alert message
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </div>
          
          {/* Advanced section could be added here for filter configuration */}
          {/* This would be expanded in a future enhancement */}
        </div>
        
        <DialogFooter className="pt-2 border-t">
          <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? (
              <>
                <span className="animate-spin mr-2">⟳</span>
                {isEdit ? 'Updating Rule...' : 'Creating Rule...'}
              </>
            ) : (
              <>{isEdit ? 'Update Rule' : 'Create Rule'}</>
            )}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}

// YamlEditor component for direct YAML editing with syntax highlighting
function YamlEditor({ 
  rule, 
  onSubmit, 
  onCancel 
}: { 
  rule?: Rule; 
  onSubmit: (data: any) => Promise<any>;
  onCancel: () => void;
}) {
  const [yamlContent, setYamlContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [lineCount, setLineCount] = useState(1);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const editorContainerRef = useRef<HTMLDivElement>(null);

  // Load the rule YAML when component mounts
  useEffect(() => {
    const fetchRuleYaml = async () => {
      if (!rule || !rule.filename) return;
      
      setLoading(true);
      setError(null);
      
      try {
        // Get the raw YAML content
        const response = await rulesApi.getRuleYaml(rule.filename);
        setYamlContent(response.content || '');
        setLineCount((response.content || '').split('\n').length);
      } catch (err) {
        console.error('Error fetching rule YAML:', err);
        setError('Failed to load rule YAML content');
      } finally {
        setLoading(false);
      }
    };

    fetchRuleYaml();
  }, [rule]);

  // Update line count when content changes
  useEffect(() => {
    setLineCount(yamlContent.split('\n').length);
  }, [yamlContent]);

  // Handle tab key in textarea
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab' && document.activeElement === editorRef.current) {
        e.preventDefault();
        const start = editorRef.current!.selectionStart;
        const end = editorRef.current!.selectionEnd;
        
        // Insert tab at cursor position
        const newValue = yamlContent.substring(0, start) + '  ' + yamlContent.substring(end);
        setYamlContent(newValue);
        
        // Move cursor position after the inserted tab
        setTimeout(() => {
          editorRef.current!.selectionStart = editorRef.current!.selectionEnd = start + 2;
        }, 0);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [yamlContent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    
    try {
      // Submit the raw YAML content
      await onSubmit({ 
        filename: rule?.filename,
        yamlContent 
      });
    } catch (err) {
      console.error('Error saving YAML:', err);
      setError('Failed to save rule YAML content');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="p-4 text-center">Loading rule content...</div>;
  }

  // Generate line numbers for editor
  const lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1);

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-50 p-4 rounded border border-red-200 text-red-800">
          {error}
        </div>
      )}
      
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <label className="text-sm font-medium">
            Edit YAML Content
            <span className="text-xs ml-2 text-gray-500">
              (Make sure to follow proper YAML syntax)
            </span>
          </label>
          <div className="text-xs text-muted-foreground">
            {lineCount} line{lineCount !== 1 ? 's' : ''}
          </div>
        </div>
        
        <div 
          ref={editorContainerRef}
          className="relative min-h-[400px] border rounded-md overflow-hidden bg-gray-900 shadow-sm"
        >
          {/* Line Numbers */}
          <div className="absolute left-0 top-0 bottom-0 w-12 py-4 bg-gray-800 text-center overflow-hidden z-10 select-none border-r border-gray-700">
            {lineNumbers.map(num => (
              <div key={num} className="text-xs text-gray-400 leading-5 px-2">
                {num}
              </div>
            ))}
          </div>
          
          {/* Editor */}
          <textarea
            ref={editorRef}
            value={yamlContent}
            onChange={(e) => setYamlContent(e.target.value)}
            className="font-mono text-sm min-h-[400px] w-full resize-y pl-14 pr-4 py-4 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-gray-900 border-0 text-gray-100"
            placeholder="# Enter YAML configuration here..."
            disabled={submitting}
            spellCheck={false}
            style={{ 
              lineHeight: '1.25rem',
              tabSize: 2,
              caretColor: '#e2e8f0'
            }}
          />
          
          {/* Syntax hint overlay (visual only) */}
          <div className="absolute right-2 bottom-2 text-xs text-gray-400 px-2 py-1 bg-gray-800 rounded-sm opacity-80 pointer-events-none">
            YAML
          </div>
        </div>
        
        <div className="flex justify-end gap-2 text-xs">
          <div className="text-muted-foreground">
            <span className="inline-block w-3 h-3 rounded-full bg-blue-400 mr-1"></span> Keys
          </div>
          <div className="text-muted-foreground">
            <span className="inline-block w-3 h-3 rounded-full bg-green-400 mr-1"></span> Strings
          </div>
          <div className="text-muted-foreground">
            <span className="inline-block w-3 h-3 rounded-full bg-amber-400 mr-1"></span> Numbers
          </div>
          <div className="text-muted-foreground">
            <span className="inline-block w-3 h-3 rounded-full bg-purple-400 mr-1"></span> Booleans
          </div>
        </div>
      </div>
      
      <DialogFooter className="pt-2 border-t">
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? (
            <>
              <span className="animate-spin mr-2">⟳</span>
              Saving...
            </>
          ) : (
            'Save Changes'
          )}
        </Button>
      </DialogFooter>
    </form>
  );
}

export const Route = createFileRoute('/_authenticated/rules')({
  component: RulesPage
})

function RulesPage() {
  const router = useRouter()
  
  // Replace URL status filter with a direct state approach
  const [activeFilter, setActiveFilter] = useState<string>('all');

  // Get all rules and filter on client-side
  const { data: allRules = [], isLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: () => rulesApi.getRules(),
  })

  // Enhanced filtering logic for rules based on selected filter
  const rules = useMemo(() => {
    if (!allRules.length) return [];
    
    if (activeFilter === 'active') {
      return allRules.filter((rule: Rule) => rule.is_enabled !== false);
    } else if (activeFilter === 'disabled') {
      return allRules.filter((rule: Rule) => rule.is_enabled === false);
    }
    
    return allRules;
  }, [allRules, activeFilter]);

  const queryClient = useQueryClient()

  const [deletingRuleId, setDeletingRuleId] = useState<string | null>(null);
  // Add state to control alert dialog visibility
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [ruleToDelete, setRuleToDelete] = useState<Rule | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (filename: string) => {
      setDeletingRuleId(filename);
      return rulesApi.deleteRule(filename);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      toast({
        title: 'Rule deleted',
        description: 'The rule has been deleted successfully.',
      });
      setDeletingRuleId(null);
      // Close the dialog after successful deletion
      setDeleteDialogOpen(false);
      setRuleToDelete(null);
    },
    onError: (error) => {
      setDeletingRuleId(null);
      toast({
        title: 'Error',
        description: 'Failed to delete rule: ' + String(error),
        variant: 'destructive'
      });
    }
  });

  const restartMutation = useMutation({
    mutationFn: () => rulesApi.restartElastAlert(),
    onSuccess: () => {
      toast({
        title: 'ElastAlert restarted',
        description: 'ElastAlert has been restarted successfully. New rules will be applied.',
      })
    },
  })

  const editMutation = useMutation({
    mutationFn: ({ filename, ruleData }: { filename: string, ruleData: any }) => 
      rulesApi.updateRule(filename, ruleData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      toast({
        title: 'Rule updated',
        description: 'The rule has been updated successfully.',
      })
    },
  })

  const createMutation = useMutation({
    mutationFn: (ruleData: any) => rulesApi.createRule(ruleData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      toast({
        title: 'Rule created',
        description: 'The rule has been created successfully.',
      })
    },
  })

  const [selectedRule, setSelectedRule] = useState<Rule | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)

  const handleDelete = (filename: string) => {
    deleteMutation.mutate(filename);
  }

  const handleRestart = () => {
    restartMutation.mutate()
  }

  const handleYamlEditSubmit = async (data: { filename?: string, yamlContent: string }) => {
    try {
      if (data.filename) {
        await rulesApi.updateRuleYaml(data.filename, data.yamlContent);
        queryClient.invalidateQueries({ queryKey: ['rules'] });
        toast({
          title: 'Rule updated',
          description: 'The rule YAML has been updated successfully.',
        });
        setSelectedRule(null);
      }
      return Promise.resolve();
    } catch (error) {
      console.error("Error updating rule YAML:", error);
      toast({
        title: 'Error',
        description: 'Failed to update rule YAML. Please check your syntax.',
        variant: 'destructive'
      });
      return Promise.reject(error);
    }
  };

  const handleCreateSubmit = async (data: { yamlContent: string }) => {
    try {
      await rulesApi.createRuleFromYaml(data.yamlContent);
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      toast({
        title: 'Rule created',
        description: 'The rule has been created successfully.',
      });
      setIsCreateDialogOpen(false);
      return Promise.resolve();
    } catch (error) {
      console.error("Error creating rule from YAML:", error);
      toast({
        title: 'Error',
        description: 'Failed to create rule. Please check your YAML syntax.',
        variant: 'destructive'
      });
      return Promise.reject(error);
    }
  };

  // Build filter tabs
  const filterTabs = [
    {
      id: 'all',
      label: 'All Rules',
      count: allRules.length,
    },
    {
      id: 'active',
      label: 'Active',
      count: allRules.filter((rule: Rule) => rule.is_enabled !== false).length,
    },
    {
      id: 'disabled',
      label: 'Disabled',
      count: allRules.filter((rule: Rule) => rule.is_enabled === false).length,
    }
  ];

  const openDeleteDialog = (rule: Rule) => {
    setRuleToDelete(rule);
    setDeleteDialogOpen(true);
  };

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
              ? `${activeFilter.charAt(0).toUpperCase() + activeFilter.slice(1)} Rules`
              : 'All Rules'}
          </h1>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ['rules'] })}>
              Refresh
            </Button>
            <Button onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> Create Rule
            </Button>
            <Button 
              onClick={handleRestart}
              disabled={restartMutation.isPending}
            >
              {restartMutation.isPending ? (
                <>
                  <span className="animate-spin mr-2">⟳</span> Restarting...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" /> Restart ElastAlert
                </>
              )}
            </Button>
          </div>
        </div>
        
        <Card>
          <CardHeader>
            <CardTitle>Rule List</CardTitle>
            <CardDescription>
              {activeFilter !== 'all'
                ? `Viewing ${activeFilter} rules (${rules.length})`
                : `View and manage all ElastAlert rules (${rules.length})`}
            </CardDescription>
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
                          <Button 
                            variant="outline" 
                            size="icon"
                            onClick={() => setSelectedRule(rule)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          
                          <Button 
                            variant="outline" 
                            size="icon" 
                            onClick={() => openDeleteDialog(rule)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </Main>

      {/* Edit Rule Dialog */}
      <Dialog open={!!selectedRule} onOpenChange={(open) => !open && setSelectedRule(null)}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Edit Rule: {selectedRule?.name}</DialogTitle>
            <DialogDescription>
              Edit rule YAML configuration
            </DialogDescription>
          </DialogHeader>
          
          {selectedRule && (
            <div className="relative">
              <YamlEditor 
                rule={selectedRule} 
                onSubmit={handleYamlEditSubmit}
                onCancel={() => setSelectedRule(null)}
              />
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Rule Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Create New Rule</DialogTitle>
            <DialogDescription>
              Create a new ElastAlert detection rule
            </DialogDescription>
          </DialogHeader>
          <YamlEditor 
            onSubmit={handleCreateSubmit}
            onCancel={() => setIsCreateDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>

      {/* Delete Rule Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the rule "{ruleToDelete?.name}".
              You won't be able to recover it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingRuleId === ruleToDelete?.filename}>
              Cancel
            </AlertDialogCancel>
            <Button 
              variant="destructive"
              onClick={() => ruleToDelete && handleDelete(ruleToDelete.filename)}
              disabled={deletingRuleId === ruleToDelete?.filename}
            >
              {deletingRuleId === ruleToDelete?.filename ? (
                <>
                  <span className="animate-spin mr-2">⟳</span>
                  Deleting...
                </>
              ) : (
                'Delete'
              )}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
} 