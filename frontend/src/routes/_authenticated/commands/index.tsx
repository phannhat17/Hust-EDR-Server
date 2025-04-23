import { createFileRoute } from '@tanstack/react-router'
import Commands from '@/features/commands'

export const Route = createFileRoute('/_authenticated/commands/')({
  component: Commands,
  validateSearch: (search) => {
    return {
      agent_id: search.agent_id ? String(search.agent_id) : undefined
    }
  }
}) 