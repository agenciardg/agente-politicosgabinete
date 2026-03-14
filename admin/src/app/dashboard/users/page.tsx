'use client'

import { useEffect, useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import type { AdminUser, Tenant } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface AdminUsersResponse {
  data: AdminUser[]
  meta: { page: number; per_page: number; total: number }
}

export default function UsersPage() {
  const { user } = useAuth()
  const router = useRouter()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const perPage = 20

  useEffect(() => {
    if (user?.role !== 'super_admin') {
      router.replace('/dashboard')
      return
    }
    loadData()
  }, [user, router, page])

  async function loadData() {
    try {
      const [usersRes, tenantsRes] = await Promise.all([
        api.get<AdminUsersResponse>(`/admin-users?page=${page}&per_page=${perPage}`),
        api.get<Tenant[]>('/tenants'),
      ])
      setUsers(usersRes.data)
      setTotal(usersRes.meta.total)
      setTenants(tenantsRes)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar usuarios')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Tem certeza que deseja excluir este usuario?')) return

    try {
      await api.delete(`/admin-users/${id}`)
      toast.success('Usuario excluido com sucesso')
      setUsers((prev) => prev.filter((u) => u.id !== id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao excluir usuario')
    }
  }

  function getTenantName(tenantId: string | null) {
    if (!tenantId) return '-'
    const t = tenants.find((t) => t.id === tenantId)
    return t?.name || tenantId
  }

  if (user?.role !== 'super_admin') return null

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="h-64 animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    )
  }

  const totalPages = Math.ceil(total / perPage)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Usuarios Administrativos</CardTitle>
            <CardDescription>Gerencie os usuarios do painel admin</CardDescription>
          </div>
          <UserDialog
            tenants={tenants}
            onSaved={(newUser) => setUsers((prev) => [...prev, newUser])}
          />
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Perfil</TableHead>
                <TableHead>Tenant</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Acoes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    Nenhum usuario cadastrado
                  </TableCell>
                </TableRow>
              ) : (
                users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">{u.name}</TableCell>
                    <TableCell className="text-muted-foreground">{u.email}</TableCell>
                    <TableCell>
                      <Badge
                        variant={u.role === 'super_admin' ? 'default' : 'secondary'}
                        className={
                          u.role === 'super_admin'
                            ? 'bg-purple-100 text-purple-700 hover:bg-purple-100'
                            : 'bg-blue-100 text-blue-700 hover:bg-blue-100'
                        }
                      >
                        {u.role === 'super_admin' ? 'Super Admin' : 'Admin Tenant'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {getTenantName(u.tenant_id)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={u.active ? 'default' : 'secondary'}
                        className={
                          u.active
                            ? 'bg-green-100 text-green-700 hover:bg-green-100'
                            : 'bg-red-100 text-red-700 hover:bg-red-100'
                        }
                      >
                        {u.active ? 'Ativo' : 'Inativo'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <UserDialog
                          tenants={tenants}
                          editUser={u}
                          onSaved={(updated) =>
                            setUsers((prev) =>
                              prev.map((x) => (x.id === updated.id ? updated : x))
                            )
                          }
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(u.id)}
                          title="Excluir"
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Anterior
              </Button>
              <span className="text-sm text-muted-foreground">
                Pagina {page} de {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Proxima
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function UserDialog({
  tenants,
  editUser,
  onSaved,
}: {
  tenants: Tenant[]
  editUser?: AdminUser
  onSaved: (user: AdminUser) => void
}) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(editUser?.name || '')
  const [email, setEmail] = useState(editUser?.email || '')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'super_admin' | 'tenant_admin'>(editUser?.role || 'tenant_admin')
  const [tenantId, setTenantId] = useState(editUser?.tenant_id || '')
  const [saving, setSaving] = useState(false)

  function resetForm() {
    if (editUser) {
      setName(editUser.name)
      setEmail(editUser.email)
      setPassword('')
      setRole(editUser.role)
      setTenantId(editUser.tenant_id || '')
    } else {
      setName('')
      setEmail('')
      setPassword('')
      setRole('tenant_admin')
      setTenantId('')
    }
  }

  useEffect(() => {
    if (open) resetForm()
  }, [open])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)

    try {
      const body: Record<string, unknown> = {
        name,
        email,
        role,
        tenant_id: role === 'tenant_admin' ? tenantId || undefined : null,
      }

      if (!editUser) {
        body.password = password
      } else if (password) {
        body.password = password
      }

      let saved: AdminUser

      if (editUser) {
        saved = await api.put<AdminUser>(`/admin-users/${editUser.id}`, body)
        toast.success('Usuario atualizado com sucesso!')
      } else {
        saved = await api.post<AdminUser>('/admin-users', body)
        toast.success('Usuario criado com sucesso!')
      }

      onSaved(saved)
      setOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar usuario')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          editUser ? (
            <Button variant="ghost" size="icon" title="Editar" />
          ) : (
            <Button className="bg-blue-600 hover:bg-blue-700" />
          )
        }
      >
        {editUser ? (
          <Pencil className="h-4 w-4" />
        ) : (
          <>
            <Plus className="mr-2 h-4 w-4" />
            Novo Usuario
          </>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editUser ? 'Editar Usuario' : 'Novo Usuario'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="user-name">Nome</Label>
            <Input
              id="user-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nome completo"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="user-email">Email</Label>
            <Input
              id="user-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@exemplo.com"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="user-password">
              Senha{editUser ? ' (deixe em branco para manter)' : ''}
            </Label>
            <Input
              id="user-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="********"
              required={!editUser}
            />
          </div>

          <div className="space-y-2">
            <Label>Perfil</Label>
            <Select value={role} onValueChange={(val) => setRole(val as 'super_admin' | 'tenant_admin')}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Selecione o perfil" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="super_admin">Super Admin</SelectItem>
                <SelectItem value="tenant_admin">Admin Tenant</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {role === 'tenant_admin' && (
            <div className="space-y-2">
              <Label>Tenant</Label>
              <Select value={tenantId} onValueChange={(val) => setTenantId(val || '')}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecione o tenant" />
                </SelectTrigger>
                <SelectContent>
                  {tenants.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" className="bg-blue-600 hover:bg-blue-700" disabled={saving}>
              {saving ? 'Salvando...' : editUser ? 'Salvar' : 'Criar'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
