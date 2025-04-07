import { useState } from 'react';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { SendCommandParams, CommandType } from '@/lib/api/commands';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertCircle, Check } from 'lucide-react';

// Schema for the command form
const commandSchema = z.object({
  type: z.string().min(1, { message: 'Command type is required' }),
  path: z.string().optional(),
  pid: z.string().optional(),
  ip: z.string().optional(),
  url: z.string().optional(),
  allowed_ips: z.string().optional(),
});

type CommandFormValues = z.infer<typeof commandSchema>;

interface CommandFormProps {
  agentId: string;
  onSubmit: (data: SendCommandParams) => void;
  isSubmitting?: boolean;
  error?: string;
  success?: boolean;
}

export function CommandForm({ agentId, onSubmit, isSubmitting, error, success }: CommandFormProps) {
  const [commandType, setCommandType] = useState<CommandType | ''>('');

  const form = useForm<CommandFormValues>({
    resolver: zodResolver(commandSchema),
    defaultValues: {
      type: '',
      path: '',
      pid: '',
      ip: '',
      url: '',
      allowed_ips: '',
    },
  });

  // Convert form values to command parameters
  const transformFormToCommand = (values: CommandFormValues): SendCommandParams => {
    const params: Record<string, string> = {};

    switch (values.type as CommandType) {
      case 'DELETE_FILE':
        if (values.path) params.path = values.path;
        break;
      case 'KILL_PROCESS':
      case 'KILL_PROCESS_TREE':
        if (values.pid) params.pid = values.pid;
        break;
      case 'BLOCK_IP':
        if (values.ip) params.ip = values.ip;
        break;
      case 'BLOCK_URL':
        if (values.url) params.url = values.url;
        break;
      case 'NETWORK_ISOLATE':
        if (values.allowed_ips) params.allowed_ips = values.allowed_ips;
        break;
      case 'NETWORK_RESTORE':
        // No params needed
        break;
    }

    return {
      agent_id: agentId,
      type: values.type as CommandType,
      params,
    };
  };

  const handleSubmit = (values: CommandFormValues) => {
    const command = transformFormToCommand(values);
    onSubmit(command);
  };

  const handleCommandTypeChange = (value: string) => {
    setCommandType(value as CommandType);
    form.setValue('type', value);
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert className="bg-green-50 text-green-800 border-green-200">
            <Check className="h-4 w-4 text-green-500" />
            <AlertTitle>Success</AlertTitle>
            <AlertDescription>Command sent successfully</AlertDescription>
          </Alert>
        )}

        <FormField
          control={form.control}
          name="type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Command Type</FormLabel>
              <Select onValueChange={handleCommandTypeChange} value={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select command type" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="DELETE_FILE">Delete File</SelectItem>
                  <SelectItem value="KILL_PROCESS">Kill Process</SelectItem>
                  <SelectItem value="KILL_PROCESS_TREE">Kill Process Tree</SelectItem>
                  <SelectItem value="BLOCK_IP">Block IP</SelectItem>
                  <SelectItem value="BLOCK_URL">Block URL</SelectItem>
                  <SelectItem value="NETWORK_ISOLATE">Network Isolate</SelectItem>
                  <SelectItem value="NETWORK_RESTORE">Network Restore</SelectItem>
                </SelectContent>
              </Select>
              <FormDescription>Select the type of command to send</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {commandType === 'DELETE_FILE' && (
          <FormField
            control={form.control}
            name="path"
            render={({ field }) => (
              <FormItem>
                <FormLabel>File Path</FormLabel>
                <FormControl>
                  <Input placeholder="C:\path\to\file.txt or /path/to/file" {...field} />
                </FormControl>
                <FormDescription>Full path to the file to delete</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {(commandType === 'KILL_PROCESS' || commandType === 'KILL_PROCESS_TREE') && (
          <FormField
            control={form.control}
            name="pid"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Process ID</FormLabel>
                <FormControl>
                  <Input placeholder="1234" {...field} />
                </FormControl>
                <FormDescription>PID of the process to terminate</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {commandType === 'BLOCK_IP' && (
          <FormField
            control={form.control}
            name="ip"
            render={({ field }) => (
              <FormItem>
                <FormLabel>IP Address</FormLabel>
                <FormControl>
                  <Input placeholder="192.168.1.1" {...field} />
                </FormControl>
                <FormDescription>IP address to block</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {commandType === 'BLOCK_URL' && (
          <FormField
            control={form.control}
            name="url"
            render={({ field }) => (
              <FormItem>
                <FormLabel>URL</FormLabel>
                <FormControl>
                  <Input placeholder="example.com" {...field} />
                </FormControl>
                <FormDescription>URL or domain to block</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {commandType === 'NETWORK_ISOLATE' && (
          <FormField
            control={form.control}
            name="allowed_ips"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Allowed IPs (Optional)</FormLabel>
                <FormControl>
                  <Input placeholder="192.168.1.1,8.8.8.8" {...field} />
                </FormControl>
                <FormDescription>Comma-separated list of IPs to allow during isolation</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        <Button type="submit" disabled={isSubmitting || !commandType}>
          {isSubmitting ? 'Sending...' : 'Send Command'}
        </Button>
      </form>
    </Form>
  );
} 