/** 偏好标签定义：表单选项（英文值）与后端类别标签（中文）的映射 */

export interface StyleOption {
  value: string
  label: string
  /** 后端景点类别标签：文化 / 美食 / 购物 / 自然 / 娱乐 */
  tag: string
}

export const STYLE_OPTIONS: StyleOption[] = [
  { value: 'photo', label: '📸 网红打卡', tag: '购物' },
  { value: 'history', label: '🏯 历史古迹', tag: '文化' },
  { value: 'food', label: '🌃 夜市美食', tag: '美食' },
  { value: 'nature', label: '🏖️ 自然风光', tag: '自然' },
  { value: 'shopping', label: '🛍️ 购物血拼', tag: '购物' },
  { value: 'theme_park', label: '🎢 主题乐园', tag: '娱乐' },
  { value: 'culture', label: '🎭 文化艺术', tag: '文化' },
  { value: 'relax', label: '🧘 休闲养生', tag: '自然' },
  { value: 'drive', label: '🚗 自驾出行', tag: '自然' },
  { value: 'outdoor', label: '🏕️ 户外探险', tag: '自然' },
]

/** 表单选项值 → 后端标签 */
export function stylesToTags(styles: string[]): string[] {
  const tags = STYLE_OPTIONS.filter((o) => styles.includes(o.value)).map((o) => o.tag)
  return Array.from(new Set(tags))
}
