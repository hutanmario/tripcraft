import { View, Text, ScrollView, StyleSheet } from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { useSafeAreaInsets } from 'react-native-safe-area-context';
import TripImage from '../interactive/TripImage';
import { formatTag, groupFitLabel } from '../../constants/interactive';
import { COLORS, FONTS, RADIUS, SHADOWS, TYPE } from '../../constants/theme';

const GRADIENTS = ['#0D1B2A', '#0D2A1F', '#1A1A2E', '#2A1A0D'];

export default function StoryMode({
  plan,
  activeDay,
  onDayChange,
  onBack,
  onSave,
  saving = false,
  saved = false,
}) {
  const insets = useSafeAreaInsets();

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <TouchableOpacity onPress={onBack} activeOpacity={0.8}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Story Mode</Text>
        <View style={styles.dayTabs}>
          {plan.days.map((d) => (
            <TouchableOpacity key={d.day_number} onPress={() => onDayChange(d.day_number)} activeOpacity={0.7}>
              <Text style={[styles.dayTab, activeDay === d.day_number && styles.dayTabActive]}>
                D{d.day_number}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <ScrollView
        style={styles.scroll}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {plan.days.map((day, index) => (
          <View key={day.day_number}>
            <View style={[styles.introCard, { backgroundColor: GRADIENTS[index % GRADIENTS.length] }]}>
              <TripImage uri={day.city_image_url || day.attractions?.[0]?.image_url} style={StyleSheet.absoluteFillObject} />
              <View style={styles.introOverlay} />

              <View style={styles.dayBadge}>
                <Text style={styles.dayBadgeText}>{day.day_number}</Text>
              </View>

              <View style={styles.introInfo}>
                <Text style={styles.introLabel}>
                  {index === 0 ? 'FIRST, WE HEAD TO' : 'NEXT, WE HEAD TO'}
                </Text>
                <Text style={styles.introCity}>{day.city}</Text>
                <Text style={styles.introMeta}>
                  Day {day.day_number} - {day.attractions.length} stops - {day.total_hours || 0}h planned
                </Text>
              </View>
            </View>

            <View style={styles.cityReasonCard}>
              <View style={styles.cityReasonTop}>
                <Text style={styles.cityReasonLabel}>WHY THIS CITY</Text>
                <Text style={styles.cityScore}>{day.city_score}% city fit</Text>
              </View>
              {day.city_group_explanation?.summary || day.city_explanations?.[0] ? (
                <Text style={styles.cityReasonText} numberOfLines={3}>
                  {day.city_group_explanation?.summary || day.city_explanations?.[0]}
                </Text>
              ) : null}
              <View style={styles.cityTags}>
                {(day.city_tags || []).slice(0, 3).map((tag) => (
                  <View key={tag} style={styles.cityTag}>
                    <Text style={styles.cityTagText}>{formatTag(tag)}</Text>
                  </View>
                ))}
              </View>
            </View>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.attractionRow}
            >
              {day.attractions.map((a) => {
                const fit = groupFitLabel(a);
                return (
                  <View key={a.id} style={styles.attractionCard}>
                    <TripImage uri={a.image_url} width={200} height={260} />
                    <View style={styles.attractionOverlay}>
                      <View style={styles.attractionInfo}>
                        <Text style={styles.attractionName} numberOfLines={2}>{a.name}</Text>
                        <View style={styles.attractionTags}>
                          {(a.tags || []).slice(0, 2).map((t) => (
                            <View key={t} style={styles.glassTag}>
                              <Text style={styles.glassTagText}>{formatTag(t)}</Text>
                            </View>
                          ))}
                        </View>
                        {a.explanations?.[0] ? (
                          <Text style={styles.attractionReason} numberOfLines={2}>{a.explanations[0]}</Text>
                        ) : null}
                        {fit ? <Text style={styles.groupFit}>{fit}</Text> : null}
                        <View style={styles.attractionMeta}>
                          <Text style={styles.attractionDur}>
                            {a.avg_duration_hours ? `~${a.avg_duration_hours}h` : '-'}
                          </Text>
                          <Text style={styles.attractionScore}>{a.score}% match</Text>
                        </View>
                      </View>
                    </View>
                  </View>
                );
              })}
            </ScrollView>

            {index < plan.days.length - 1 && (
              <View style={styles.divider}>
                <View style={styles.dividerLine} />
                <Text style={styles.dividerDots}>...</Text>
                <View style={styles.dividerLine} />
              </View>
            )}
          </View>
        ))}

        <View style={[styles.saveBar, { paddingBottom: insets.bottom + 12 }]}>
          <TouchableOpacity
            onPress={onSave}
            activeOpacity={0.85}
            style={[styles.saveBtn, (saving || saved) && styles.saveBtnDisabled]}
            disabled={saving || saved}
          >
            <Text style={styles.saveBtnText}>
              {saved ? 'Saved' : saving ? 'Saving...' : 'Save This Trip'}
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.cream },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: COLORS.cream,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    paddingHorizontal: 20,
    paddingBottom: 12,
    zIndex: 10,
  },
  backText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
    fontFamily: FONTS.sansSemi,
  },
  headerTitle: {
    fontSize: 18,
    ...TYPE.serifItalic,
    color: COLORS.ink,
  },
  dayTabs: { flexDirection: 'row', gap: 8 },
  dayTab: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.sub,
    fontFamily: FONTS.sansSemi,
  },
  dayTabActive: { color: COLORS.primary },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 0 },
  introCard: {
    height: 220,
    overflow: 'hidden',
    justifyContent: 'flex-end',
  },
  introOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(13,27,42,0.48)',
  },
  dayBadge: {
    position: 'absolute',
    top: 20,
    right: 20,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(42,157,143,0.2)',
    borderWidth: 1.5,
    borderColor: 'rgba(42,157,143,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dayBadgeText: {
    fontSize: 16,
    fontWeight: '700',
    color: COLORS.primary,
    fontFamily: FONTS.sansBold,
  },
  introInfo: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 80,
  },
  introLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.6)',
    letterSpacing: 2,
    fontFamily: FONTS.sansMedium,
  },
  introCity: {
    fontSize: 42,
    ...TYPE.serifItalic,
    color: '#fff',
    marginTop: 4,
    lineHeight: 48,
  },
  introMeta: {
    fontSize: 12,
    fontFamily: FONTS.mono,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 6,
  },
  cityReasonCard: {
    marginHorizontal: 16,
    marginTop: 14,
    marginBottom: 2,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    backgroundColor: COLORS.surface,
    padding: 14,
    ...SHADOWS.sm,
  },
  cityReasonTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  cityReasonLabel: {
    fontSize: 10,
    fontFamily: FONTS.mono,
    color: COLORS.sub,
    letterSpacing: 1.5,
  },
  cityScore: {
    fontSize: 10,
    fontFamily: FONTS.mono,
    color: COLORS.primary,
  },
  cityReasonText: {
    fontSize: 12,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    lineHeight: 18,
    marginTop: 8,
  },
  cityTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 9 },
  cityTag: {
    backgroundColor: COLORS.tagBg,
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 9,
  },
  cityTagText: {
    fontSize: 10,
    fontFamily: FONTS.mono,
    color: COLORS.primary,
  },
  attractionRow: {
    paddingHorizontal: 16,
    paddingVertical: 16,
    gap: 12,
    flexDirection: 'row',
  },
  attractionCard: {
    width: 200,
    height: 260,
    borderRadius: RADIUS.lg,
    overflow: 'hidden',
    ...SHADOWS.lg,
  },
  attractionOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'flex-end',
  },
  attractionInfo: {
    backgroundColor: 'rgba(13,27,42,0.78)',
    padding: 14,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
  },
  attractionName: {
    fontSize: 18,
    ...TYPE.serifItalic,
    color: '#fff',
    lineHeight: 22,
  },
  attractionTags: { flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  glassTag: {
    backgroundColor: 'rgba(255,255,255,0.18)',
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  glassTagText: {
    fontSize: 10,
    fontFamily: FONTS.mono,
    color: '#fff',
  },
  attractionReason: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.72)',
    fontFamily: FONTS.sans,
    lineHeight: 15,
    marginTop: 8,
  },
  groupFit: {
    fontSize: 10,
    color: COLORS.primary,
    fontFamily: FONTS.mono,
    marginTop: 6,
  },
  attractionMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
  attractionDur: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.75)',
    fontFamily: FONTS.sans,
  },
  attractionScore: {
    fontSize: 11,
    fontFamily: FONTS.mono,
    color: COLORS.primary,
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginVertical: 8,
    gap: 12,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: COLORS.border },
  dividerDots: { fontSize: 14, letterSpacing: 4, color: COLORS.primary },
  saveBar: {
    paddingHorizontal: 20,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  saveBtn: {
    height: 52,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },
  saveBtnDisabled: { opacity: 0.65 },
  saveBtnText: {
    fontSize: 18,
    ...TYPE.serifItalic,
    color: '#fff',
  },
});
