/**
 * Gap 15: Frontend i18n hook.
 *
 * Provides a t() function for looking up translated strings.
 * Currently English-only; additional locales can be added by importing
 * more JSON files and selecting based on a locale context/state.
 */

import en from './en.json'

const TRANSLATIONS = { en }
const DEFAULT_LOCALE = 'en'

/**
 * Simple translation hook.
 *
 * Usage:
 *   const { t } = useTranslation()
 *   <button>{t('auth.login')}</button>
 *   <span>{t('rating.stars', { count: 5 })}</span>
 */
export function useTranslation(locale = DEFAULT_LOCALE) {
  const strings = TRANSLATIONS[locale] || TRANSLATIONS[DEFAULT_LOCALE]

  function t(key, params) {
    let value = strings[key] || key
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        value = value.replace(`{${k}}`, v)
      })
    }
    return value
  }

  return { t, locale }
}

export default useTranslation
