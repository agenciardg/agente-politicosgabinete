'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ChevronDown, ChevronRight, Save } from 'lucide-react'
import { api } from '@/lib/api'
import type { Panel, AgentPanel, Department } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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

interface PanelsConfigProps {
  agentId: string
  tenantId: string
}

interface PanelRow {
  panel: Panel
  agentPanel?: AgentPanel
}

export function PanelsConfig({ agentId, tenantId }: PanelsConfigProps) {
  const [rows, setRows] = useState<PanelRow[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [savingPanelId, setSavingPanelId] = useState<string | null>(null)

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
    try {
      if (row.agentPanel) {
        const updated = await api.put<AgentPanel>(`/panels/agent-panel/${row.agentPanel.id}?tenant_id=${tenantId}`, {
          active: !row.agentPanel.active,
        })
        setRows((prev) =>
          prev.map((r) =>
            r.panel.id === row.panel.id ? { ...r, agentPanel: updated } : r
          )
        )
      } else {
        const created = await api.post<AgentPanel>(`/panels/agent/${agentId}?tenant_id=${tenantId}`, {
          tenant_panel_id: row.panel.id,
          active: true,
        })
        setRows((prev) =>
          prev.map((r) =>
            r.panel.id === row.panel.id ? { ...r, agentPanel: created } : r
          )
        )
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar painel')
    }
  }

  async function handleSavePanel(row: PanelRow) {
    if (!row.agentPanel) return
    setSavingPanelId(row.agentPanel.id)

    try {
      const updated = await api.put<AgentPanel>(`/panels/agent-panel/${row.agentPanel.id}?tenant_id=${tenantId}`, {
        agent_description: row.agentPanel.agent_description || '',
        step_id: row.agentPanel.step_id || undefined,
        department_id: row.agentPanel.department_id || undefined,
      })
      setRows((prev) =>
        prev.map((r) =>
          r.panel.id === row.panel.id ? { ...r, agentPanel: updated } : r
        )
      )
      toast.success('Painel salvo com sucesso!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar painel')
    } finally {
      setSavingPanelId(null)
    }
  }

  async function handleFieldMappingSave(agentPanelId: string, panelCustomFieldId: string, instruction: string) {
    try {
      await api.put(`/panels/${agentPanelId}/field-mappings?tenant_id=${tenantId}`, {
        panel_custom_field_id: panelCustomFieldId,
        storage_instruction: instruction,
      })
      toast.success('Mapeamento salvo!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar mapeamento')
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
                      {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </Button>

                    <Switch
                      checked={row.agentPanel?.active ?? false}
                      onCheckedChange={() => handleToggle(row)}
                    />

                    <div className="flex-1">
                      <p className="font-medium">{row.panel.name || 'Painel sem nome'}</p>
                      <p className="text-sm text-muted-foreground">
                        {row.panel.steps?.length || 0} etapas, {row.panel.custom_fields?.length || 0} campos
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
                                  ? { ...r, agentPanel: { ...r.agentPanel, agent_description: e.target.value } }
                                  : r
                              )
                            )
                          }}
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
                              onValueChange={(val) => {
                                setRows((prev) =>
                                  prev.map((r) =>
                                    r.panel.id === row.panel.id && r.agentPanel
                                      ? { ...r, agentPanel: { ...r.agentPanel, step_id: val || undefined } }
                                      : r
                                  )
                                )
                              }}
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
                              onValueChange={(val) => {
                                setRows((prev) =>
                                  prev.map((r) =>
                                    r.panel.id === row.panel.id && r.agentPanel
                                      ? { ...r, agentPanel: { ...r.agentPanel, department_id: val || undefined } }
                                      : r
                                  )
                                )
                              }}
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

                      {row.panel.custom_fields && row.panel.custom_fields.length > 0 && (
                        <div className="space-y-2">
                          <Label>Mapeamento de Campos</Label>
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Campo</TableHead>
                                <TableHead>Instrucao de armazenamento</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {row.panel.custom_fields.map((cf) => {
                                const mapping = row.agentPanel?.field_mappings?.find(
                                  (fm) => fm.panel_custom_field_id === cf.id
                                )
                                return (
                                  <TableRow key={cf.id}>
                                    <TableCell className="font-medium">{cf.helena_field_name}</TableCell>
                                    <TableCell>
                                      <Input
                                        placeholder="Como armazenar este campo..."
                                        defaultValue={mapping?.storage_instruction || ''}
                                        onBlur={(e) =>
                                          handleFieldMappingSave(
                                            row.agentPanel!.id,
                                            cf.id,
                                            e.target.value
                                          )
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
                        onClick={() => handleSavePanel(row)}
                        disabled={savingPanelId === row.agentPanel!.id}
                        className="bg-blue-600 hover:bg-blue-700"
                      >
                        <Save className="mr-2 h-4 w-4" />
                        {savingPanelId === row.agentPanel!.id ? 'Salvando...' : 'Salvar Painel'}
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
  )
}
