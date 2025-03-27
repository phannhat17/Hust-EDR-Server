import {
  IconLayoutDashboard,
  IconAlertTriangle,
  IconRuler,
  IconServer,
} from '@tabler/icons-react'
import { Command } from 'lucide-react'
import { type SidebarData } from '../types'

export const sidebarData: SidebarData = {
  user: {
    name: 'Admin',
    email: 'admin@hust-edr.com',
    avatar: '/avatars/shadcn.jpg',
  },
  teams: [
    {
      name: 'HUST EDR',
      logo: Command,
      plan: 'Security Dashboard',
    },
  ],
  navGroups: [
    {
      title: 'EDR System',
      items: [
        {
          title: 'Dashboard',
          url: '/',
          icon: IconLayoutDashboard,
        },
        {
          title: 'Alerts',
          url: '/alerts',
          icon: IconAlertTriangle,
        },
        {
          title: 'Rules',
          url: '/rules',
          icon: IconRuler,
        },
        {
          title: 'Agents',
          url: '/agents',
          icon: IconServer,
        },
      ],
    },
  ],
}
