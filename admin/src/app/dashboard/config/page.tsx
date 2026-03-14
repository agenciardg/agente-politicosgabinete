'use client'

import { useEffect, useState, useCallback } from 'react'
import { toast } from 'sonner'
import {
  Save,
  RefreshCw,
  Plus,
  Trash2,
  MessageSquare,
  ArrowRightLeft,
  Clock,
  ChevronDown,
  ChevronRight,
  Settings,
  Play,
} from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import type {
  Tenant,
  Agent,
  FollowupPrompt,
  ContactField,
  AgentField,
  Panel,
  AgentPanel,
  AssessorNumber,
  MetricsSummary,
  Department,
  FollowupQueueItem,
} from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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

// ─── Types locais ──────────────────────────────────────────

interface FieldRow {
  contactField: ContactField
  agentField?: AgentField
}

interface PanelRow {
  panel: Panel
  agentPanel?: AgentPanel
}

type Period = '24h' | '7d' | '30d'

const periodLabels: Record<Period, string> = {
  '24h': 'Ultimas 24 horas',
  '7d': 'Ultimos 7 dias',
  '30d': 'Ultimos 30 dias',
}

// ─── Page ──────────────────────────────────────────────────

export default function TenantConfigPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!tenantId) return
    api
      .get<Tenant>(`/tenants/${tenantId}`)
      .then(setTenant)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Erro ao carregar configuracao'))
      .finally(() => setLoading(false))
  }, [tenantId])

  if (!tenantId) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          Sem tenant associado ao usuario.
        </CardContent>
      </Card>
    )
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
          Configuracao nao encontrada.
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings className="h-6 w-6 text-muted-foreground" />
          <h1 className="text-2xl font-bold">Configuracao</h1>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            tenant.active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          }`}
        >
          {tenant.active ? 'Ativo' : 'Inativo'}
        </span>
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
          <GeralTab tenant={tenant} setTenant={setTenant} tenantId={tenantId} />
        </TabsContent>

        <TabsContent value="principal" className="mt-4">
          <AgentTab agentType="principal" tenantId={tenantId} />
        </TabsContent>

        <TabsContent value="assessor" className="mt-4">
          <AgentTab agentType="assessor" tenantId={tenantId} />
        </TabsContent>

        <TabsContent value="followup" className="mt-4">
          <FollowupTab />
        </TabsContent>

        <TabsContent value="metricas" className="mt-4">
          <MetricasTab tenantId={tenantId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ─── Tab 1: Geral ──────────────────────────────────────────

function GeralTab({
  tenant,
  setTenant,
  tenantId,
}: {
  tenant: Tenant
  setTenant: React.Dispatch<React.SetStateAction<Tenant | null>>
  tenantId: string
}) {
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)

  async function handleSave() {
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
      toast.success('Configuracao salva com sucesso!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar')
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuracoes Gerais</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="cfg-name">Nome</Label>
            <Input
              id="cfg-name"
              value={tenant.name}
              onChange={(e) => setTenant((prev) => prev ? { ...prev, name: e.target.value } : prev)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cfg-slug">Slug</Label>
            <Input id="cfg-slug" value={tenant.slug} readOnly className="bg-muted" />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="cfg-helena">Token Helena</Label>
            <Input
              id="cfg-helena"
              type="password"
              value={tenant.helena_api_token || ''}
              onChange={(e) =>
                setTenant((prev) => prev ? { ...prev, helena_api_token: e.target.value } : prev)
              }
              placeholder="Token da API Helena"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cfg-llmkey">Chave LLM</Label>
            <Input
              id="cfg-llmkey"
              type="password"
              value={tenant.llm_api_key || ''}
              onChange={(e) =>
                setTenant((prev) => prev ? { ...prev, llm_api_key: e.target.value } : prev)
              }
              placeholder="Chave da API LLM"
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="cfg-llmprov">Provedor LLM</Label>
            <Input
              id="cfg-llmprov"
              value={tenant.llm_provider || ''}
              onChange={(e) =>
                setTenant((prev) => prev ? { ...prev, llm_provider: e.target.value } : prev)
              }
              placeholder="openai, anthropic, etc."
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cfg-due">Horas para vencimento</Label>
            <Input
              id="cfg-due"
              type="number"
              value={tenant.due_hours}
              onChange={(e) =>
                setTenant((prev) => prev ? { ...prev, due_hours: Number(e.target.value) } : prev)
              }
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="cfg-fu1">Follow-up 1 (min)</Label>
            <Input
              id="cfg-fu1"
              type="number"
              value={tenant.followup_1_minutes}
              onChange={(e) =>
                setTenant((prev) =>
                  prev ? { ...prev, followup_1_minutes: Number(e.target.value) } : prev
                )
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cfg-fu2">Follow-up 2 (min)</Label>
            <Input
              id="cfg-fu2"
              type="number"
              value={tenant.followup_2_minutes}
              onChange={(e) =>
                setTenant((prev) =>
                  prev ? { ...prev, followup_2_minutes: Number(e.target.value) } : prev
                )
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cfg-fu3">Follow-up 3 (min)</Label>
            <Input
              id="cfg-fu3"
              type="number"
              value={tenant.followup_3_minutes}
              onChange={(e) =>
                setTenant((prev) =>
                  prev ? { ...prev, followup_3_minutes: Number(e.target.value) } : prev
                )
              }
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Switch
            checked={tenant.active}
            onCheckedChange={(checked) =>
              setTenant((prev) => prev ? { ...prev, active: checked } : prev)
            }
          />
          <Label>Tenant ativo</Label>
        </div>

        <Separator />

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
  )
}

// ─── Tab 2 & 3: Agent ──────────────────────────────────────

function AgentTab({
  agentType,
  tenantId,
}: {
  agentType: 'principal' | 'assessor'
  tenantId: string
}) {
  const [agent, setAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)

  const loadAgent = useCallback(() => {
    setLoading(true)
    api
      .get<Agent[]>('/agents')
      .then((agents) => {
        const found = agents.find((a) => a.agent_type === agentType)
        setAgent(found || null)
      })
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Erro ao carregar agente'))
      .finally(() => setLoading(false))
  }, [agentType])

  useEffect(() => {
    loadAgent()
  }, [loadAgent])

  async function handleCreate() {
    setCreating(true)
    try {
      const created = await api.post<Agent>(`/agents?tenant_id=${tenantId}`, {
        agent_type: agentType,
        name: agentType === 'principal' ? 'Agente Principal' : 'Agente Assessor',
      })
      setAgent(created)
      toast.success('Agente criado com sucesso!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar agente')
    } finally {
      setCreating(false)
    }
  }

  async function handleSave() {
    if (!agent) return
    setSaving(true)
    try {
      const updated = await api.put<Agent>(`/agents/${agent.id}?tenant_id=${tenantId}`, {
        name: agent.name,
        persona_prompt: agent.persona_prompt,
        behavior_prompt: agent.behavior_prompt,
      })
      setAgent(updated)
      toast.success('Agente salvo com sucesso!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar agente')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="h-48 animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    )
  }

  if (!agent) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-muted-foreground mb-4">
            Agente {agentType === 'principal' ? 'principal' : 'assessor'} nao encontrado.
          </p>
          <Button
            onClick={handleCreate}
            disabled={creating}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="mr-2 h-4 w-4" />
            {creating
              ? 'Criando...'
              : `Criar Agente ${agentType === 'principal' ? 'Principal' : 'Assessor'}`}
          </Button>
        </CardContent>
      </Card>
    )
  }

  const title = agentType === 'principal' ? 'Agente Principal' : 'Agente Assessor'

  return (
    <div className="space-y-6">
      {/* Prompts */}
      <Card>
        <CardHeader>
          <CardTitle>{title} - Prompts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor={`${agentType}-name`}>Nome</Label>
            <Input
              id={`${agentType}-name`}
              value={agent.name}
              onChange={(e) => setAgent({ ...agent, name: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${agentType}-persona`}>Prompt de Persona</Label>
            <Textarea
              id={`${agentType}-persona`}
              rows={6}
              value={agent.persona_prompt || ''}
              onChange={(e) => setAgent({ ...agent, persona_prompt: e.target.value })}
              placeholder="Descreva a persona do agente..."
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${agentType}-behavior`}>Prompt de Comportamento</Label>
            <Textarea
              id={`${agentType}-behavior`}
              rows={6}
              value={agent.behavior_prompt || ''}
              onChange={(e) => setAgent({ ...agent, behavior_prompt: e.target.value })}
              placeholder="Descreva o comportamento do agente..."
            />
          </div>
          <Button onClick={handleSave} className="bg-blue-600 hover:bg-blue-700" disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? 'Salvando...' : 'Salvar Prompts'}
          </Button>
        </CardContent>
      </Card>

      {/* Follow-up prompts */}
      <FollowupPromptsSection agentId={agent.id} />

      {/* Panels */}
      <PanelsSection agentId={agent.id} tenantId={tenantId} />

      {/* Fields */}
      <FieldsSection agentId={agent.id} tenantId={tenantId} />

      {/* Assessor numbers (tab 3 only) */}
      {agentType === 'assessor' && (
        <AssessorNumbersSection agentId={agent.id} tenantId={tenantId} />
      )}
    </div>
  )
}

// ─── Follow-up Prompts Section ─────────────────────────────

function FollowupPromptsSection({ agentId }: { agentId: string }) {
  const [prompts, setPrompts] = useState<FollowupPrompt[]>([])
  const [loading, setLoading] = useState(true)
  const [savingMap, setSavingMap] = useState<Record<number, boolean>>({})

  useEffect(() => {
    api
      .get<FollowupPrompt[]>(`/agents/${agentId}/followup-prompts`)
      .then(setPrompts)
      .catch(() => setPrompts([]))
      .finally(() => setLoading(false))
  }, [agentId])

  function updateText(num: number, text: string) {
    setPrompts((prev) => {
      const copy = [...prev]
      const idx = copy.findIndex((p) => p.followup_number === num)
      if (idx >= 0) {
        copy[idx] = { ...copy[idx], prompt_template: text }
      } else {
        copy.push({ id: '', agent_id: agentId, followup_number: num, prompt_template: text })
      }
      return copy
    })
  }

  async function handleSave(num: number) {
    const prompt = prompts.find((p) => p.followup_number === num)
    setSavingMap((prev) => ({ ...prev, [num]: true }))
    try {
      await api.put(`/agents/${agentId}/followup-prompts/${num}`, {
        prompt_template: prompt?.prompt_template || '',
      })
      toast.success(`Follow-up ${num} salvo!`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar follow-up')
    } finally {
      setSavingMap((prev) => ({ ...prev, [num]: false }))
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="py-6">
          <div className="h-24 animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Prompts de Follow-up</CardTitle>
        <CardDescription>Templates de mensagem para cada follow-up automatico</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {[1, 2, 3].map((num) => {
          const prompt = prompts.find((p) => p.followup_number === num)
          const isSaving = savingMap[num] || false

          return (
            <div key={num} className="space-y-2">
              <Label>Follow-up {num}</Label>
              <Textarea
                rows={4}
                value={prompt?.prompt_template || ''}
                onChange={(e) => updateText(num, e.target.value)}
                placeholder={`Template do follow-up ${num}...`}
              />
              <Button
                size="sm"
                onClick={() => handleSave(num)}
                className="bg-blue-600 hover:bg-blue-700"
                disabled={isSaving}
              >
                <Save className="mr-2 h-4 w-4" />
                {isSaving ? 'Salvando...' : 'Salvar'}
              </Button>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

// ─── Panels Section ────────────────────────────────────────

function PanelsSection({ agentId, tenantId }: { agentId: string; tenantId: string }) {
  const [rows, setRows] = useState<PanelRow[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [panels, agentPanels, deps] = await Promise.all([
          api.get<Panel[]>(`/panels?tenant_id=${tenantId}`),
          api.get<AgentPanel[]>(`/panels/agent/${agentId}?tenant_id=${tenantId}`),
          api.get<Department[]>(`/departments?tenant_id=${tenantId}`).catch(() => [] as Department[]),
        ])

        const merged = panels.map((p) => ({
          panel: p,
          agentPanel: agentPanels.find((ap) => ap.tenant_panel_id === p.id),
        }))

        setRows(merged)
        setDepartments(deps)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Erro ao carregar paineis')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [agentId, tenantId])

  async function handleToggle(row: PanelRow) {
    if (row.agentPanel) {
      try {
        const updated = await api.put<AgentPanel>(`/panels/agent-panel/${row.agentPanel.id}?tenant_id=${tenantId}`, {
          active: !row.agentPanel.active,
        })
        setRows((prev) =>
          prev.map((r) => (r.panel.id === row.panel.id ? { ...r, agentPanel: updated } : r))
        )
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Erro ao atualizar painel')
      }
    } else {
      try {
        const created = await api.post<AgentPanel>(`/panels/agent/${agentId}?tenant_id=${tenantId}`, {
          tenant_panel_id: row.panel.id,
          active: true,
        })
        setRows((prev) =>
          prev.map((r) => (r.panel.id === row.panel.id ? { ...r, agentPanel: created } : r))
        )
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Erro ao ativar painel')
      }
    }
  }

  async function handleUpdate(row: PanelRow, field: string, value: string) {
    if (!row.agentPanel) return
    try {
      const updated = await api.put<AgentPanel>(`/panels/agent-panel/${row.agentPanel.id}?tenant_id=${tenantId}`, {
        [field]: value || undefined,
      })
      setRows((prev) =>
        prev.map((r) => (r.panel.id === row.panel.id ? { ...r, agentPanel: updated } : r))
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar painel')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Paineis</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-32 animate-pulse rounded bg-muted" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum painel encontrado. Sincronize com Helena primeiro.
          </p>
        ) : (
          <div className="space-y-3">
            {rows.map((row) => {
              const isExpanded = expandedId === row.panel.id

              return (
                <div key={row.panel.id} className="rounded-lg border">
                  <div className="flex items-center gap-3 p-4">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => setExpandedId(isExpanded ? null : row.panel.id)}
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </Button>

                    <Switch
                      checked={row.agentPanel?.active ?? false}
                      onCheckedChange={() => handleToggle(row)}
                    />

                    <div className="flex-1">
                      <p className="font-medium">{row.panel.name || 'Painel sem nome'}</p>
                      <p className="text-sm text-muted-foreground">
                        {row.panel.steps?.length || 0} etapas, {row.panel.custom_fields?.length || 0}{' '}
                        campos
                      </p>
                    </div>
                  </div>

                  {isExpanded && row.agentPanel && (
                    <div className="border-t p-4 space-y-4">
                      <div className="space-y-2">
                        <Label>Descricao para o agente</Label>
                        <Textarea
                          value={row.agentPanel.agent_description || ''}
                          onChange={(e) => {
                            setRows((prev) =>
                              prev.map((r) =>
                                r.panel.id === row.panel.id && r.agentPanel
                                  ? {
                                      ...r,
                                      agentPanel: {
                                        ...r.agentPanel,
                                        agent_description: e.target.value,
                                      },
                                    }
                                  : r
                              )
                            )
                          }}
                          onBlur={(e) => handleUpdate(row, 'agent_description', e.target.value)}
                          placeholder="Descreva quando usar este painel..."
                          rows={3}
                        />
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        {row.panel.steps && row.panel.steps.length > 0 && (
                          <div className="space-y-2">
                            <Label>Etapa</Label>
                            <Select
                              value={row.agentPanel.step_id || ''}
                              onValueChange={(val) => val && handleUpdate(row, 'step_id', val)}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Selecione uma etapa" />
                              </SelectTrigger>
                              <SelectContent>
                                {row.panel.steps.map((step) => (
                                  <SelectItem key={step.id} value={step.id}>
                                    {step.step_name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        )}

                        {departments.length > 0 && (
                          <div className="space-y-2">
                            <Label>Departamento</Label>
                            <Select
                              value={row.agentPanel.department_id || ''}
                              onValueChange={(val) => val && handleUpdate(row, 'department_id', val)}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Selecione um departamento" />
                              </SelectTrigger>
                              <SelectContent>
                                {departments.map((dep) => (
                                  <SelectItem key={dep.id} value={dep.id}>
                                    {dep.department_name || dep.helena_department_id}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Fields Section ────────────────────────────────────────

function FieldsSection({ agentId, tenantId }: { agentId: string; tenantId: string }) {
  const [rows, setRows] = useState<FieldRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [contactFields, agentFields] = await Promise.all([
          api.get<ContactField[]>(`/fields?tenant_id=${tenantId}`),
          api.get<AgentField[]>(`/fields/agent/${agentId}?tenant_id=${tenantId}`),
        ])

        const merged = contactFields.map((cf) => ({
          contactField: cf,
          agentField: agentFields.find((af) => af.contact_field_id === cf.id),
        }))

        setRows(merged)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Erro ao carregar campos')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [agentId, tenantId])

  async function handleToggle(row: FieldRow) {
    try {
      if (row.agentField) {
        const updated = await api.put<AgentField>(`/fields/agent-field/${row.agentField.id}?tenant_id=${tenantId}`, {
          active: !row.agentField.active,
        })
        setRows((prev) =>
          prev.map((r) =>
            r.contactField.id === row.contactField.id ? { ...r, agentField: updated } : r
          )
        )
      } else {
        const created = await api.post<AgentField>(`/fields/agent/${agentId}?tenant_id=${tenantId}`, {
          contact_field_id: row.contactField.id,
          active: true,
        })
        setRows((prev) =>
          prev.map((r) =>
            r.contactField.id === row.contactField.id ? { ...r, agentField: created } : r
          )
        )
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar campo')
    }
  }

  async function handleInstructionChange(row: FieldRow, instruction: string) {
    if (!row.agentField) return
    try {
      const updated = await api.put<AgentField>(`/fields/agent-field/${row.agentField.id}?tenant_id=${tenantId}`, {
        instruction,
      })
      setRows((prev) =>
        prev.map((r) =>
          r.contactField.id === row.contactField.id ? { ...r, agentField: updated } : r
        )
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar instrucao')
    }
  }

  async function handleOrderChange(row: FieldRow, order: number) {
    if (!row.agentField) return
    try {
      const updated = await api.put<AgentField>(`/fields/agent-field/${row.agentField.id}?tenant_id=${tenantId}`, {
        field_order: order,
      })
      setRows((prev) =>
        prev.map((r) =>
          r.contactField.id === row.contactField.id ? { ...r, agentField: updated } : r
        )
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar ordem')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Campos do Contato</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-32 animate-pulse rounded bg-muted" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum campo encontrado. Sincronize com Helena primeiro.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">Ativo</TableHead>
                <TableHead>Campo</TableHead>
                <TableHead>Chave</TableHead>
                <TableHead>Instrucao</TableHead>
                <TableHead className="w-20">Ordem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.contactField.id}>
                  <TableCell>
                    <Switch
                      checked={row.agentField?.active ?? false}
                      onCheckedChange={() => handleToggle(row)}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    {row.contactField.helena_field_name || row.contactField.helena_field_key}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {row.contactField.helena_field_key}
                  </TableCell>
                  <TableCell>
                    <Input
                      placeholder="Instrucao para o agente..."
                      value={row.agentField?.instruction || ''}
                      onChange={(e) => {
                        setRows((prev) =>
                          prev.map((r) =>
                            r.contactField.id === row.contactField.id && r.agentField
                              ? {
                                  ...r,
                                  agentField: { ...r.agentField, instruction: e.target.value },
                                }
                              : r
                          )
                        )
                      }}
                      onBlur={(e) => handleInstructionChange(row, e.target.value)}
                      disabled={!row.agentField?.active}
                      className="max-w-[300px]"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      value={row.agentField?.field_order ?? ''}
                      onChange={(e) => {
                        const val = Number(e.target.value)
                        setRows((prev) =>
                          prev.map((r) =>
                            r.contactField.id === row.contactField.id && r.agentField
                              ? { ...r, agentField: { ...r.agentField, field_order: val } }
                              : r
                          )
                        )
                      }}
                      onBlur={(e) => handleOrderChange(row, Number(e.target.value))}
                      disabled={!row.agentField?.active}
                      className="w-20"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Assessor Numbers Section ──────────────────────────────

function AssessorNumbersSection({
  agentId,
  tenantId,
}: {
  agentId: string
  tenantId: string
}) {
  const [numbers, setNumbers] = useState<AssessorNumber[]>([])
  const [loading, setLoading] = useState(true)
  const [phone, setPhone] = useState('')
  const [label, setLabel] = useState('')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    api
      .get<AssessorNumber[]>('/assessor-numbers')
      .then(setNumbers)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Erro ao carregar numeros'))
      .finally(() => setLoading(false))
  }, [tenantId])

  async function handleAdd() {
    if (!phone) return
    setAdding(true)
    try {
      const num = await api.post<AssessorNumber>(`/assessor-numbers?tenant_id=${tenantId}`, {
        agent_id: agentId,
        phone_number: phone,
        label: label || undefined,
      })
      setNumbers((prev) => [...prev, num])
      setPhone('')
      setLabel('')
      toast.success('Numero adicionado!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao adicionar numero')
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/assessor-numbers/${id}?tenant_id=${tenantId}`)
      setNumbers((prev) => prev.filter((n) => n.id !== id))
      toast.success('Numero removido!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao remover numero')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Numeros do Assessor</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Telefone (ex: 5511999999999)"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <Input
            placeholder="Rotulo (opcional)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="max-w-[200px]"
          />
          <Button
            onClick={handleAdd}
            disabled={adding || !phone}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="mr-1 h-4 w-4" />
            Adicionar
          </Button>
        </div>

        {loading ? (
          <div className="h-20 animate-pulse rounded bg-muted" />
        ) : numbers.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum numero cadastrado</p>
        ) : (
          <div className="space-y-2">
            {numbers.map((num) => (
              <div
                key={num.id}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div>
                  <p className="font-medium">{num.phone_number}</p>
                  {num.label && <p className="text-sm text-muted-foreground">{num.label}</p>}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(num.id)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Tab 4: Follow-up Queue ────────────────────────────────

function FollowupTab() {
  const [items, setItems] = useState<FollowupQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    api
      .get<FollowupQueueItem[]>('/followup/queue')
      .then(setItems)
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : 'Erro ao carregar fila de follow-up')
      )
      .finally(() => setLoading(false))
  }, [])

  async function handleProcess() {
    setProcessing(true)
    try {
      await api.post('/followup/process')
      toast.success('Processamento de follow-ups iniciado!')
      // Reload queue
      const updated = await api.get<FollowupQueueItem[]>('/followup/queue')
      setItems(updated)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao processar follow-ups')
    } finally {
      setProcessing(false)
    }
  }

  function formatDate(dateStr: string): string {
    try {
      return new Date(dateStr).toLocaleString('pt-BR')
    } catch {
      return dateStr
    }
  }

  function statusColor(status: string): string {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-700'
      case 'sent':
        return 'bg-green-100 text-green-700'
      case 'failed':
        return 'bg-red-100 text-red-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Fila de Follow-up</h2>
        <Button
          onClick={handleProcess}
          disabled={processing}
          className="bg-blue-600 hover:bg-blue-700"
        >
          <Play className={`mr-2 h-4 w-4 ${processing ? 'animate-spin' : ''}`} />
          {processing ? 'Processando...' : 'Processar Agora'}
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4">
          {loading ? (
            <div className="h-32 animate-pulse rounded bg-muted" />
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Nenhum follow-up na fila
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sessao</TableHead>
                  <TableHead>Telefone</TableHead>
                  <TableHead>Tipo Agente</TableHead>
                  <TableHead>Follow-up #</TableHead>
                  <TableHead>Agendado</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs">
                      {item.session_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell>{item.phone_number}</TableCell>
                    <TableCell className="capitalize">{item.agent_type}</TableCell>
                    <TableCell>{item.followup_number}</TableCell>
                    <TableCell>{formatDate(item.scheduled_at)}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(item.status)}`}
                      >
                        {item.status}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Tab 5: Metricas ───────────────────────────────────────

function MetricasTab({ tenantId }: { tenantId: string }) {
  const [period, setPeriod] = useState<Period>('7d')
  const [summary, setSummary] = useState<MetricsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api
      .get<MetricsSummary>(`/metrics/summary?period=${period}`)
      .then(setSummary)
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : 'Erro ao carregar metricas')
        setSummary(null)
      })
      .finally(() => setLoading(false))
  }, [tenantId, period])

  function formatTime(seconds: number): string {
    if (seconds < 60) return `${Math.round(seconds)}s`
    if (seconds < 3600) return `${Math.round(seconds / 60)}min`
    return `${Math.round(seconds / 3600)}h`
  }

  const categories = summary?.categories_breakdown || {}
  const maxCategory = Math.max(...Object.values(categories), 1)

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        {(Object.keys(periodLabels) as Period[]).map((p) => (
          <Button
            key={p}
            variant={period === p ? 'default' : 'outline'}
            size="sm"
            onClick={() => setPeriod(p)}
            className={period === p ? 'bg-blue-600 hover:bg-blue-700' : ''}
          >
            {periodLabels[p]}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="py-6">
                <div className="h-16 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : !summary ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Sem dados para o periodo selecionado
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total de Conversas
                </CardTitle>
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{summary.total_conversations}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total de Transferencias
                </CardTitle>
                <ArrowRightLeft className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{summary.total_transfers}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Tempo Medio de Resposta
                </CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {formatTime(summary.avg_response_time_seconds)}
                </div>
              </CardContent>
            </Card>
          </div>

          {Object.keys(categories).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Categorias</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(categories)
                  .sort(([, a], [, b]) => b - a)
                  .map(([category, count]) => (
                    <div key={category} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span className="font-medium">{category}</span>
                        <span className="text-muted-foreground">{count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-blue-600 transition-all"
                          style={{ width: `${(count / maxCategory) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
