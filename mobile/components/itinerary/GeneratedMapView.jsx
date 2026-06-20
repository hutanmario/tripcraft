import { useEffect, useRef, useState } from 'react';
import { Animated, Dimensions, ScrollView, StyleSheet, Text, View } from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MapWebView from '../interactive/MapWebView';
import TripImage from '../interactive/TripImage';
import { formatTag } from '../../constants/interactive';
import { COLORS, FONTS, RADIUS, SHADOWS, TYPE } from '../../constants/theme';

const { height: SCREEN_HEIGHT, width: SCREEN_WIDTH } = Dimensions.get('window');

export default function GeneratedMapView({
  plan,
  routePoints,
  activeDay,
  onDayChange,
  onStoryMode,
  onSummary,
  onBack,
}) {
  const insets = useSafeAreaInsets();
  const currentDay = plan.days.find((d) => d.day_number === activeDay) || plan.days[0];
  const sheetY = useRef(new Animated.Value(0)).current;
  const [sheetExpanded, setSheetExpanded] = useState(true);

  const sheetHeight = Math.min(SCREEN_HEIGHT * 0.5, SCREEN_HEIGHT - insets.top - 118);
  const collapsedHeight = Math.min(128 + insets.bottom, sheetHeight);
  const collapsedOffset = Math.max(sheetHeight - collapsedHeight, 0);
  const cardWidth = Math.min(228, Math.max(204, SCREEN_WIDTH * 0.56));

  useEffect(() => {
    Animated.spring(sheetY, {
      toValue: sheetExpanded ? 0 : collapsedOffset,
      tension: 72,
      friction: 12,
      useNativeDriver: true,
    }).start();
  }, [sheetExpanded, collapsedOffset, sheetY]);

  useEffect(() => {
    setSheetExpanded(true);
  }, [activeDay]);

  if (!currentDay) return null;

  const dayRoutePoints = (currentDay.route_points?.length ? currentDay.route_points : currentDay.attractions)
    .filter((p) => p.lat && (p.lng ?? p.lon))
    .map((p, index) => ({
      id: index + 1,
      lat: p.lat,
      lng: p.lng ?? p.lon,
      label: String(index + 1),
    }));

  const fallbackDaysWithCoords = plan.days.filter((d) => d.lat && d.lng);
  const avgLat = fallbackDaysWithCoords.reduce((s, d) => s + d.lat, 0) / Math.max(fallbackDaysWithCoords.length, 1);
  const avgLng = fallbackDaysWithCoords.reduce((s, d) => s + d.lng, 0) / Math.max(fallbackDaysWithCoords.length, 1);
  const dayAvgLat = dayRoutePoints.reduce((s, p) => s + p.lat, 0) / Math.max(dayRoutePoints.length, 1);
  const dayAvgLng = dayRoutePoints.reduce((s, p) => s + p.lng, 0) / Math.max(dayRoutePoints.length, 1);
  const center = currentDay.lat && currentDay.lng
    ? { lat: currentDay.lat, lng: currentDay.lng }
    : dayRoutePoints.length
      ? { lat: dayAvgLat, lng: dayAvgLng }
      : { lat: avgLat, lng: avgLng };

  const markers = dayRoutePoints.length
    ? dayRoutePoints
    : fallbackDaysWithCoords.map((d) => ({
      id: d.day_number,
      lat: d.lat,
      lng: d.lng,
      label: String(d.day_number),
    }));
  const cityReason = currentDay.city_group_explanation?.summary || currentDay.city_explanations?.[0];

  function expandSheet() {
    setSheetExpanded(true);
  }

  function toggleSheet() {
    setSheetExpanded((value) => !value);
  }

  function handleDayChange(dayNumber) {
    setSheetExpanded(true);
    onDayChange(dayNumber);
  }

  function handleMarkerPress(id) {
    setSheetExpanded(true);
    if (!dayRoutePoints.length) onDayChange(Number(id));
  }

  return (
    <View style={styles.root}>
      <MapWebView
        key={`generated-day-map-${activeDay}`}
        markers={markers}
        center={center}
        zoom={dayRoutePoints.length ? 13 : 6}
        mode={dayRoutePoints.length ? 'city' : 'country'}
        routePoints={dayRoutePoints.length ? dayRoutePoints : routePoints}
        routeMode={dayRoutePoints.length ? 'foot' : 'driving'}
        routeStyle="solid"
        activeMarkerId={dayRoutePoints.length ? null : activeDay}
        onMarkerPress={handleMarkerPress}
        onMapPress={expandSheet}
      />

      <View style={[styles.topOverlay, { paddingTop: insets.top + 10 }]}>
        <View style={styles.topRow}>
          <TouchableOpacity style={styles.countryPill} onPress={onBack} activeOpacity={0.85}>
            <Ionicons name="chevron-back" size={19} color={COLORS.ink} />
            <Text style={styles.countryText} numberOfLines={1}>{plan.country}</Text>
          </TouchableOpacity>

          <View style={styles.dayPill}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.dayPillContent}>
              {plan.days.map((d) => (
                <TouchableOpacity
                  key={d.day_number}
                  style={[styles.dayBtn, activeDay === d.day_number && styles.dayBtnActive]}
                  onPress={() => handleDayChange(d.day_number)}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.dayBtnText, activeDay === d.day_number && styles.dayBtnTextActive]}>
                    D{d.day_number}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        </View>

        <View style={styles.routeStrip}>
          <Text style={styles.routeIndex}>{String(activeDay).padStart(2, '0')}</Text>
          <Text style={styles.routeTitle}>Map View</Text>
          <Text style={styles.routeMeta} numberOfLines={1}>
            Generated route - {currentDay.city}
          </Text>
        </View>
      </View>

      <Animated.View
        style={[
          styles.sheet,
          {
            height: sheetHeight,
            paddingBottom: insets.bottom + 8,
            transform: [{ translateY: sheetY }],
          },
        ]}
      >
        <TouchableOpacity style={styles.sheetHandleArea} activeOpacity={0.8} onPress={toggleSheet}>
          <View style={styles.sheetHandle} />
          <Ionicons
            name={sheetExpanded ? 'chevron-down' : 'chevron-up'}
            size={17}
            color={COLORS.muted}
            style={styles.sheetChevron}
          />
        </TouchableOpacity>

        <View style={styles.actionRow}>
          <TouchableOpacity style={styles.actionPrimary} onPress={onStoryMode} activeOpacity={0.85}>
            <Ionicons name="book-outline" size={17} color={COLORS.surface} />
            <Text style={styles.actionPrimaryText}>Story Mode</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionSecondary} onPress={onSummary} activeOpacity={0.85}>
            <Ionicons name="list-outline" size={17} color={COLORS.primary} />
            <Text style={styles.actionSecondaryText}>Summary</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.panelHeader}>
          <Text style={styles.panelTitle}>Day {activeDay} - {currentDay.city}</Text>
          <Text style={styles.panelStops}>{currentDay.attractions.length} stops</Text>
        </View>

        <ScrollView
          style={styles.sheetScroll}
          contentContainerStyle={styles.sheetScrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.cityReasonBox}>
            <View style={styles.cityReasonTop}>
              <Text style={styles.cityReasonLabel}>WHY THIS CITY</Text>
              <Text style={styles.cityScore}>{currentDay.city_score}% fit</Text>
            </View>
            {cityReason ? (
              <Text style={styles.cityReasonText}>{cityReason}</Text>
            ) : null}
            <View style={styles.cityTags}>
              {(currentDay.city_tags || []).slice(0, 4).map((tag) => (
                <View key={tag} style={styles.cityTag}>
                  <Text style={styles.cityTagText}>{formatTag(tag)}</Text>
                </View>
              ))}
            </View>
          </View>

          <View style={styles.attractionsTop}>
            <Text style={styles.attractionsLabel}>ATTRACTIONS</Text>
            <Text style={styles.attractionsHint}>Swipe sideways</Text>
          </View>

          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.cardRow}
          >
            {currentDay.attractions.map((a) => (
              <View key={a.id} style={[styles.card, { width: cardWidth }]}>
                <TripImage uri={a.image_url} width={cardWidth} height={122} />
                <View style={styles.cardBody}>
                  <Text style={styles.cardName} numberOfLines={2}>{a.name}</Text>
                  <View style={styles.cardTags}>
                    {(a.tags || []).slice(0, 4).map((t) => (
                      <View key={t} style={styles.tag}>
                        <Text style={styles.tagText}>{formatTag(t)}</Text>
                      </View>
                    ))}
                  </View>
                  {a.explanations?.[0] ? (
                    <Text style={styles.cardReason} numberOfLines={3}>{a.explanations[0]}</Text>
                  ) : null}
                  <View style={styles.cardMeta}>
                    <Text style={styles.cardDur}>
                      {a.avg_duration_hours ? `~${a.avg_duration_hours}h` : '-'}
                    </Text>
                    <Text style={styles.cardScore}>{a.score}% match</Text>
                  </View>
                </View>
              </View>
            ))}
          </ScrollView>
        </ScrollView>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },
  topOverlay: {
    position: 'absolute',
    left: 14,
    right: 14,
    top: 0,
    zIndex: 30,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  countryPill: {
    minWidth: 122,
    maxWidth: 154,
    height: 46,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    ...SHADOWS.md,
  },
  countryText: {
    flex: 1,
    ...TYPE.serifItalic,
    fontSize: 20,
    lineHeight: 23,
    color: COLORS.ink,
  },
  dayPill: {
    flex: 1,
    height: 46,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    overflow: 'hidden',
    ...SHADOWS.md,
  },
  dayPillContent: {
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 6,
    minHeight: 44,
  },
  dayBtn: {
    minWidth: 39,
    height: 34,
    borderRadius: RADIUS.full,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
  dayBtnActive: {
    backgroundColor: COLORS.primary,
  },
  dayBtnText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 12,
    color: COLORS.sub,
  },
  dayBtnTextActive: {
    color: COLORS.surface,
  },
  routeStrip: {
    marginTop: 8,
    alignSelf: 'flex-start',
    borderRadius: RADIUS.full,
    backgroundColor: 'rgba(255,255,255,0.84)',
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  routeIndex: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.primary,
  },
  routeTitle: {
    fontFamily: FONTS.sansBold,
    fontSize: 12,
    color: COLORS.ink,
  },
  routeMeta: {
    maxWidth: SCREEN_WIDTH * 0.52,
    fontFamily: FONTS.sans,
    fontSize: 10,
    color: COLORS.sub,
  },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 40,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    backgroundColor: COLORS.surface,
    borderTopWidth: 1,
    borderColor: COLORS.borderSoft,
    overflow: 'hidden',
    ...SHADOWS.lg,
  },
  sheetHandleArea: {
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sheetHandle: {
    width: 52,
    height: 5,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.border,
  },
  sheetChevron: {
    position: 'absolute',
    right: 22,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 20,
    marginBottom: 10,
  },
  actionPrimary: {
    flex: 1,
    height: 46,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.navy,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  actionPrimaryText: {
    ...TYPE.serifItalic,
    fontSize: 19,
    color: COLORS.surface,
  },
  actionSecondary: {
    flex: 1,
    height: 46,
    borderRadius: RADIUS.full,
    borderWidth: 1.5,
    borderColor: COLORS.primary,
    backgroundColor: COLORS.surface,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  actionSecondaryText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 14,
    color: COLORS.primary,
  },
  panelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    paddingHorizontal: 20,
    paddingBottom: 9,
  },
  panelTitle: {
    flex: 1,
    fontSize: 25,
    ...TYPE.serifItalic,
    color: COLORS.ink,
  },
  panelStops: {
    fontSize: 11,
    fontFamily: FONTS.mono,
    color: COLORS.primary,
  },
  sheetScroll: {
    flex: 1,
  },
  sheetScrollContent: {
    paddingBottom: 28,
  },
  cityReasonBox: {
    marginHorizontal: 20,
    marginBottom: 14,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    backgroundColor: COLORS.paper,
    padding: 12,
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
    letterSpacing: 0,
  },
  cityScore: {
    fontSize: 10,
    fontFamily: FONTS.mono,
    color: COLORS.primary,
  },
  cityReasonText: {
    fontSize: 13,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    lineHeight: 19,
    marginTop: 8,
  },
  cityTags: {
    flexDirection: 'row',
    gap: 6,
    flexWrap: 'wrap',
    marginTop: 10,
  },
  cityTag: {
    backgroundColor: COLORS.tagBg,
    borderRadius: RADIUS.full,
    paddingVertical: 5,
    paddingHorizontal: 9,
  },
  cityTagText: {
    fontSize: 10,
    color: COLORS.primary,
    fontFamily: FONTS.mono,
  },
  attractionsTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginBottom: 8,
  },
  attractionsLabel: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.primary,
  },
  attractionsHint: {
    fontFamily: FONTS.sans,
    fontSize: 11,
    color: COLORS.muted,
  },
  cardRow: {
    paddingHorizontal: 20,
    paddingBottom: 8,
    gap: 14,
    flexDirection: 'row',
  },
  card: {
    minHeight: 264,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    overflow: 'hidden',
    backgroundColor: COLORS.surface,
    ...SHADOWS.md,
  },
  cardBody: {
    padding: 12,
  },
  cardName: {
    fontSize: 15,
    lineHeight: 19,
    color: COLORS.ink,
    fontFamily: FONTS.sansBold,
  },
  cardTags: {
    flexDirection: 'row',
    gap: 5,
    marginTop: 8,
    flexWrap: 'wrap',
  },
  tag: {
    backgroundColor: COLORS.tagBg,
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  tagText: {
    fontSize: 10,
    color: COLORS.primary,
    fontFamily: FONTS.mono,
  },
  cardReason: {
    fontSize: 11,
    color: COLORS.sub,
    fontFamily: FONTS.sans,
    lineHeight: 16,
    marginTop: 9,
  },
  cardMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
  },
  cardDur: {
    fontSize: 12,
    color: COLORS.sub,
    fontFamily: FONTS.sans,
  },
  cardScore: {
    fontSize: 11,
    fontFamily: FONTS.mono,
    color: COLORS.primary,
  },
});
