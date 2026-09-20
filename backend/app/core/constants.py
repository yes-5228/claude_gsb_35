"""业务枚举与规则常量。"""

from enum import StrEnum


class RestroomStatus(StrEnum):
    NORMAL = "正常开放"
    MAINTENANCE = "维修中"
    CLOSED = "暂停使用"


class RestroomGrade(StrEnum):
    FIRST = "一类"
    SECOND = "二类"
    THIRD = "三类"


class Shift(StrEnum):
    MORNING = "早班"
    MIDDLE = "中班"
    NIGHT = "晚班"


class InspectionResult(StrEnum):
    NORMAL = "正常"
    ABNORMAL = "发现问题"


class IssueCategory(StrEnum):
    CLEANING = "保洁不到位"
    FACILITY = "设施损坏"
    ODOR = "异味扰民"
    CONSUMABLE = "耗材缺失"
    SAFETY = "安全隐患"
    OTHER = "其他"


class IssueSeverity(StrEnum):
    NORMAL = "一般"
    SERIOUS = "严重"
    URGENT = "紧急"


class IssueStatus(StrEnum):
    PENDING = "待整改"
    PROCESSING = "整改中"
    REVIEWING = "待验收"
    DONE = "已完成"
    CLOSED = "已关闭"


# 整改流转规则：当前状态 -> 允许流转到的状态
ISSUE_TRANSITIONS: dict[str, list[str]] = {
    IssueStatus.PENDING: [IssueStatus.PROCESSING, IssueStatus.CLOSED],
    IssueStatus.PROCESSING: [IssueStatus.REVIEWING, IssueStatus.CLOSED],
    IssueStatus.REVIEWING: [IssueStatus.DONE, IssueStatus.PROCESSING],
    IssueStatus.DONE: [IssueStatus.CLOSED],
    IssueStatus.CLOSED: [],
}

# 状态流转对应的动作名称，用于生成整改流水
TRANSITION_ACTIONS: dict[tuple[str, str], str] = {
    (IssueStatus.PENDING, IssueStatus.PROCESSING): "开始整改",
    (IssueStatus.PENDING, IssueStatus.CLOSED): "作废关闭",
    (IssueStatus.PROCESSING, IssueStatus.REVIEWING): "提交验收",
    (IssueStatus.PROCESSING, IssueStatus.CLOSED): "终止关闭",
    (IssueStatus.REVIEWING, IssueStatus.DONE): "验收通过",
    (IssueStatus.REVIEWING, IssueStatus.PROCESSING): "验收驳回",
    (IssueStatus.DONE, IssueStatus.CLOSED): "归档关闭",
}

# 巡查检查项目录（每项满分与不合格阈值见 services/rules.py，评分规则单一来源）
INSPECTION_CHECK_ITEMS: list[str] = [
    "地面与台阶清洁",
    "便池蹲位清洁",
    "洗手台与镜面",
    "通风除臭",
    "耗材补充",
    "垃圾清运",
    "工具与标识摆放",
    "墙面门窗卫生",
]

# 仍处于整改闭环中的状态，用于统计未整改问题
OPEN_ISSUE_STATUSES: list[str] = [
    IssueStatus.PENDING,
    IssueStatus.PROCESSING,
    IssueStatus.REVIEWING,
]
