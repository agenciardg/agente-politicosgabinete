'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { MessageSquare, ArrowRightLeft, Clock } from 'lucide-react'
import { api } from '@/lib/api'
import type { MetricsSummary } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface MetricsDashboardProps {
  tenantId: string
}

type Period = '24h' | '7d' | '30d'

const periodLabels: Record<Period, string> = {
  '24h': 'Ultimas 24 horas',
  '7d': 'Ultimos 7 dias',
  '30d': 'Ultimos 30 dias',
}

export function MetricsDashboard({ tenantId }: MetricsDashboardProps) {
  const [period, setPeriod] = useState<Period>('7d')
  const [summary, setSummary] = useState<MetricsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api
      .get<MetricsSummary>(`/metrics/summary?tenant_id=${tenantId}&period=${period}`)
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
      {/* Period selector */}
      <div className="flex items-center gap-4">
        <Select value={period} onValueChange={(val) => setPeriod(val as Period)}>
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="Selecione o periodo" />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(periodLabels) as Period[]).map((p) => (
              <SelectItem key={p} value={p}>
                {periodLabels[p]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex gap-2">
          {(Object.keys(periodLabels) as Period[]).map((p) => (
            <Button
              key={p}
              variant={period === p ? 'default' : 'outline'}
              size="sm"
              onClick={() => setPeriod(p)}
              className={period === p ? 'bg-blue-600 hover:bg-blue-700' : ''}
            >
              {p}
            </Button>
          ))}
        </div>
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
          {/* Metric cards */}
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

          {/* Categories breakdown */}
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
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{category}</span>
                        <Badge variant="secondary">{count}</Badge>
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
