export interface User {
  id: string
  email: string
  name: string
  role: 'super_admin' | 'tenant_admin'
  tenant_id: string | null
}

export interface Tenant {
  id: string
  name: string
  slug: string
  helena_api_token?: string
  llm_api_key?: string
  llm_provider?: string
  followup_1_minutes: number
  followup_2_minutes: number
  followup_3_minutes: number
  due_hours: number
  checkpoint_timeout_hours?: number
  active: boolean
  created_at?: string
  updated_at?: string
}

export interface Agent {
  id: string
  tenant_id: string
  agent_type: 'principal' | 'assessor'
  name: string
  persona_prompt?: string
  behavior_prompt?: string
  active?: boolean
}

export interface FollowupPrompt {
  id: string
  agent_id: string
  followup_number: number
  prompt_template: string
  active?: boolean
}

export interface ContactField {
  id: string
  tenant_id: string
  helena_field_key: string
  helena_field_name?: string
}

export interface AgentField {
  id: string
  agent_id: string
  contact_field_id: string
  instruction?: string
  field_order?: number
  required?: boolean
  active?: boolean
}

export interface Panel {
  id: string
  tenant_id: string
  name?: string
  steps?: { id: string; step_name: string }[]
  custom_fields?: { id: string; helena_field_name: string }[]
}

export interface AgentPanel {
  id: string
  agent_id: string
  tenant_panel_id: string
  agent_description?: string
  step_id?: string
  department_id?: string
  active?: boolean
  field_mappings?: FieldMapping[]
}

export interface FieldMapping {
  id: string
  agent_panel_id: string
  panel_custom_field_id: string
  storage_instruction: string
  active?: boolean
}

export interface AssessorNumber {
  id: string
  tenant_id: string
  agent_id: string
  phone_number: string
  label?: string
  active?: boolean
}

export interface MetricsSummary {
  total_conversations: number
  total_transfers: number
  avg_response_time_seconds: number
  categories_breakdown: Record<string, number>
  period: string
}

export interface Department {
  id: string
  tenant_id: string
  helena_department_id: string
  department_name?: string
}

export interface FollowupQueueItem {
  id: string
  session_id: string
  phone_number: string
  agent_type: string
  followup_number: number
  scheduled_at: string
  status: string
}

export interface AdminUser {
  id: string
  email: string
  name: string
  role: 'super_admin' | 'tenant_admin'
  tenant_id: string | null
  active: boolean
  created_at: string
  updated_at: string
}
