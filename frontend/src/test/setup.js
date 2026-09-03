import '@testing-library/jest-dom/vitest'

// jsdom implements neither of these, and components under test call both.
window.matchMedia ??= (query) => ({
  matches: false,
  media: query,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
})

if (!URL.createObjectURL) {
  URL.createObjectURL = () => 'blob:mock'
  URL.revokeObjectURL = () => {}
}
