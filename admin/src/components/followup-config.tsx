'use client'

import { useEffect, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { Play, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import type { FollowupQueueItem } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface FollowupConfigProps {
  tenantId: string
}

const statusConfig: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  pending: { label: 'Pendente', variant: 'outline' },
  sent: { label: 'Enviado', variant: 'default' },
  failed: { label: 'Falhou', variant: 'destructive' },
}

export function FollowupConfig({ tenantId }: FollowupConfigProps) {
  const [queue, setQueue] = useState<FollowupQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)

  const loadQueue = useCallback(async () => {
    try {
      const items = await api.get<FollowupQueueItem[]>(`/followup/queue?tenant_id=${tenantId}`)
      setQueue(items)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar fila de follow-up')
    } finally {
      setLoading(false)
    }
  }, [tenantId])

  useEffect(() => {
    loadQueue()

    const interval = setInterval(loadQueue, 30000)
    return () => clearInterval(interval)
  }, [loadQueue])

  async function handleProcess() {
    setProcessing(true)
    try {
      const result = await api.post<{ success: boolean; result: string }>('/followup/process')
      if (result.success) {
        toast.success('Follow-ups processados com sucesso!')
      } else {
        toast.error('Erro ao processar follow-ups')
      }
      await loadQueue()
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

  function getStatusBadge(status: string) {
    const config = statusConfig[status] || { label: status, variant: 'secondary' as const }
    return <Badge variant={config.variant}>{config.label}</Badge>
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Fila de Follow-up</CardTitle>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadQueue}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Atualizar
          </Button>
          <Button
            size="sm"
            onClick={handleProcess}
            disabled={processing}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Play className="mr-2 h-4 w-4" />
            {processing ? 'Processando...' : 'Processar Agora'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-32 animate-pulse rounded bg-muted" />
        ) : queue.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            Nenhum follow-up na fila
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sessao</TableHead>
                <TableHead>Telefone</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Follow-up #</TableHead>
                <TableHead>Agendado</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono text-sm">
                    {item.session_id.slice(0, 8)}...
                  </TableCell>
                  <TableCell>{item.phone_number}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {item.agent_type === 'principal' ? 'Principal' : 'Assessor'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">{item.followup_number}</TableCell>
                  <TableCell>{formatDate(item.scheduled_at)}</TableCell>
                  <TableCell>{getStatusBadge(item.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
