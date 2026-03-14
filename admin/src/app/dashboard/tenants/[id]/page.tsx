'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { toast } from 'sonner'
import { RefreshCw, Save } from 'lucide-react'
import { api } from '@/lib/api'
import type { Tenant } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AgentConfig } from '@/components/agent-config'
import { FollowupConfig } from '@/components/followup-config'
import { MetricsDashboard } from '@/components/metrics-dashboard'

export default function TenantConfigPage() {
  const params = useParams()
  const tenantId = params.id as string
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    api.get<Tenant>(`/tenants/${tenantId}`)
      .then(setTenant)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Erro ao carregar tenant'))
      .finally(() => setLoading(false))
  }, [tenantId])

  async function handleSave() {
    if (!tenant) return
    setSaving(true)

    try {
      const updated = await api.put<Tenant>(`/tenants/${tenantId}`, {
        name: tenant.name,
        slug: tenant.slug,
        helena_api_token: tenant.helena_api_token,
        llm_api_key: tenant.llm_api_key,
        llm_provider: tenant.llm_provider,
        followup_1_minutes: tenant.followup_1_minutes,
        followup_2_minutes: tenant.followup_2_minutes,
        followup_3_minutes: tenant.followup_3_minutes,
        due_hours: tenant.due_hours,
        active: tenant.active,
      })
      setTenant(updated)
      toast.success('Tenant salvo com sucesso!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar tenant')
    } finally {
      setSaving(false)
    }
  }

  async function handleSync() {
    setSyncing(true)
    try {
      await api.post(`/tenants/${tenantId}/sync`)
      toast.success('Sincronizacao com Helena iniciada!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao sincronizar')
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <Card>
          <CardContent className="py-8">
            <div className="h-64 animate-pulse rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!tenant) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          Tenant nao encontrado
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{tenant.name}</h1>
        <Badge tenant={tenant} />
      </div>

      <Tabs defaultValue="geral">
        <TabsList>
          <TabsTrigger value="geral">Geral</TabsTrigger>
          <TabsTrigger value="principal">Agente Principal</TabsTrigger>
          <TabsTrigger value="assessor">Agente Assessor</TabsTrigger>
          <TabsTrigger value="followup">Follow-up</TabsTrigger>
          <TabsTrigger value="metricas">Metricas</TabsTrigger>
        </TabsList>

        <TabsContent value="geral" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Configuracoes Gerais</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Nome</Label>
                  <Input
                    id="name"
                    value={tenant.name}
                    onChange={(e) => setTenant({ ...tenant, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slug">Slug</Label>
                  <Input
                    id="slug"
                    value={tenant.slug}
                    onChange={(e) => setTenant({ ...tenant, slug: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="helena-token">Token Helena</Label>
                  <Input
                    id="helena-token"
                    type="password"
                    value={tenant.helena_api_token || ''}
                    onChange={(e) => setTenant({ ...tenant, helena_api_token: e.target.value })}
                    placeholder="Token da API Helena"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="llm-key">Chave LLM</Label>
                  <Input
                    id="llm-key"
                    type="password"
                    value={tenant.llm_api_key || ''}
                    onChange={(e) => setTenant({ ...tenant, llm_api_key: e.target.value })}
                    placeholder="Chave da API LLM"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="llm-provider">Provedor LLM</Label>
                <Input
                  id="llm-provider"
                  value={tenant.llm_provider || ''}
                  onChange={(e) => setTenant({ ...tenant, llm_provider: e.target.value })}
                  placeholder="grok"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <div className="space-y-2">
                  <Label htmlFor="followup1">Follow-up 1 (min)</Label>
                  <Input
                    id="followup1"
                    type="number"
                    value={tenant.followup_1_minutes}
                    onChange={(e) => setTenant({ ...tenant, followup_1_minutes: Number(e.target.value) })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="followup2">Follow-up 2 (min)</Label>
                  <Input
                    id="followup2"
                    type="number"
                    value={tenant.followup_2_minutes}
                    onChange={(e) => setTenant({ ...tenant, followup_2_minutes: Number(e.target.value) })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="followup3">Follow-up 3 (min)</Label>
                  <Input
                    id="followup3"
                    type="number"
                    value={tenant.followup_3_minutes}
                    onChange={(e) => setTenant({ ...tenant, followup_3_minutes: Number(e.target.value) })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="due-hours">Prazo (horas)</Label>
                  <Input
                    id="due-hours"
                    type="number"
                    value={tenant.due_hours}
                    onChange={(e) => setTenant({ ...tenant, due_hours: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={tenant.active}
                  onCheckedChange={(checked) => setTenant({ ...tenant, active: checked })}
                />
                <Label>Tenant ativo</Label>
              </div>

              <div className="flex gap-2">
                <Button onClick={handleSave} className="bg-blue-600 hover:bg-blue-700" disabled={saving}>
                  <Save className="mr-2 h-4 w-4" />
                  {saving ? 'Salvando...' : 'Salvar'}
                </Button>
                <Button variant="outline" onClick={handleSync} disabled={syncing}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
                  {syncing ? 'Sincronizando...' : 'Sincronizar com Helena'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="principal" className="mt-4">
          <AgentConfig agentType="principal" tenantId={tenantId} />
        </TabsContent>

        <TabsContent value="assessor" className="mt-4">
          <AgentConfig agentType="assessor" tenantId={tenantId} />
        </TabsContent>

        <TabsContent value="followup" className="mt-4">
          <FollowupConfig tenantId={tenantId} />
        </TabsContent>

        <TabsContent value="metricas" className="mt-4">
          <MetricsDashboard tenantId={tenantId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function Badge({ tenant }: { tenant: Tenant }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tenant.active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
      {tenant.active ? 'Ativo' : 'Inativo'}
    </span>
  )
}
