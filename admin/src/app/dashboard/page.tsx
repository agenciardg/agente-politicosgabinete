'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Building2, Users, MessageSquare, ArrowUpRight } from 'lucide-react'
import type { Tenant, MetricsSummary } from '@/types'

export default function DashboardPage() {
  const { user } = useAuth()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        if (user?.role === 'super_admin') {
          const t = await api.get<Tenant[]>('/tenants')
          setTenants(t)
        }
        try {
          const m = await api.get<MetricsSummary>('/metrics/summary')
          setMetrics(m)
        } catch {
          // metrics may not be available for super_admin without tenant
        }
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [user])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Bem-vindo, {user?.name || user?.email}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {user?.role === 'super_admin' && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Tenants Ativos</CardTitle>
              <Building2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {tenants.filter(t => t.active).length}
              </div>
              <p className="text-xs text-muted-foreground">
                {tenants.length} total
              </p>
            </CardContent>
          </Card>
        )}

        {metrics && (
          <>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Conversas</CardTitle>
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{metrics.total_conversations}</div>
                <p className="text-xs text-muted-foreground">
                  Periodo: {metrics.period}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Transferencias</CardTitle>
                <ArrowUpRight className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{metrics.total_transfers}</div>
                <p className="text-xs text-muted-foreground">
                  Periodo: {metrics.period}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Tempo Medio</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {metrics.avg_response_time_seconds.toFixed(1)}s
                </div>
                <p className="text-xs text-muted-foreground">
                  Resposta media
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {metrics?.categories_breakdown && Object.keys(metrics.categories_breakdown).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Categorias</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(metrics.categories_breakdown).map(([cat, count]) => (
                <div key={cat} className="flex items-center justify-between">
                  <span className="text-sm font-medium">{cat}</span>
                  <span className="text-sm text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
