'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Building2,
  Users,
  Settings,
  LogOut
} from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['super_admin', 'tenant_admin'] },
  { href: '/dashboard/tenants', label: 'Tenants', icon: Building2, roles: ['super_admin'] },
  { href: '/dashboard/users', label: 'Usuarios', icon: Users, roles: ['super_admin'] },
  { href: '/dashboard/config', label: 'Configuracao', icon: Settings, roles: ['tenant_admin'] },
]

export function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  const filteredItems = navItems.filter((item) =>
    item.roles.includes(user?.role || '')
  )

  return (
    <aside className="hidden md:flex md:w-64 md:flex-col md:border-r bg-card h-screen sticky top-0">
      <div className="flex h-16 items-center border-b px-6">
        <Link href="/dashboard" className="text-xl font-bold text-blue-600">
          AgentPolitico
        </Link>
      </div>
      <nav className="flex-1 space-y-1 p-4">
        {filteredItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-blue-50 text-blue-600'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          )
        })}
      </nav>
      <div className="border-t p-4">
        <div className="mb-2 px-3 text-xs text-muted-foreground truncate">
          {user?.email}
        </div>
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 text-muted-foreground hover:text-foreground"
          onClick={logout}
        >
          <LogOut className="h-5 w-5" />
          Sair
        </Button>
      </div>
    </aside>
  )
}
