import { createFileRoute } from '@tanstack/react-router'
import Commands from '@/features/commands'

export const Route = createFileRoute('/_authenticated/commands/')({
  component: Commands,
}) 