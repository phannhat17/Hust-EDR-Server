import { useNavigate } from '@tanstack/react-router'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { IconChevronDown, IconLogout, IconSettings, IconUser } from '@tabler/icons-react'

interface ProfileDropdownProps {
  username?: string
  email?: string
  avatarUrl?: string
  onLogout?: () => void
}

export function ProfileDropdown({
  username = 'Admin User',
  email = 'admin@example.com',
  avatarUrl,
  onLogout,
}: ProfileDropdownProps) {
  const navigate = useNavigate()

  const handleLogout = () => {
    if (onLogout) {
      onLogout()
    } else {
      // Default logout behavior - navigate to login
      navigate({ to: '/sign-in' })
    }
  }

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-8 p-0 flex items-center">
          <Avatar className="h-8 w-8 mr-2">
            {avatarUrl ? (
              <AvatarImage src={avatarUrl} alt={username} />
            ) : (
              <AvatarFallback>{getInitials(username)}</AvatarFallback>
            )}
          </Avatar>
          <span className="hidden sm:inline-block">{username}</span>
          <IconChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <div className="flex flex-col">
            <span>{username}</span>
            <span className="text-xs text-muted-foreground">{email}</span>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onClick={() => navigate({ to: '/settings' })}>
            <IconUser className="mr-2 h-4 w-4" />
            Profile
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate({ to: '/settings' })}>
            <IconSettings className="mr-2 h-4 w-4" />
            Settings
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
          <IconLogout className="mr-2 h-4 w-4" />
          Logout
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
