// ── Shared constants ─────────────────────────────────────────────────────────
// Centralized emoji maps and lookups used across multiple components.
// Issue #16: Extracted from WhiskeyCard, ChatSidebar, Feed, ScanBottle, Discover, WhiskeyDetail.

export const CATEGORY_EMOJI = {
  bourbon: '🥃',
  scotch: '🏔',
  irish: '☘️',
  japanese: '⛩',
  rye: '🌾',
  canadian: '🍁',
  'single malt': '🏰',
  blended: '🥃',
  'world whisky': '🌍',
  'bottled in bond': '🏛️',
  'grain whiskey': '🌾',
  'blended malt': '🥃',
  wheat: '🌿',
  'tennessee': '🎸',
  'corn whiskey': '🌽',
}

export function getCategoryEmoji(category) {
  return CATEGORY_EMOJI[(category || '').toLowerCase()] ?? '🥃'
}

// Issue #17: Centralized food pairing emoji lookup (was a fragile if/else chain in WhiskeyDetail)
const FOOD_EMOJI_MAP = {
  steak: '🥩', beef: '🥩', wagyu: '🥩', brisket: '🥩',
  salmon: '🐟', sashimi: '🐟', fish: '🐟',
  oyster: '🦪',
  lamb: '🍖',
  pastrami: '🥓', charcuterie: '🥓', 'cured meat': '🥓',
  chocolate: '🍫',
  cheese: '🧀', cheddar: '🧀', gouda: '🧀', 'gruyère': '🧀', 'blue cheese': '🧀',
  pie: '🥧', tart: '🥧', crumble: '🥧', baklava: '🥧', gingerbread: '🥧', mochi: '🥧',
  bread: '🍞', poutine: '🍞',
  nut: '🥜', pecan: '🥜', almond: '🥜',
  fruit: '🍎', apple: '🍎', berry: '🍎', citrus: '🍎',
  miso: '🍜', soup: '🍜',
  pepper: '🌶️', szechuan: '🌶️', spic: '🌶️',
  maple: '🍁',
  honey: '🍯',
  caramel: '🍮',
  bbq: '🔥', smoked: '🔥',
  popcorn: '🍿',
  sushi: '🍣',
  lobster: '🦞', crab: '🦀', shrimp: '🦐',
  pork: '🐷',
  chicken: '🍗', turkey: '🦃',
  mushroom: '🍄',
  olive: '🫒',
}

export function foodEmoji(item) {
  const l = (item || '').toLowerCase()
  for (const [keyword, emoji] of Object.entries(FOOD_EMOJI_MAP)) {
    if (l.includes(keyword)) return emoji
  }
  return '🍽️'
}

// Whiskey category options — single source of truth for Browse, Feed, etc.
export const WHISKEY_CATEGORIES = [
  { value: 'bourbon',      label: 'Bourbon' },
  { value: 'scotch',       label: 'Scotch' },
  { value: 'irish',        label: 'Irish' },
  { value: 'japanese',     label: 'Japanese' },
  { value: 'rye',          label: 'Rye' },
  { value: 'canadian',     label: 'Canadian' },
  { value: 'single malt',  label: 'Single Malt' },
  { value: 'blended',      label: 'Blended' },
]

// Max file size for uploads (10MB)
export const MAX_UPLOAD_SIZE = 10 * 1024 * 1024
export const MAX_UPLOAD_SIZE_LABEL = '10MB'
