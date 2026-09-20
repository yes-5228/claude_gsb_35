"""业务规则单一来源。

巡查评分、问题编号生成、整改期限推算、超期判定的唯一实现。
录入、查询、统计等所有入口必须从这里取规则，禁止在其它模块重写，
以保证同一批数据在任何入口算出的得分、期限与超期结论都相同。
"""

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import (
    DEFAULT_RECTIFICATION_DAYS,
    GRADE_EXCELLENT,
    GRADE_FAIL,
    GRADE_GOOD,
    GRADE_MIN_EXCELLENT,
    GRADE_MIN_GOOD,
    GRADE_MIN_PASS,
    GRADE_PASS,
    INSPECTION_ITEM_MAX_SCORE,
    INSPECTION_ITEM_PROBLEM_THRESHOLD,
    ISSUE_CODE_PREFIX,
    ISSUE_CODE_SEQ_WIDTH,
    ISSUE_RECTIFICATION_DAYS,
    OPEN_ISSUE_STATUSES,
    InspectionResult,
)
from app.models import Issue

# ---------------------------------------------------------------------------
# 巡查评分
# ---------------------------------------------------------------------------


def calc_score(items: list[dict]) -> float:
    """按检查项平均得分换算成百分制。"""
    if not items:
        return 0.0
    total = sum(float(item["score"]) for item in items)
    full = len(items) * INSPECTION_ITEM_MAX_SCORE
    return round(total / full * 100, 1)


def score_to_grade(score: float) -> str:
    if score >= GRADE_MIN_EXCELLENT:
        return GRADE_EXCELLENT
    if score >= GRADE_MIN_GOOD:
        return GRADE_GOOD
    if score >= GRADE_MIN_PASS:
        return GRADE_PASS
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
# 问题编号生成
# ---------------------------------------------------------------------------


def next_issue_code(db: Session, *, now: datetime | None = None) -> str:
    """生成形如 WT-20260920-001 的问题编号：前缀 + 上报日期 + 当日流水号。"""
    moment = now or datetime.now()
    prefix = f"{ISSUE_CODE_PREFIX}-{moment:%Y%m%d}"
    seq = (
        db.scalar(select(func.count()).select_from(Issue).where(Issue.code.like(f"{prefix}-%")))
        or 0
    ) + 1
    while True:
        code = f"{prefix}-{seq:0{ISSUE_CODE_SEQ_WIDTH}d}"
        if not db.scalar(select(Issue.id).where(Issue.code == code)):
            return code
        seq += 1


# ---------------------------------------------------------------------------
# 整改期限推算
# ---------------------------------------------------------------------------


def rectification_days(severity: str) -> int:
    """按严重程度取整改天数，未列出的程度取默认值。"""
    key = severity.value if hasattr(severity, "value") else str(severity)
    return ISSUE_RECTIFICATION_DAYS.get(key, DEFAULT_RECTIFICATION_DAYS)


def default_deadline(severity: str, base: datetime) -> datetime:
    """以 base 为起点按严重程度推算默认整改期限。"""
    return base + timedelta(days=rectification_days(severity))


# ---------------------------------------------------------------------------
# 超期判定
# ---------------------------------------------------------------------------


def is_overdue(deadline: datetime | None, status: str, *, now: datetime | None = None) -> bool:
    """超期判定：有期限、状态未闭环、期限已过。与 overdue_conditions 同口径。"""
    if deadline is None or status not in OPEN_ISSUE_STATUSES:
        return False
    return deadline < (now or datetime.now())


def overdue_conditions(now: datetime | None = None) -> list:
    """超期筛选的 SQL 条件，与 is_overdue 同口径。"""
    moment = now or datetime.now()
    return [
        Issue.deadline.is_not(None),
        Issue.deadline < moment,
        Issue.status.in_(OPEN_ISSUE_STATUSES),
    ]


def not_overdue_conditions(now: datetime | None = None) -> list:
    """「未超期」筛选的 SQL 条件：未闭环且（无期限或期限未过）。"""
    moment = now or datetime.now()
    return [
        or_(Issue.deadline.is_(None), Issue.deadline >= moment),
        Issue.status.in_(OPEN_ISSUE_STATUSES),
    ]
