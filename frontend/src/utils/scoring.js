/**
 * 巡查评分计算。规则参数由后端 /meta/dictionaries 下发（见 utils/rules.js），
 * 这里的默认值与后端 app.services.rules 保持一致，仅作为字典未加载时的兜底。
 */
export const DEFAULT_MAX_SCORE = 10;
export const DEFAULT_GRADE_THRESHOLDS = { excellent: 90, good: 80, pass: 70 };
export const DEFAULT_PROBLEM_THRESHOLD = 6;

export function calcScore(items, maxScore = DEFAULT_MAX_SCORE) {
  if (!items?.length) return 0;
  const total = items.reduce((sum, item) => sum + Number(item.score || 0), 0);
  return Math.round((total / (items.length * maxScore)) * 1000) / 10;
}

export function gradeOf(score, thresholds = DEFAULT_GRADE_THRESHOLDS) {
  if (score >= thresholds.excellent) return '优秀';
  if (score >= thresholds.good) return '良好';
  if (score >= thresholds.pass) return '合格';
  return '不合格';
}

export function resultOf(items, score, rules = {}) {
  const problemThreshold = rules.problemThreshold ?? DEFAULT_PROBLEM_THRESHOLD;
  const hasProblem = items.some((item) => Number(item.score) < problemThreshold);
  return hasProblem || gradeOf(score, rules.thresholds) === '不合格' ? '发现问题' : '正常';
}
