"""字典接口：供前端下拉选项使用。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import (
    INSPECTION_CHECK_ITEMS,
    ISSUE_TRANSITIONS,
    OPEN_ISSUE_STATUSES,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    RestroomGrade,
    RestroomStatus,
    Shift,
)
from app.core.database import get_db
from app.services import inspection_service, rules

router = APIRouter(prefix="/meta", tags=["字典"])


class RestroomOption(BaseModel):
    id: int
    code: str
    name: str
    district: str


class GradeThreshold(BaseModel):
    """百分制得分达到 min_score（含）时对应等级。"""

    min_score: float
    grade: str


class Dictionaries(BaseModel):
    restroom_status: list[str]
    restroom_grade: list[str]
    shift: list[str]
    issue_category: list[str]
    issue_severity: list[str]
    issue_status: list[str]
    inspection_check_items: list[str]
    # 以下评分/期限/超期口径均取自 app.services.rules，前端只消费、不另立规则
    inspection_item_max_score: int
    inspection_item_problem_threshold: int
    grade_thresholds: list[GradeThreshold]
    grade_fail: str
    issue_open_status: list[str]
    issue_deadline_days: dict[str, int]
    issue_deadline_days_default: int
    issue_transitions: dict[str, list[str]]


@router.get("/dictionaries", response_model=Dictionaries, summary="枚举字典")
def get_dictionaries() -> Dictionaries:
    return Dictionaries(
        restroom_status=[item.value for item in RestroomStatus],
        restroom_grade=[item.value for item in RestroomGrade],
        shift=[item.value for item in Shift],
        issue_category=[item.value for item in IssueCategory],
        issue_severity=[item.value for item in IssueSeverity],
        issue_status=[item.value for item in IssueStatus],
        inspection_check_items=list(INSPECTION_CHECK_ITEMS),
        inspection_item_max_score=rules.INSPECTION_ITEM_MAX_SCORE,
        inspection_item_problem_threshold=rules.INSPECTION_ITEM_PROBLEM_THRESHOLD,
        grade_thresholds=[
            GradeThreshold(min_score=lower, grade=grade)
            for lower, grade in rules.GRADE_THRESHOLDS
        ],
        grade_fail=rules.GRADE_FAIL,
        issue_open_status=list(OPEN_ISSUE_STATUSES),
        issue_deadline_days=dict(rules.ISSUE_DEADLINE_DAYS),
        issue_deadline_days_default=rules.ISSUE_DEADLINE_DAYS_DEFAULT,
        issue_transitions={key: list(value) for key, value in ISSUE_TRANSITIONS.items()},
    )


@router.get("/restroom-options", response_model=list[RestroomOption], summary="公厕下拉选项")
def get_restroom_options(
    db: Annotated[Session, Depends(get_db)], keyword: str | None = None
) -> list[RestroomOption]:
    rows = inspection_service.restroom_options(db, keyword=keyword)
    return [
        RestroomOption(id=row.id, code=row.code, name=row.name, district=row.district)
        for row in rows
    ]
