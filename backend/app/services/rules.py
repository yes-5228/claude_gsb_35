"""领域规则的单一来源。

巡查评分、问题期限推算、超期判定、问题编号生成四组规则只允许在此处定义，
录入（create/update）、查询过滤、统计看板以及导出等所有入口都必须调用本模块，
避免同一规则在多处各写一份导致口径漂移。

前端预览/标签需要同口径时，通过 ``/meta/dictionaries`` 暴露本模块的常量取值，
前端不再自带硬编码阈值。
"""

from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.constants import (
    OPEN_ISSUE_STATUSES,
    InspectionResult,
    IssueSeverity,
)
from app.models import Issue

# ---------------------------------------------------------------------------
# 巡查评分规则
# ---------------------------------------------------------------------------

# 单检查项满分
INSPECTION_ITEM_MAX_SCORE = 10

# 单检查项低于该分数视为不合格项
INSPECTION_ITEM_PROBLEM_THRESHOLD = 6

# 百分制得分 -> 等级的阈值（下界，含），顺序即由高到低
GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (90, "优秀"),
    (80, "良好"),
    (70, "合格"),
]
GRADE_FAIL = "不合格"


def calc_score(items: list[dict]) -> float:
    """按检查项平均得分换算成百分制。"""
    if not items:
        return 0.0
    total = sum(float(item["score"]) for item in items)
    full = len(items) * INSPECTION_ITEM_MAX_SCORE
    return round(total / full * 100, 1)


def score_to_grade(score: float) -> str:
    for lower_bound, grade in GRADE_THRESHOLDS:
        if score >= lower_bound:
            return grade
    return GRADE_FAIL


def is_abnormal(items: list[dict]) -> bool:
    """存在低于合格线的检查项即判定为发现问题。"""
    return any(float(item["score"]) < INSPECTION_ITEM_PROBLEM_THRESHOLD for item in items)


def build_result(items: list[dict], score: float) -> str:
    if is_abnormal(items) or score_to_grade(score) == GRADE_FAIL:
        return InspectionResult.ABNORMAL.value
    return InspectionResult.NORMAL.value


def evaluate(items: list[dict]) -> tuple[float, str, str]:
    """返回 (得分, 等级, 巡查结论)。"""
    score = calc_score(items)
    return score, score_to_grade(score), build_result(items, score)


def problem_items(items: list[dict]) -> list[dict]:
    return [item for item in items if float(item["score"]) < INSPECTION_ITEM_PROBLEM_THRESHOLD]


# ---------------------------------------------------------------------------
# 问题期限推算规则
# ---------------------------------------------------------------------------

# 各严重程度对应的整改期限（自上报时间起的天数）；未列出的程度使用默认值
ISSUE_DEADLINE_DAYS: dict[str, int] = {
    IssueSeverity.URGENT.value: 1,
    IssueSeverity.SERIOUS.value: 3,
    IssueSeverity.NORMAL.value: 3,
}
ISSUE_DEADLINE_DAYS_DEFAULT = 3


def deadline_days_for(severity: str) -> int:
    """某严重程度下的整改期限天数，所有入口推算期限时统一调用。"""
    return ISSUE_DEADLINE_DAYS.get(severity, ISSUE_DEADLINE_DAYS_DEFAULT)


def derive_deadline(report_time: datetime, severity: str) -> datetime:
    """依据上报时间与严重程度推算默认整改期限。"""
    return report_time + timedelta(days=deadline_days_for(severity))


# ---------------------------------------------------------------------------
# 超期判定规则
# ---------------------------------------------------------------------------

def is_open_status(status: str) -> bool:
    """状态是否仍处于整改闭环中（未完成、未关闭）。"""
    return status in OPEN_ISSUE_STATUSES


def is_overdue(
    deadline: datetime | None,
    status: str,
    *,
    now: datetime | None = None,
) -> bool:
    """超期：设有期限、期限早于当前时间且状态仍未闭环。

    同时接收 ORM 对象（带 ``deadline``/``status`` 属性）或两个裸值，
    供录入回显、列表、详情与统计复用同一份判定。
    """
    current = now or datetime.now()
    return deadline is not None and is_open_status(status) and deadline < current


def overdue_conditions(now: datetime) -> list:
    """SQL 版超期条件，与 :func:`is_overdue` 严格同口径。"""
    return [
        Issue.deadline.is_not(None),
        Issue.deadline < now,
        Issue.status.in_(OPEN_ISSUE_STATUSES),
    ]


def not_overdue_conditions(now: datetime) -> list:
    """SQL 版「未超期」条件，与 :func:`is_overdue` 的取反同口径。"""
    return [
        or_(Issue.deadline.is_(None), Issue.deadline >= now),
        Issue.status.in_(OPEN_ISSUE_STATUSES),
    ]


# ---------------------------------------------------------------------------
# 问题编号生成规则
# ---------------------------------------------------------------------------

ISSUE_CODE_PREFIX = "WT"


def next_issue_code(db: Session, *, now: datetime | None = None) -> str:
    """生成当日问题编号：``WT-YYYYMMDD-NNN``，三位流水号，跳过已占用编号。"""
    from sqlalchemy import func, select

    current = now or datetime.now()
    prefix = current.strftime(f"{ISSUE_CODE_PREFIX}-%Y%m%d")
    seq = (
        db.scalar(select(func.count()).select_from(Issue).where(Issue.code.like(f"{prefix}-%")))
        or 0
    ) + 1
    while True:
        code = f"{prefix}-{seq:03d}"
        if not db.scalar(select(Issue.id).where(Issue.code == code)):
            return code
        seq += 1
