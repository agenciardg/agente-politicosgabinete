'use client'

import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { Tenant } from '@/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

interface CreateTenantModalProps {
  onCreated: (tenant: Tenant) => void
}

export function CreateTenantModal({ onCreated }: CreateTenantModalProps) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [helenaToken, setHelenaToken] = useState('')
  const [loading, setLoading] = useState(false)

  function handleNameChange(value: string) {
    setName(value)
    setSlug(slugify(value))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)

    try {
      const tenant = await api.post<Tenant>('/tenants', {
        name,
        slug,
        helena_api_token: helenaToken || undefined,
      })
      toast.success('Tenant criado com sucesso!')
      onCreated(tenant)
      setOpen(false)
      setName('')
      setSlug('')
      setHelenaToken('')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar tenant')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button className="bg-blue-600 hover:bg-blue-700" />}
      >
        Criar Tenant
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo Tenant</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tenant-name">Nome</Label>
            <Input
              id="tenant-name"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Nome do tenant"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tenant-slug">Slug</Label>
            <Input
              id="tenant-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="slug-do-tenant"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tenant-token">Token Helena (opcional)</Label>
            <Input
              id="tenant-token"
              type="password"
              value={helenaToken}
              onChange={(e) => setHelenaToken(e.target.value)}
              placeholder="Token da API Helena"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" className="bg-blue-600 hover:bg-blue-700" disabled={loading}>
              {loading ? 'Criando...' : 'Criar'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
