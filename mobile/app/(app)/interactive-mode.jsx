import {
  useEffect,
  useMemo,
  useState } from 'react';
import { Alert,
  Dimensions,
  Modal,
  View,
  Text,
  StyleSheet
} from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';

import AsyncStorage from '@react-native-async-storage/async-storage';

const FAB_BOTTOM = Math.round(Dimensions.get('window').height * 0.45 + 16);
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../context/AuthContext';
import LoadingScreen from '../../components/interactive/LoadingScreen';
import CountryMapView from '../../components/interactive/CountryMapView';
import CityMapView from '../../components/interactive/CityMapView';
import AttractionDetail from '../../components/interactive/AttractionDetail';
import SuggestedPanel from '../../components/interactive/SuggestedPanel';
import TripSummary from '../../components/interactive/TripSummary';
import {
  fetchCities, fetchAttractions, fetchSuggested, fetchNextCity,
  haversineKm,
  MAX_DAY_HOURS,
  groupFitLabel,
  primaryExplanation,
  scoreText,
  formatTag,
} from '../../constants/interactive';
import { FONTS, TYPE } from '../../constants/theme';
import apiClient from '../../services/api';
import { getCurrentUserSessionId } from '../../services/session';

const CITY_STEPS = new Set(['CITY', 'DETAIL', 'SUGGESTED', 'SUGGESTED_DETAIL']);
const MAX_DAYS = 10;

function paramValue(value, fallback = '') {
  if (Array.isArray(value)) return value[0] ?? fallback;
  return value ?? fallback;
}

function clampDays(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(Math.max(Math.round(parsed), 1), MAX_DAYS);
}

function makeTripItem(attraction, city, day) {
  return {
    uid: `${Date.now()}-${attraction.id}-${Math.random().toString(36).slice(2)}`,
    attraction,
    city,
    day,
  };
}

function pointFromAttraction(item) {
  return {
    lat: item.attraction.lat,
    lng: item.attraction.lng,
    label: item.attraction.name,
  };
}

export default function InteractiveModeScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const params = useLocalSearchParams();
  const { user } = useAuth();
  const countryName = paramValue(params.country_name, paramValue(params.country, ''));
  const countryId = Number(paramValue(params.country_id, '')) || null;
  const planId = paramValue(params.planId, '');
  const routeSessionId = paramValue(params.session_id, '');
  const groupTripId = paramValue(params.group_trip_id, '');
  const isReadOnly = paramValue(params.readOnly, '') === 'true';
  const initialDays = clampDays(paramValue(params.days, '1'));
  // ── Navigation ──
  const [step, setStep] = useState('LOADING');
  const [selectedCity, setSelectedCity] = useState(null);
  const [selectedAttraction, setSelectedAttraction] = useState(null);
  const [selectedSuggested, setSelectedSuggested] = useState(null);
  const [addNextCity, setAddNextCity] = useState(false);

  // ── Trip ──
  const [tripItems, setTripItems] = useState([]);
  const [days, setDays] = useState(initialDays);
  const [currentDay, setCurrentDay] = useState(1);

  // ── API ──
  const [sessionId, setSessionId] = useState(null);
  const [cities, setCities] = useState([]);
  const [attractions, setAttractions] = useState([]);
  const [suggested, setSuggested] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const [draftLoaded, setDraftLoaded] = useState(false);

  const draftKey = useMemo(() => {
    const userPart = user?.id || 'anon';
    const countryPart = countryId || countryName || 'unknown';
    const groupPart = groupTripId || 'solo';
    const sessionPart = sessionId || routeSessionId || 'latest';
    return `fim_draft:${userPart}:${sessionPart}:${countryPart}:${groupPart}`;
  }, [user?.id, sessionId, routeSessionId, countryId, countryName, groupTripId]);

  // ── Feat 3: next city modal ──
  const [nextCityModal, setNextCityModal] = useState(null);

  useEffect(() => {
    if (planId) return;
    const t = setTimeout(() => setStep('COUNTRY'), 2500);
    return () => clearTimeout(t);
  }, [planId]);

  useEffect(() => {
    if (planId) return;
    if (routeSessionId) {
      setLoadError('');
      setSessionId(routeSessionId);
      return;
    }
    getCurrentUserSessionId(user)
      .then((id) => {
        if (id) {
          setLoadError('');
          setSessionId(id);
        }
        else setLoadError('Could not load interactive mode');
      })
      .catch(() => setLoadError('Could not load interactive mode'));
  }, [user?.id, planId, routeSessionId]);

  useEffect(() => {
    if (!planId) return;
    setLoading(true);
    apiClient.get(`/fim/trips/${planId}`)
      .then(({ data }) => {
        setDays(clampDays(data.num_days));
        setCurrentDay(1);
        setTripItems((data.items || []).map((item) => ({
          uid: `saved-${item.day}-${item.order}-${item.attraction.id}`,
          attraction: item.attraction,
          city: item.city,
          day: item.day,
        })));
        setSelectedCity(data.items?.[0]?.city || null);
        setStep('SUMMARY');
      })
      .catch(() => setLoadError('Could not load interactive mode'))
      .finally(() => setLoading(false));
  }, [planId]);

  useEffect(() => {
    if (planId || isReadOnly || !sessionId) {
      setDraftLoaded(true);
      return;
    }

    let cancelled = false;
    AsyncStorage.getItem(draftKey)
      .then((raw) => {
        if (cancelled || !raw) return;
        const draft = JSON.parse(raw);
        if (!draft?.tripItems?.length) return;
        setDays(clampDays(draft.days || initialDays));
        setCurrentDay(Math.min(clampDays(draft.currentDay || 1), clampDays(draft.days || initialDays)));
        setTripItems(draft.tripItems || []);
        setSelectedCity(draft.selectedCity || null);
        setStep(draft.selectedCity ? 'CITY' : 'COUNTRY');
        Alert.alert('Draft restored', 'Your unsaved interactive trip was restored.');
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setDraftLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [draftKey, sessionId, planId, isReadOnly]);

  useEffect(() => {
    if (!draftLoaded || planId || isReadOnly || !sessionId || tripItems.length === 0) return;
    const payload = {
      version: 1,
      updated_at: new Date().toISOString(),
      countryName,
      countryId,
      groupTripId,
      sessionId,
      days,
      currentDay,
      selectedCity,
      tripItems,
    };
    AsyncStorage.setItem(draftKey, JSON.stringify(payload)).catch(() => {});
  }, [
    draftLoaded,
    draftKey,
    planId,
    isReadOnly,
    sessionId,
    countryName,
    countryId,
    groupTripId,
    days,
    currentDay,
    selectedCity,
    tripItems,
  ]);

  useEffect(() => {
    if (step !== 'COUNTRY' || !sessionId || !countryName || planId) return;
    setLoading(true);
    setLoadError('');
    fetchCities(countryName, sessionId, countryId, groupTripId)
      .then(setCities)
      .catch(() => setLoadError('Could not load interactive mode'))
      .finally(() => setLoading(false));
  }, [step, sessionId, countryName, countryId, groupTripId, planId]);

  useEffect(() => {
    if (step !== 'CITY' || !sessionId || !selectedCity) return;
    setLoading(true);
    setLoadError('');
    fetchAttractions(selectedCity.id, sessionId, groupTripId)
      .then(setAttractions)
      .catch(() => setLoadError('Could not load interactive mode'))
      .finally(() => setLoading(false));
  }, [step, selectedCity, sessionId, groupTripId]);

  useEffect(() => {
    if (step !== 'SUGGESTED' || !sessionId || !selectedCity) return;
    const excludeIds = tripItems.map((i) => i.attraction.id).filter(Boolean);
    const currentDayItems = tripItems.filter((i) => i.day === currentDay && i.attraction?.id);
    const currentDayIds = currentDayItems.map((i) => i.attraction.id);
    const lastAttractionId = getLastDayAttraction(currentDay)?.id || null;
    setLoading(true);
    setLoadError('');
    fetchSuggested(selectedCity.id, sessionId, excludeIds, { currentDayIds, lastAttractionId, groupTripId })
      .then(setSuggested)
      .catch(() => setLoadError('Could not load interactive mode'))
      .finally(() => setLoading(false));
  }, [step, sessionId, selectedCity, tripItems, currentDay, groupTripId]);

  /* ── Handlers ── */

  function getRoutePointsForDay(day) {
    return tripItems
      .filter((item) => item.day === day && item.attraction?.lat && item.attraction?.lng)
      .map(pointFromAttraction);
  }

  function getLastTripPoint() {
    const lastItem = [...tripItems].reverse().find((item) => item.attraction?.lat && item.attraction?.lng);
    return lastItem ? pointFromAttraction(lastItem) : null;
  }

  function getLastDayAttraction(day) {
    const lastItem = [...tripItems]
      .reverse()
      .find((item) => item.day === day && item.attraction?.id);
    return lastItem?.attraction || null;
  }

  function getDayHours(day, items = tripItems) {
    return items
      .filter((item) => item.day === day)
      .reduce((sum, item) => sum + Number(item.attraction?.avg_duration_hours || 1), 0);
  }

  function addTripItem(attraction, day, nextStep) {
    setTripItems((prev) => [...prev, makeTripItem(attraction, selectedCity, day)]);
    setCurrentDay(day);
    if (nextStep === 'SUGGESTED') setSelectedSuggested(null);
    setStep(nextStep);
  }

  function addWithCapacityCheck(attraction, nextStep) {
    const duration = Number(attraction?.avg_duration_hours || 1);
    const projectedHours = getDayHours(currentDay) + duration;

    if (projectedHours <= MAX_DAY_HOURS) {
      addTripItem(attraction, currentDay, nextStep);
      return;
    }

    if (currentDay < days) {
      const nextDay = currentDay + 1;
      Alert.alert(
        `Day ${currentDay} is full`,
        `Adding this stop would bring Day ${currentDay} to ${projectedHours.toFixed(1)}h. Move it to Day ${nextDay}?`,
        [
          { text: 'Cancel', style: 'cancel' },
          { text: `Keep Day ${currentDay}`, onPress: () => addTripItem(attraction, currentDay, nextStep) },
          { text: `Add to Day ${nextDay}`, onPress: () => addTripItem(attraction, nextDay, nextStep) },
        ]
      );
      return;
    }

    Alert.alert(
      'Last day is full',
      `This stop would bring Day ${currentDay} to ${projectedHours.toFixed(1)}h.`,
      [
        { text: 'Review trip', onPress: () => setStep('SUMMARY') },
        { text: 'Add anyway', onPress: () => addTripItem(attraction, currentDay, nextStep) },
      ]
    );
  }

  function handleCitySelect(city) {
    if (addNextCity) setAddNextCity(false);
    setSelectedCity(city);
    setStep('CITY');
  }

  function handleBackToCountry() {
    setSelectedCity(null);
    setStep('COUNTRY');
  }

  function handleAttractionSelect(attraction) {
    setSelectedAttraction(attraction);
    setStep('DETAIL');
  }

  function handleBackToCity() { setStep('CITY'); }

  function handleAddToTrip(attraction) {
    addWithCapacityCheck(attraction, 'SUGGESTED');
  }

  function handleSuggestedSelect(attraction) {
    setSelectedSuggested(attraction);
    setStep('SUGGESTED_DETAIL');
  }

  function handleChooseAnother() { setStep('CITY'); }

  async function handleFindNextCity() {
    if (!sessionId) {
      Alert.alert('No quiz session', 'Please complete the quiz before continuing the interactive trip.');
      return;
    }
    if (currentDay >= days) {
      Alert.alert('Trip days complete', 'You reached the selected number of days. Review your trip or remove a stop.');
      setStep('SUMMARY');
      return;
    }

    const nextDay = currentDay + 1;
    setCurrentDay(nextDay);
    setAddNextCity(true);
    setSelectedCity(null);
    setSelectedAttraction(null);
    setSelectedSuggested(null);

    const last = getLastTripPoint();
    const visitedCityIds = [...new Set(tripItems.map((item) => item.city?.id).filter(Boolean))];
    const visitedCityNames = [...new Set(tripItems.map((item) => item.city?.city || item.city?.name).filter(Boolean))];

    try {
      setLoading(true);
      const next = await fetchNextCity(countryName, sessionId, {
        countryId,
        groupTripId,
        visitedCityIds,
        visitedCityNames,
        lastPoint: last,
        currentDay: nextDay,
        days,
      });
      if (next) {
        setNextCityModal({ city: next, last: last || { lat: next.lat, lng: next.lng }, distanceKm: next.distance_km });
        return;
      }
    } catch {
    } finally {
      setLoading(false);
    }

    setStep('COUNTRY');
  }

  function handleViewSummary() { setStep('SUMMARY'); }

  function handleAddSuggested(attraction) {
    addWithCapacityCheck(attraction, 'SUGGESTED');
  }

  function handleDeleteTripItem(target) {
    setTripItems((prev) => prev.filter((item) => item.uid !== target.uid));
  }

  function handleMoveTripItem(target, direction) {
    setTripItems((prev) => {
      const dayItems = prev.filter((item) => item.day === target.day);
      const idx = dayItems.findIndex((item) => item.uid === target.uid);
      const nextIdx = idx + direction;
      if (idx < 0 || nextIdx < 0 || nextIdx >= dayItems.length) return prev;

      const reordered = [...dayItems];
      [reordered[idx], reordered[nextIdx]] = [reordered[nextIdx], reordered[idx]];

      const daysInTrip = [...new Set(prev.map((item) => item.day))].sort((a, b) => a - b);
      return daysInTrip.flatMap((day) =>
        day === target.day ? reordered : prev.filter((item) => item.day === day)
      );
    });
  }

  async function handleSaveTrip() {
    if (isReadOnly) return;
    if (!sessionId) {
      Alert.alert('Error', 'No quiz session found. Please complete the quiz first.');
      return;
    }
    if (tripItems.length === 0) {
      Alert.alert('Empty trip', 'Add at least one stop before saving.');
      return;
    }
    setSaving(true);
    try {
      const items = tripItems.map((item) => ({
        attraction_id: item.attraction.id,
        day: item.day,
        order: tripItems.filter((i) => i.day === item.day).findIndex((i) => i.uid === item.uid),
      }));

      await apiClient.post('/fim/trips', {
        session_id: sessionId,
        country: countryName,
        country_id: countryId,
        group_trip_id: groupTripId ? Number(groupTripId) : null,
        num_days: days,
        items,
      });
      await AsyncStorage.removeItem(draftKey).catch(() => {});

      Alert.alert(
        groupTripId ? 'Group Trip Saved' : 'Trip Saved',
        `Your ${countryName} trip has been saved to your profile.`,
        [{ text: 'Back to Home', onPress: () => router.push('/(app)/dashboard') }]
      );
    } catch {
      Alert.alert('Error', 'Could not save trip. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  /* ── Render ── */

  if (loadError) {
    return (
      <View style={styles.errorWrap}>
        <Ionicons name="alert-circle-outline" size={34} color="#E76F51" />
        <Text style={styles.errorTitle}>Could not load interactive mode</Text>
        <Text style={styles.errorText}>Please check your quiz profile and try again.</Text>
        <TouchableOpacity style={styles.errorBtn} activeOpacity={0.85} onPress={() => router.back()}>
          <Text style={styles.errorBtnText}>Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (step === 'LOADING') return <LoadingScreen />;

  if (step === 'SUMMARY') {
    return (
      <TripSummary
        tripItems={tripItems}
        days={days}
        country={countryName || 'Trip'}
        saving={saving}
        onBack={() => (isReadOnly ? router.back() : setStep(selectedCity ? 'CITY' : 'COUNTRY'))}
        onEdit={isReadOnly ? null : () => setStep(selectedCity ? 'CITY' : 'COUNTRY')}
        onSave={isReadOnly ? null : handleSaveTrip}
        onDelete={isReadOnly ? null : handleDeleteTripItem}
        onMove={isReadOnly ? null : handleMoveTripItem}
      />
    );
  }

  const showCity = CITY_STEPS.has(step);
  const flowStep = step === 'COUNTRY' ? 1 : 2;
  const lastDayAttraction = getLastDayAttraction(currentDay);

  return (
    <View style={styles.container}>
      {step === 'COUNTRY' && (
        <CountryMapView
          country={countryName || 'Trip'}
          cities={cities}
          routePoints={getRoutePointsForDay(currentDay)}
          loading={loading}
          currentDay={currentDay}
          days={days}
          tripItems={tripItems}
          onDayChange={setCurrentDay}
          onCitySelect={handleCitySelect}
        />
      )}
      {showCity && selectedCity && (
        <CityMapView
          city={selectedCity}
          routePoints={getRoutePointsForDay(currentDay)}
          attractions={attractions}
          loading={loading}
          currentDay={currentDay}
          days={days}
          tripItems={tripItems}
          onDayChange={setCurrentDay}
          onBack={handleBackToCountry}
          onAttractionSelect={handleAttractionSelect}
        />
      )}

      <FlowStepper active={flowStep} top={insets.top + 58} />

      {step === 'DETAIL' && (
        <AttractionDetail
          attraction={selectedAttraction}
          city={selectedCity}
          onBack={handleBackToCity}
          onAddToTrip={handleAddToTrip}
        />
      )}
      {step === 'SUGGESTED' && (
        <SuggestedPanel
          addedAttraction={lastDayAttraction || selectedAttraction}
          cityName={selectedCity?.name}
          suggested={suggested}
          loading={loading}
          onSuggestedSelect={handleSuggestedSelect}
          onChooseAnother={handleChooseAnother}
          onFindNextCity={handleFindNextCity}
          onViewSummary={handleViewSummary}
        />
      )}
      {step === 'SUGGESTED_DETAIL' && (
        <AttractionDetail
          attraction={selectedSuggested}
          city={selectedCity}
          onBack={() => setStep('SUGGESTED')}
          onAddToTrip={handleAddSuggested}
        />
      )}


      {/* Feat 4: FAB */}
      {tripItems.length > 0 && (
        <TouchableOpacity style={styles.fab} activeOpacity={0.85} onPress={() => setStep('SUMMARY')}>
          <Ionicons name="map" size={22} color="#FFFFFF" />
          <View style={styles.fabBadge}>
            <Text style={styles.fabBadgeText}>{tripItems.length}</Text>
          </View>
        </TouchableOpacity>
      )}

      {/* Feat 3: Next city recommendation modal */}
      <Modal
        visible={!!nextCityModal}
        transparent
        animationType="slide"
        onRequestClose={() => { setNextCityModal(null); setStep('COUNTRY'); }}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            {nextCityModal && (
              <>
                <Text style={styles.modalEyebrow}>Next recommended city</Text>
                <Text style={styles.modalCityName}>{nextCityModal.city.city || nextCityModal.city.name}</Text>
                <Text style={styles.modalMeta}>
                  {scoreText(nextCityModal.city)}
                  {nextCityModal.distanceKm != null
                    ? ` - ~${Math.round(nextCityModal.distanceKm)} km away`
                    : ` - ~${haversineKm(
                      nextCityModal.last.lat, nextCityModal.last.lng,
                      nextCityModal.city.lat, nextCityModal.city.lng
                    ).toFixed(0)} km away`}
                </Text>
                {(nextCityModal.city.next_city_reasons || [primaryExplanation(nextCityModal.city)])
                  .filter(Boolean)
                  .slice(0, 3)
                  .map((reason) => (
                    <Text key={reason} style={styles.modalReason}>{reason}</Text>
                  ))}
                {groupFitLabel(nextCityModal.city) ? (
                  <Text style={styles.modalGroupFit}>{groupFitLabel(nextCityModal.city)}</Text>
                ) : null}
                <View style={styles.modalTags}>
                  {(nextCityModal.city.tags || []).map((tag) => (
                    <View key={tag} style={styles.modalTag}>
                      <Text style={styles.modalTagText}>{formatTag(tag)}</Text>
                    </View>
                  ))}
                </View>
                <View style={styles.modalBtns}>
                  <TouchableOpacity
                    style={styles.modalPrimary}
                    activeOpacity={0.85}
                    onPress={() => { setNextCityModal(null); handleCitySelect(nextCityModal.city); }}
                  >
                    <Text style={styles.modalPrimaryText}>
                      Go to {nextCityModal.city.city || nextCityModal.city.name}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.modalGhost}
                    activeOpacity={0.8}
                    onPress={() => { setNextCityModal(null); setStep('COUNTRY'); }}
                  >
                    <Text style={styles.modalGhostText}>Choose another city</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

function FlowStepper({ active, top }) {
  const steps = [
    { id: 1, label: 'Choose city' },
    { id: 2, label: 'Add stops' },
    { id: 3, label: 'Review trip' },
  ];

  return (
    <View style={[styles.stepper, { top }]}>
      {steps.map((item) => {
        const isActive = item.id === active;
        const isDone = item.id < active;
        return (
          <View key={item.id} style={[styles.stepperItem, isActive && styles.stepperItemActive]}>
            <View style={[styles.stepperDot, (isActive || isDone) && styles.stepperDotActive]}>
              <Text style={[styles.stepperDotText, (isActive || isDone) && styles.stepperDotTextActive]}>
                {item.id}
              </Text>
            </View>
            <Text style={[styles.stepperText, isActive && styles.stepperTextActive]}>{item.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0D1B2A' },

  errorWrap: {
    flex: 1,
    backgroundColor: '#0D1B2A',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 28,
  },
  errorTitle: {
    fontSize: 24,
    ...TYPE.serifItalic,
    color: '#FFFFFF',
    marginTop: 14,
    textAlign: 'center',
  },
  errorText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.72)',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  errorBtn: {
    marginTop: 22,
    height: 48,
    borderRadius: 100,
    paddingHorizontal: 28,
    backgroundColor: '#2A9D8F',
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },

  stepper: {
    position: 'absolute',
    left: 16,
    right: 16,
    zIndex: 70,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
  },
  stepperItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 6,
    paddingHorizontal: 9,
    borderRadius: 100,
    backgroundColor: 'rgba(13,27,42,0.62)',
  },
  stepperItemActive: {
    backgroundColor: '#FFFFFF',
  },
  stepperDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepperDotActive: {
    backgroundColor: '#2A9D8F',
  },
  stepperDotText: {
    fontSize: 10,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.8)',
  },
  stepperDotTextActive: {
    color: '#FFFFFF',
  },
  stepperText: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.82)',
    fontWeight: '600',
  },
  stepperTextActive: {
    color: '#0D1B2A',
  },

  /* Feat 4: FAB */
  fab: {
    position: 'absolute',
    bottom: FAB_BOTTOM,
    right: 16,
    zIndex: 80,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#2A9D8F',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#0D1B2A',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 12,
    elevation: 8,
  },
  fabBadge: {
    position: 'absolute',
    top: -6,
    right: -6,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#E76F51',
    alignItems: 'center',
    justifyContent: 'center',
  },
  fabBadgeText: { fontSize: 11, fontWeight: '700', color: '#FFFFFF', fontFamily: 'sans-serif' },

  /* Feat 3: modal */
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(13,27,42,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 24,
    marginHorizontal: 32,
    width: '85%',
  },
  modalEyebrow: {
    fontSize: 12,
    fontFamily: 'sans-serif',
    color: '#6B7280',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  modalCityName: {
    fontSize: 28,
    ...TYPE.serifItalic,
    color: '#1A1A2E',
    marginTop: 8,
  },
  modalMeta: {
    fontSize: 12,
    fontFamily: 'monospace',
    color: '#2A9D8F',
    marginTop: 4,
  },
  modalReason: {
    fontSize: 12,
    fontFamily: 'sans-serif',
    color: '#1A1A2E',
    lineHeight: 18,
    marginTop: 10,
  },
  modalGroupFit: {
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: '700',
    color: '#2A9D8F',
    marginTop: 6,
  },
  modalTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 12 },
  modalTag: {
    backgroundColor: '#E6F4F2',
    borderRadius: 100,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  modalTagText: { fontSize: 12, color: '#2A9D8F', fontFamily: 'sans-serif' },
  modalBtns: { gap: 10, marginTop: 20 },
  modalPrimary: {
    height: 52,
    borderRadius: 100,
    backgroundColor: '#2A9D8F',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalPrimaryText: { fontSize: 15, fontWeight: '600', color: '#FFFFFF', fontFamily: 'sans-serif' },
  modalGhost: {
    height: 48,
    borderRadius: 100,
    borderWidth: 1.5,
    borderColor: 'rgba(26,26,46,0.12)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalGhostText: { fontSize: 14, color: '#1A1A2E', fontFamily: 'sans-serif' },
});
