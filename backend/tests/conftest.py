"""测试夹具：使用独立的 SQLite 文件，避免污染开发数据。"""

import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR / "data" / "test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["CORS_ORIGINS"] = "*"

if TEST_DB.exists():
    TEST_DB.unlink()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Issue  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_issue(db_session, restroom):
    """直接走 ORM 构造问题，供规则单测控制 deadline/status。"""
    from app.services import rules

    created: list[Issue] = []

    def _make(*, status="待整改", deadline=None, code=None, severity="一般"):
        issue = Issue(
            code=code or rules.next_issue_code(db_session),
            restroom_id=restroom["id"],
            title=f"规则测试问题 {len(created) + 1}",
            description="",
            category="其他",
            severity=severity,
            status=status,
            reporter="测试员",
            assignee="",
            report_time=datetime.now(),
            deadline=deadline,
        )
        db_session.add(issue)
        db_session.commit()
        db_session.refresh(issue)
        created.append(issue)
        return issue

    return _make


@pytest.fixture
def restroom(client) -> dict:
    response = client.post(
        "/api/v1/restrooms",
        json={
            "name": "测试公厕",
            "district": "测试区",
            "address": "测试路 1 号",
            "grade": "二类",
            "status": "正常开放",
            "manager": "测试员",
            "stall_count": 6,
            "basin_count": 3,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def full_items(score: float = 9.0) -> list[dict]:
    from app.core.constants import INSPECTION_CHECK_ITEMS

    return [{"name": name, "score": score} for name in INSPECTION_CHECK_ITEMS]
