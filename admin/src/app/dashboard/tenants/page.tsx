'use client'

import { useEffect, useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Plus, Trash2 } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import type { Tenant } from '@/types'
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export default function TenantsPage() {
  const { user } = useAuth()
  const router = useRouter()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (user?.role !== 'super_admin') {
      router.replace('/dashboard')
      return
    }
    loadTenants()
  }, [user, router])

  async function loadTenants() {
    try {
      const data = await api.get<Tenant[]>('/tenants')
      setTenants(data)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar tenants')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation()
    if (!confirm('Tem certeza que deseja excluir este tenant?')) return

    try {
      await api.delete(`/tenants/${id}`)
      toast.success('Tenant excluido com sucesso')
      setTenants((prev) => prev.filter((t) => t.id !== id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao excluir tenant')
    }
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

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Tenants</CardTitle>
            <CardDescription>Gerencie os tenants do sistema</CardDescription>
          </div>
          <CreateTenantDialog onCreated={(tenant) => setTenants((prev) => [...prev, tenant])} />
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Slug</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Criado em</TableHead>
                <TableHead className="text-right">Acoes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenants.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                    Nenhum tenant cadastrado
                  </TableCell>
                </TableRow>
              ) : (
                tenants.map((tenant) => (
                  <TableRow
                    key={tenant.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/dashboard/tenants/${tenant.id}`)}
                  >
                    <TableCell className="font-medium">{tenant.name}</TableCell>
                    <TableCell className="text-muted-foreground">{tenant.slug}</TableCell>
                    <TableCell>
                      <Badge
                        variant={tenant.active ? 'default' : 'secondary'}
                        className={
                          tenant.active
                            ? 'bg-green-100 text-green-700 hover:bg-green-100'
                            : 'bg-red-100 text-red-700 hover:bg-red-100'
                        }
                      >
                        {tenant.active ? 'Ativo' : 'Inativo'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {tenant.created_at
                        ? new Date(tenant.created_at).toLocaleDateString('pt-BR')
                        : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => handleDelete(e, tenant.id)}
                        title="Excluir"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

function CreateTenantDialog({ onCreated }: { onCreated: (tenant: Tenant) => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [helenaToken, setHelenaToken] = useState('')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmProvider, setLlmProvider] = useState('grok')
  const [followup1, setFollowup1] = useState(20)
  const [followup2, setFollowup2] = useState(60)
  const [followup3, setFollowup3] = useState(60)
  const [dueHours, setDueHours] = useState(24)
  const [saving, setSaving] = useState(false)

  function handleNameChange(value: string) {
    setName(value)
    setSlug(slugify(value))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)

    try {
      const tenant = await api.post<Tenant>('/tenants', {
        name,
        slug,
        helena_api_token: helenaToken || undefined,
        llm_api_key: llmApiKey || undefined,
        llm_provider: llmProvider,
        followup_1_minutes: followup1,
        followup_2_minutes: followup2,
        followup_3_minutes: followup3,
        due_hours: dueHours,
      })
      toast.success('Tenant criado com sucesso!')
      onCreated(tenant)
      setOpen(false)
      resetForm()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar tenant')
    } finally {
      setSaving(false)
    }
  }

  function resetForm() {
    setName('')
    setSlug('')
    setHelenaToken('')
    setLlmApiKey('')
    setLlmProvider('grok')
    setFollowup1(20)
    setFollowup2(60)
    setFollowup3(60)
    setDueHours(24)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button className="bg-blue-600 hover:bg-blue-700" />}
      >
        <Plus className="mr-2 h-4 w-4" />
        Novo Tenant
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Novo Tenant</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="ct-name">Nome</Label>
              <Input
                id="ct-name"
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="Nome do tenant"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-slug">Slug</Label>
              <Input
                id="ct-slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="slug-do-tenant"
                required
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="ct-helena">Token Helena</Label>
              <Input
                id="ct-helena"
                type="password"
                value={helenaToken}
                onChange={(e) => setHelenaToken(e.target.value)}
                placeholder="Token da API Helena"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-llm-key">Chave LLM</Label>
              <Input
                id="ct-llm-key"
                type="password"
                value={llmApiKey}
                onChange={(e) => setLlmApiKey(e.target.value)}
                placeholder="Chave da API LLM"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="ct-llm-provider">Provedor LLM</Label>
            <Input
              id="ct-llm-provider"
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value)}
              placeholder="grok"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="ct-f1">Follow-up 1 (min)</Label>
              <Input
                id="ct-f1"
                type="number"
                value={followup1}
                onChange={(e) => setFollowup1(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-f2">Follow-up 2 (min)</Label>
              <Input
                id="ct-f2"
                type="number"
                value={followup2}
                onChange={(e) => setFollowup2(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-f3">Follow-up 3 (min)</Label>
              <Input
                id="ct-f3"
                type="number"
                value={followup3}
                onChange={(e) => setFollowup3(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="ct-due">Prazo (horas)</Label>
            <Input
              id="ct-due"
              type="number"
              value={dueHours}
              onChange={(e) => setDueHours(Number(e.target.value))}
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" className="bg-blue-600 hover:bg-blue-700" disabled={saving}>
              {saving ? 'Criando...' : 'Criar'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
