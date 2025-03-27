import { createFileRoute } from '@tanstack/react-router'
import AgentRegistration from '@/features/agents/registration'

export const Route = createFileRoute('/_authenticated/agents/register/')({
  component: AgentRegistration,
}) 