"""字典接口：供前端下拉选项使用。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import (
    DEFAULT_RECTIFICATION_DAYS,
    GRADE_MIN_EXCELLENT,
    GRADE_MIN_GOOD,
    GRADE_MIN_PASS,
    INSPECTION_CHECK_ITEMS,
    INSPECTION_ITEM_MAX_SCORE,
    INSPECTION_ITEM_PROBLEM_THRESHOLD,
    ISSUE_RECTIFICATION_DAYS,
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
from app.services import inspection_service

router = APIRouter(prefix="/meta", tags=["字典"])


class RestroomOption(BaseModel):
    id: int
    code: str
    name: str
    district: str


class Dictionaries(BaseModel):
    restroom_status: list[str]
    restroom_grade: list[str]
    shift: list[str]
    issue_category: list[str]
    issue_severity: list[str]
    issue_status: list[str]
    inspection_check_items: list[str]
    inspection_item_max_score: int
    issue_transitions: dict[str, list[str]]
    # 业务规则参数：与 app.services.rules 同源，供前端录入预览与展示取值
    inspection_grade_thresholds: dict[str, int]
    inspection_item_problem_threshold: int
    issue_rectification_days: dict[str, int]
    issue_default_rectification_days: int
    issue_open_statuses: list[str]


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
        inspection_item_max_score=INSPECTION_ITEM_MAX_SCORE,
        issue_transitions={key: list(value) for key, value in ISSUE_TRANSITIONS.items()},
        inspection_grade_thresholds={
            "excellent": GRADE_MIN_EXCELLENT,
            "good": GRADE_MIN_GOOD,
            "pass": GRADE_MIN_PASS,
        },
        inspection_item_problem_threshold=INSPECTION_ITEM_PROBLEM_THRESHOLD,
        issue_rectification_days=dict(ISSUE_RECTIFICATION_DAYS),
        issue_default_rectification_days=DEFAULT_RECTIFICATION_DAYS,
        issue_open_statuses=list(OPEN_ISSUE_STATUSES),
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
