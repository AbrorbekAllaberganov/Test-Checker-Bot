import {
  useMutation,
  useQuery,
  useQueryClient,
  keepPreviousData,
} from '@tanstack/react-query'

import { api } from './client'
import type {
  AuditLogItem,
  BroadcastDetail,
  BroadcastListItem,
  BroadcastPreview,
  DashboardOverview,
  GroupDetail,
  GroupListItem,
  KpiCards,
  OmrInspector,
  Page,
  PlanOut,
  ScanListItem,
  StudentListItem,
  SubscriptionOut,
  SubscriptionRow,
  SystemStatus,
  TeacherDetail,
  TeacherListItem,
  TestDetail,
  TestListItem,
} from './types'

/**
 * TanStack Query v5 hook'lari.
 *
 * Kalitlar (`queryKeys`) iyerarxik: `['teachers']` ni invalidatsiya qilish
 * barcha ustoz so'rovlarini (ro'yxat + tafsilot) yangilaydi.
 */

export const queryKeys = {
  dashboard: ['dashboard'] as const,
  overview: (days: number) => ['dashboard', 'overview', days] as const,
  kpi: () => ['dashboard', 'kpi'] as const,
  system: () => ['system', 'status'] as const,

  teachers: ['teachers'] as const,
  teacherList: (params: TeacherListParams) => ['teachers', 'list', params] as const,
  teacher: (id: number) => ['teachers', 'detail', id] as const,

  groups: ['groups'] as const,
  groupList: (params: GroupListParams) => ['groups', 'list', params] as const,
  group: (id: number) => ['groups', 'detail', id] as const,

  students: ['students'] as const,
  studentList: (params: StudentListParams) => ['students', 'list', params] as const,

  tests: ['tests'] as const,
  testList: (params: TestListParams) => ['tests', 'list', params] as const,
  test: (id: number) => ['tests', 'detail', id] as const,

  scans: ['scans'] as const,
  scanList: (params: ScanListParams) => ['scans', 'list', params] as const,
  reviewQueue: (page: number) => ['scans', 'review-queue', page] as const,
  scan: (id: number) => ['scans', 'detail', id] as const,

  plans: ['plans'] as const,
  subscriptions: ['subscriptions'] as const,
  subscriptionList: (params: SubscriptionListParams) =>
    ['subscriptions', 'list', params] as const,

  broadcasts: ['broadcasts'] as const,
  broadcastList: (page: number) => ['broadcasts', 'list', page] as const,
  broadcast: (id: number) => ['broadcasts', 'detail', id] as const,

  auditLogs: ['audit-logs'] as const,
  auditList: (params: AuditListParams) => ['audit-logs', 'list', params] as const,
}

// ── Parametr turlari ────────────────────────────────────────────────────

export interface PageParams {
  page: number
  page_size: number
}

export interface TeacherListParams extends PageParams {
  search?: string
  blocked?: boolean
  admin_only?: boolean
  plan_code?: string
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
}

export interface GroupListParams extends PageParams {
  owner_id?: number
  search?: string
}

export interface StudentListParams extends PageParams {
  group_id?: number
  owner_id?: number
  search?: string
}

export interface TestListParams extends PageParams {
  group_id?: number
  owner_id?: number
  question_count?: number
  search?: string
}

export interface ScanListParams extends PageParams {
  status?: string
  needs_review?: boolean
  owner_id?: number
  test_id?: number
  group_id?: number
  max_confidence?: number
}

export interface SubscriptionListParams extends PageParams {
  plan_code?: string
  status?: string
  search?: string
  over_quota?: boolean
}

export interface AuditListParams extends PageParams {
  action?: string
  actor_id?: number
  object_type?: string
}

/** `undefined` va bo'sh qiymatlarni query string'dan olib tashlaydi. */
function clean<T extends object>(params: T): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== '' && value !== null,
    ),
  )
}

// ── Dashboard ───────────────────────────────────────────────────────────

export function useOverview(days = 30) {
  return useQuery({
    queryKey: queryKeys.overview(days),
    queryFn: async () => {
      const { data } = await api.get<DashboardOverview>(
        '/api/admin/dashboard/overview',
        { params: { days } },
      )
      return data
    },
    // Dashboard og'ir so'rov — 60 soniya davomida qayta so'ralmaydi.
    staleTime: 60_000,
  })
}

export function useKpi(refetchMs?: number) {
  return useQuery({
    queryKey: queryKeys.kpi(),
    queryFn: async () => {
      const { data } = await api.get<KpiCards>('/api/admin/dashboard/kpi')
      return data
    },
    refetchInterval: refetchMs,
  })
}

export function useSystemStatus(refetchMs = 30_000) {
  return useQuery({
    queryKey: queryKeys.system(),
    queryFn: async () => {
      const { data } = await api.get<SystemStatus>('/api/admin/system/status')
      return data
    },
    refetchInterval: refetchMs,
  })
}

// ── Ustozlar ────────────────────────────────────────────────────────────

export function useTeachers(params: TeacherListParams) {
  return useQuery({
    queryKey: queryKeys.teacherList(params),
    queryFn: async () => {
      const { data } = await api.get<Page<TeacherListItem>>('/api/admin/users', {
        params: clean(params),
      })
      return data
    },
    // Sahifa almashganda jadval "sakramasligi" uchun eski ma'lumot turadi.
    placeholderData: keepPreviousData,
  })
}

export function useTeacher(id: number | null) {
  return useQuery({
    queryKey: queryKeys.teacher(id ?? 0),
    queryFn: async () => {
      const { data } = await api.get<TeacherDetail>(`/api/admin/users/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

export function useBlockTeacher() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { userId: number; blocked: boolean; reason?: string }) => {
      const { data } = await api.post<TeacherDetail>(
        `/api/admin/users/${vars.userId}/block`,
        { blocked: vars.blocked, reason: vars.reason ?? null },
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.teachers })
      void qc.invalidateQueries({ queryKey: queryKeys.dashboard })
    },
  })
}

export function useChangeAdminRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { userId: number; adminRole: string | null }) => {
      const { data } = await api.patch<TeacherDetail>(
        `/api/admin/users/${vars.userId}/role`,
        { admin_role: vars.adminRole },
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.teachers })
    },
  })
}

// ── Explorer ────────────────────────────────────────────────────────────

export function useGroups(params: GroupListParams) {
  return useQuery({
    queryKey: queryKeys.groupList(params),
    queryFn: async () => {
      const { data } = await api.get<Page<GroupListItem>>('/api/admin/groups', {
        params: clean(params),
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useGroup(id: number | null) {
  return useQuery({
    queryKey: queryKeys.group(id ?? 0),
    queryFn: async () => {
      const { data } = await api.get<GroupDetail>(`/api/admin/groups/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

export function useStudents(params: StudentListParams) {
  return useQuery({
    queryKey: queryKeys.studentList(params),
    queryFn: async () => {
      const { data } = await api.get<Page<StudentListItem>>('/api/admin/students', {
        params: clean(params),
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useTests(params: TestListParams) {
  return useQuery({
    queryKey: queryKeys.testList(params),
    queryFn: async () => {
      const { data } = await api.get<Page<TestListItem>>('/api/admin/tests', {
        params: clean(params),
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useTest(id: number | null) {
  return useQuery({
    queryKey: queryKeys.test(id ?? 0),
    queryFn: async () => {
      const { data } = await api.get<TestDetail>(`/api/admin/tests/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

// ── Skanlar ─────────────────────────────────────────────────────────────

export function useScans(params: ScanListParams) {
  return useQuery({
    queryKey: queryKeys.scanList(params),
    queryFn: async () => {
      const { data } = await api.get<Page<ScanListItem>>('/api/admin/scans', {
        params: clean(params),
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useReviewQueue(page: number, pageSize = 25) {
  return useQuery({
    queryKey: queryKeys.reviewQueue(page),
    queryFn: async () => {
      const { data } = await api.get<Page<ScanListItem>>(
        '/api/admin/scans/review-queue',
        { params: { page, page_size: pageSize } },
      )
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useScan(id: number | null) {
  return useQuery({
    queryKey: queryKeys.scan(id ?? 0),
    queryFn: async () => {
      const { data } = await api.get<OmrInspector>(`/api/admin/scans/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

export function useOverrideScan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      attemptId: number
      answers: Record<string, string | null>
      reason?: string
      notifyTeacher: boolean
    }) => {
      const { data } = await api.post<OmrInspector>(
        `/api/admin/scans/${vars.attemptId}/override`,
        {
          answers: vars.answers,
          reason: vars.reason ?? null,
          notify_teacher: vars.notifyTeacher,
        },
      )
      return data
    },
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.scan(data.id), data)
      void qc.invalidateQueries({ queryKey: queryKeys.scans })
      void qc.invalidateQueries({ queryKey: queryKeys.dashboard })
    },
  })
}

export function useResolveScan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { attemptId: number; reason?: string }) => {
      const { data } = await api.post<OmrInspector>(
        `/api/admin/scans/${vars.attemptId}/resolve`,
        null,
        { params: clean({ reason: vars.reason }) },
      )
      return data
    },
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.scan(data.id), data)
      void qc.invalidateQueries({ queryKey: queryKeys.scans })
    },
  })
}

// ── Tarif va obunalar ───────────────────────────────────────────────────

export function usePlans(includeInactive = false) {
  return useQuery({
    queryKey: [...queryKeys.plans, includeInactive],
    queryFn: async () => {
      const { data } = await api.get<PlanOut[]>('/api/admin/plans', {
        params: { include_inactive: includeInactive },
      })
      return data
    },
  })
}

export function useSavePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { id?: number; payload: Partial<PlanOut> }) => {
      const { data } = vars.id
        ? await api.put<PlanOut>(`/api/admin/plans/${vars.id}`, vars.payload)
        : await api.post<PlanOut>('/api/admin/plans', vars.payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.plans })
      void qc.invalidateQueries({ queryKey: queryKeys.subscriptions })
    },
  })
}

export function useSubscriptions(params: SubscriptionListParams) {
  return useQuery({
    queryKey: queryKeys.subscriptionList(params),
    queryFn: async () => {
      const { data } = await api.get<Page<SubscriptionRow>>(
        '/api/admin/subscriptions',
        { params: clean(params) },
      )
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useAssignPlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      userId: number
      planId: number
      status: string
      durationDays?: number | null
      resetUsage: boolean
      note?: string
    }) => {
      const { data } = await api.post<SubscriptionOut>(
        `/api/admin/subscriptions/${vars.userId}/assign`,
        {
          plan_id: vars.planId,
          status: vars.status,
          duration_days: vars.durationDays ?? null,
          reset_usage: vars.resetUsage,
          note: vars.note ?? null,
        },
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.subscriptions })
      void qc.invalidateQueries({ queryKey: queryKeys.teachers })
      void qc.invalidateQueries({ queryKey: queryKeys.plans })
    },
  })
}

export function useGrantCredits() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { userId: number; credits: number; note?: string }) => {
      const { data } = await api.post<SubscriptionOut>(
        `/api/admin/subscriptions/${vars.userId}/credits`,
        { credits: vars.credits, note: vars.note ?? null },
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.subscriptions })
      void qc.invalidateQueries({ queryKey: queryKeys.teachers })
    },
  })
}

// ── Broadcast ───────────────────────────────────────────────────────────

export function useBroadcasts(page: number, pageSize = 20) {
  return useQuery({
    queryKey: queryKeys.broadcastList(page),
    queryFn: async () => {
      const { data } = await api.get<Page<BroadcastListItem>>(
        '/api/admin/broadcasts',
        { params: { page, page_size: pageSize } },
      )
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useBroadcast(id: number | null, pollWhileSending = true) {
  return useQuery({
    queryKey: queryKeys.broadcast(id ?? 0),
    queryFn: async () => {
      const { data } = await api.get<BroadcastDetail>(`/api/admin/broadcasts/${id}`)
      return data
    },
    enabled: id !== null,
    // Yuborish davom etayotganda progress'ni jonli ko'rsatamiz.
    refetchInterval: (query) => {
      if (!pollWhileSending) return false
      const status = query.state.data?.status
      return status === 'queued' || status === 'sending' ? 2_000 : false
    },
  })
}

export interface BroadcastPayload {
  title?: string | null
  body: string
  parse_mode: 'HTML' | 'Markdown' | 'None'
  audience: string
  target_user_ids?: number[] | null
  send_now: boolean
}

export function usePreviewBroadcast() {
  return useMutation({
    mutationFn: async (payload: BroadcastPayload) => {
      const { data } = await api.post<BroadcastPreview>(
        '/api/admin/broadcasts/preview',
        payload,
      )
      return data
    },
  })
}

export function useCreateBroadcast() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: BroadcastPayload) => {
      const { data } = await api.post<BroadcastDetail>('/api/admin/broadcasts', payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.broadcasts })
    },
  })
}

export function useSendBroadcast() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post<BroadcastDetail>(
        `/api/admin/broadcasts/${id}/send`,
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.broadcasts })
    },
  })
}

export function useCancelBroadcast() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post<BroadcastDetail>(
        `/api/admin/broadcasts/${id}/cancel`,
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.broadcasts })
    },
  })
}

// ── Audit ───────────────────────────────────────────────────────────────

export function useAuditLogs(params: AuditListParams) {
  return useQuery({
    queryKey: queryKeys.auditList(params),
    queryFn: async () => {
      const { data } = await api.get<Page<AuditLogItem>>('/api/admin/audit-logs', {
        params: clean(params),
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useAuditActions() {
  return useQuery({
    queryKey: ['audit-logs', 'actions'],
    queryFn: async () => {
      const { data } = await api.get<string[]>('/api/admin/audit-logs/actions')
      return data
    },
    staleTime: Infinity,
  })
}
