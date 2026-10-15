import 'fake-indexeddb/auto'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'https://expense.test/' })
for (const name of ['window', 'document', 'navigator', 'localStorage', 'HTMLElement', 'HTMLInputElement', 'Node', 'Event', 'MouseEvent']) {
  Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name] })
}
Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
globalThis.getComputedStyle = dom.window.getComputedStyle.bind(dom.window)
globalThis.IS_REACT_ACT_ENVIRONMENT = true
// Tests must never contact the deployed API. All IndexedDB storage is in memory.
globalThis.fetch = async () => { throw new Error('Network access is forbidden in tests') }
window.confirm = () => false
