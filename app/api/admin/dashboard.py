"""
app/api/admin/dashboard.py — Executive Dashboard endpointlari.

`/overview` — bitta so'rovda barcha kartochka va grafiklar. Og'ir so'rovlar
parallel (`asyncio.gather`) bajariladi, shu sababli sahifa ochilishi eng
sekin so'rov qancha bo'lsa shuncha vaqt oladi.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.admin.deps import DbDep, require_analyst
from app.schemas.admin.dashboard import (
    DashboardOverview,
    FailureBreakdown,
    KpiCards,
    PlanUsage,
    QuestionDistributionItem,
    ScanPoint,
    SystemStatus,
    TeacherActivityPoint,
    TopTeacher,
)
from app.services import admin_metrics, system_status

router = APIRouter(
    prefix="/dashboard",
    tags=["admin:dashboard"],
    dependencies=[Depends(require_analyst)],
)


@router.get("/kpi", response_model=KpiCards)
async def get_kpi(db: DbDep) -> KpiCards:
    """Faqat KPI kartochkalari — tez-tez yangilab turish uchun (polling)."""
    summary = await admin_metrics.kpi_summary(db)
    return KpiCards(**summary.__dict__)


@router.get("/scans-timeseries", response_model=list[ScanPoint])
async def get_scan_timeseries(
    db: DbDep,
    days: int = Query(30, ge=1, le=365),
) -> list[ScanPoint]:
    rows = await admin_metrics.scan_timeseries(db, days=days)
    return [ScanPoint(**r) for r in rows]


@router.get("/teacher-activity", response_model=list[TeacherActivityPoint])
async def get_teacher_activity(
    db: DbDep,
    days: int = Query(30, ge=1, le=365),
) -> list[TeacherActivityPoint]:
    rows = await admin_metrics.active_teachers_timeseries(db, days=days)
    return [TeacherActivityPoint(**r) for r in rows]


@router.get("/question-distribution", response_model=list[QuestionDistributionItem])
async def get_question_distribution(db: DbDep) -> list[QuestionDistributionItem]:
    rows = await admin_metrics.question_count_distribution(db)
    return [QuestionDistributionItem(**r) for r in rows]


@router.get("/failures", response_model=FailureBreakdown)
async def get_failures(
    db: DbDep,
    days: int = Query(30, ge=1, le=365),
) -> FailureBreakdown:
    return FailureBreakdown(**await admin_metrics.failure_breakdown(db, days=days))


@router.get("/plans-usage", response_model=list[PlanUsage])
async def get_plans_usage(db: DbDep) -> list[PlanUsage]:
    rows = await admin_metrics.plan_distribution(db)
    return [PlanUsage(**r) for r in rows]


@router.get("/top-teachers", response_model=list[TopTeacher])
async def get_top_teachers(
    db: DbDep,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
) -> list[TopTeacher]:
    rows = await admin_metrics.top_teachers(db, limit=limit, days=days)
    return [TopTeacher(**r) for r in rows]


@router.get("/system", response_model=SystemStatus)
async def get_system_status(db: DbDep) -> SystemStatus:
    """Redis / Celery / Postgres holati."""
    return SystemStatus(**await system_status.full_status(db))


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(
    db: DbDep,
    days: int = Query(30, ge=7, le=365, description="Grafiklar davri (kun)"),
) -> DashboardOverview:
    """Dashboard sahifasi uchun to'liq ma'lumot — bitta so'rovda."""
    # DIQQAT: bitta AsyncSession bir vaqtda faqat bitta so'rovni bajara oladi
    # (parallel ishlatilsa "session is already flushing / concurrent operations"
    # xatosi chiqadi), shu sababli DB chaqiruvlari ketma-ket.
    kpi = await admin_metrics.kpi_summary(db)
    scans = await admin_metrics.scan_timeseries(db, days=days)
    activity = await admin_metrics.active_teachers_timeseries(db, days=days)
    distribution = await admin_metrics.question_count_distribution(db)
    failures = await admin_metrics.failure_breakdown(db, days=days)
    plans = await admin_metrics.plan_distribution(db)
    top = await admin_metrics.top_teachers(db, limit=10, days=days)

    # Redis/Celery tekshiruvi DB dan mustaqil — sessiya bo'shagach chaqiramiz.
    system = await system_status.full_status(db)

    return DashboardOverview(
        kpi=KpiCards(**kpi.__dict__),
        scan_timeseries=[ScanPoint(**r) for r in scans],
        teacher_activity=[TeacherActivityPoint(**r) for r in activity],
        question_distribution=[QuestionDistributionItem(**r) for r in distribution],
        failures=FailureBreakdown(**failures),
        plans=[PlanUsage(**r) for r in plans],
        top_teachers=[TopTeacher(**r) for r in top],
        system=SystemStatus(**system),
    )
