/**
 * 业务规则参数入口：后端 /meta/dictionaries 是规则的唯一来源，
 * 这里把字典字段整理成前端计算所需的形状；字典未加载时回退到
 * 与后端 app.services.rules 一致的内置默认值，保证页面立即可用。
 */
import {
  DEFAULT_GRADE_THRESHOLDS,
  DEFAULT_MAX_SCORE,
  DEFAULT_PROBLEM_THRESHOLD,
} from './scoring.js';

export const DEFAULT_OPEN_STATUSES = ['待整改', '整改中', '待验收'];
export const DEFAULT_RECTIFICATION_DAYS = { 一般: 3, 严重: 3, 紧急: 1 };
export const DEFAULT_FALLBACK_RECTIFICATION_DAYS = 3;

/** 巡查评分规则参数：满分、等级线、单项不合格线。 */
export function scoringRules(dictionaries) {
  return {
    maxScore: dictionaries?.inspection_item_max_score ?? DEFAULT_MAX_SCORE,
    thresholds: dictionaries?.inspection_grade_thresholds ?? DEFAULT_GRADE_THRESHOLDS,
    problemThreshold:
      dictionaries?.inspection_item_problem_threshold ?? DEFAULT_PROBLEM_THRESHOLD,
  };
}

/** 未闭环状态列表，与后端 OPEN_ISSUE_STATUSES 同源。 */
export function openStatuses(dictionaries) {
  return dictionaries?.issue_open_statuses ?? DEFAULT_OPEN_STATUSES;
}

/** 是否超期未整改：有期限、状态未闭环、期限已过。与后端 rules.is_overdue 同口径。 */
export function isOverdue(deadline, status, open = DEFAULT_OPEN_STATUSES) {
  if (!deadline) return false;
  if (!open.includes(status)) return false;
  return new Date(deadline).getTime() < Date.now();
}

/** 按严重程度推算默认整改期限，天数映射来自后端字典。 */
export function defaultDeadline(severity, dictionaries, base = new Date()) {
  const daysMap = dictionaries?.issue_rectification_days ?? DEFAULT_RECTIFICATION_DAYS;
  const fallback =
    dictionaries?.issue_default_rectification_days ?? DEFAULT_FALLBACK_RECTIFICATION_DAYS;
  const days = daysMap[severity] ?? fallback;
  return new Date(base.getTime() + days * 24 * 3600 * 1000);
}
