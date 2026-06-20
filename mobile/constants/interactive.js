import apiClient from '../services/api';
import { COLORS } from './theme';

export const MAX_DAY_HOURS = 8;

export const C = {
  primary: COLORS.primary,
  primaryDark: COLORS.primaryDark,
  navy: COLORS.navy,
  bg: '#F8F9FA',
  ink: COLORS.ink,
  sub: COLORS.sub,
  tagBg: COLORS.tagBg,
  border: COLORS.borderSoft,
  shadow: {
    shadowColor: COLORS.navy,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 20,
    elevation: 4,
  },
};

export function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function formatTag(slug) {
  return String(slug || '').replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function primaryExplanation(item) {
  return item?.group_explanation?.summary || item?.explanations?.[0] || '';
}

export function groupFitLabel(item) {
  const group = item?.group_explanation;
  if (!group?.total_members) return null;
  return `${group.fit_count}/${group.total_members} group fit`;
}

export function memberReasonText(member) {
  if (!member) return '';
  const reasons = (member.reasons || []).slice(0, 2).join(', ');
  return reasons ? `${member.name}: ${reasons}` : `${member.name}: ${member.fit || 'match'}`;
}

function clamp01(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  if (n > 1) return Math.max(0, Math.min(n / 100, 1));
  return Math.max(0, Math.min(n, 1));
}

export function rawScore(itemOrScore) {
  if (typeof itemOrScore === 'number') return clamp01(itemOrScore);
  return clamp01(itemOrScore?.raw_score ?? itemOrScore?.score ?? 0);
}

function clampPct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(Math.round(n), 100));
}

export function scorePct(itemOrScore) {
  if (typeof itemOrScore !== 'number' && itemOrScore?.display_score_pct != null) {
    return clampPct(itemOrScore.display_score_pct);
  }
  return Math.round(rawScore(itemOrScore) * 100);
}

export function scoreBand(itemOrScore) {
  const pct = scorePct(itemOrScore);
  if (pct >= 55) return 'Strong match';
  if (pct >= 35) return 'Good match';
  if (pct >= 20) return 'Exploratory fit';
  if (pct > 0) return 'Light signal';
  return 'No signal';
}

export function scoreText(itemOrScore) {
  const pct = scorePct(itemOrScore);
  return `${scoreBand(itemOrScore)} - ${pct}/100 fit`;
}

function markerScores(data) {
  const raw = data.map((item) => rawScore(item.score));
  const min = Math.min(...raw);
  const max = Math.max(...raw);
  return raw.map((score) => {
    if (max === min) return 80;
    return Math.round(62 + ((score - min) / (max - min)) * 34);
  });
}

function inflatedDisplayScores(data, minDisplay = 70, maxDisplay = 96) {
  const decorated = decorateScores(data);
  if (decorated.length === 0) return decorated;

  const rawValues = decorated.map((item) => rawScore(item));
  const min = Math.min(...rawValues);
  const max = Math.max(...rawValues);

  return decorated.map((item, index) => {
    const raw = rawValues[index];
    const display = max === min
      ? Math.round((minDisplay + maxDisplay) / 2)
      : Math.round(minDisplay + ((raw - min) / (max - min)) * (maxDisplay - minDisplay));
    const withDisplay = { ...item, display_score_pct: display };
    return {
      ...withDisplay,
      match_label: scoreBand(withDisplay),
      score_label: scoreText(withDisplay),
    };
  });
}
function decorateScores(data) {
  if (!Array.isArray(data) || data.length === 0) return [];
  const visualScores = markerScores(data);
  return data.map((item, index) => {
    const raw = rawScore(item.score);
    return {
      ...item,
      raw_score: raw,
      score_pct: Math.round(raw * 100),
      marker_score: visualScores[index],
      match_label: scoreBand(raw),
      score_label: scoreText(raw),
    };
  });
}

export async function fetchCities(country, sessionId, countryId = null, groupTripId = null) {
  const params = { country, session_id: sessionId };
  if (countryId) params.country_id = countryId;
  if (groupTripId) params.group_trip_id = groupTripId;

  const { data } = await apiClient.get('/fim/cities', { params });
  return decorateScores(data).map((city, index) => ({
    ...city,
    id: city.id ?? index + 1,
    name: city.city,
  }));
}

export async function fetchAttractions(cityId, sessionId, groupTripId = null) {
  const params = { session_id: sessionId };
  if (groupTripId) params.group_trip_id = groupTripId;

  const { data } = await apiClient.get(`/fim/cities/${cityId}/attractions`, { params });
  return inflatedDisplayScores(data).map((attraction) => ({
    ...attraction,
    meta: attraction.avg_duration_hours ? `~${attraction.avg_duration_hours}h` : null,
  }));
}

export async function fetchSuggested(cityId, sessionId, excludeIds = [], context = {}) {
  const params = new URLSearchParams({ session_id: sessionId });
  excludeIds.forEach((id) => params.append('exclude_ids', String(id)));
  (context.currentDayIds || []).forEach((id) => params.append('current_day_ids', String(id)));
  if (context.lastAttractionId) params.append('last_attraction_id', String(context.lastAttractionId));
  if (context.groupTripId) params.append('group_trip_id', String(context.groupTripId));

  const { data } = await apiClient.get(`/fim/cities/${cityId}/suggested`, { params });
  return inflatedDisplayScores(data).map((attraction) => ({
    ...attraction,
    meta: attraction.avg_duration_hours ? `~${attraction.avg_duration_hours}h` : null,
  }));
}

export async function fetchNextCity(country, sessionId, context = {}) {
  const params = new URLSearchParams({ country, session_id: sessionId });
  if (context.countryId) params.append('country_id', String(context.countryId));
  if (context.groupTripId) params.append('group_trip_id', String(context.groupTripId));
  (context.visitedCityIds || []).forEach((id) => params.append('visited_city_ids', String(id)));
  (context.visitedCityNames || []).forEach((name) => params.append('visited_city_names', String(name)));
  if (context.lastPoint?.lat != null) params.append('last_lat', String(context.lastPoint.lat));
  if (context.lastPoint?.lng != null) params.append('last_lng', String(context.lastPoint.lng));
  if (context.currentDay) params.append('current_day', String(context.currentDay));
  if (context.days) params.append('days', String(context.days));

  const { data } = await apiClient.get('/fim/next-city', { params });
  if (!data) return null;
  return decorateScores([data]).map((city) => ({
    ...city,
    name: city.city,
    explanations: city.next_city_reasons?.length ? city.next_city_reasons : city.explanations,
  }))[0];
}

export async function fetchOSRMDistance(from, to, mode = 'foot') {
  if (!from?.lat || !from?.lng || !to?.lat || !to?.lng) {
    throw new Error('Missing route coordinates');
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const url = `https://router.project-osrm.org/route/v1/${mode}/` +
      `${from.lng},${from.lat};${to.lng},${to.lat}?overview=false`;
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error('Route service unavailable');
    const data = await res.json();
    if (!data.routes?.[0]) throw new Error('No route returned');
    const km = (data.routes[0].distance / 1000).toFixed(1);
    const min = Math.round(data.routes[0].duration / 60);
    return `${km} km - ${min} min walk`;
  } finally {
    clearTimeout(timeout);
  }
}
