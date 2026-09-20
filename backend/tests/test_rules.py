"""规则层测试：评分、编号、期限推算、超期判定的单一来源与各入口口径一致性。"""

from datetime import datetime, timedelta

import pytest

from app.core import constants
from app.core.constants import InspectionResult, IssueSeverity, IssueStatus
from app.services import rules
from tests.conftest import full_items


class TestScoringRules:
    def test_score_is_percentage_of_full_marks(self):
        items = [{"name": "a", "score": 9}, {"name": "b", "score": 9}]
        assert rules.calc_score(items) == 90.0

    def test_empty_items_score_zero(self):
        assert rules.calc_score([]) == 0.0

    @pytest.mark.parametrize(
        ("score", "grade"),
        [
            (100, "优秀"),
            (90, "优秀"),
            (89.9, "良好"),
            (80, "良好"),
            (79.9, "合格"),
            (70, "合格"),
            (69.9, "不合格"),
            (0, "不合格"),
        ],
    )
    def test_grade_boundaries(self, score, grade):
        assert rules.score_to_grade(score) == grade

    def test_single_low_item_marks_abnormal(self):
        items = full_items(9)
        items[0]["score"] = constants.INSPECTION_ITEM_PROBLEM_THRESHOLD - 0.1
        assert rules.is_abnormal(items)
        assert rules.evaluate(items)[2] == InspectionResult.ABNORMAL.value

    def test_item_at_threshold_is_not_abnormal(self):
        items = [{"name": "a", "score": constants.INSPECTION_ITEM_PROBLEM_THRESHOLD}]
        assert not rules.is_abnormal(items)

    def test_fail_grade_forces_abnormal_result(self):
        # 全部刚好达标但总分低于合格线，结论仍为发现问题
        items = full_items(6)
        score, grade, result = rules.evaluate(items)
        assert (score, grade) == (60.0, "不合格")
        assert result == InspectionResult.ABNORMAL.value

    def test_problem_items_only_returns_low_scores(self):
        items = full_items(9)
        items[3]["score"] = 2
        assert rules.problem_items(items) == [items[3]]


class TestIssueCodeRules:
    def test_code_format_and_sequence(self, client, restroom):
        today = datetime.now().strftime("%Y%m%d")
        codes = []
        for index in range(2):
            issue = client.post(
                "/api/v1/issues",
                json={"restroom_id": restroom["id"], "title": f"编号规则验证 {index}"},
            ).json()
            codes.append(issue["code"])
        prefix = f"{constants.ISSUE_CODE_PREFIX}-{today}-"
        assert all(code.startswith(prefix) for code in codes)
        seqs = sorted(int(code.removeprefix(prefix)) for code in codes)
        assert seqs[1] == seqs[0] + 1


class TestDeadlineRules:
    BASE = datetime(2026, 9, 20, 10, 0)

    def test_urgent_is_one_day(self):
        assert rules.default_deadline(IssueSeverity.URGENT, self.BASE) == self.BASE + timedelta(
            days=1
        )

    def test_serious_and_normal_are_three_days(self):
        for severity in (IssueSeverity.SERIOUS, IssueSeverity.NORMAL, "严重", "一般"):
            assert rules.default_deadline(severity, self.BASE) == self.BASE + timedelta(days=3)

    def test_unknown_severity_falls_back_to_default(self):
        assert rules.default_deadline("其他", self.BASE) == self.BASE + timedelta(
            days=constants.DEFAULT_RECTIFICATION_DAYS
        )


class TestOverdueRules:
    def test_open_issue_past_deadline_is_overdue(self):
        assert rules.is_overdue(datetime.now() - timedelta(hours=1), IssueStatus.PENDING)

    def test_closed_statuses_are_never_overdue(self):
        past = datetime.now() - timedelta(days=30)
        for status in (IssueStatus.DONE, IssueStatus.CLOSED):
            assert not rules.is_overdue(past, status)

    def test_no_deadline_is_never_overdue(self):
        assert not rules.is_overdue(None, IssueStatus.PENDING)

    def test_future_deadline_is_not_overdue(self):
        assert not rules.is_overdue(datetime.now() + timedelta(days=1), IssueStatus.PROCESSING)


def test_dictionaries_expose_rule_parameters(client):
    """字典接口下发的规则参数必须与规则层同源。"""
    payload = client.get("/api/v1/meta/dictionaries").json()
    assert payload["inspection_grade_thresholds"] == {
        "excellent": constants.GRADE_MIN_EXCELLENT,
        "good": constants.GRADE_MIN_GOOD,
        "pass": constants.GRADE_MIN_PASS,
    }
    assert payload["inspection_item_problem_threshold"] == (
        constants.INSPECTION_ITEM_PROBLEM_THRESHOLD
    )
    assert payload["issue_rectification_days"] == {
        str(key): value for key, value in constants.ISSUE_RECTIFICATION_DAYS.items()
    }
    assert payload["issue_default_rectification_days"] == constants.DEFAULT_RECTIFICATION_DAYS
    assert payload["issue_open_statuses"] == [str(s) for s in constants.OPEN_ISSUE_STATUSES]


def test_stored_score_matches_rules(client, restroom):
    """不变量：录入返回、详情读回的得分/等级/结论都与规则函数重算结果一致。"""
    items = full_items(9)
    items[0]["score"] = 4
    expected = rules.evaluate(items)

    created = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "规则巡查员", "items": items},
    ).json()
    assert (created["score"], created["grade"], created["result"]) == expected

    detail = client.get(f"/api/v1/inspections/{created['id']}").json()
    assert (detail["score"], detail["grade"], detail["result"]) == expected


def test_overdue_consistent_across_entries(client, restroom):
    """不变量：同一批问题，列表筛选、逐条判定、看板统计的超期结论相同。"""
    now = datetime.now()
    payloads = [
        {"title": "超期未闭环", "deadline": (now - timedelta(days=1)).isoformat()},
        {"title": "期限未到", "deadline": (now + timedelta(days=1)).isoformat()},
        {"title": "无期限"},
        {"title": "超期但会闭环", "deadline": (now - timedelta(days=2)).isoformat()},
    ]
    created_ids = []
    for payload in payloads:
        issue = client.post(
            "/api/v1/issues", json={"restroom_id": restroom["id"], **payload}
        ).json()
        created_ids.append(issue["id"])

    # 把最后一条推进到已闭环：待整改 -> 整改中 -> 待验收 -> 已完成
    for target in ("整改中", "待验收", "已完成"):
        response = client.post(
            f"/api/v1/issues/{created_ids[-1]}/transitions",
            json={"to_status": target, "operator": "值班长"},
        )
        assert response.status_code == 200, response.text

    # 入口一：用规则函数对全量问题逐条判定
    all_issues = client.get("/api/v1/issues", params={"page_size": 100}).json()["items"]
    expected_ids = {
        issue["id"]
        for issue in all_issues
        if rules.is_overdue(
            datetime.fromisoformat(issue["deadline"]) if issue["deadline"] else None,
            issue["status"],
        )
    }
    assert created_ids[0] in expected_ids
    assert not set(created_ids[1:]) & expected_ids

    # 入口二：列表 overdue=true 筛选
    listed = client.get("/api/v1/issues", params={"overdue": "true", "page_size": 100}).json()
    assert {item["id"] for item in listed["items"]} == expected_ids
    assert listed["meta"]["total"] == len(expected_ids)

    # 入口三：看板统计的超期数量
    overview = client.get("/api/v1/stats/overview").json()
    assert overview["issue_overdue"] == len(expected_ids)
