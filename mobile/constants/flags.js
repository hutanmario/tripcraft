// Maps country names (as returned by the backend) to their flag emoji.
// Covers all countries currently seeded in TripCraft.
const FLAG_MAP = {
  // A
  Albania: '🇦🇱', Andorra: '🇦🇩', Austria: '🇦🇹',
  // B
  Belarus: '🇧🇾', Belgium: '🇧🇪', 'Bosnia and Herzegovina': '🇧🇦', Bulgaria: '🇧🇬',
  // C
  Croatia: '🇭🇷', Cyprus: '🇨🇾', 'Czech Republic': '🇨🇿', Czechia: '🇨🇿',
  // D
  Denmark: '🇩🇰',
  // E
  Estonia: '🇪🇪',
  // F
  Finland: '🇫🇮', France: '🇫🇷',
  // G
  Germany: '🇩🇪', Greece: '🇬🇷',
  // H
  Hungary: '🇭🇺',
  // I
  Iceland: '🇮🇸', Ireland: '🇮🇪', Italy: '🇮🇹',
  // K
  Kosovo: '🇽🇰',
  // L
  Latvia: '🇱🇻', Liechtenstein: '🇱🇮', Lithuania: '🇱🇹', Luxembourg: '🇱🇺',
  // M
  Malta: '🇲🇹', Moldova: '🇲🇩', Monaco: '🇲🇨', Montenegro: '🇲🇪',
  // N
  Netherlands: '🇳🇱', 'North Macedonia': '🇲🇰', Norway: '🇳🇴',
  // P
  Poland: '🇵🇱', Portugal: '🇵🇹',
  // R
  Romania: '🇷🇴', Russia: '🇷🇺',
  // S
  'San Marino': '🇸🇲', Serbia: '🇷🇸', Slovakia: '🇸🇰', Slovenia: '🇸🇮',
  Spain: '🇪🇸', Sweden: '🇸🇪', Switzerland: '🇨🇭',
  // T
  Turkey: '🇹🇷',
  // U
  Ukraine: '🇺🇦', 'United Kingdom': '🇬🇧',
  // V
  'Vatican City': '🇻🇦',
};

/**
 * Returns the flag emoji for a country name.
 * Falls back to '🌍' if the country is not in the map.
 */
export function countryFlag(name) {
  if (!name) return '🌍';
  return FLAG_MAP[name] ?? '🌍';
}
