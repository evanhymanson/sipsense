/**
 * Convert an image/video URL to the correct src.
 * Full CDN URLs (https://...) pass through; relative paths get the /api prefix.
 */
export function mediaUrl(url) {
  if (!url) return null
  return url.startsWith('http') ? url : `/api${url}`
}
