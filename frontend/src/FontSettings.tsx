import { FONT_SIZE_OPTIONS, type FontSize } from './fontPreferences'

export function FontSettings({ value, onChange }: { value: FontSize, onChange: (value: FontSize) => void }) {
  return <section className="panel">
    <div className="panel-title">字体与显示</div>
    <p className="hint">使用当前设备的系统字体。字号仅保存在这台设备，选择后立即生效。</p>
    <div className="font-size-options" role="group" aria-label="字体大小">
      {FONT_SIZE_OPTIONS.map(option => <button
        key={option.value}
        type="button"
        aria-pressed={value === option.value}
        onClick={() => onChange(option.value)}
      >{option.label}</button>)}
    </div>
    <div className="font-preview">示例：今天支出 ¥26.00</div>
  </section>
}
