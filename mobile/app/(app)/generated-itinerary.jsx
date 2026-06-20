import {
  useEffect,
  useRef,
  useState } from 'react';
import {
  Alert,
  Animated,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View
} from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';

import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useLocalSearchParams, useRouter } from 'expo-router';
import LoadingScreen from '../../components/interactive/LoadingScreen';
import GeneratedMapView from '../../components/itinerary/GeneratedMapView';
import StoryMode from '../../components/itinerary/StoryMode';
import TripSummary from '../../components/interactive/TripSummary';
import { COLORS, FONTS, RADIUS, TYPE } from '../../constants/theme';
import apiClient from '../../services/api';

const ASPECTS = [
  { key: 'matches_style', label: 'Matches my style', positive: true },
  { key: 'good_cities',   label: 'Great city picks', positive: true },
  { key: 'too_many_stops', label: 'Too many stops',  positive: false },
  { key: 'wrong_vibe',    label: 'Wrong vibe',       positive: false },
];

const REGENERATE_OPTIONS = [
  {
    key: 'relaxed_pace',
    title: 'More relaxed',
    subtitle: 'Fewer stops and a calmer rhythm.',
    icon: 'leaf-outline',
    feedback: ['relaxed_pace'],
  },
  {
    key: 'more_nature',
    title: 'More nature',
    subtitle: 'More parks, viewpoints and outdoor stops.',
    icon: 'trail-sign-outline',
    feedback: ['more_nature'],
  },
  {
    key: 'cheaper',
    title: 'Cheaper',
    subtitle: 'Prefer lower-cost attractions and budget fit.',
    icon: 'wallet-outline',
    feedback: ['cheaper'],
  },
];

function RatingModal({ visible, country, planId, onDone }) {
  const [stars, setStars] = useState(0);
  const [aspects, setAspects] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const slideAnim = useRef(new Animated.Value(400)).current;

  useEffect(() => {
    if (visible) {
      setStars(0);
      setAspects([]);
      Animated.spring(slideAnim, {
        toValue: 0, tension: 60, friction: 10, useNativeDriver: true,
      }).start();
    }
  }, [visible]);

  function toggleAspect(key) {
    setAspects(prev =>
      prev.includes(key) ? prev.filter(a => a !== key) : [...prev, key]
    );
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  }

  function handleStar(n) {
    setStars(n);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  }

  async function handleSubmit() {
    if (stars === 0) return;
    setSubmitting(true);
    try {
      await apiClient.post(`/itinerary/plan/${planId}/rate`, {
        rating: stars,
        aspects,
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      onDone(true);
    } catch {
      onDone(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => onDone(false)}>
      <Pressable style={styles.ratingBackdrop} onPress={() => onDone(false)}>
        <Animated.View
          style={[styles.ratingSheet, { transform: [{ translateY: slideAnim }] }]}
          onStartShouldSetResponder={() => true}
        >
          {/* Handle */}
          <View style={styles.ratingHandle} />

          <Text style={styles.ratingTitle}>How does this plan feel?</Text>
          <Text style={styles.ratingCountry}>{country}</Text>

          {/* Stars */}
          <View style={styles.starsRow}>
            {[1, 2, 3, 4, 5].map(n => (
              <TouchableOpacity key={n} onPress={() => handleStar(n)} activeOpacity={0.7}>
                <Text style={[styles.star, n <= stars && styles.starActive]}>★</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Quick picks */}
          <Text style={styles.aspectsLabel}>Quick feedback (optional)</Text>
          <View style={styles.aspectsGrid}>
            {ASPECTS.map(({ key, label, positive }) => {
              const selected = aspects.includes(key);
              return (
                <TouchableOpacity
                  key={key}
                  style={[
                    styles.aspectPill,
                    selected && (positive ? styles.aspectPillPos : styles.aspectPillNeg),
                  ]}
                  onPress={() => toggleAspect(key)}
                  activeOpacity={0.8}
                >
                  <Text style={[
                    styles.aspectText,
                    selected && (positive ? styles.aspectTextPos : styles.aspectTextNeg),
                  ]}>
                    {selected ? (positive ? '✓ ' : '✗ ') : ''}{label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Actions */}
          <View style={styles.ratingActions}>
            <TouchableOpacity
              style={[styles.submitBtn, stars === 0 && styles.submitBtnDisabled]}
              activeOpacity={0.85}
              disabled={stars === 0 || submitting}
              onPress={handleSubmit}
            >
              <Text style={styles.submitBtnText}>
                {submitting ? 'Saving...' : 'Submit rating'}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => onDone(false)} activeOpacity={0.7}>
              <Text style={styles.skipText}>Skip</Text>
            </TouchableOpacity>
          </View>

          {/* Academic note */}
          <Text style={styles.ratingNote}>
            Your rating refines your travel profile for future recommendations.
          </Text>
        </Animated.View>
      </Pressable>
    </Modal>
  );
}

function RegenerateModal({ visible, country, regenerating, onClose, onSelect }) {
  const slideAnim = useRef(new Animated.Value(400)).current;

  useEffect(() => {
    if (visible) {
      Animated.spring(slideAnim, {
        toValue: 0,
        tension: 62,
        friction: 11,
        useNativeDriver: true,
      }).start();
    } else {
      slideAnim.setValue(400);
    }
  }, [visible]);

  function choose(option) {
    if (regenerating) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onSelect(option.feedback);
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.ratingBackdrop} onPress={onClose}>
        <Animated.View
          style={[styles.regenerateSheet, { transform: [{ translateY: slideAnim }] }]}
          onStartShouldSetResponder={() => true}
        >
          <View style={styles.ratingHandle} />

          <View style={styles.regenerateHeaderRow}>
            <View style={styles.regenerateIconBadge}>
              <Ionicons name="sparkles-outline" size={18} color={TEAL} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.regenerateEyebrow}>SMART REBUILD</Text>
              <Text style={styles.regenerateTitle}>Tune this itinerary.</Text>
            </View>
          </View>

          <Text style={styles.regenerateSubtitle}>
            {country || 'This trip'} will be rebuilt as a new version. Your current plan stays untouched.
          </Text>

          <View style={styles.regenerateOptions}>
            {REGENERATE_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.key}
                style={[styles.regenerateOption, regenerating && styles.regenerateOptionDisabled]}
                activeOpacity={0.84}
                disabled={regenerating}
                onPress={() => choose(option)}
              >
                <View style={styles.regenerateOptionIcon}>
                  <Ionicons name={option.icon} size={18} color={TEAL} />
                </View>
                <View style={styles.regenerateOptionTextWrap}>
                  <Text style={styles.regenerateOptionTitle}>{option.title}</Text>
                  <Text style={styles.regenerateOptionSubtitle}>{option.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={17} color="#B0AB9F" />
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.regenerateActions}>
            <TouchableOpacity style={styles.regenerateCancelBtn} activeOpacity={0.75} onPress={onClose}>
              <Text style={styles.regenerateCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </Animated.View>
      </Pressable>
    </Modal>
  );
}

function normalizePlan(data) {
  const countryName = data?.country?.name || data?.country_name || 'Trip';
  const days = (data?.days || []).map((day) => ({
    ...day,
    day_number: day.day_number ?? day.day,
    city: day.city || day.city_name || 'Unknown',
    lat: day.lat,
    lng: day.lng,
    city_score: day.city_score || 82,
    city_tags: day.city_tags || [],
    city_matched_tags: day.city_matched_tags || [],
    city_explanations: day.city_explanations || [],
    city_group_explanation: day.city_group_explanation || null,
    attractions: (day.attractions || []).map((attr) => ({
      ...attr,
      lat: attr.lat,
      lng: attr.lng ?? attr.lon,
      tags: attr.tags || [],
      matched_tags: attr.matched_tags || [],
      explanations: attr.explanations || [],
    })),
  }));
  return {
    ...data,
    country: countryName,
    num_days: data?.num_days || data?.nr_zile || data?.totals?.days || days.length,
    days,
  };
}

function routePointsForPlan(plan) {
  return (plan?.days || [])
    .filter((day) => day.lat && day.lng)
    .map((day) => ({ lat: day.lat, lng: day.lng, label: day.city }));
}

function tripItemsForPlan(plan) {
  return (plan?.days || []).flatMap((day) =>
    (day.attractions || []).map((attr, index) => ({
      uid: `generated-${day.day_number}-${attr.id}-${index}`,
      attraction: attr,
      city: { id: day.city_id, city: day.city, name: day.city, lat: day.lat, lng: day.lng },
      day: day.day_number,
    }))
  );
}

export default function GeneratedItinerary() {
  const { plan_id, group_trip_id } = useLocalSearchParams();
  const router = useRouter();
  const [currentPlanId, setCurrentPlanId] = useState(plan_id);
  const [plan, setPlan] = useState(null);
  const [step, setStep] = useState('LOADING');
  const [activeDay, setActiveDay] = useState(1);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showRating, setShowRating] = useState(false);
  const [showRegenerate, setShowRegenerate] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const transitionAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    setCurrentPlanId(plan_id);
  }, [plan_id]);

  useEffect(() => {
    transitionAnim.setValue(0);
    Animated.timing(transitionAnim, {
      toValue: 1,
      duration: 220,
      useNativeDriver: true,
    }).start();
  }, [step]);

  async function loadPlan(id, nextStep = 'MAP') {
    if (!id) { setError('Could not load itinerary.'); setStep('ERROR'); return; }
    setStep('LOADING');
    setError('');
    return apiClient.get(`/itinerary/plan/${id}/experience`)
      .then(({ data }) => {
        const nextPlan = normalizePlan(data);
        setPlan(nextPlan);
        setActiveDay(nextPlan.days[0]?.day_number || 1);
        setStep(nextStep);
      })
      .catch((e) => {
        setError(e.response?.data?.detail || 'Could not load itinerary.');
        setStep('ERROR');
      });
  }

  useEffect(() => {
    loadPlan(currentPlanId);
  }, [currentPlanId]);

  async function handleSave() {
    if (!currentPlanId || saving || saved) return;
    setSaving(true);
    try {
      await apiClient.post(`/itinerary/plan/${currentPlanId}/save`, {
        group_trip_id: group_trip_id || plan?.group?.trip_id || null,
      });
      setSaved(true);
      // Show rating modal instead of plain Alert
      setShowRating(true);
    } catch (e) {
      Alert.alert('Error', e.response?.data?.detail || 'Could not save itinerary.');
    } finally {
      setSaving(false);
    }
  }

  async function regenerateWith(feedback) {
    if (!currentPlanId || regenerating) return;
    setShowRegenerate(false);
    setRegenerating(true);
    try {
      const { data } = await apiClient.post(`/itinerary/plan/${currentPlanId}/regenerate`, { feedback });
      const newPlanId = String(data.plan_id);
      setSaved(false);
      setCurrentPlanId(newPlanId);
      router.replace({
        pathname: '/(app)/generated-itinerary',
        params: {
          plan_id: newPlanId,
          ...(group_trip_id ? { group_trip_id } : {}),
        },
      });
    } catch (e) {
      Alert.alert('Could not regenerate', e.response?.data?.detail || 'Please try again.');
    } finally {
      setRegenerating(false);
    }
  }

  function handleRegenerate() {
    setShowRegenerate(true);
  }

  function handleReplaceAttraction(item) {
    if (!currentPlanId || !item?.attraction?.id || !item?.day) return;
    Alert.alert(
      'Replace this stop?',
      'TripCraft will choose a similar fit in the same city.',
      [
        { text: 'Similar', onPress: () => replaceAttraction(item, []) },
        { text: 'Shorter', onPress: () => replaceAttraction(item, ['shorter']) },
        { text: 'Cheaper', onPress: () => replaceAttraction(item, ['cheaper']) },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  }

  async function replaceAttraction(item, feedback) {
    try {
      await apiClient.post(
        `/itinerary/plan/${currentPlanId}/days/${item.day}/replace-attraction`,
        { attraction_id: item.attraction.id, feedback, apply: true }
      );
      await loadPlan(currentPlanId, 'SUMMARY');
    } catch (e) {
      Alert.alert('Could not replace stop', e.response?.data?.detail || 'No good alternative found.');
    }
  }

  async function handleMemoryAttraction(item, sentiment) {
    if (!currentPlanId || !item?.attraction?.id) return;
    try {
      await apiClient.post(`/itinerary/plan/${currentPlanId}/memory`, {
        liked_attraction_ids: sentiment === 'like' ? [item.attraction.id] : [],
        disliked_attraction_ids: sentiment === 'dislike' ? [item.attraction.id] : [],
        aspects: sentiment === 'like' ? ['great_vibe'] : ['wrong_vibe'],
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Alert.alert(
        sentiment === 'like' ? 'Saved as a favorite signal' : 'Saved as a weak fit',
        'TripCraft will use this memory in future recommendations.'
      );
    } catch (e) {
      Alert.alert('Could not save memory', e.response?.data?.detail || 'Please try again.');
    }
  }

  function handleRatingDone(submitted) {
    setShowRating(false);
    if (submitted) {
      Alert.alert(
        'Thank you!',
        'Your feedback was saved and will refine your future recommendations.',
        [{ text: 'Great' }]
      );
    }
  }

  const transitionStyle = {
    opacity: transitionAnim,
    transform: [{
      translateY: transitionAnim.interpolate({
        inputRange: [0, 1],
        outputRange: [12, 0],
      }),
    }],
  };

  if (step === 'LOADING') return <LoadingScreen subtitle="Building your itinerary..." />;

  if (step === 'ERROR' || !plan) {
    return (
      <View style={styles.errorRoot}>
        <Text style={styles.errorTitle}>Could not load itinerary</Text>
        <Text style={styles.errorText}>{error || 'Please try again.'}</Text>
        <TouchableOpacity style={styles.errorBtn} activeOpacity={0.85} onPress={() => router.back()}>
          <Text style={styles.errorBtnText}>Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <>
      {step === 'MAP' && (
        <Animated.View style={[styles.screenTransition, transitionStyle]}>
          <GeneratedMapView
            plan={plan}
            routePoints={routePointsForPlan(plan)}
            activeDay={activeDay}
            onDayChange={setActiveDay}
            onStoryMode={() => setStep('STORY')}
            onSummary={() => setStep('SUMMARY')}
            onBack={() => router.back()}
          />
        </Animated.View>
      )}

      {step === 'STORY' && (
        <Animated.View style={[styles.screenTransition, transitionStyle]}>
          <StoryMode
            plan={plan}
            activeDay={activeDay}
            onDayChange={setActiveDay}
            onBack={() => setStep('MAP')}
            onSave={handleSave}
            saving={saving}
            saved={saved}
          />
        </Animated.View>
      )}

      {step === 'SUMMARY' && (
        <Animated.View style={[styles.screenTransition, transitionStyle]}>
          <TripSummary
            tripItems={tripItemsForPlan(plan)}
            days={plan.num_days}
            country={plan.country}
            saving={saving}
            isAutoGenerated
            onBack={() => setStep('MAP')}
            onSave={handleSave}
            onReplace={handleReplaceAttraction}
            onMemory={handleMemoryAttraction}
            onRegenerate={handleRegenerate}
            regenerating={regenerating}
          />
        </Animated.View>
      )}

      <RatingModal
        visible={showRating}
        country={plan?.country || 'your trip'}
        planId={currentPlanId}
        onDone={handleRatingDone}
      />

      <RegenerateModal
        visible={showRegenerate}
        country={plan?.country}
        regenerating={regenerating}
        onClose={() => setShowRegenerate(false)}
        onSelect={regenerateWith}
      />
    </>
  );
}

const TEAL = COLORS.primary;
const INK = COLORS.ink;
const CREAM = COLORS.cream;

const styles = StyleSheet.create({
  screenTransition: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },
  errorRoot: {
    flex: 1, backgroundColor: COLORS.cream,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 28,
  },
  errorTitle: { fontSize: 24, ...TYPE.serifItalic, color: COLORS.ink, textAlign: 'center' },
  errorText:  { fontSize: 13, color: COLORS.muted, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  errorBtn:   { height: 48, borderRadius: RADIUS.full, backgroundColor: TEAL, paddingHorizontal: 28, alignItems: 'center', justifyContent: 'center', marginTop: 22 },
  errorBtnText: { fontSize: 14, color: COLORS.surface, fontFamily: FONTS.sansSemi },

  // Rating modal
  ratingBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  ratingSheet: {
    backgroundColor: CREAM,
    borderTopLeftRadius: RADIUS.lg,
    borderTopRightRadius: RADIUS.lg,
    paddingHorizontal: 24,
    paddingBottom: 40,
    paddingTop: 12,
  },
  ratingHandle: {
    width: 36, height: 4, borderRadius: 2,
    backgroundColor: COLORS.border, alignSelf: 'center', marginBottom: 20,
  },
  ratingTitle: {
    ...TYPE.serifItalic, fontSize: 26,
    color: INK, marginBottom: 4,
  },
  ratingCountry: {
    fontFamily: FONTS.sans, fontSize: 13, color: COLORS.muted, marginBottom: 24,
  },
  starsRow: {
    flexDirection: 'row', gap: 10, marginBottom: 28,
  },
  star: {
    fontSize: 38, color: COLORS.border,
  },
  starActive: {
    color: '#F4A50D',
  },
  aspectsLabel: {
    fontFamily: FONTS.sans, fontSize: 11, color: COLORS.muted,
    letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 12,
  },
  aspectsGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 28,
  },
  aspectPill: {
    borderWidth: 1, borderColor: COLORS.border,
    borderRadius: RADIUS.full, paddingVertical: 8, paddingHorizontal: 16,
    backgroundColor: COLORS.surface,
  },
  aspectPillPos: { borderColor: TEAL, backgroundColor: '#E6F4F2' },
  aspectPillNeg: { borderColor: '#E76F51', backgroundColor: '#FDF0EC' },
  aspectText: {
    fontFamily: FONTS.sansMedium, fontSize: 13, color: INK,
  },
  aspectTextPos: { color: TEAL },
  aspectTextNeg: { color: '#E76F51' },
  ratingActions: {
    gap: 12, alignItems: 'center',
  },
  submitBtn: {
    width: '100%', height: 52, borderRadius: RADIUS.full,
    backgroundColor: COLORS.navy, alignItems: 'center', justifyContent: 'center',
  },
  submitBtnDisabled: { backgroundColor: COLORS.border },
  submitBtnText: {
    fontFamily: FONTS.sansSemi, fontSize: 15, color: COLORS.surface,
  },
  skipText: {
    fontFamily: FONTS.sans, fontSize: 13, color: COLORS.muted,
  },
  ratingNote: {
    fontFamily: FONTS.sans, fontSize: 11, color: COLORS.muted,
    textAlign: 'center', marginTop: 16, lineHeight: 16,
  },
  regenerateSheet: {
    backgroundColor: CREAM,
    borderTopLeftRadius: RADIUS.lg,
    borderTopRightRadius: RADIUS.lg,
    paddingHorizontal: 22,
    paddingBottom: 34,
    paddingTop: 12,
  },
  regenerateHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  regenerateIconBadge: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: COLORS.tagBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  regenerateEyebrow: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: TEAL,
    letterSpacing: 0,
    marginBottom: 4,
  },
  regenerateTitle: {
    ...TYPE.serifItalic,
    fontSize: 28,
    color: INK,
    lineHeight: 32,
  },
  regenerateSubtitle: {
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: COLORS.muted,
    lineHeight: 19,
    marginBottom: 18,
  },
  regenerateOptions: {
    gap: 10,
  },
  regenerateOption: {
    minHeight: 72,
    borderRadius: RADIUS.md,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  regenerateOptionDisabled: {
    opacity: 0.55,
  },
  regenerateOptionIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: COLORS.tagBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  regenerateOptionTextWrap: {
    flex: 1,
  },
  regenerateOptionTitle: {
    fontFamily: FONTS.sansSemi,
    fontSize: 15,
    color: INK,
    marginBottom: 3,
  },
  regenerateOptionSubtitle: {
    fontFamily: FONTS.sans,
    fontSize: 12,
    color: COLORS.muted,
    lineHeight: 17,
  },
  regenerateActions: {
    alignItems: 'center',
    marginTop: 18,
  },
  regenerateCancelBtn: {
    paddingVertical: 10,
    paddingHorizontal: 18,
  },
  regenerateCancelText: {
    fontFamily: FONTS.sansMedium,
    fontSize: 13,
    color: COLORS.muted,
  },
});
