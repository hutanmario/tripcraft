import {
  useEffect,
  useState } from 'react';
import { ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View
} from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { useSafeAreaInsets } from 'react-native-safe-area-context';
import TripImage from './TripImage';
import { C, fetchOSRMDistance, formatTag, groupFitLabel, primaryExplanation, scoreText } from '../../constants/interactive';
import { FONTS, TYPE } from '../../constants/theme';

export default function SuggestedPanel({
  addedAttraction,
  cityName,
  suggested = [],
  loading = false,
  onSuggestedSelect,
  onChooseAnother,
  onFindNextCity,
  onViewSummary,
}) {
  const insets = useSafeAreaInsets();
  const [distances, setDistances] = useState({});

  useEffect(() => {
    let cancelled = false;
    if (!addedAttraction?.lat || !addedAttraction?.lng || suggested.length === 0) return undefined;
    setDistances({});

    suggested.forEach(async (item) => {
      if (!item.lat || !item.lng) return;
      try {
        const text = await fetchOSRMDistance(addedAttraction, item);
        const km = text.split(' km')[0];
        if (!cancelled) setDistances((prev) => ({ ...prev, [item.id]: `${km} km away` }));
      } catch {
        if (!cancelled) setDistances((prev) => ({ ...prev, [item.id]: null }));
      }
    });

    return () => {
      cancelled = true;
    };
  }, [addedAttraction, suggested]);

  return (
    <View style={styles.fullscreen} pointerEvents="box-none">
      <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={onChooseAnother} />

      <View style={styles.sheet}>
        <View style={styles.dragHandle} />

        <View style={styles.header}>
          <View style={styles.checkCircle}>
            <Text style={styles.checkMark}>✓</Text>
          </View>
          <View style={styles.headerText}>
            <Text style={styles.addedTitle}>Added</Text>
            <Text style={styles.addedSub}>Route-aware suggestions for this day</Text>
          </View>
        </View>

        {loading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={C.primary} />
            <Text style={styles.loadingText}>Loading recommendations...</Text>
          </View>
        ) : suggested.length === 0 ? (
          <View style={styles.loadingWrap}>
            <Text style={styles.loadingText}>No more strong suggestions in this city.</Text>
          </View>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.cardsRow}>
            {suggested.map((item) => (
              <TallCard
                key={item.id}
                item={item}
                distance={distances[item.id]}
                onPress={() => onSuggestedSelect?.(item)}
              />
            ))}
          </ScrollView>
        )}

        <View style={[styles.actions, { paddingBottom: insets.bottom + 12 }]}>
          {onViewSummary ? (
            <TouchableOpacity style={styles.summaryBtn} activeOpacity={0.8} onPress={onViewSummary}>
              <Text style={styles.summaryBtnText}>View Trip Summary</Text>
            </TouchableOpacity>
          ) : null}
          <TouchableOpacity style={styles.ghostBtn} activeOpacity={0.8} onPress={onChooseAnother}>
            <Text style={styles.ghostBtnText}>Choose another attraction in {cityName || 'this city'}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.primaryBtn} activeOpacity={0.85} onPress={onFindNextCity}>
            <Text style={styles.primaryBtnText}>Find next city</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

function TallCard({ item, distance, onPress }) {
  const fitLabel = groupFitLabel(item);
  const explanation = primaryExplanation(item);

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.9} style={styles.card}>
      <View style={styles.cardTop}>
        <TripImage uri={item.image_url} style={StyleSheet.absoluteFillObject} />
        <View style={styles.cardTopOverlay} />
        <View style={styles.cardHint}>
          <Text style={styles.cardHintText}>{'>'}</Text>
        </View>
      </View>
      <View style={styles.cardBody}>
        <Text style={styles.cardName} numberOfLines={1}>{item.name}</Text>
        <View style={styles.tagsRow}>
          {(item.tags || []).map((tag) => (
            <View key={tag} style={styles.tag}>
              <Text style={styles.tagText}>{formatTag(tag)}</Text>
            </View>
          ))}
        </View>
        <View style={styles.cardFooter}>
          <Text style={styles.cardMeta}>{item.meta || 'Flexible stop'}</Text>
        </View>
        <Text style={styles.cardScore}>{scoreText(item)}</Text>
        {explanation ? <Text style={styles.reasonText} numberOfLines={2}>{explanation}</Text> : null}
        {fitLabel ? <Text style={styles.groupFitText}>{fitLabel}</Text> : null}
        {distance !== null ? (
          <Text style={styles.distanceText}>{distance === undefined ? 'Calculating route...' : distance}</Text>
        ) : (
          <Text style={styles.distanceMuted}>Route unavailable</Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  fullscreen: { ...StyleSheet.absoluteFillObject, zIndex: 50 },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(13,27,42,0.45)' },
  sheet: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: '64%',
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    overflow: 'hidden',
  },
  dragHandle: {
    width: 36,
    height: 4,
    borderRadius: 100,
    backgroundColor: 'rgba(26,26,46,0.15)',
    alignSelf: 'center',
    marginTop: 12,
    marginBottom: 4,
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 20, paddingVertical: 14 },
  checkCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(76,175,80,0.14)',
    borderWidth: 1.5,
    borderColor: 'rgba(76,175,80,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkMark: { fontSize: 22, color: '#4CAF50' },
  headerText: { gap: 2, flex: 1 },
  addedTitle: { fontSize: 21, ...TYPE.serif, color: C.ink },
  addedSub: { fontSize: 13, color: C.sub, fontFamily: 'Inter_400Regular' },
  cardsRow: { paddingHorizontal: 20, gap: 12, paddingBottom: 8 },
  card: {
    width: 210,
    borderRadius: 16,
    backgroundColor: '#FFFFFF',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: C.border,
    shadowColor: '#0D1B2A',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
  cardTop: { height: 118, backgroundColor: C.primary, overflow: 'hidden' },
  cardTopOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(13,40,46,0.25)' },
  cardBody: { padding: 12, gap: 6 },
  cardName: { fontSize: 15, fontWeight: '700', color: C.ink, fontFamily: 'Inter_400Regular' },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  tag: { backgroundColor: C.tagBg, borderRadius: 100, paddingVertical: 3, paddingHorizontal: 8 },
  tagText: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium' },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 },
  cardMeta: { fontSize: 12, color: C.sub, fontFamily: 'Inter_400Regular' },
  cardScore: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium', fontWeight: '700' },
  reasonText: { fontSize: 11, color: C.ink, fontFamily: 'Inter_400Regular', lineHeight: 16 },
  groupFitText: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium', fontWeight: '700' },
  distanceText: { fontSize: 11, color: C.primary, fontFamily: 'Inter_500Medium', marginTop: 4 },
  distanceMuted: { fontSize: 11, color: C.sub, fontFamily: 'Inter_500Medium', marginTop: 4 },
  cardHint: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 24,
    height: 24,
    borderRadius: 100,
    backgroundColor: 'rgba(255,255,255,0.86)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  cardHintText: { fontFamily: 'Inter_600SemiBold', fontSize: 12, color: C.primary, fontWeight: '600' },
  loadingWrap: { alignItems: 'center', marginTop: 32, paddingHorizontal: 20 },
  loadingText: { textAlign: 'center', color: C.sub, marginTop: 12, fontFamily: 'Inter_400Regular', fontSize: 13 },
  actions: { gap: 10, paddingHorizontal: 20, paddingTop: 8 },
  summaryBtn: {
    height: 50,
    borderRadius: 100,
    borderWidth: 1.5,
    borderColor: C.primary,
    backgroundColor: 'transparent',
    justifyContent: 'center',
    alignItems: 'center',
  },
  summaryBtnText: { fontSize: 13, color: C.primary, fontFamily: 'Inter_400Regular', fontWeight: '600' },
  ghostBtn: {
    height: 50,
    borderRadius: 100,
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  ghostBtnText: { fontSize: 13, color: C.ink, fontFamily: 'Inter_400Regular' },
  primaryBtn: {
    height: 52,
    borderRadius: 100,
    backgroundColor: C.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  primaryBtnText: { fontSize: 15, fontWeight: '600', color: '#FFFFFF', fontFamily: 'Inter_400Regular' },
});
