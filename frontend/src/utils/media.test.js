import { describe, it, expect } from 'vitest'
import { mediaUrl } from './media.js'

describe('mediaUrl', () => {
  it('returns null for null input', () => {
    expect(mediaUrl(null)).toBeNull()
  })

  it('returns null for undefined input', () => {
    expect(mediaUrl(undefined)).toBeNull()
  })

  it('returns null for empty string', () => {
    expect(mediaUrl('')).toBeNull()
  })

  it('passes through HTTPS URLs unchanged', () => {
    const url = 'https://cdn.sipsense.ai/uploads/bottle.png'
    expect(mediaUrl(url)).toBe(url)
  })

  it('passes through HTTP URLs unchanged', () => {
    const url = 'http://localhost:8000/uploads/bottle.png'
    expect(mediaUrl(url)).toBe(url)
  })

  it('prepends /api to relative paths', () => {
    expect(mediaUrl('/uploads/bottles/trace.png')).toBe('/api/uploads/bottles/trace.png')
  })

  it('prepends /api to relative video paths', () => {
    expect(mediaUrl('/uploads/videos/abc123.mp4')).toBe('/api/uploads/videos/abc123.mp4')
  })
})
