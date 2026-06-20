import {
  useRef,
  useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Dimensions,
  ScrollView,
  StyleSheet,
  Text,
  View
} from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import BottomPanel from './BottomPanel';
import DaySwitch from './DaySwitch';
import TripImage from './TripImage';
import MapWebView from './MapWebView';
import { C, MAX_DAY_HOURS, formatTag, groupFitLabel, primaryExplanation, scoreText } from '../../constants/interactive';
import { FONTS, TYPE } from '../../constants/theme';

const FALLBACK_CENTER = { lat: 46.8, lng: 2.35 };
const PANEL_PCT = 0.45;
const { height: SCREEN_H } = Dimensions.get('window');

function countryCenter(cities) {
  const withCoords = cities.filter((city) => city.lat && city.lng);
  if (withCoords.length === 0) return FALLBACK_CENTER;
  return {
    lat: withCoords.reduce((sum, city) => sum + Number(city.lat), 0) / withCoords.length,
    lng: withCoords.reduce((sum, city) => sum + Number(city.lng), 0) / withCoords.length,
  };
}

export default function CountryMapView({
  country = 'Trip',
  cities = [],
  routePoints = [],
  loading = false,
  currentDay = 1,
  days = 1,
  tripItems = [],
  onDayChange,
  onCitySelect,
}) {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const hintOpacity = useRef(new Animated.Value(1)).current;
  const [hintVisible, setHintVisible] = useState(true);

  const dayItems = tripItems.filter((item) => item.day === currentDay);
  const hoursUsed = dayItems.reduce((sum, item) => sum + (item.attraction?.avg_duration_hours || 1), 0);
  const pct = Math.min(hoursUsed / MAX_DAY_HOURS, 1);
  const isFull = hoursUsed >= MAX_DAY_HOURS;

  function dismissHint() {
    if (!hintVisible) return;
    Animated.timing(hintOpacity, { toValue: 0, duration: 300, useNativeDriver: true })
      .start(() => setHintVisible(false));
  }

  function handleMarkerPress(id) {
    const city = cities.find((item) => item.id === id);
    if (city && onCitySelect) {
      dismissHint();
      onCitySelect(city);
    }
  }

  return (
    <View style={styles.container}>
      <MapWebView
        markers={cities}
        center={countryCenter(cities)}
        zoom={5}
        mode="country"
        routePoints={routePoints}
        routeMode="driving"
        onMarkerPress={handleMarkerPress}
      />

      <View style={[styles.topBar, { top: insets.top + 8 }]}>
        <TouchableOpacity style={styles.backPill} activeOpacity={0.8} onPress={() => router.back()}>
          <Text style={styles.backPillText}>{'<'} {country}</Text>
        </TouchableOpacity>
        <DaySwitch active={currentDay} total={days} onChange={onDayChange} />
      </View>

      {hintVisible && (
        <Animated.View style={[styles.hint, { opacity: hintOpacity, bottom: SCREEN_H * PANEL_PCT + 52 }]}>
          <Text style={styles.hintText}>Tap a city to explore</Text>
        </Animated.View>
      )}

      <View style={[styles.dayIndicator, { bottom: SCREEN_H * PANEL_PCT + 8 }]}>
        <Text style={styles.dayIndicatorText}>Adding to Day {currentDay}</Text>
      </View>

      <BottomPanel heightPercent={PANEL_PCT}>
        <View style={styles.panelHeader}>
          <Text style={styles.panelTitle}>Suggested Cities</Text>
          <Text style={styles.panelSub}>Ranked by your real profile score</Text>
        </View>

        <View style={styles.capacityWrap}>
          <View style={styles.capacityRow}>
            <Text style={styles.capacityLabel}>Capacity</Text>
            <Text style={[styles.capacityValue, isFull && styles.capacityFull]}>
              {hoursUsed.toFixed(1)}h / {MAX_DAY_HOURS}h
            </Text>
          </View>
          <View style={styles.barTrack}>
            <View style={[styles.barFill, { width: `${pct * 100}%`, backgroundColor: isFull ? '#E76F51' : C.primary }]} />
          </View>
          {isFull ? (
            <Text style={styles.fullText}>
              {currentDay < days
                ? `Day ${currentDay} is full. New stops will ask before moving to Day ${currentDay + 1}.`
                : 'This day is full. Review the trip or remove a stop.'}
            </Text>
          ) : null}
        </View>

        {loading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={C.primary} />
            <Text style={styles.loadingText}>Loading recommendations...</Text>
          </View>
        ) : cities.length === 0 ? (
          <View style={styles.loadingWrap}>
            <Text style={styles.loadingText}>No cities available for this country.</Text>
          </View>
        ) : (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.citiesRow}
          >
            {cities.map((city, index) => (
              <CityCard
                key={city.id ?? index}
                city={city}
                first={index === 0}
                onPress={() => {
                  dismissHint();
                  onCitySelect?.(city);
                }}
              />
            ))}
          </ScrollView>
        )}
      </BottomPanel>
    </View>
  );
}

function CityCard({ city, first, onPress }) {
  const fitLabel = groupFitLabel(city);
  const explanation = primaryExplanation(city);

  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={[styles.card, first && styles.cardFirst]}>
      <View style={styles.cardTop}>
        <TripImage uri={city.image_url} style={StyleSheet.absoluteFillObject} />
        <Text style={styles.cardCityLabel}>{(city.name || city.city || '').toUpperCase()}</Text>
        <View style={styles.cardGlobe} />
      </View>
      <View style={styles.cardBody}>
        <Text style={styles.cardName}>{city.name || city.city}</Text>
        <View style={styles.tagsRow}>
          {(city.tags || []).map((tag) => (
            <View key={tag} style={styles.tag}>
              <Text style={styles.tagText}>{formatTag(tag)}</Text>
            </View>
          ))}
        </View>
        {city.description ? (
          <Text style={styles.cardDesc} numberOfLines={2} ellipsizeMode="tail">{city.description}</Text>
        ) : null}
        {explanation ? <Text style={styles.explanationText} numberOfLines={2}>{explanation}</Text> : null}
        {fitLabel ? <Text style={styles.groupFitText}>{fitLabel}</Text> : null}
        <Text style={styles.matchText}>{scoreText(city)}</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  topBar: { position: 'absolute', left: 16, right: 16, flexDirection: 'row', alignItems: 'center', gap: 8 },
  backPill: {
    backgroundColor: '#FFFFFF',
    borderRadius: 100,
    paddingVertical: 10,
    paddingHorizontal: 20,
    shadowColor: '#0D1B2A',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 4,
  },
  backPillText: { fontFamily: 'Inter_600SemiBold', fontSize: 14, color: C.ink, fontWeight: '600' },
  hint: {
    position: 'absolute',
    alignSelf: 'center',
    backgroundColor: 'rgba(13,27,42,0.75)',
    borderRadius: 100,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  hintText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  dayIndicator: {
    position: 'absolute',
    left: 16,
    borderRadius: 100,
    paddingVertical: 8,
    paddingHorizontal: 14,
    backgroundColor: 'rgba(255,255,255,0.92)',
  },
  dayIndicatorText: { fontSize: 12, color: C.ink, fontWeight: '700' },
  panelHeader: { paddingHorizontal: 20, paddingTop: 18, paddingBottom: 10 },
  panelTitle: { fontSize: 26, ...TYPE.serifItalic, color: C.ink },
  panelSub: { fontSize: 13, color: C.sub, marginTop: 2 },
  capacityWrap: { paddingHorizontal: 20, marginBottom: 10 },
  capacityRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  capacityLabel: { fontSize: 11, color: C.sub, fontFamily: 'Inter_400Regular' },
  capacityValue: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium' },
  capacityFull: { color: '#E76F51' },
  barTrack: { height: 5, borderRadius: 100, backgroundColor: C.tagBg, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 100 },
  fullText: { fontSize: 12, color: '#E76F51', fontFamily: 'Inter_400Regular', marginTop: 6, textAlign: 'center' },
  citiesRow: { paddingHorizontal: 20, gap: 14, paddingBottom: 20 },
  card: {
    width: 220,
    borderRadius: 18,
    backgroundColor: '#FFFFFF',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: C.border,
  },
  cardFirst: {
    borderColor: C.primary,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.16,
    shadowRadius: 14,
    elevation: 5,
  },
  cardTop: { height: 106, backgroundColor: C.primary, overflow: 'hidden' },
  cardCityLabel: {
    position: 'absolute',
    left: 14,
    bottom: 12,
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0,
  },
  cardGlobe: {
    position: 'absolute',
    right: 12,
    top: 12,
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: 'rgba(255,255,255,0.22)',
  },
  cardBody: { padding: 14, gap: 7 },
  cardName: { fontSize: 18, fontWeight: '800', color: C.ink },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  tag: { backgroundColor: C.tagBg, borderRadius: 100, paddingVertical: 3, paddingHorizontal: 8 },
  tagText: { fontSize: 10, color: C.primary, fontFamily: 'Inter_500Medium' },
  cardDesc: { fontSize: 12, color: C.sub, lineHeight: 17 },
  explanationText: { fontSize: 11, color: C.ink, fontFamily: 'Inter_400Regular', lineHeight: 16 },
  groupFitText: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium', fontWeight: '700' },
  matchText: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium', textAlign: 'right', marginTop: 2 },
  loadingWrap: { alignItems: 'center', marginTop: 32 },
  loadingText: { textAlign: 'center', color: C.sub, marginTop: 12, fontFamily: 'Inter_400Regular', fontSize: 13 },
});
