"""规则单一来源（app.services.rules）的口径一致性测试。

这些不变量必须始终成立：同一批数据无论从录入、列表筛选还是统计入口，
得分/等级/结论、期限、超期结论与编号格式都只能由 rules 算出同一份结果。
"""

from datetime import datetime, timedelta

from app.core.constants import IssueStatus
from app.services import rules


def test_score_grade_and_result_boundaries():
    items = [{"name": f"项{i}", "score": 8} for i in range(8)]
    assert rules.calc_score(items) == 80.0
    assert rules.score_to_grade(80.0) == "良好"
    assert rules.score_to_grade(79.9) == "合格"
    assert rules.score_to_grade(90.0) == "优秀"
    assert rules.score_to_grade(69.9) == "不合格"

    # 总分合格但存在不合格项时，结论仍为「发现问题」
    items_with_low = [{"name": "差项", "score": 5}] + [
        {"name": f"项{i}", "score": 9} for i in range(7)
    ]
    score, grade, result = rules.evaluate(items_with_low)
    assert result == "发现问题"
    assert rules.problem_items(items_with_low)[0]["name"] == "差项"
    assert score < 90

    assert rules.evaluate([]) == (0.0, "不合格", "发现问题")


def test_deadline_derivation_uses_severity():
    report = datetime(2026, 9, 20, 10, 0)
    assert rules.derive_deadline(report, "紧急") == report + timedelta(days=1)
    assert rules.derive_deadline(report, "严重") == report + timedelta(days=3)
    assert rules.derive_deadline(report, "一般") == report + timedelta(days=3)
    # 未知程度走默认天数
    assert rules.derive_deadline(report, "未知") == report + timedelta(days=3)


def test_overdue_predicate_matches_open_statuses():
    now = datetime(2026, 9, 20, 12, 0)
    past = now - timedelta(hours=1)
    future = now + timedelta(hours=1)

    for status in ("待整改", "整改中", "待验收"):
        assert rules.is_overdue(past, status, now=now) is True
        assert rules.is_overdue(future, status, now=now) is False
    for status in ("已完成", "已关闭"):
        assert rules.is_overdue(past, status, now=now) is False
    assert rules.is_overdue(None, "待整改", now=now) is False


def test_sql_conditions_agree_with_predicate(db_session, make_issue):
    """SQL 过滤条件必须与 Python 判定逐条一致：两个入口口径相同。"""
    now = datetime.now()
    scenarios = [
        ("待整改", now - timedelta(days=1), True),
        ("整改中", now + timedelta(days=1), False),
        ("待验收", None, False),
        ("已完成", now - timedelta(days=1), False),
        ("已关闭", now - timedelta(days=1), False),
        ("待整改", now + timedelta(days=2), False),
    ]
    issues = [
        make_issue(status=status, deadline=deadline)
        for status, deadline, _ in scenarios
    ]

    for issue, (_, _, expected) in zip(issues, scenarios):
        assert rules.is_overdue(issue.deadline, issue.status, now=now) is expected

    from sqlalchemy import select

    from app.models import Issue

    overdue_rows = set(
        db_session.scalars(select(Issue).where(*rules.overdue_conditions(now))).all()
    )
    not_overdue_open_rows = set(
        db_session.scalars(select(Issue).where(*rules.not_overdue_conditions(now))).all()
    )
    expected_overdue = {issue for issue, (_, _, flag) in zip(issues, scenarios) if flag}
    assert overdue_rows == expected_overdue
    # 「未超期」视图只覆盖未闭环状态，已完成/已关闭不在任一超期视图内
    assert {issue.status for issue in not_overdue_open_rows} <= set(rules.OPEN_ISSUE_STATUSES)


def test_issue_code_format_and_sequence(db_session, make_issue):
    today = datetime.now().strftime("%Y%m%d")
    make_issue(status=IssueStatus.PENDING, deadline=None)
    code = rules.next_issue_code(db_session)
    assert code.startswith(f"WT-{today}-")
    assert len(code.split("-")[-1]) == 3
    make_issue(code=code, status=IssueStatus.PENDING, deadline=None)
    next_code = rules.next_issue_code(db_session)
    assert next_code != code and next_code.startswith(f"WT-{today}-")
