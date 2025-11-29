/**
 * Language support configuration for voice agents by pricing tier.
 *
 * Each tier uses different STT providers with varying language support:
 * - Budget: Deepgram Nova-2 (~36 languages)
 * - Balanced: Google Cloud STT (125+ languages)
 * - Premium: OpenAI Whisper via Realtime API (57 languages with good WER)
 */

export interface Language {
  code: string; // BCP-47 code (e.g., "en-US")
  name: string; // Display name
  whisperCode?: string; // ISO 639-1 code for Whisper (e.g., "en")
}

// Languages supported by ALL tiers (Deepgram Nova-2 + Google + OpenAI Whisper)
// This is the intersection of all three providers
const COMMON_LANGUAGES: Language[] = [
  { code: "en-US", name: "English (US)", whisperCode: "en" },
  { code: "en-GB", name: "English (UK)", whisperCode: "en" },
  { code: "en-AU", name: "English (Australia)", whisperCode: "en" },
  { code: "es-ES", name: "Spanish (Spain)", whisperCode: "es" },
  { code: "es-MX", name: "Spanish (Mexico)", whisperCode: "es" },
  { code: "fr-FR", name: "French", whisperCode: "fr" },
  { code: "fr-CA", name: "French (Canada)", whisperCode: "fr" },
  { code: "de-DE", name: "German", whisperCode: "de" },
  { code: "it-IT", name: "Italian", whisperCode: "it" },
  { code: "pt-BR", name: "Portuguese (Brazil)", whisperCode: "pt" },
  { code: "pt-PT", name: "Portuguese (Portugal)", whisperCode: "pt" },
  { code: "nl-NL", name: "Dutch", whisperCode: "nl" },
  { code: "pl-PL", name: "Polish", whisperCode: "pl" },
  { code: "ru-RU", name: "Russian", whisperCode: "ru" },
  { code: "ja-JP", name: "Japanese", whisperCode: "ja" },
  { code: "ko-KR", name: "Korean", whisperCode: "ko" },
  { code: "zh-CN", name: "Chinese (Simplified)", whisperCode: "zh" },
  { code: "zh-TW", name: "Chinese (Traditional)", whisperCode: "zh" },
  { code: "hi-IN", name: "Hindi", whisperCode: "hi" },
  { code: "tr-TR", name: "Turkish", whisperCode: "tr" },
  { code: "vi-VN", name: "Vietnamese", whisperCode: "vi" },
  { code: "th-TH", name: "Thai", whisperCode: "th" },
  { code: "id-ID", name: "Indonesian", whisperCode: "id" },
  { code: "sv-SE", name: "Swedish", whisperCode: "sv" },
  { code: "da-DK", name: "Danish", whisperCode: "da" },
  { code: "no-NO", name: "Norwegian", whisperCode: "no" },
  { code: "fi-FI", name: "Finnish", whisperCode: "fi" },
  { code: "cs-CZ", name: "Czech", whisperCode: "cs" },
  { code: "el-GR", name: "Greek", whisperCode: "el" },
  { code: "hu-HU", name: "Hungarian", whisperCode: "hu" },
  { code: "ro-RO", name: "Romanian", whisperCode: "ro" },
  { code: "uk-UA", name: "Ukrainian", whisperCode: "uk" },
  { code: "bg-BG", name: "Bulgarian", whisperCode: "bg" },
  { code: "sk-SK", name: "Slovak", whisperCode: "sk" },
  { code: "ms-MY", name: "Malay", whisperCode: "ms" },
];

// Additional languages supported by OpenAI Whisper (Premium tier)
// These have good Word Error Rate (WER) in GPT Realtime
const PREMIUM_ADDITIONAL_LANGUAGES: Language[] = [
  { code: "ar-SA", name: "Arabic", whisperCode: "ar" },
  { code: "he-IL", name: "Hebrew", whisperCode: "he" },
  { code: "fa-IR", name: "Persian (Farsi)", whisperCode: "fa" },
  { code: "ur-PK", name: "Urdu", whisperCode: "ur" },
  { code: "bn-BD", name: "Bengali", whisperCode: "bn" },
  { code: "ta-IN", name: "Tamil", whisperCode: "ta" },
  { code: "te-IN", name: "Telugu", whisperCode: "te" },
  { code: "mr-IN", name: "Marathi", whisperCode: "mr" },
  { code: "gu-IN", name: "Gujarati", whisperCode: "gu" },
  { code: "kn-IN", name: "Kannada", whisperCode: "kn" },
  { code: "ml-IN", name: "Malayalam", whisperCode: "ml" },
  { code: "ne-NP", name: "Nepali", whisperCode: "ne" },
  { code: "si-LK", name: "Sinhala", whisperCode: "si" },
  { code: "tl-PH", name: "Tagalog", whisperCode: "tl" },
  { code: "sw-KE", name: "Swahili", whisperCode: "sw" },
  { code: "af-ZA", name: "Afrikaans", whisperCode: "af" },
  { code: "hr-HR", name: "Croatian", whisperCode: "hr" },
  { code: "sr-RS", name: "Serbian", whisperCode: "sr" },
  { code: "sl-SI", name: "Slovenian", whisperCode: "sl" },
  { code: "lt-LT", name: "Lithuanian", whisperCode: "lt" },
  { code: "lv-LV", name: "Latvian", whisperCode: "lv" },
  { code: "et-EE", name: "Estonian", whisperCode: "et" },
  { code: "is-IS", name: "Icelandic", whisperCode: "is" },
  { code: "mk-MK", name: "Macedonian", whisperCode: "mk" },
  { code: "bs-BA", name: "Bosnian", whisperCode: "bs" },
  { code: "sq-AL", name: "Albanian", whisperCode: "sq" },
  { code: "az-AZ", name: "Azerbaijani", whisperCode: "az" },
  { code: "kk-KZ", name: "Kazakh", whisperCode: "kk" },
  { code: "hy-AM", name: "Armenian", whisperCode: "hy" },
  { code: "ka-GE", name: "Georgian", whisperCode: "ka" },
  { code: "be-BY", name: "Belarusian", whisperCode: "be" },
  { code: "gl-ES", name: "Galician", whisperCode: "gl" },
  { code: "ca-ES", name: "Catalan", whisperCode: "ca" },
  { code: "eu-ES", name: "Basque", whisperCode: "eu" },
  { code: "cy-GB", name: "Welsh", whisperCode: "cy" },
  { code: "mt-MT", name: "Maltese", whisperCode: "mt" },
  { code: "mi-NZ", name: "Maori", whisperCode: "mi" },
];

// Additional languages supported by Google (Balanced tier) but NOT by Deepgram
// These work for Balanced and Premium but not Budget
const BALANCED_ADDITIONAL_LANGUAGES: Language[] = [
  { code: "ar-SA", name: "Arabic", whisperCode: "ar" },
  { code: "he-IL", name: "Hebrew", whisperCode: "he" },
  { code: "fa-IR", name: "Persian (Farsi)", whisperCode: "fa" },
  { code: "bn-BD", name: "Bengali", whisperCode: "bn" },
  { code: "ta-IN", name: "Tamil", whisperCode: "ta" },
  { code: "te-IN", name: "Telugu", whisperCode: "te" },
  { code: "mr-IN", name: "Marathi", whisperCode: "mr" },
  { code: "gu-IN", name: "Gujarati", whisperCode: "gu" },
  { code: "kn-IN", name: "Kannada", whisperCode: "kn" },
  { code: "ml-IN", name: "Malayalam", whisperCode: "ml" },
  { code: "tl-PH", name: "Tagalog", whisperCode: "tl" },
  { code: "sw-KE", name: "Swahili", whisperCode: "sw" },
  { code: "af-ZA", name: "Afrikaans", whisperCode: "af" },
  { code: "hr-HR", name: "Croatian", whisperCode: "hr" },
  { code: "sr-RS", name: "Serbian", whisperCode: "sr" },
  { code: "sl-SI", name: "Slovenian", whisperCode: "sl" },
  { code: "lt-LT", name: "Lithuanian", whisperCode: "lt" },
  { code: "lv-LV", name: "Latvian", whisperCode: "lv" },
  { code: "et-EE", name: "Estonian", whisperCode: "et" },
  { code: "is-IS", name: "Icelandic", whisperCode: "is" },
  { code: "ca-ES", name: "Catalan", whisperCode: "ca" },
];

export type PricingTierType = "budget" | "balanced" | "premium-mini" | "premium";

/**
 * Get languages available for a specific pricing tier.
 */
export function getLanguagesForTier(tier: PricingTierType): Language[] {
  switch (tier) {
    case "budget":
      // Deepgram Nova-2 only
      return [...COMMON_LANGUAGES].sort((a, b) => a.name.localeCompare(b.name));

    case "balanced":
      // Google Cloud STT - common + additional Google languages
      return [...COMMON_LANGUAGES, ...BALANCED_ADDITIONAL_LANGUAGES].sort((a, b) =>
        a.name.localeCompare(b.name)
      );

    case "premium-mini":
    case "premium":
      // OpenAI Whisper - common + all premium languages
      return [...COMMON_LANGUAGES, ...PREMIUM_ADDITIONAL_LANGUAGES].sort((a, b) =>
        a.name.localeCompare(b.name)
      );

    default:
      return COMMON_LANGUAGES;
  }
}

/**
 * Check if a language code is valid for a given tier.
 */
export function isLanguageValidForTier(languageCode: string, tier: PricingTierType): boolean {
  const languages = getLanguagesForTier(tier);
  return languages.some((lang) => lang.code === languageCode);
}

/**
 * Get the Whisper language code (ISO 639-1) from a BCP-47 code.
 * Used for Premium tier transcription config.
 */
export function getWhisperCode(bcp47Code: string): string | undefined {
  const allLanguages = [...COMMON_LANGUAGES, ...PREMIUM_ADDITIONAL_LANGUAGES];
  const language = allLanguages.find((lang) => lang.code === bcp47Code);
  return language?.whisperCode;
}

/**
 * Get a fallback language if the current selection is invalid for the new tier.
 * Returns en-US as the safest default.
 */
export function getFallbackLanguage(currentLanguage: string, newTier: PricingTierType): string {
  if (isLanguageValidForTier(currentLanguage, newTier)) {
    return currentLanguage;
  }
  return "en-US";
}
