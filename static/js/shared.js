/* ═══════════════════════════════════════════════════
   AGSKY — SHARED JS
   Language switcher, localStorage, common helpers
   ═══════════════════════════════════════════════════ */

// Current language (default English)
window.AGSKY_LANG = localStorage.getItem('agsky_lang') || 'english';

/**
 * Get translated text by key
 * Supports nested keys like "legend.healthy"
 */
function t(key) {
  const lang = window.AGSKY_LANG;
  const translations = window.AGSKY_TRANSLATIONS[lang] || window.AGSKY_TRANSLATIONS.english;

  const parts = key.split('.');
  let value = translations;
  for (const part of parts) {
    if (value && typeof value === 'object') value = value[part];
    else return key;
  }
  return value || key;
}

/**
 * Set language + update UI + save to localStorage
 * Elements with data-i18n="key" will auto-update
 */
function setLanguage(lang) {
  window.AGSKY_LANG = lang;
  localStorage.setItem('agsky_lang', lang);

  // Update all data-i18n elements
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const txt = t(key);
    if (typeof txt === 'string') {
      el.textContent = txt;
    }
  });

  // Update all data-i18n-placeholder elements
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    el.placeholder = t(key);
  });

  // Update active language button
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === lang);
  });

  // Callback if page defines it
  if (typeof window.onLanguageChange === 'function') {
    window.onLanguageChange(lang);
  }
}

/**
 * Initialize language on page load
 */
function initLanguage() {
  // Attach click handlers to language buttons
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => setLanguage(btn.dataset.lang));
  });

  // Apply current language
  setLanguage(window.AGSKY_LANG);
}

/**
 * Get logged-in user (from localStorage)
 */
function getCurrentUser() {
  const data = localStorage.getItem('agsky_user');
  return data ? JSON.parse(data) : null;
}

/**
 * Save user to localStorage
 */
function saveCurrentUser(user) {
  localStorage.setItem('agsky_user', JSON.stringify(user));
}

/**
 * Logout — clear user data
 */
function logout() {
  localStorage.removeItem('agsky_user');
  sessionStorage.clear();
  window.location.href = '/auth';
}

/**
 * Require auth — redirect to /auth if no user
 */
function requireAuth() {
  const user = getCurrentUser();
  if (!user) {
    window.location.href = '/auth';
    return null;
  }
  return user;
}

/**
 * API fetch helper
 */
async function api(endpoint, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json' }
  };
  const config = { ...defaults, ...options };
  if (config.body && typeof config.body !== 'string') {
    config.body = JSON.stringify(config.body);
  }

  try {
    const res = await fetch(endpoint, config);
    const data = await res.json();
    return data;
  } catch (err) {
    return { error: err.message };
  }
}

/**
 * Get crops filtered by land type
 */
function getCropsForLandType(landType) {
  if (!landType) return window.AGSKY_CROPS;
  return window.AGSKY_CROPS.filter(c => c.land.includes(landType));
}

/**
 * Get crop display name in current language
 */
function getCropName(cropId) {
  const crop = window.AGSKY_CROPS.find(c => c.id === cropId);
  if (!crop) return cropId;
  return window.AGSKY_LANG === 'tamil' ? crop.name_ta : crop.name_en;
}

/**
 * Auto-initialize on DOM ready
 */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLanguage);
} else {
  initLanguage();
}