'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Save, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type {
  Agent,
  AgentField,
  AgentPanel,
  AssessorNumber,
  ContactField,
  Department,
  FollowupPrompt,
  Panel,
} from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
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

interface AgentConfigProps {
  agentType: 'principal' | 'assessor'
  tenantId: string
}

export function AgentConfig({ agentType, tenantId }: AgentConfigProps) {
  const [agent, setAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)

  // Followup prompts
  const [followups, setFollowups] = useState<FollowupPrompt[]>([])
  const [savingFollowup, setSavingFollowup] = useState<Record<number, boolean>>({})

  // Panels
  const [panels, setPanels] = useState<Panel[]>([])
  const [agentPanels, setAgentPanels] = useState<AgentPanel[]>([])

  // Fields
  const [contactFields, setContactFields] = useState<ContactField[]>([])
  const [agentFields, setAgentFields] = useState<AgentField[]>([])

  // Departments
  const [departments, setDepartments] = useState<Department[]>([])

  // Saving panels
  const [savingPanelId, setSavingPanelId] = useState<string | null>(null)

  // Saving fields
  const [savingFields, setSavingFields] = useState(false)

  // Assessor numbers
  const [assessorNumbers, setAssessorNumbers] = useState<AssessorNumber[]>([])
  const [newPhone, setNewPhone] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [addingNumber, setAddingNumber] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const agents = await api.get<Agent[]>(`/agents?tenant_id=${tenantId}`)
        const found = agents.find((a) => a.agent_type === agentType)
        setAgent(found || null)

        if (found) {
          await loadAgentData(found.id)
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Erro ao carregar agente')
      } finally {
        setLoading(false)
      }
    }

    load()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId, agentType])

  async function loadAgentData(agentId: string) {
    const [fpResult, panelsResult, agentPanelsResult, fieldsResult, agentFieldsResult, depsResult] =
      await Promise.allSettled([
        api.get<FollowupPrompt[]>(`/agents/${agentId}/followup-prompts?tenant_id=${tenantId}`),
        api.get<Panel[]>(`/panels?tenant_id=${tenantId}`),
        api.get<AgentPanel[]>(`/panels/agent/${agentId}?tenant_id=${tenantId}`),
        api.get<ContactField[]>(`/fields?tenant_id=${tenantId}`),
        api.get<AgentField[]>(`/fields/agent/${agentId}?tenant_id=${tenantId}`),
        api.get<Department[]>(`/departments?tenant_id=${tenantId}`),
      ])

    if (fpResult.status === 'fulfilled') setFollowups(fpResult.value)
    if (panelsResult.status === 'fulfilled') setPanels(panelsResult.value)
    if (agentPanelsResult.status === 'fulfilled') setAgentPanels(agentPanelsResult.value)
    if (fieldsResult.status === 'fulfilled') setContactFields(fieldsResult.value)
    if (agentFieldsResult.status === 'fulfilled') setAgentFields(agentFieldsResult.value)
    if (depsResult.status === 'fulfilled') setDepartments(depsResult.value)

    if (agentType === 'assessor') {
      try {
        const nums = await api.get<AssessorNumber[]>(`/assessor-numbers?tenant_id=${tenantId}`)
        setAssessorNumbers(nums)
      } catch {
        // ignore
      }
    }
  }

  async function handleCreate() {
    setCreating(true)
    try {
      const created = await api.post<Agent>(`/agents?tenant_id=${tenantId}`, {
        tenant_id: tenantId,
        agent_type: agentType,
        name: agentType === 'principal' ? 'Agente Principal' : 'Agente Assessor',
        persona_prompt: '',
        behavior_prompt: '',
      })
      setAgent(created)
      await loadAgentData(created.id)
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

  async function handleSaveFollowup(num: number) {
    if (!agent) return
    const prompt = followups.find((f) => f.followup_number === num)
    setSavingFollowup((prev) => ({ ...prev, [num]: true }))
    try {
      await api.put(`/agents/${agent.id}/followup-prompts/${num}?tenant_id=${tenantId}`, {
        prompt_template: prompt?.prompt_template || '',
        active: prompt?.active ?? true,
      })
      toast.success(`Follow-up ${num} salvo!`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar follow-up')
    } finally {
      setSavingFollowup((prev) => ({ ...prev, [num]: false }))
    }
  }

  function updateFollowupText(num: number, text: string) {
    setFollowups((prev) => {
      const idx = prev.findIndex((f) => f.followup_number === num)
      if (idx >= 0) {
        const updated = [...prev]
        updated[idx] = { ...updated[idx], prompt_template: text }
        return updated
      }
      return [
        ...prev,
        { id: '', agent_id: agent?.id || '', followup_number: num, prompt_template: text },
      ]
    })
  }

  // Panel helpers
  async function handleTogglePanel(panel: Panel) {
    if (!agent) return
    const existing = agentPanels.find((ap) => ap.tenant_panel_id === panel.id)
    try {
      if (existing) {
        const updated = await api.put<AgentPanel>(`/panels/agent-panel/${existing.id}?tenant_id=${tenantId}`, {
          active: !existing.active,
        })
        setAgentPanels((prev) => prev.map((ap) => (ap.id === existing.id ? updated : ap)))
      } else {
        const created = await api.post<AgentPanel>(`/panels/agent/${agent.id}?tenant_id=${tenantId}`, {
          tenant_panel_id: panel.id,
          agent_description: '',
          step_id: undefined,
          department_id: undefined,
        })
        setAgentPanels((prev) => [...prev, created])
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar painel')
    }
  }

  async function handleSavePanel(ap: AgentPanel) {
    setSavingPanelId(ap.id)
    try {
      const updated = await api.put<AgentPanel>(`/panels/agent-panel/${ap.id}?tenant_id=${tenantId}`, {
        agent_description: ap.agent_description || '',
        step_id: ap.step_id || undefined,
        department_id: ap.department_id || undefined,
      })
      setAgentPanels((prev) => prev.map((p) => (p.id === ap.id ? updated : p)))
      toast.success('Painel salvo com sucesso!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar painel')
    } finally {
      setSavingPanelId(null)
    }
  }

  async function handleFieldMappingSave(agentPanelId: string, panelCustomFieldId: string, instruction: string, active: boolean = true) {
    try {
      await api.put(`/panels/${agentPanelId}/field-mappings?tenant_id=${tenantId}`, {
        panel_custom_field_id: panelCustomFieldId,
        storage_instruction: instruction,
        active,
      })
      toast.success(active ? 'Mapeamento salvo!' : 'Campo desativado!')
      // Reload agent panels to get updated field_mappings
      if (agent) {
        try {
          const updated = await api.get<AgentPanel[]>(`/panels/agent/${agent.id}?tenant_id=${tenantId}`)
          setAgentPanels(updated)
        } catch {
          // Reload failed but save succeeded - don't lose state
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar mapeamento')
    }
  }

  // Field helpers
  async function handleToggleField(cf: ContactField) {
    if (!agent) return
    const existing = agentFields.find((af) => af.contact_field_id === cf.id)
    try {
      if (existing) {
        const updated = await api.put<AgentField>(`/fields/agent-field/${existing.id}?tenant_id=${tenantId}`, {
          active: !existing.active,
        })
        setAgentFields((prev) => prev.map((af) => (af.id === existing.id ? updated : af)))
      } else {
        const created = await api.post<AgentField>(`/fields/agent/${agent.id}?tenant_id=${tenantId}`, {
          contact_field_id: cf.id,
          instruction: '',
          field_order: 0,
          required: false,
        })
        setAgentFields((prev) => [...prev, created])
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar campo')
    }
  }

  async function handleUpdateField(agentFieldId: string, data: Partial<AgentField>) {
    try {
      const updated = await api.put<AgentField>(`/fields/agent-field/${agentFieldId}?tenant_id=${tenantId}`, data)
      setAgentFields((prev) => prev.map((af) => (af.id === agentFieldId ? updated : af)))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar campo')
    }
  }

  async function handleSaveAllFields() {
    setSavingFields(true)
    try {
      const activeFields = agentFields.filter((af) => af.active)
      await Promise.all(
        activeFields.map((af) =>
          api.put<AgentField>(`/fields/agent-field/${af.id}?tenant_id=${tenantId}`, {
            instruction: af.instruction || '',
            field_order: af.field_order ?? 0,
            required: af.required ?? false,
          })
        )
      )
      toast.success('Campos salvos com sucesso!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar campos')
    } finally {
      setSavingFields(false)
    }
  }

  // Assessor number helpers
  async function handleAddNumber() {
    if (!agent || !newPhone) return
    setAddingNumber(true)
    try {
      const created = await api.post<AssessorNumber>(`/assessor-numbers?tenant_id=${tenantId}`, {
        tenant_id: tenantId,
        agent_id: agent.id,
        phone_number: newPhone,
        label: newLabel || undefined,
      })
      setAssessorNumbers((prev) => [...prev, created])
      setNewPhone('')
      setNewLabel('')
      toast.success('Numero adicionado!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao adicionar numero')
    } finally {
      setAddingNumber(false)
    }
  }

  async function handleDeleteNumber(id: string) {
    try {
      await api.delete(`/assessor-numbers/${id}?tenant_id=${tenantId}`)
      setAssessorNumbers((prev) => prev.filter((n) => n.id !== id))
      toast.success('Numero removido!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao remover numero')
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
            Nenhum agente {agentType === 'principal' ? 'principal' : 'assessor'} encontrado.
          </p>
          <Button
            onClick={handleCreate}
            disabled={creating}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="mr-2 h-4 w-4" />
            {creating ? 'Criando...' : 'Criar Agente'}
          </Button>
        </CardContent>
      </Card>
    )
  }

  const title = agentType === 'principal' ? 'Agente Principal' : 'Agente Assessor'

  return (
    <div className="space-y-6">
      {/* Agent edit form */}
      <Card>
        <CardHeader>
          <CardTitle>{title} - Configuracao</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="agent-name">Nome</Label>
            <Input
              id="agent-name"
              value={agent.name}
              onChange={(e) => setAgent({ ...agent, name: e.target.value })}
              placeholder="Nome do agente"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="persona">Prompt de Persona</Label>
            <Textarea
              id="persona"
              rows={6}
              value={agent.persona_prompt || ''}
              onChange={(e) => setAgent({ ...agent, persona_prompt: e.target.value })}
              placeholder="Descreva a persona do agente..."
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="behavior">Prompt de Comportamento</Label>
            <Textarea
              id="behavior"
              rows={6}
              value={agent.behavior_prompt || ''}
              onChange={(e) => setAgent({ ...agent, behavior_prompt: e.target.value })}
              placeholder="Descreva o comportamento do agente..."
            />
          </div>
          <Button onClick={handleSave} className="bg-blue-600 hover:bg-blue-700" disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? 'Salvando...' : 'Salvar Agente'}
          </Button>
        </CardContent>
      </Card>

      {/* Followup Prompts */}
      <Card>
        <CardHeader>
          <CardTitle>Prompts de Follow-up</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3].map((num) => {
            const prompt = followups.find((f) => f.followup_number === num)
            return (
              <div key={num} className="space-y-2">
                <Label>Follow-up {num}</Label>
                <Textarea
                  rows={3}
                  value={prompt?.prompt_template || ''}
                  onChange={(e) => updateFollowupText(num, e.target.value)}
                  placeholder={`Template do follow-up ${num}...`}
                />
                <Button
                  size="sm"
                  onClick={() => handleSaveFollowup(num)}
                  disabled={savingFollowup[num]}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  <Save className="mr-2 h-4 w-4" />
                  {savingFollowup[num] ? 'Salvando...' : 'Salvar'}
                </Button>
                {num < 3 && <Separator className="mt-4" />}
              </div>
            )
          })}
        </CardContent>
      </Card>

      {/* Panels */}
      <Card>
        <CardHeader>
          <CardTitle>Paineis</CardTitle>
        </CardHeader>
        <CardContent>
          {panels.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum painel encontrado. Sincronize com Helena primeiro.
            </p>
          ) : (
            <div className="space-y-4">
              {panels.map((panel) => {
                const ap = agentPanels.find((a) => a.tenant_panel_id === panel.id)
                return (
                  <div key={panel.id} className="rounded-lg border p-4 space-y-3">
                    <div className="flex items-center gap-3">
                      <Switch
                        checked={ap?.active ?? false}
                        onCheckedChange={() => handleTogglePanel(panel)}
                      />
                      <div className="flex-1">
                        <p className="font-medium">{panel.name || 'Painel sem nome'}</p>
                        <p className="text-sm text-muted-foreground">
                          {panel.steps?.length || 0} etapas
                        </p>
                      </div>
                    </div>
                    {ap && ap.active && (
                      <div className="space-y-3 pl-12">
                        <div className="space-y-2">
                          <Label>Descricao para o agente</Label>
                          <Textarea
                            rows={2}
                            value={ap.agent_description || ''}
                            onChange={(e) =>
                              setAgentPanels((prev) =>
                                prev.map((p) =>
                                  p.id === ap.id
                                    ? { ...p, agent_description: e.target.value }
                                    : p
                                )
                              )
                            }
                            placeholder="Descreva quando usar este painel..."
                          />
                        </div>
                        <div className="grid gap-4 md:grid-cols-2">
                          {panel.steps && panel.steps.length > 0 ? (
                            <div className="space-y-2">
                              <Label>Etapa</Label>
                              <Select
                                value={ap.step_id || ''}
                                onValueChange={(val) =>
                                  setAgentPanels((prev) =>
                                    prev.map((p) =>
                                      p.id === ap.id ? { ...p, step_id: val || undefined } : p
                                    )
                                  )
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue placeholder="Selecione uma etapa" />
                                </SelectTrigger>
                                <SelectContent>
                                  {panel.steps.map((step) => (
                                    <SelectItem key={step.id} value={step.id}>
                                      {step.step_name}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                          ) : (
                            <div className="space-y-2">
                              <Label>Etapa (ID)</Label>
                              <Input
                                value={ap.step_id || ''}
                                onChange={(e) =>
                                  setAgentPanels((prev) =>
                                    prev.map((p) =>
                                      p.id === ap.id ? { ...p, step_id: e.target.value } : p
                                    )
                                  )
                                }
                                placeholder="ID da etapa"
                              />
                            </div>
                          )}
                          {departments.length > 0 ? (
                            <div className="space-y-2">
                              <Label>Departamento</Label>
                              <Select
                                value={ap.department_id || ''}
                                onValueChange={(val) =>
                                  setAgentPanels((prev) =>
                                    prev.map((p) =>
                                      p.id === ap.id ? { ...p, department_id: val || undefined } : p
                                    )
                                  )
                                }
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
                          ) : (
                            <div className="space-y-2">
                              <Label>Departamento (ID)</Label>
                              <Input
                                value={ap.department_id || ''}
                                onChange={(e) =>
                                  setAgentPanels((prev) =>
                                    prev.map((p) =>
                                      p.id === ap.id ? { ...p, department_id: e.target.value } : p
                                    )
                                  )
                                }
                                placeholder="ID do departamento"
                              />
                            </div>
                          )}
                        </div>
                        {panel.custom_fields && panel.custom_fields.length > 0 && (
                          <div className="space-y-2">
                            <Label>Campos Customizados do Painel</Label>
                            <p className="text-xs text-muted-foreground">
                              Configure como o agente deve preencher cada campo do painel Helena.
                            </p>
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead className="w-12">Ativo</TableHead>
                                  <TableHead>Campo</TableHead>
                                  <TableHead>Instrucao de preenchimento</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {panel.custom_fields.map((cf) => {
                                  const mapping = ap.field_mappings?.find(
                                    (fm) => fm.panel_custom_field_id === cf.id
                                  )
                                  const isActive = mapping?.active ?? false
                                  return (
                                    <TableRow key={cf.id} className={!isActive ? 'opacity-50' : ''}>
                                      <TableCell>
                                        <Switch
                                          checked={isActive}
                                          onCheckedChange={(checked) =>
                                            handleFieldMappingSave(
                                              ap.id,
                                              cf.id,
                                              mapping?.storage_instruction || '',
                                              checked
                                            )
                                          }
                                        />
                                      </TableCell>
                                      <TableCell className="font-medium whitespace-nowrap">
                                        {cf.helena_field_name}
                                      </TableCell>
                                      <TableCell>
                                        <Input
                                          key={`${cf.id}-${mapping?.storage_instruction || ''}`}
                                          placeholder="Ex: Extrair o assunto da demanda do cidadao..."
                                          defaultValue={mapping?.storage_instruction || ''}
                                          disabled={!isActive}
                                          onBlur={(e) =>
                                            handleFieldMappingSave(ap.id, cf.id, e.target.value, isActive)
                                          }
                                        />
                                      </TableCell>
                                    </TableRow>
                                  )
                                })}
                              </TableBody>
                            </Table>
                          </div>
                        )}
                        <Button
                          size="sm"
                          onClick={() => handleSavePanel(ap)}
                          disabled={savingPanelId === ap.id}
                          className="bg-blue-600 hover:bg-blue-700"
                        >
                          <Save className="mr-2 h-4 w-4" />
                          {savingPanelId === ap.id ? 'Salvando...' : 'Salvar Painel'}
                        </Button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Fields */}
      <Card>
        <CardHeader>
          <CardTitle>Campos do Contato</CardTitle>
        </CardHeader>
        <CardContent>
          {contactFields.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum campo encontrado. Sincronize com Helena primeiro.
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">Ativo</TableHead>
                    <TableHead>Campo</TableHead>
                    <TableHead>Instrucao</TableHead>
                    <TableHead className="w-20">Ordem</TableHead>
                    <TableHead className="w-24">Obrigatorio</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contactFields.map((cf) => {
                    const af = agentFields.find((f) => f.contact_field_id === cf.id)
                    return (
                      <TableRow key={cf.id}>
                        <TableCell>
                          <Switch
                            checked={af?.active ?? false}
                            onCheckedChange={() => handleToggleField(cf)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">
                          {cf.helena_field_name || cf.helena_field_key}
                        </TableCell>
                        <TableCell>
                          <Textarea
                            rows={1}
                            placeholder="Instrucao para o agente..."
                            value={af?.instruction || ''}
                            onChange={(e) =>
                              setAgentFields((prev) =>
                                prev.map((f) =>
                                  f.id === af?.id
                                    ? { ...f, instruction: e.target.value }
                                    : f
                                )
                              )
                            }
                            disabled={!af?.active}
                            className="min-h-[36px]"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            value={af?.field_order ?? 0}
                            onChange={(e) =>
                              setAgentFields((prev) =>
                                prev.map((f) =>
                                  f.id === af?.id
                                    ? { ...f, field_order: Number(e.target.value) }
                                    : f
                                )
                              )
                            }
                            disabled={!af?.active}
                            className="w-16"
                          />
                        </TableCell>
                        <TableCell>
                          <Switch
                            checked={af?.required ?? false}
                            onCheckedChange={(checked) => {
                              if (af) {
                                setAgentFields((prev) =>
                                  prev.map((f) =>
                                    f.id === af.id ? { ...f, required: checked } : f
                                  )
                                )
                              }
                            }}
                            disabled={!af?.active}
                          />
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              <div className="mt-4">
                <Button
                  onClick={handleSaveAllFields}
                  disabled={savingFields}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  <Save className="mr-2 h-4 w-4" />
                  {savingFields ? 'Salvando...' : 'Salvar Campos'}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Assessor Numbers */}
      {agentType === 'assessor' && (
        <Card>
          <CardHeader>
            <CardTitle>Numeros do Assessor</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="Telefone (ex: 5511999999999)"
                value={newPhone}
                onChange={(e) => setNewPhone(e.target.value)}
              />
              <Input
                placeholder="Rotulo (opcional)"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                className="max-w-[200px]"
              />
              <Button
                onClick={handleAddNumber}
                disabled={addingNumber || !newPhone}
                className="bg-blue-600 hover:bg-blue-700"
              >
                <Plus className="mr-1 h-4 w-4" />
                Adicionar
              </Button>
            </div>

            {assessorNumbers.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhum numero cadastrado</p>
            ) : (
              <div className="space-y-2">
                {assessorNumbers.map((num) => (
                  <div
                    key={num.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div>
                      <p className="font-medium">{num.phone_number}</p>
                      {num.label && (
                        <p className="text-sm text-muted-foreground">{num.label}</p>
                      )}
                    </div>
                    <Badge variant={num.active ? 'default' : 'secondary'}>
                      {num.active ? 'Ativo' : 'Inativo'}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteNumber(num.id)}
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
      )}
    </div>
  )
}
