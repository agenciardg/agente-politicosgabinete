'use client'

import { CheckCircle2, Circle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface ChecklistItem {
  label: string
  completed: boolean
}

interface OnboardingChecklistProps {
  items: ChecklistItem[]
}

export function OnboardingChecklist({ items }: OnboardingChecklistProps) {
  const completed = items.filter((i) => i.completed).length
  const total = items.length

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Checklist de Configuracao</span>
          <span className="text-sm font-normal text-muted-foreground">
            {completed}/{total} completos
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {items.map((item, index) => (
            <div key={index} className="flex items-center gap-3">
              {item.completed ? (
                <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0" />
              ) : (
                <Circle className="h-5 w-5 text-muted-foreground shrink-0" />
              )}
              <span className={item.completed ? 'text-muted-foreground line-through' : 'font-medium'}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
