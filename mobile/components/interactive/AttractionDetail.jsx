import { ScrollView, StyleSheet, Text, View } from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { useSafeAreaInsets } from 'react-native-safe-area-context';
import TripImage from './TripImage';
import { C, formatTag, groupFitLabel, memberReasonText, primaryExplanation, scoreText } from '../../constants/interactive';
import { FONTS, TYPE } from '../../constants/theme';

function feeText(value) {
  if (value == null) return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return n <= 0 ? 'Free entry' : `EUR ${n.toFixed(n % 1 === 0 ? 0 : 1)}`;
}

export default function AttractionDetail({ attraction, city, onBack, onAddToTrip }) {
  const insets = useSafeAreaInsets();
  if (!attraction) return null;

  const cityName = city?.name || city?.city || 'Selected city';
  const explanation = primaryExplanation(attraction);
  const fitLabel = groupFitLabel(attraction);
  const memberReasons = attraction?.group_explanation?.member_reasons || [];
  const stats = [
    attraction.avg_duration_hours ? `~${attraction.avg_duration_hours}h` : null,
    feeText(attraction.entry_fee_eur),
    attraction.rating ? `${Number(attraction.rating).toFixed(1)}/5 rating` : null,
    scoreText(attraction),
  ].filter(Boolean);

  return (
    <View style={styles.fullscreen} pointerEvents="box-none">
      <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={onBack} />

      <View style={styles.sheet}>
        <View style={styles.hero}>
          <TripImage uri={attraction.image_url} style={StyleSheet.absoluteFillObject} />
          <View style={styles.heroOverlay} />
          <View style={styles.dragHandle} />
          <View style={styles.heroBottom}>
            <Text style={styles.heroTitle}>{attraction.name}</Text>
            <Text style={styles.heroSub}>{cityName}</Text>
          </View>
        </View>

        <ScrollView style={styles.scrollBody} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <View style={styles.statsRow}>
            {stats.map((stat) => (
              <View key={stat} style={styles.statChip}>
                <Text style={styles.statChipText}>{stat}</Text>
              </View>
            ))}
          </View>

          <Text style={styles.sectionLabel}>Matched tags</Text>
          <View style={styles.tagsRow}>
            {(attraction.tags || []).map((tag) => (
              <View key={tag} style={styles.tagMatched}>
                <Text style={styles.tagMatchedText}>{formatTag(tag)}</Text>
              </View>
            ))}
          </View>

          <Text style={styles.sectionLabel}>Why this fits</Text>
          <View style={styles.explanationBox}>
            {explanation ? <Text style={styles.description}>{explanation}</Text> : null}
            {(attraction.explanations || []).slice(1, 4).map((item) => (
              <Text key={item} style={styles.reasonLine}>{item}</Text>
            ))}
            {fitLabel ? <Text style={styles.groupFitText}>{fitLabel}</Text> : null}
          </View>

          {memberReasons.length > 0 ? (
            <>
              <Text style={styles.sectionLabel}>Group signals</Text>
              <View style={styles.memberBox}>
                {memberReasons.slice(0, 4).map((member) => (
                  <Text key={member.user_id} style={styles.memberLine}>
                    {memberReasonText(member)}
                  </Text>
                ))}
              </View>
            </>
          ) : null}
        </ScrollView>

        <View style={[styles.actionBar, { paddingBottom: insets.bottom + 12 }]}>
          <TouchableOpacity style={styles.ghostBtn} activeOpacity={0.8} onPress={onBack}>
            <Text style={styles.ghostBtnText}>{'<'} Map</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.primaryBtn} activeOpacity={0.85} onPress={() => onAddToTrip?.(attraction)}>
            <Text style={styles.primaryBtnText}>Add to Trip</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fullscreen: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 50,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(13,27,42,0.45)',
  },
  sheet: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: '78%',
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    overflow: 'hidden',
  },
  hero: { height: 200, overflow: 'hidden' },
  heroOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 120,
    backgroundColor: 'rgba(13,40,46,0.70)',
  },
  dragHandle: {
    width: 36,
    height: 4,
    borderRadius: 100,
    backgroundColor: 'rgba(255,255,255,0.55)',
    alignSelf: 'center',
    marginTop: 12,
  },
  heroBottom: {
    position: 'absolute',
    bottom: 16,
    left: 20,
    right: 20,
  },
  heroTitle: {
    fontSize: 26,
    ...TYPE.serifItalic,
    color: '#FFFFFF',
  },
  heroSub: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.75)',
    fontFamily: 'Inter_400Regular',
    marginTop: 2,
  },
  scrollBody: { flex: 1 },
  scrollContent: { padding: 20, gap: 16 },
  statsRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  statChip: {
    backgroundColor: C.bg,
    borderRadius: 100,
    paddingVertical: 7,
    paddingHorizontal: 13,
  },
  statChipText: { fontSize: 12, fontWeight: '700', color: C.ink, fontFamily: 'Inter_400Regular' },
  sectionLabel: {
    fontSize: 12,
    fontFamily: 'Inter_700Bold',
    fontWeight: '700',
    letterSpacing: 0,
    color: C.sub,
    textTransform: 'uppercase',
  },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tagMatched: {
    backgroundColor: C.primary,
    borderRadius: 100,
    paddingVertical: 5,
    paddingHorizontal: 12,
  },
  tagMatchedText: { fontSize: 12, color: '#FFFFFF', fontFamily: 'Inter_400Regular' },
  explanationBox: {
    backgroundColor: C.bg,
    borderRadius: 14,
    padding: 14,
    gap: 8,
  },
  memberBox: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 14,
    padding: 14,
    gap: 7,
  },
  description: { fontSize: 14, color: C.ink, fontFamily: 'Inter_400Regular', lineHeight: 22 },
  reasonLine: { fontSize: 12, color: C.sub, fontFamily: 'Inter_400Regular', lineHeight: 18 },
  groupFitText: { fontSize: 12, color: C.primary, fontFamily: 'Inter_500Medium', fontWeight: '700' },
  memberLine: { fontSize: 12, color: C.ink, fontFamily: 'Inter_400Regular', lineHeight: 18 },
  actionBar: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 20,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: C.border,
    backgroundColor: '#FFFFFF',
  },
  ghostBtn: {
    height: 52,
    paddingHorizontal: 18,
    borderRadius: 100,
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  ghostBtnText: { fontSize: 14, color: C.ink, fontFamily: 'Inter_400Regular' },
  primaryBtn: {
    flex: 1,
    height: 52,
    borderRadius: 100,
    backgroundColor: C.primary,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },
  primaryBtnText: {
    fontSize: 18,
    ...TYPE.serifItalic,
    color: '#FFFFFF',
  },
});
