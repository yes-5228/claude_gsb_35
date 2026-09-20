import { getCachedDictionaries } from '../hooks/useDictionaries.js';

/**
 * 规则口径单一来源在前端的投影。
 *
 * 阈值、等级、未闭环状态集合与期限天数都不允许在页面里硬编码：
 * 后端 app/services/rules.py 通过 /meta/dictionaries 下发这些常量，
 * 本模块只负责读取与套算，保证录入预览、列表/详情标签与服务端同口径。
 * 字典尚未加载完成时使用与后端一致的内置兜底值，仅用于首帧渲染。
 */
export const FALLBACK = {
  maxScore: 10,
  problemThreshold: 6,
  gradeThresholds: [
    { min_score: 90, grade: '优秀' },
    { min_score: 80, grade: '良好' },
    { min_score: 70, grade: '合格' },
  ],
  gradeFail: '不合格',
  openStatus: ['待整改', '整改中', '待验收'],
  deadlineDays: { 紧急: 1, 严重: 3, 一般: 3 },
  deadlineDaysDefault: 3,
};

export function rulesConfig() {
  const dict = getCachedDictionaries();
  if (!dict) return FALLBACK;
  return {
    maxScore: dict.inspection_item_max_score ?? FALLBACK.maxScore,
    problemThreshold:
      dict.inspection_item_problem_threshold ?? FALLBACK.problemThreshold,
    gradeThresholds: dict.grade_thresholds?.length
      ? dict.grade_thresholds
      : FALLBACK.gradeThresholds,
    gradeFail: dict.grade_fail || FALLBACK.gradeFail,
    openStatus: dict.issue_open_status?.length ? dict.issue_open_status : FALLBACK.openStatus,
    deadlineDays: Object.keys(dict.issue_deadline_days || {}).length
      ? dict.issue_deadline_days
      : FALLBACK.deadlineDays,
    deadlineDaysDefault: dict.issue_deadline_days_default ?? FALLBACK.deadlineDaysDefault,
  };
}

export function calcScore(items, config = rulesConfig()) {
  if (!items?.length) return 0;
  const maxScore = config.maxScore;
  const total = items.reduce((sum, item) => sum + Number(item.score || 0), 0);
  return Math.round((total / (items.length * maxScore)) * 1000) / 10;
}

export function gradeOf(score, config = rulesConfig()) {
  for (const { min_score, grade } of config.gradeThresholds) {
    if (score >= min_score) return grade;
  }
  return config.gradeFail;
}

export function isProblemItem(item, config = rulesConfig()) {
  return Number(item.score) < config.problemThreshold;
}

export function resultOf(items, score, config = rulesConfig()) {
  const hasProblem = items.some((item) => isProblemItem(item, config));
  return hasProblem || gradeOf(score, config) === config.gradeFail ? '发现问题' : '正常';
}

/** 某严重程度对应的整改期限天数。 */
export function deadlineDaysFor(severity, config = rulesConfig()) {
  return config.deadlineDays[severity] ?? config.deadlineDaysDefault;
}

/** 依据上报时间与严重程度推算默认期限，与后端 rules.derive_deadline 同口径。 */
export function deriveDeadline(reportTime, severity, config = rulesConfig()) {
  const base = reportTime ? new Date(reportTime) : new Date();
  base.setDate(base.getDate() + deadlineDaysFor(severity, config));
  return base;
}

/** 超期：设有期限、期限早于当前时间且状态仍处于未闭环。 */
export function isOverdue(deadline, status, config = rulesConfig()) {
  if (!deadline) return false;
  if (!config.openStatus.includes(status)) return false;
  return new Date(deadline).getTime() < Date.now();
}
