const ALLOWED_TAGS = new Set(['think', 'serp', 'thinking', 'phase', 'title', 'final'])
const TAG_RE = /<\s*\/?\s*([a-zA-Z]+)(?:\s+[^>]*)?>/g
const PHASE_OPEN_RE = /<phase\s+id="(\d+)">/g
const PHASE_BLOCK_RE = /(<phase\s+id="(\d+)">)([\s\S]*?)(<\/phase>)/g
const SERP_QUERIES_BLOCK_RE =
  /<!--\s*<serp_queries>\s*\n(?<json>\[.*?\])\s*\n<\/serp_queries>\s*-->\s*$/s

function _extractBlock(text, openTag, closeTag) {
  const start = text.indexOf(openTag)
  const end = text.lastIndexOf(closeTag)
  if (start < 0 || end < 0) return { content: null, err: 'missing_block' }
  const contentStart = start + openTag.length
  if (end < contentStart) return { content: null, err: 'invalid_block_order' }
  return { content: text.slice(contentStart, end), err: null }
}

export function validateThinkingMLV45(reply) {
  const text = String(reply || '').trim()
  if (!text) return { ok: false, reason: 'empty_reply' }
  if (text === '<<ParsingError>>') return { ok: false, reason: 'parsing_error_marker' }

  if ((text.match(/<thinking>/g) || []).length !== 1 || (text.match(/<\/thinking>/g) || []).length !== 1) {
    return { ok: false, reason: 'invalid_thinking_block_count' }
  }
  if ((text.match(/<final>/g) || []).length !== 1 || (text.match(/<\/final>/g) || []).length !== 1) {
    return { ok: false, reason: 'invalid_final_block_count' }
  }
  if ((text.match(/<serp>/g) || []).length > 1 || (text.match(/<\/serp>/g) || []).length > 1) {
    return { ok: false, reason: 'invalid_serp_block_count' }
  }
  if ((text.match(/<think>/g) || []).length > 1 || (text.match(/<\/think>/g) || []).length > 1) {
    return { ok: false, reason: 'invalid_think_block_count' }
  }

  const thinkingOpen = text.indexOf('<thinking>')
  const thinkingClose = text.indexOf('</thinking>')
  const finalOpen = text.indexOf('<final>')
  const finalClose = text.indexOf('</final>')
  if (thinkingOpen < 0 || thinkingClose < 0 || finalOpen < 0 || finalClose < 0) {
    return { ok: false, reason: 'missing_required_blocks' }
  }
  if (thinkingOpen > thinkingClose) return { ok: false, reason: 'invalid_thinking_order' }
  if (finalOpen > finalClose) return { ok: false, reason: 'invalid_final_order' }

  if (text.includes('<serp>')) {
    const serpOpen = text.indexOf('<serp>')
    if (serpOpen > thinkingOpen) return { ok: false, reason: 'invalid_sequence_serp_thinking' }
  }

  if (thinkingClose + '</thinking>'.length > finalOpen) return { ok: false, reason: 'invalid_sequence_thinking_final' }
  const between = text.slice(thinkingClose + '</thinking>'.length, finalOpen)
  if (between.trim()) return { ok: false, reason: 'final_not_immediately_after_thinking' }

  // 允许标签白名单（大小写敏感）；与后端/脚本保持一致：仅检查 tagName 为纯字母的标签
  TAG_RE.lastIndex = 0
  for (;;) {
    const m = TAG_RE.exec(text)
    if (!m) break
    const tagName = String(m[1] || '').trim()
    if (tagName && !ALLOWED_TAGS.has(tagName)) return { ok: false, reason: `unexpected_tag:${tagName}` }
  }

  const thinkingBlock = _extractBlock(text, '<thinking>', '</thinking>')
  if (thinkingBlock.err || thinkingBlock.content == null) return { ok: false, reason: 'missing_thinking_content' }
  const thinkingContent = thinkingBlock.content

  const phaseIds = []
  PHASE_OPEN_RE.lastIndex = 0
  for (;;) {
    const m = PHASE_OPEN_RE.exec(thinkingContent)
    if (!m) break
    phaseIds.push(Number(m[1]))
  }
  if (!phaseIds.length) return { ok: false, reason: 'missing_phase' }
  if (phaseIds[0] !== 1) return { ok: false, reason: 'phase_id_not_start_from_1' }
  for (let idx = 1; idx < phaseIds.length; idx += 1) {
    if (phaseIds[idx] !== phaseIds[idx - 1] + 1) return { ok: false, reason: 'phase_id_not_strict_increment' }
  }

  const phaseBlocks = []
  PHASE_BLOCK_RE.lastIndex = 0
  for (;;) {
    const m = PHASE_BLOCK_RE.exec(thinkingContent)
    if (!m) break
    phaseBlocks.push(m)
  }
  if (phaseBlocks.length !== phaseIds.length) return { ok: false, reason: 'phase_block_mismatch' }
  for (const m of phaseBlocks) {
    const body = String(m[3] || '')
    if ((body.match(/<title>/g) || []).length !== 1 || (body.match(/<\/title>/g) || []).length !== 1) {
      return { ok: false, reason: 'invalid_title_count_in_phase' }
    }
  }

  const finalBlock = _extractBlock(text, '<final>', '</final>')
  if (finalBlock.err || finalBlock.content == null) return { ok: false, reason: 'missing_final_content' }
  const finalStripped = String(finalBlock.content).trim()
  const match = SERP_QUERIES_BLOCK_RE.exec(finalStripped)
  if (!match) return { ok: false, reason: 'missing_or_invalid_serp_queries_block' }

  const jsonText = String(match.groups?.json || '').trim()
  let queries
  try {
    queries = JSON.parse(jsonText)
  } catch {
    return { ok: false, reason: 'serp_queries_json_parse_error' }
  }
  if (!Array.isArray(queries)) return { ok: false, reason: 'serp_queries_not_array' }
  if (queries.length > 5) return { ok: false, reason: 'serp_queries_too_many' }
  if (new Set(queries.map((q) => String(q))).size !== queries.length) return { ok: false, reason: 'serp_queries_not_deduped' }
  for (const q of queries) {
    if (typeof q !== 'string') return { ok: false, reason: 'serp_queries_item_not_string' }
    if (q.length > 80) return { ok: false, reason: 'serp_queries_item_too_long' }
  }

  return { ok: true, reason: 'ok' }
}

