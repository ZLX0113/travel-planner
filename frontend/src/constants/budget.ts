/** 预算档位（每人）—— 最低 1000 元，「自定义」允许手动输入 */

export const MIN_BUDGET = 1000

export const CUSTOM_BUDGET = '自定义'

export const BUDGET_OPTIONS = [
  '¥1,000-5,000',
  '¥5,000-8,000',
  '¥8,000-15,000',
  '¥15,000+',
  CUSTOM_BUDGET,
]

/** 默认档位 */
export const DEFAULT_BUDGET = '¥5,000-8,000'

/** 把记忆里的预算数值映射回档位（区间左闭右开，避免出现空档） */
export function budgetToOption(budget: number | null): string | undefined {
  if (!budget) return undefined
  if (budget <= 5000) return BUDGET_OPTIONS[0]
  if (budget <= 8000) return BUDGET_OPTIONS[1]
  if (budget <= 15000) return BUDGET_OPTIONS[2]
  return BUDGET_OPTIONS[3]
}
