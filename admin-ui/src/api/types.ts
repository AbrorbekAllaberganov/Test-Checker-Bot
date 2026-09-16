/**
 * Backend (FastAPI) javoblarining TypeScript ko'rinishi.
 *
 * Bu fayl `app/schemas/admin/*.py` ning aynan aksi — Pydantic sxemasi
 * o'zgarsa, shu yer ham yangilanishi kerak. (Kattaroq loyihada buni
 * `openapi-typescript` bilan avtomatlashtirish tavsiya etiladi:
 * `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts`)
 */

// ── Umumiy ──────────────────────────────────────────────────────────────

export interface PageMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface Page<T> {
  items: T[]
  meta: PageMeta
}

export type AdminRole = 'SUPERADMIN' | 'SUPPORT_OPERATOR' | 'ANALYST'
export type SubscriptionStatus = 'trial' | 'active' | 'expired' | 'cancelled'
export type ScanStatus = 'pending' | 'done' | 'error'
export type BroadcastAudience =
  | 'all'
  | 'active_subscribers'
  | 'free_tier'
  | 'specific'
export type BroadcastStatus =
  | 'draft'
  | 'queued'
  | 'sending'
  | 'sent'
  | 'failed'
  | 'cancelled'

// ── Auth ────────────────────────────────────────────────────────────────

export interface AdminProfile {
  id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  admin_role: AdminRole
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  profile: AdminProfile
}

export interface OtpRequestResult {
  ok: boolean
  message: string
  retry_after_seconds: number
  expires_in_seconds: number
}

// ── Dashboard ───────────────────────────────────────────────────────────

export interface KpiCards {
  total_teachers: number
  active_teachers_30d: number
  blocked_teachers: number
  total_groups: number
  total_students: number
  total_tests: number
  total_scans: number
  scans_today: number
  scans_7d: number
  omr_accuracy: number
  needs_review_count: number
  error_rate: number
  avg_score_percent: number
  paying_subscribers: number
  new_teachers_7d: number
}

export interface ScanPoint {
  date: string
  total: number
  clean: number
  review: number
  errors: number
}

export interface TeacherActivityPoint {
  date: string
  active_teachers: number
  new_teachers: number
}

export interface QuestionDistributionItem {
  question_count: number
  tests: number
  scans: number
}

export interface FailureBreakdown {
  period_days: number
  total_scans: number
  ambiguous_count: number
  error_count: number
  overridden_count: number
  ambiguity_rate: number
  failure_rate: number
  reasons: { reason: string; count: number }[]
}

export interface PlanUsage {
  plan_code: string
  plan_name: string
  price_uzs: number
  subscribers: number
  scans_used: number
  mrr_uzs: number
}

export interface TopTeacher {
  user_id: number
  full_name: string | null
  username: string | null
  telegram_id: number
  scans: number
}

export interface ComponentStatus {
  name: string
  status: 'up' | 'down' | 'degraded' | 'unknown'
  detail: string
  metrics: Record<string, unknown>
}

export interface SystemStatus {
  overall: string
  components: ComponentStatus[]
}

export interface DashboardOverview {
  kpi: KpiCards
  scan_timeseries: ScanPoint[]
  teacher_activity: TeacherActivityPoint[]
  question_distribution: QuestionDistributionItem[]
  failures: FailureBreakdown
  plans: PlanUsage[]
  top_teachers: TopTeacher[]
  system: SystemStatus
}

// ── Ustozlar ────────────────────────────────────────────────────────────

export interface TeacherListItem {
  id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  role: string
  admin_role: AdminRole | null
  is_blocked: boolean
  blocked_reason: string | null
  created_at: string
  last_seen_at: string | null
  groups_count: number
  students_count: number
  tests_count: number
  scans_count: number
  plan_code: string | null
  plan_name: string | null
  subscription_status: SubscriptionStatus | null
  scans_used: number
  scan_limit: number | null
}

export interface TeacherStats {
  groups_count: number
  students_count: number
  tests_count: number
  scans_count: number
  scans_30d: number
  needs_review_count: number
  avg_score_percent: number
  last_scan_at: string | null
}

export interface RecentActivityItem {
  attempt_id: number
  student_name: string | null
  test_title: string | null
  score: number | null
  total: number | null
  percent: number | null
  status: ScanStatus
  needs_review: boolean
  created_at: string
}

export interface TeacherGroupBrief {
  id: number
  name: string
  students_count: number
  tests_count: number
  created_at: string
}

export interface TeacherDetail {
  id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  role: string
  admin_role: AdminRole | null
  is_blocked: boolean
  blocked_reason: string | null
  blocked_at: string | null
  blocked_by: string | null
  created_at: string
  last_seen_at: string | null
  stats: TeacherStats
  subscription: SubscriptionOut | null
  groups: TeacherGroupBrief[]
  recent_activity: RecentActivityItem[]
}

// ── Obuna / Tarif ───────────────────────────────────────────────────────

export interface PlanOut {
  id: number
  code: string
  name: string
  description: string | null
  price_uzs: number
  max_groups: number | null
  max_students_per_group: number | null
  monthly_scan_limit: number | null
  is_active: boolean
  sort_order: number
  subscribers_count: number
}

export interface SubscriptionOut {
  id: number
  plan_id: number
  plan_code: string
  plan_name: string
  status: SubscriptionStatus
  starts_at: string
  ends_at: string | null
  period_start: string
  period_end: string
  scans_used: number
  bonus_credits: number
  scan_limit: number | null
  scans_remaining: number | null
  usage_percent: number
  max_groups: number | null
  max_students_per_group: number | null
  note: string | null
}

export interface SubscriptionRow {
  user_id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  is_blocked: boolean
  subscription: SubscriptionOut | null
}

// ── Explorer ────────────────────────────────────────────────────────────

export interface GroupListItem {
  id: number
  name: string
  created_at: string
  owner_id: number
  owner_name: string | null
  owner_telegram_id: number | null
  students_count: number
  tests_count: number
  scans_count: number
}

export interface StudentListItem {
  id: number
  full_name: string
  telegram_id: number | null
  group_id: number
  group_name: string | null
  created_at: string
  attempts_count: number
  avg_percent: number | null
}

export interface TestListItem {
  id: number
  title: string
  question_count: number
  variant_count: number
  created_at: string
  group_id: number
  group_name: string | null
  owner_id: number | null
  owner_name: string | null
  tituls_count: number
  attempts_count: number
  avg_percent: number | null
}

/**
 * O'quvchiga berilgan varaq va uning natijasi.
 * `attempt_id === null` — varaq chiqarilgan, lekin hali skanlanmagan.
 */
export interface StudentAttemptItem {
  titul_id: number
  titul_created_at: string
  test_id: number
  test_title: string
  question_count: number
  variant_count: number
  attempt_id: number | null
  score: number | null
  total: number | null
  percent: number | null
  needs_review: boolean
  manual_override: boolean
  confidence: number | null
  status: ScanStatus | null
  created_at: string | null
}

export interface StudentDetail {
  id: number
  full_name: string
  telegram_id: number | null
  group_id: number
  group_name: string | null
  owner_id: number | null
  owner_name: string | null
  created_at: string
  tituls_count: number
  attempts_count: number
  graded_count: number
  avg_percent: number | null
  best_percent: number | null
  attempts: StudentAttemptItem[]
}

export interface GroupDetail {
  id: number
  name: string
  created_at: string
  owner_id: number
  owner_name: string | null
  owner_telegram_id: number | null
  students: StudentListItem[]
  tests: TestListItem[]
}

export interface StudentResultItem {
  attempt_id: number | null
  student_id: number
  student_name: string
  score: number | null
  total: number | null
  percent: number | null
  needs_review: boolean
  status: ScanStatus | null
  created_at: string | null
}

export interface ItemAnalysisRow {
  question: string
  correct_count: number
  incorrect_count: number
  unmarked_count: number
  correct_percent: number
}

export interface TestDetail {
  id: number
  title: string
  question_count: number
  variant_count: number
  answer_key: Record<string, string>
  created_at: string
  group_id: number
  group_name: string | null
  owner_id: number | null
  owner_name: string | null
  attempts_count: number
  avg_percent: number | null
  results: StudentResultItem[]
  item_analysis: ItemAnalysisRow[]
}

// ── Skanlar / OMR ───────────────────────────────────────────────────────

export interface ScanListItem {
  id: number
  status: ScanStatus
  needs_review: boolean
  manual_override: boolean
  score: number | null
  total: number | null
  percent: number | null
  confidence: number | null
  error_msg: string | null
  created_at: string
  student_id: number | null
  student_name: string | null
  test_id: number | null
  test_title: string | null
  group_id: number | null
  group_name: string | null
  owner_id: number | null
  owner_name: string | null
}

export interface BubbleCell {
  letter: string
  fill_ratio: number
  is_selected: boolean
  is_correct_key: boolean
}

export interface ScanQuestionRow {
  question: string
  detected: string | null
  correct: string | null
  is_correct: boolean
  flag: string | null
  confidence: number | null
  bubbles: BubbleCell[]
}

export interface OmrInspector {
  id: number
  status: ScanStatus
  needs_review: boolean
  manual_override: boolean
  score: number | null
  total: number | null
  percent: number | null
  confidence: number | null
  error_msg: string | null
  created_at: string
  reviewed_at: string | null
  reviewed_by: string | null
  student_id: number | null
  student_name: string | null
  test_id: number | null
  test_title: string | null
  group_name: string | null
  owner_id: number | null
  owner_name: string | null
  owner_telegram_id: number | null
  question_count: number
  variant_letters: string[]
  source_url: string | null
  debug_url: string | null
  questions: ScanQuestionRow[]
}

// ── Broadcast ───────────────────────────────────────────────────────────

export interface RecipientRow {
  user_id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  status: 'pending' | 'sent' | 'failed' | 'blocked_bot'
  error_msg: string | null
  sent_at: string | null
}

export interface BroadcastListItem {
  id: number
  title: string | null
  body_preview: string
  audience: BroadcastAudience
  status: BroadcastStatus
  total_count: number
  sent_count: number
  failed_count: number
  created_by: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface BroadcastDetail extends BroadcastListItem {
  body: string
  parse_mode: string
  target_user_ids: number[] | null
  error_msg: string | null
  recipients: RecipientRow[]
}

export interface BroadcastPreview {
  audience: string
  recipients_count: number
  rendered_text: string
  sample_recipients: RecipientRow[]
}

// ── Audit ───────────────────────────────────────────────────────────────

export interface AuditLogItem {
  id: number
  actor_id: number | null
  actor_label: string
  action: string
  object_type: string | null
  object_id: string | null
  payload: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}
