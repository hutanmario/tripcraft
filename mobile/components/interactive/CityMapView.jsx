import { ActivityIndicator, Dimensions, ScrollView, StyleSheet, Text, View } from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { useSafeAreaInsets } from 'react-native-safe-area-context';
import BottomPanel from './BottomPanel';
import DaySwitch from './DaySwitch';
import TripImage from './TripImage';
import MapWebView from './MapWebView';
import { C, MAX_DAY_HOURS, formatTag, groupFitLabel, primaryExplanation, scorePct, scoreText } from '../../constants/interactive';
import { FONTS, TYPE } from '../../constants/theme';

const PANEL_PCT = 0.50;
const { height: SCREEN_H } = Dimensions.get('window');

export default function CityMapView({
  city,
  routePoints,
  attractions = [],
  loading = false,
  currentDay = 1,
  days = 1,
  tripItems = [],
  onDayChange,
  onBack,
  onAttractionSelect,
}) {
  const insets = useSafeAreaInsets();
  if (!city) return null;

  const dayAttractions = tripItems.filter((item) => item.day === currentDay);
  const hoursUsed = dayAttractions.reduce((sum, item) => sum + (item.attraction?.avg_duration_hours || 1), 0);
  const pct = Math.min(hoursUsed / MAX_DAY_HOURS, 1);
  const isFull = hoursUsed >= MAX_DAY_HOURS;

  function handleMarkerPress(id) {
    const attraction = attractions.find((item) => item.id === id);
    if (attraction && onAttractionSelect) onAttractionSelect(attraction);
  }

  return (
    <View style={styles.container}>
      <MapWebView
        markers={attractions}
        center={{ lat: city.lat, lng: city.lng }}
        zoom={13}
        mode="city"
        routePoints={routePoints}
        routeMode="foot"
        onMarkerPress={handleMarkerPress}
      />

      <View style={[styles.topBar, { top: insets.top + 8 }]}>
        <TouchableOpacity style={styles.backPill} activeOpacity={0.8} onPress={onBack}>
          <Text style={styles.backPillText}>{'<'} {city.name}</Text>
        </TouchableOpacity>
        <DaySwitch active={currentDay} total={days} onChange={onDayChange} />
      </View>

      <View style={[styles.dayIndicator, { bottom: SCREEN_H * PANEL_PCT + 8 }]}>
        <Text style={styles.dayIndicatorText}>Adding to Day {currentDay}</Text>
      </View>

      <BottomPanel heightPercent={PANEL_PCT}>
        <View style={styles.panelHeader}>
          <Text style={styles.panelTitle}>Attractions in {city.name}</Text>
          {!loading ? (
            <Text style={styles.panelSub}>Sorted by fit, route context and time - {attractions.length} found</Text>
          ) : null}
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
        ) : attractions.length === 0 ? (
          <View style={styles.loadingWrap}>
            <Text style={styles.loadingText}>No attractions available for this city.</Text>
          </View>
        ) : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.listContent}>
            {attractions.map((attraction, index) => (
              <AttractionRow
                key={attraction.id ?? index}
                attraction={attraction}
                first={index === 0}
                onPress={() => onAttractionSelect?.(attraction)}
              />
            ))}
          </ScrollView>
        )}
      </BottomPanel>
    </View>
  );
}

function AttractionRow({ attraction, first, onPress }) {
  const fitLabel = groupFitLabel(attraction);
  const explanation = primaryExplanation(attraction);

  return (
    <TouchableOpacity activeOpacity={0.82} onPress={onPress} style={[styles.row, first && styles.rowFirst]}>
      <TripImage uri={attraction.image_url} width={56} height={56} borderRadius={12} />

      <View style={styles.info}>
        <Text style={styles.name} numberOfLines={1}>{attraction.name}</Text>
        <View style={styles.tagsRow}>
          {(attraction.tags || []).slice(0, 2).map((tag) => (
            <View key={tag} style={styles.tag}>
              <Text style={styles.tagText} numberOfLines={1}>{formatTag(tag)}</Text>
            </View>
          ))}
        </View>
        {attraction.meta ? <Text style={styles.meta}>{attraction.meta}</Text> : null}
        {explanation ? <Text style={styles.reasonText} numberOfLines={2}>{explanation}</Text> : null}
        {fitLabel ? <Text style={styles.groupFitText}>{fitLabel}</Text> : null}
        <Text style={styles.scoreLabel}>{scoreText(attraction)}</Text>
      </View>

      <View style={styles.scoreCircle} pointerEvents="none">
        <Text style={styles.scoreText}>{scorePct(attraction)}</Text>
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
  dayIndicator: {
    position: 'absolute',
    left: 16,
    borderRadius: 100,
    paddingVertical: 8,
    paddingHorizontal: 14,
    backgroundColor: 'rgba(255,255,255,0.92)',
  },
  dayIndicatorText: { fontFamily: 'Inter_600SemiBold', fontSize: 12, color: C.ink, fontWeight: '600' },
  panelHeader: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 },
  panelTitle: { fontSize: 23, ...TYPE.serifItalic, color: C.ink },
  panelSub: { fontSize: 12, color: C.sub, marginTop: 2 },
  capacityWrap: { paddingHorizontal: 16, marginBottom: 8 },
  capacityRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  capacityLabel: { fontSize: 11, color: C.sub, fontFamily: 'Inter_400Regular' },
  capacityValue: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium' },
  capacityFull: { color: '#E76F51' },
  barTrack: { height: 5, borderRadius: 100, backgroundColor: C.tagBg, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 100 },
  fullText: { fontSize: 12, color: '#E76F51', fontFamily: 'Inter_400Regular', marginTop: 6, textAlign: 'center' },
  listContent: { paddingHorizontal: 16, paddingBottom: 24, gap: 10 },
  row: {
    flexDirection: 'row',
    gap: 12,
    padding: 10,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
  },
  rowFirst: {
    borderColor: C.primary,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.14,
    shadowRadius: 10,
    elevation: 4,
  },
  info: { flex: 1, gap: 4 },
  name: { fontSize: 15, fontWeight: '800', color: C.ink, fontFamily: 'Inter_400Regular' },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  tag: { backgroundColor: C.tagBg, borderRadius: 100, paddingVertical: 3, paddingHorizontal: 8 },
  tagText: { fontSize: 10, color: C.primary, fontFamily: 'Inter_500Medium' },
  meta: { fontSize: 11, color: C.sub },
  reasonText: { fontSize: 11, color: C.ink, fontFamily: 'Inter_400Regular', lineHeight: 16 },
  groupFitText: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium', fontWeight: '700' },
  scoreLabel: { fontSize: 10, color: C.sub, fontFamily: 'Inter_500Medium' },
  scoreCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreText: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium', fontWeight: '700' },
  loadingWrap: { alignItems: 'center', marginTop: 32 },
  loadingText: { textAlign: 'center', color: C.sub, marginTop: 12, fontFamily: 'Inter_400Regular', fontSize: 13 },
});
