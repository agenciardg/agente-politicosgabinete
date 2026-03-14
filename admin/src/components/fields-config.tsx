'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { ContactField, AgentField } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface FieldsConfigProps {
  agentId: string
  tenantId: string
}

interface FieldRow {
  contactField: ContactField
  agentField?: AgentField
}

export function FieldsConfig({ agentId, tenantId }: FieldsConfigProps) {
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
            r.contactField.id === row.contactField.id
              ? { ...r, agentField: updated }
              : r
          )
        )
      } else {
        const created = await api.post<AgentField>(`/fields/agent/${agentId}?tenant_id=${tenantId}`, {
          contact_field_id: row.contactField.id,
          active: true,
        })
        setRows((prev) =>
          prev.map((r) =>
            r.contactField.id === row.contactField.id
              ? { ...r, agentField: created }
              : r
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
          r.contactField.id === row.contactField.id
            ? { ...r, agentField: updated }
            : r
        )
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar instrucao')
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
                              ? { ...r, agentField: { ...r.agentField, instruction: e.target.value } }
                              : r
                          )
                        )
                      }}
                      onBlur={(e) => handleInstructionChange(row, e.target.value)}
                      disabled={!row.agentField?.active}
                      className="max-w-[300px]"
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
