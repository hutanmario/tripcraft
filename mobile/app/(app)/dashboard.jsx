import {
  View,
  Text,
  ScrollView,
  Image,
  SafeAreaView,
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Animated,
  Dimensions
} from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { useCallback, useEffect, useState, useRef } from 'react';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window')
import { useFocusEffect, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from '../../context/AuthContext';
import { useQuiz } from '../../context/QuizContext';
import apiClient from '../../services/api';
import { getCurrentUserSessionId, removeCurrentUserSessionId } from '../../services/session';
import { COLORS, FONTS, SPACING, RADIUS, SHADOWS, TYPE } from '../../constants/theme';
import PlanTripModal from './components/PlanTripModal';
import { Ionicons } from '@expo/vector-icons';
import BottomTabBar from './components/BottomTabBar';
import EuropeHeatmap from './components/EuropeHeatmap';
import { countryFlag } from '../../constants/flags';

const DOT_COLORS = [COLORS.teal, COLORS.sage, COLORS.ink];

function slugToLabel(slug) {
  return slug
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function normalizedScore(countries, score) {
  if (!countries || countries.length === 0) return 82;
  const scores = countries.map((c) => c.score ?? 0);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  if (max === min) return 82;
  return Math.round(70 + (((score ?? 0) - min) / (max - min)) * 25);
}

function getCountryReasons(item, limit = 2) {
  return (item?.matching_reasons || [])
    .filter((reason) => reason?.reason)
    .slice(0, limit);
}

function getPrimaryReason(item) {
  const [reason] = getCountryReasons(item, 1);
  if (reason?.reason) return reason.reason;

  const tags = (item?.matching_tags || []).slice(0, 2).map(slugToLabel);
  if (tags.length > 0) return `Strong match for ${tags.join(' and ')}.`;
  return '';
}

function buildRegionInsight(countries) {
  const top = (countries || []).slice(0, 3).filter((country) => country?.country_name);
  if (top.length === 0) return '';

  const names = top.map((country) => country.country_name).join(', ').replace(/, ([^,]*)$/, ' and $1');
  const tags = [];
  top.forEach((country) => {
    (country.matching_tags || []).forEach((tag) => {
      const label = slugToLabel(tag);
      if (label && !tags.includes(label)) tags.push(label);
    });
  });

  if (tags.length > 0) {
    return `Your strongest map cluster leans toward ${names}, mostly driven by ${tags.slice(0, 3).join(', ').replace(/, ([^,]*)$/, ' and $1')}.`;
  }
  return `Your strongest map cluster currently leans toward ${names}.`;
}

function predictionConfidence(confidence, cardCount) {
  if (confidence?.label) {
    const value = Number(confidence.value ?? 0);
    const color = value >= 0.7 ? '#4A7C59' : value >= 0.45 ? '#2A9D8F' : '#C9A227';
    return { label: confidence.label, color };
  }
  if (!cardCount || cardCount < 5) return { label: 'Early signal', color: '#C9A227' };
  if (cardCount < 12) return { label: 'Medium confidence', color: '#2A9D8F' };
  return { label: 'High confidence', color: '#4A7C59' };
}

function planTimestamp(plan) {
  const time = Date.parse(plan?.saved_at || plan?.created_at || '');
  return Number.isFinite(time) ? time : 0;
}

function latestSavedPlan(plans) {
  return [...(plans || [])].sort((a, b) => planTimestamp(b) - planTimestamp(a))[0] || null;
}

function savedPlanTitle(plan) {
  const name = plan?.trip_name || plan?.country_name || 'your trip';
  return plan?.is_group ? `Continue ${name} with your group` : `Continue your ${name} itinerary`;
}

function savedPlanSubtitle(plan) {
  const pieces = [
    plan?.nr_zile ? `${plan.nr_zile} days` : null,
    plan?.nr_cities ? `${plan.nr_cities} cities` : null,
    plan?.total_stops ? `${plan.total_stops} stops` : null,
  ].filter(Boolean);
  return pieces.length ? pieces.join(' / ') : 'Pick up where you left off.';
}

export default function DashboardScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, logout } = useAuth();
  useQuiz(); // keep context alive

  const [profileData, setProfileData] = useState(null);
  const [resultsData, setResultsData] = useState(null);
  const [savedPlans, setSavedPlans] = useState([]);
  const [userData, setUserData] = useState(null);
  const [noQuiz, setNoQuiz] = useState(false);
  const [loading, setLoading] = useState(true);
  const [menuVisible, setMenuVisible] = useState(false);
  const [mapVisible, setMapVisible] = useState(false);
  const [mapPreviewCountry, setMapPreviewCountry] = useState(null);
  const [selectedCountry, setSelectedCountry] = useState(null);
  const [selectedCard, setSelectedCard] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const hasLoadedDashboard = useRef(false);
  const backdropOpacity = useRef(new Animated.Value(0)).current;
  const cardScale = useRef(new Animated.Value(0.9)).current;
  const cardOpacity = useRef(new Animated.Value(0)).current;

  function handleCardPress(item) {
    setSelectedCard(item);
    setShowModal(true);
    Animated.parallel([
      Animated.timing(backdropOpacity, { toValue: 1, duration: 300, useNativeDriver: true }),
      Animated.spring(cardScale, { toValue: 1, tension: 80, friction: 8, useNativeDriver: true }),
      Animated.timing(cardOpacity, { toValue: 1, duration: 250, useNativeDriver: true }),
    ]).start();
  }

  function handleClose() {
    Animated.parallel([
      Animated.timing(backdropOpacity, { toValue: 0, duration: 200, useNativeDriver: true }),
      Animated.timing(cardScale, { toValue: 0.9, duration: 200, useNativeDriver: true }),
      Animated.timing(cardOpacity, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => {
      setShowModal(false);
      setSelectedCard(null);
    });
  }

  function openPlanModal(item) {
    setSelectedCountry({ id: item.country_id, name: item.country_name, flag_emoji: countryFlag(item.country_name) });
  }

  function openSavedPlan(plan) {
    if (!plan) return;
    if (plan.source === 'fim') {
      router.push({
        pathname: '/(app)/interactive-mode',
        params: { planId: String(plan.plan_id), country: plan.country_name, readOnly: 'true' },
      });
      return;
    }

    router.push({
      pathname: '/(app)/generated-itinerary',
      params: {
        plan_id: String(plan.plan_id),
        ...(plan.group_trip_id ? { group_trip_id: String(plan.group_trip_id) } : {}),
      },
    });
  }

  function handleFullMapCountryPress(item) {
    setMapPreviewCountry(item);
    setMapVisible(false);
    setTimeout(() => handleCardPress(item), 250);
  }

  useEffect(() => {
    hasLoadedDashboard.current = false;
  }, [user?.id]);

  useFocusEffect(useCallback(() => {
    let cancelled = false;
    (async () => {
      try {
        if (!hasLoadedDashboard.current) setLoading(true);
        const raw = await AsyncStorage.getItem('user_data');
        if (!cancelled && raw) setUserData(JSON.parse(raw));

        const sessionId = await getCurrentUserSessionId(user);
        if (!sessionId) {
          if (!cancelled) {
            setNoQuiz(true);
            hasLoadedDashboard.current = true;
          }
          return;
        }
        if (!cancelled) setNoQuiz(false);
        try {
          const [profileRes, resultsRes, savedRes] = await Promise.allSettled([
            apiClient.get(`/quiz/v4/profile/${sessionId}`),
            apiClient.get(`/quiz/v4/results/${sessionId}`),
            apiClient.get('/itinerary/saved'),
          ]);
          if (profileRes.status !== 'fulfilled' || resultsRes.status !== 'fulfilled') {
            throw new Error('Could not load dashboard recommendations');
          }
          if (cancelled) return;
          setProfileData(profileRes.value.data);
          setResultsData(resultsRes.value.data);
          hasLoadedDashboard.current = true;
          if (savedRes.status === 'fulfilled') {
            setSavedPlans(savedRes.value.data?.plans || []);
          }
        } catch {
          if (!hasLoadedDashboard.current) {
            await removeCurrentUserSessionId(user);
            if (!cancelled) setNoQuiz(true);
          }
        }
      } catch {
        if (!cancelled && !hasLoadedDashboard.current) setNoQuiz(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [user?.id]));

  const fullName = user?.full_name || userData?.full_name || '';
  const initial = fullName ? fullName[0].toUpperCase() : '?';
  const firstName = fullName.split(' ')[0] || 'there';
  const profileTags = profileData?.profile || [];
  const leafTags = profileTags.length
    ? profileTags.filter((t) => t.is_leaf).slice(0, 8)
    : [];
  const topCountries = resultsData?.top_countries || [];
  const mapCountries = resultsData?.map_countries?.length
    ? resultsData.map_countries
    : topCountries;
  const latestPlan = latestSavedPlan(savedPlans);
  const topCountry = topCountries[0] || null;
  const selectedMapCountry = mapPreviewCountry && mapCountries.some((country) =>
    (country.iso2 || '').toUpperCase() === (mapPreviewCountry.iso2 || '').toUpperCase()
  )
    ? mapPreviewCountry
    : topCountry;
  const topCountryMatch = topCountry ? normalizedScore(mapCountries, topCountry.score ?? 0) : null;
  const selectedMapMatch = selectedMapCountry ? normalizedScore(mapCountries, selectedMapCountry.score ?? 0) : null;
  const primaryReason = getPrimaryReason(topCountry);
  const selectedMapReason = getPrimaryReason(selectedMapCountry);
  const selectedMapTags = (selectedMapCountry?.matching_tags || []).slice(0, 2);
  const regionInsight = buildRegionInsight(topCountries);
  const strongestSignals = (leafTags.length ? leafTags : profileTags)
    .filter((tag) => tag?.name)
    .slice(0, 3);

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingWrap}>
        <ActivityIndicator size="large" color={COLORS.teal} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      {/* ─── HEADER (absolute) ─── */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.brandRow}>
          <Text style={styles.brand}>TripCraft</Text>
          <View style={styles.brandDot} />
        </View>
        <View style={styles.userRow}>
          <Text style={styles.hiText}>Hi, {firstName}</Text>
          <TouchableOpacity
            style={styles.avatar}
            activeOpacity={0.8}
            onPress={() => setMenuVisible(true)}
          >
            <Text style={styles.avatarText}>{initial}</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.scrollContent, { paddingTop: insets.top + 60 }]}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── AVATAR BOTTOM SHEET ─── */}
        <Modal
          transparent
          visible={menuVisible}
          animationType="slide"
          onRequestClose={() => setMenuVisible(false)}
        >
          <Pressable style={styles.menuBackdrop} onPress={() => setMenuVisible(false)}>
            <View style={styles.menuSheet}>
              <View style={styles.menuDragHandle} />

              <TouchableOpacity
                style={styles.menuItem}
                activeOpacity={0.7}
                onPress={() => { setMenuVisible(false); router.push('/(app)/quiz/start'); }}
              >
                <Ionicons name="refresh-outline" size={20} color={COLORS.ink} />
                <Text style={styles.menuItemText}>Retake quiz</Text>
              </TouchableOpacity>

              <View style={styles.menuSep} />

              <TouchableOpacity
                style={styles.menuItem}
                activeOpacity={0.7}
                onPress={() => { setMenuVisible(false); logout(); router.replace('/(auth)/welcome'); }}
              >
                <Ionicons name="log-out-outline" size={20} color={COLORS.teal} />
                <Text style={[styles.menuItemText, styles.menuItemSignOut]}>Sign out</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.menuCancel}
                activeOpacity={0.7}
                onPress={() => setMenuVisible(false)}
              >
                <Text style={styles.menuCancelText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </Pressable>
        </Modal>

        {noQuiz ? (
          /* ─── NO QUIZ STATE ─── */
          <View style={styles.noQuizWrap}>
            <Text style={styles.noQuizTitle}>Ready to explore?</Text>
            <Text style={styles.noQuizSubtitle}>
              Take our quick quiz and we'll find your perfect travel match.
            </Text>
            <TouchableOpacity
              style={styles.inkBtn}
              activeOpacity={0.85}
              onPress={() => router.push('/(app)/quiz/start')}
            >
              <Text style={styles.inkBtnText}>Take the quiz →</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {latestPlan && (
              <View style={styles.section}>
                <TouchableOpacity
                  style={styles.nextActionCard}
                  activeOpacity={0.88}
                  onPress={() => openSavedPlan(latestPlan)}
                >
                  <View style={styles.nextActionTop}>
                    <View style={styles.nextActionIcon}>
                      <Ionicons name="play-circle-outline" size={22} color={COLORS.surface} />
                    </View>
                    <View style={styles.nextActionCopy}>
                      <Text style={styles.nextActionLabel}>NEXT BEST ACTION</Text>
                      <Text style={styles.nextActionTitle} numberOfLines={2}>
                        {savedPlanTitle(latestPlan)}
                      </Text>
                      <Text style={styles.nextActionSubtitle} numberOfLines={2}>
                        {savedPlanSubtitle(latestPlan)}
                      </Text>
                    </View>
                  </View>
                  <View style={styles.nextActionFooter}>
                    <View style={styles.nextActionPill}>
                      <Ionicons
                        name={latestPlan.is_group ? 'people-outline' : 'bookmark-outline'}
                        size={13}
                        color={COLORS.primary}
                      />
                      <Text style={styles.nextActionPillText}>
                        {latestPlan.is_group ? 'Group trip' : 'Saved trip'}
                      </Text>
                    </View>
                    <View style={styles.nextActionButton}>
                      <Text style={styles.nextActionButtonText}>Continue</Text>
                      <Ionicons name="chevron-forward" size={14} color={COLORS.surface} />
                    </View>
                  </View>
                </TouchableOpacity>
              </View>
            )}

            {/* ─── SECTION 1: YOUR PROFILE ─── */}
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>YOUR PROFILE</Text>
              <Text style={styles.sectionTitle}>
                Your travel <Text style={styles.italic}>tags.</Text>
              </Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.chipsRow}
              >
                {leafTags.map((tag, i) => (
                  <View key={tag.slug ?? tag.name ?? i} style={styles.chip}>
                    <View style={[styles.chipDot, { backgroundColor: DOT_COLORS[i % 3] }]} />
                    <Text style={styles.chipText}>{tag.name}</Text>
                  </View>
                ))}
              </ScrollView>
            </View>

            {/* ─── HEATMAP ─── */}
            <View style={styles.section}>
              <View style={styles.mapSectionHeader}>
                <Text style={styles.heatmapLabel}>YOUR MATCH MAP</Text>
                <TouchableOpacity
                  style={styles.openMapBtn}
                  activeOpacity={0.8}
                  onPress={() => setMapVisible(true)}
                >
                  <Ionicons name="expand-outline" size={14} color={COLORS.teal} />
                  <Text style={styles.openMapText}>Open map</Text>
                </TouchableOpacity>
              </View>
              <EuropeHeatmap
                countries={mapCountries}
                height={270}
                compact
                showLegend
                highlightedIso2={topCountry?.iso2}
                selectedIso2={selectedMapCountry?.iso2}
                onCountryPress={setMapPreviewCountry}
              />

              {selectedMapCountry && (
                <TouchableOpacity
                  style={styles.mapPreviewCard}
                  activeOpacity={0.86}
                  onPress={() => handleCardPress(selectedMapCountry)}
                >
                  <View style={styles.mapPreviewHeader}>
                    <View style={styles.mapPreviewTitleRow}>
                      <Text style={styles.mapPreviewFlag}>{countryFlag(selectedMapCountry.country_name)}</Text>
                      <View style={styles.mapPreviewTitleWrap}>
                        <Text style={styles.mapPreviewLabel}>
                          {selectedMapCountry.iso2 === topCountry?.iso2 ? 'Top country on your map' : 'Selected country'}
                        </Text>
                        <Text style={styles.mapPreviewCountry}>{selectedMapCountry.country_name}</Text>
                      </View>
                    </View>
                    <View style={styles.mapPreviewScore}>
                      <Text style={styles.mapPreviewScoreText}>{selectedMapMatch}%</Text>
                    </View>
                  </View>

                  <Text style={styles.mapPreviewReason} numberOfLines={2}>
                    {selectedMapReason || `This country has a measurable overlap with your quiz profile.`}
                  </Text>

                  <View style={styles.mapPreviewFooter}>
                    <View style={styles.mapPreviewTags}>
                      {selectedMapTags.map((tag) => (
                        <View key={tag} style={styles.mapPreviewTag}>
                          <Text style={styles.mapPreviewTagText}>{slugToLabel(tag)}</Text>
                        </View>
                      ))}
                    </View>
                    <View style={styles.mapPreviewLink}>
                      <Text style={styles.mapPreviewLinkText}>Details</Text>
                      <Ionicons name="chevron-forward" size={13} color={COLORS.primary} />
                    </View>
                  </View>
                </TouchableOpacity>
              )}

              {!!regionInsight && (
                <View style={styles.regionInsightCard}>
                  <View style={styles.regionInsightIcon}>
                    <Ionicons name="analytics-outline" size={14} color={COLORS.primary} />
                  </View>
                  <View style={styles.regionInsightCopy}>
                    <Text style={styles.regionInsightLabel}>WHY THIS REGION?</Text>
                    <Text style={styles.regionInsightText}>{regionInsight}</Text>
                  </View>
                </View>
              )}
            </View>

            {/* ─── SECTION 2: TOP MATCHES ─── */}
            <View style={styles.section}>
              <View style={styles.sectionHeaderRow}>
                <Text style={styles.sectionLabel}>TOP MATCHES</Text>
                <TouchableOpacity onPress={() => router.push('/(app)/destinations')}>
                  <Text style={styles.seeAll}>See all</Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.sectionTitle}>
                Where you <Text style={styles.italic}>should go.</Text>
              </Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.cardsRow}
              >
                {topCountries.slice(0, 3).map((item, i) => {
                  const matchPct = normalizedScore(mapCountries, item.score ?? 0);
                  const tags = (item.matching_tags || []).slice(0, 2);
                  const reason = getPrimaryReason(item);
                  const conf = predictionConfidence(resultsData?.confidence, profileData?.card_count);
                  return (
                    <TouchableOpacity
                      key={item.country_name ?? i}
                      style={styles.countryCard}
                      activeOpacity={0.88}
                      onPress={() => handleCardPress(item)}
                    >
                      <View style={styles.cardImageWrap}>
                        <Image
                          source={{ uri: item.image_url }}
                          style={styles.cardImage}
                          resizeMode="cover"
                        />
                        <View style={styles.scoreBadge}>
                          <Text style={styles.scoreBadgeText}>• {matchPct} %</Text>
                          <Text style={[styles.scorePredictedText, { color: conf.color }]}>
                            PREDICTED
                          </Text>
                        </View>
                      </View>
                      <View style={styles.cardBody}>
                        <View style={styles.cardNameRow}>
                          <Text style={styles.cardCountry}>{item.country_name}</Text>
                          <Text style={styles.cardCapital}>{item.capital}</Text>
                        </View>
                        <View style={styles.cardTagsRow}>
                          {tags.map((tag, ti) => (
                            <View key={ti} style={styles.cardTag}>
                              <Text style={styles.cardTagText}>{slugToLabel(tag)}</Text>
                            </View>
                          ))}
                        </View>
                        {!!reason && (
                          <View style={styles.cardReasonBox}>
                            <Ionicons name="sparkles-outline" size={12} color={COLORS.teal} />
                            <Text style={styles.cardReasonText} numberOfLines={2}>
                              {reason}
                            </Text>
                          </View>
                        )}
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>

              {topCountry && (
                <View style={styles.postMatchActions}>
                  {!latestPlan && topCountry && (
                    <TouchableOpacity
                      style={styles.nextActionCard}
                      activeOpacity={0.88}
                      onPress={() => openPlanModal(topCountry)}
                    >
                      <View style={styles.nextActionTop}>
                        <View style={styles.nextActionIcon}>
                          <Ionicons name="navigate-outline" size={22} color={COLORS.surface} />
                        </View>
                        <View style={styles.nextActionCopy}>
                          <Text style={styles.nextActionLabel}>NEXT BEST ACTION</Text>
                          <Text style={styles.nextActionTitle} numberOfLines={2}>
                            Plan your {topCountry?.country_name} trip
                          </Text>
                          <Text style={styles.nextActionSubtitle} numberOfLines={2}>
                            {primaryReason || `Your quiz points most strongly toward ${topCountry?.country_name}.`}
                          </Text>
                        </View>
                      </View>
                      <View style={styles.nextActionFooter}>
                        <View style={styles.nextActionPill}>
                          <Ionicons name="sparkles-outline" size={13} color={COLORS.primary} />
                          <Text style={styles.nextActionPillText}>{topCountryMatch}% match</Text>
                        </View>
                        <View style={styles.nextActionButton}>
                          <Text style={styles.nextActionButtonText}>Start planning</Text>
                          <Ionicons name="chevron-forward" size={14} color={COLORS.surface} />
                        </View>
                      </View>
                    </TouchableOpacity>
                  )}

                  {topCountry && (
                    <View style={styles.recommendationInsight}>
                      <View style={styles.insightHeader}>
                        <View style={styles.insightIcon}>
                          <Ionicons name="sparkles-outline" size={15} color={COLORS.primary} />
                        </View>
                        <View style={styles.insightTextWrap}>
                          <Text style={styles.insightLabel}>WHY {topCountry.country_name} RANKS FIRST</Text>
                          <Text style={styles.insightText}>
                            {primaryReason || 'It has the strongest overlap with your current travel profile.'}
                          </Text>
                        </View>
                      </View>

                      {strongestSignals.length > 0 && (
                        <View style={styles.signalRow}>
                          <Text style={styles.signalLabel}>Strongest signals</Text>
                          <View style={styles.signalChips}>
                            {strongestSignals.map((tag, index) => (
                              <View key={tag.slug || tag.name || index} style={styles.signalChip}>
                                <Text style={styles.signalChipText}>{tag.name}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}
                    </View>
                  )}
                </View>
              )}
            </View>

            {/* ─── SECTION 3: YOU MIGHT ALSO LOVE ─── */}
            {topCountries.length > 3 && (
              <View style={styles.section}>
                <Text style={[styles.sectionLabel, styles.mutedLabel]}>
                  YOU MIGHT ALSO LOVE
                </Text>
                <Text style={styles.sectionTitle}>Beyond your usual picks.</Text>
                <Text style={styles.sectionSubtitle}>
                  Places with smaller, but still explainable matches.
                </Text>
                <View style={styles.sideBySide}>
                  {topCountries.slice(3, 5).map((item, i) => {
                    const reason = getPrimaryReason(item);
                    return (
                      <TouchableOpacity
                        key={item.country_name ?? i}
                        style={styles.smallCard}
                        activeOpacity={0.88}
                        onPress={() => handleCardPress(item)}
                      >
                        <Image
                          source={{ uri: item.image_url }}
                          style={styles.smallCardImage}
                          resizeMode="cover"
                        />
                        <Text style={styles.smallCardName}>{item.country_name}</Text>
                        <Text style={styles.smallCardDesc} numberOfLines={3}>
                          {reason || item.description || `Explore ${item.country_name} with a personalized itinerary.`}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
            )}
          </>
        )}
      </ScrollView>

      {/* ─── ANIMATED COUNTRY MODAL ─── */}
      <Modal
        visible={mapVisible}
        animationType="slide"
        onRequestClose={() => setMapVisible(false)}
      >
        <SafeAreaView style={styles.mapModalSafe}>
          <View style={styles.mapModalHeader}>
            <View style={styles.mapModalTitleWrap}>
              <Text style={styles.mapModalLabel}>MATCH MAP</Text>
              <Text style={styles.mapModalTitle}>Explore your fit across Europe.</Text>
            </View>
            <TouchableOpacity
              style={styles.mapCloseBtn}
              activeOpacity={0.8}
              onPress={() => setMapVisible(false)}
            >
              <Ionicons name="close" size={20} color={COLORS.ink} />
            </TouchableOpacity>
          </View>

          <EuropeHeatmap
            countries={mapCountries}
            height={Math.max(430, SCREEN_HEIGHT - insets.top - insets.bottom - 168)}
            highlightedIso2={topCountry?.iso2}
            selectedIso2={selectedMapCountry?.iso2}
            onCountryPress={handleFullMapCountryPress}
          />

          <Text style={styles.mapModalHint}>
            Tap a country to see the recommendation reasons and plan options.
          </Text>
        </SafeAreaView>
      </Modal>

      <Modal visible={showModal} transparent animationType="none" onRequestClose={handleClose}>
        <Animated.View style={[StyleSheet.absoluteFillObject, styles.modalBackdrop, { opacity: backdropOpacity }]}>
          <TouchableOpacity style={{ flex: 1 }} onPress={handleClose} activeOpacity={1} />
        </Animated.View>

        <Animated.View style={[styles.modalCard, { transform: [{ scale: cardScale }], opacity: cardOpacity }]}>
          <View style={styles.modalHeader}>
            <View style={styles.modalTitleRow}>
              <Text style={styles.modalFlag}>{countryFlag(selectedCard?.country_name)}</Text>
              <View>
                <Text style={styles.modalCountryName}>{selectedCard?.country_name}</Text>
                {(() => {
                  const conf = predictionConfidence(resultsData?.confidence, profileData?.card_count);
                  const matchPct = normalizedScore(mapCountries, selectedCard?.score ?? 0);
                  return (
                    <View style={styles.modalPredictedRow}>
                      <Text style={styles.modalPredictedScore}>{matchPct}% predicted match</Text>
                      <View style={[styles.modalConfidencePill, { backgroundColor: conf.color + '22' }]}>
                        <View style={[styles.modalConfidenceDot, { backgroundColor: conf.color }]} />
                        <Text style={[styles.modalConfidenceText, { color: conf.color }]}>{conf.label}</Text>
                      </View>
                    </View>
                  );
                })()}
              </View>
            </View>
            <TouchableOpacity onPress={handleClose} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Text style={styles.modalClose}>✕</Text>
            </TouchableOpacity>
          </View>

          {(selectedCard?.matching_tags || []).length > 0 && (
            <View style={styles.modalTagsRow}>
              {(selectedCard.matching_tags || []).slice(0, 4).map((tag, i) => (
                <View key={i} style={styles.modalTag}>
                  <Text style={styles.modalTagText}>{slugToLabel(tag)}</Text>
                </View>
              ))}
            </View>
          )}

          <Text style={styles.modalDesc}>
            {selectedCard?.description || `Discover the beauty and culture of ${selectedCard?.country_name}.`}
          </Text>

          {getCountryReasons(selectedCard, 3).length > 0 && (
            <View style={styles.modalExplainBox}>
              <View style={styles.modalExplainHeader}>
                <Ionicons name="sparkles-outline" size={15} color={COLORS.teal} />
                <Text style={styles.modalExplainTitle}>Why this fits</Text>
              </View>
              {getCountryReasons(selectedCard, 3).map((reason, index) => (
                <View key={reason.tag_slug || reason.tag_name || index} style={styles.modalReasonItem}>
                  <Text style={styles.modalReasonTag}>
                    {reason.tag_name || slugToLabel(reason.tag_slug || 'match')}
                  </Text>
                  <Text style={styles.modalReasonText}>{reason.reason}</Text>
                </View>
              ))}
            </View>
          )}

          {(selectedCard?.penalty_reasons || []).length > 0 && (
            <View style={styles.modalExplainBox}>
              <View style={styles.modalExplainHeader}>
                <Ionicons name="alert-circle-outline" size={15} color={COLORS.teal} />
                <Text style={styles.modalExplainTitle}>Fit cautions</Text>
              </View>
              {(selectedCard.penalty_reasons || []).slice(0, 2).map((reason, index) => (
                <View key={reason.constraint || index} style={styles.modalReasonItem}>
                  <Text style={styles.modalReasonTag}>{reason.title || 'Constraint'}</Text>
                  <Text style={styles.modalReasonText}>{reason.reason}</Text>
                </View>
              ))}
            </View>
          )}

          <TouchableOpacity
            style={styles.modalPlanBtn}
            activeOpacity={0.85}
            onPress={() => {
              handleClose();
              setTimeout(() => openPlanModal(selectedCard), 300);
            }}
          >
            <Text style={styles.modalPlanBtnText}>Plan a trip to {selectedCard?.country_name}</Text>
          </TouchableOpacity>
        </Animated.View>
      </Modal>

      {selectedCountry && (
        <PlanTripModal
          visible={!!selectedCountry}
          country={selectedCountry}
          onClose={() => setSelectedCountry(null)}
        />
      )}

      <BottomTabBar />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },
  loadingWrap: {
    flex: 1,
    backgroundColor: COLORS.cream,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 80,
  },

  /* Header */
  header: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F5F1EA',
    paddingHorizontal: 24,
    paddingBottom: 12,
    borderBottomWidth: 0.5,
    borderBottomColor: '#E0DAD0',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  brand: {
    fontSize: 22,
    ...TYPE.serifItalic,
    color: COLORS.ink,
  },
  brandDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: COLORS.teal,
    marginTop: 2,
  },
  userRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
  },
  hiText: {
    fontSize: 14,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.ink,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontFamily: FONTS.sans,
    fontWeight: '700',
  },

  /* No quiz */
  noQuizWrap: {
    alignItems: 'center',
    paddingHorizontal: SPACING.xl,
    paddingTop: SPACING.xxl,
    gap: SPACING.md,
  },
  noQuizTitle: {
    fontSize: 30,
    ...TYPE.serif,
    color: COLORS.ink,
    textAlign: 'center',
  },
  noQuizSubtitle: {
    fontSize: 15,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    textAlign: 'center',
    lineHeight: 22,
  },
  inkBtn: {
    marginTop: SPACING.sm,
    backgroundColor: COLORS.ink,
    borderRadius: RADIUS.full,
    paddingVertical: 14,
    paddingHorizontal: SPACING.xl,
  },
  inkBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontFamily: FONTS.sans,
    fontWeight: '600',
  },

  /* Sections */
  section: {
    paddingHorizontal: SPACING.md,
    paddingTop: SPACING.lg,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  mapSectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  heatmapLabel: {
    fontFamily: 'JetBrainsMono_400Regular',
    fontSize: 10,
    color: '#888780',
    letterSpacing: 1.5,
  },
  openMapBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: RADIUS.full,
    backgroundColor: '#FFFFFF',
    paddingVertical: 5,
    paddingHorizontal: 10,
  },
  openMapText: {
    fontSize: 11,
    color: COLORS.teal,
    fontFamily: FONTS.sansMedium,
  },
  mapPreviewCard: {
    marginTop: SPACING.sm,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: SPACING.md,
    ...SHADOWS.sm,
  },
  mapPreviewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: SPACING.sm,
    marginBottom: 8,
  },
  mapPreviewTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    flex: 1,
  },
  mapPreviewFlag: {
    fontSize: 24,
  },
  mapPreviewTitleWrap: {
    flex: 1,
  },
  mapPreviewLabel: {
    fontSize: 10,
    color: COLORS.primary,
    fontFamily: FONTS.sansSemi,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  mapPreviewCountry: {
    fontSize: 19,
    color: COLORS.ink,
    ...TYPE.serifItalic,
  },
  mapPreviewScore: {
    backgroundColor: COLORS.primary,
    borderRadius: RADIUS.full,
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  mapPreviewScoreText: {
    fontSize: 12,
    color: COLORS.surface,
    fontFamily: FONTS.sansSemi,
  },
  mapPreviewReason: {
    fontSize: 12,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    lineHeight: 18,
  },
  mapPreviewFooter: {
    marginTop: SPACING.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: SPACING.sm,
  },
  mapPreviewTags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    flex: 1,
  },
  mapPreviewTag: {
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.tagBg,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  mapPreviewTagText: {
    fontSize: 10,
    color: COLORS.primary,
    fontFamily: FONTS.sansMedium,
  },
  mapPreviewLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  mapPreviewLinkText: {
    fontSize: 12,
    color: COLORS.primary,
    fontFamily: FONTS.sansSemi,
  },
  regionInsightCard: {
    marginTop: SPACING.sm,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: SPACING.sm,
    backgroundColor: COLORS.tagBg,
    borderRadius: RADIUS.md,
    padding: SPACING.md,
  },
  regionInsightIcon: {
    width: 28,
    height: 28,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  regionInsightCopy: {
    flex: 1,
  },
  regionInsightLabel: {
    fontSize: 10,
    color: COLORS.primary,
    fontFamily: FONTS.sansSemi,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  regionInsightText: {
    fontSize: 12,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    lineHeight: 18,
  },
  sectionLabel: {
    fontSize: 11,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    color: COLORS.teal,
    fontFamily: FONTS.sans,
    fontWeight: '600',
    marginBottom: 4,
  },
  mutedLabel: {
    color: COLORS.muted,
  },
  sectionTitle: {
    fontSize: 28,
    ...TYPE.serif,
    color: COLORS.ink,
    lineHeight: 34,
    marginBottom: SPACING.sm,
  },
  italic: {
    ...TYPE.serifItalic,
    color: COLORS.teal,
  },
  sectionSubtitle: {
    fontSize: 14,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    marginBottom: SPACING.md,
    lineHeight: 20,
  },
  seeAll: {
    fontSize: 13,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    textDecorationLine: 'underline',
    marginBottom: 4,
  },

  /* Next action */
  postMatchActions: {
    marginTop: SPACING.md,
  },
  nextActionCard: {
    backgroundColor: COLORS.ink,
    borderRadius: RADIUS.lg,
    padding: SPACING.md,
    gap: SPACING.md,
    ...SHADOWS.md,
  },
  nextActionTop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: SPACING.md,
  },
  nextActionIcon: {
    width: 44,
    height: 44,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  nextActionCopy: {
    flex: 1,
  },
  nextActionLabel: {
    fontSize: 10,
    color: COLORS.tagBg,
    fontFamily: FONTS.sansSemi,
    letterSpacing: 0,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  nextActionTitle: {
    fontSize: 24,
    color: COLORS.surface,
    ...TYPE.serifItalic,
    lineHeight: 28,
  },
  nextActionSubtitle: {
    marginTop: 8,
    fontSize: 13,
    color: '#D8D5CE',
    fontFamily: FONTS.sans,
    lineHeight: 19,
  },
  nextActionFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: SPACING.sm,
  },
  nextActionPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.full,
    paddingVertical: 7,
    paddingHorizontal: 11,
  },
  nextActionPillText: {
    fontSize: 12,
    color: COLORS.primary,
    fontFamily: FONTS.sansSemi,
  },
  nextActionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: COLORS.primary,
    borderRadius: RADIUS.full,
    paddingVertical: 9,
    paddingHorizontal: 14,
  },
  nextActionButtonText: {
    fontSize: 13,
    color: COLORS.surface,
    fontFamily: FONTS.sansSemi,
  },
  recommendationInsight: {
    marginTop: SPACING.sm,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: SPACING.md,
    ...SHADOWS.sm,
  },
  insightHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: SPACING.sm,
  },
  insightIcon: {
    width: 30,
    height: 30,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.tagBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  insightTextWrap: {
    flex: 1,
  },
  insightLabel: {
    fontSize: 10,
    color: COLORS.primary,
    fontFamily: FONTS.sansSemi,
    letterSpacing: 0,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  insightText: {
    fontSize: 13,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    lineHeight: 19,
  },
  signalRow: {
    marginTop: SPACING.md,
  },
  signalLabel: {
    fontSize: 11,
    color: COLORS.muted,
    fontFamily: FONTS.sansSemi,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  signalChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  signalChip: {
    backgroundColor: COLORS.cream,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingVertical: 5,
    paddingHorizontal: 10,
  },
  signalChipText: {
    fontSize: 11,
    color: COLORS.ink,
    fontFamily: FONTS.sansMedium,
  },

  /* Profile chips */
  chipsRow: {
    flexDirection: 'row',
    gap: SPACING.sm,
    paddingRight: SPACING.md,
    paddingBottom: SPACING.xs,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: '#FFFFFF',
  },
  chipDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  chipText: {
    fontSize: 13,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
  },

  /* Top matches horizontal cards */
  cardsRow: {
    flexDirection: 'row',
    gap: SPACING.md,
    paddingRight: SPACING.md,
    paddingBottom: SPACING.xs,
  },
  countryCard: {
    width: 240,
    backgroundColor: '#FFFFFF',
    borderRadius: RADIUS.md,
    overflow: 'hidden',
    ...SHADOWS.md,
  },
  cardImageWrap: {
    position: 'relative',
  },
  cardImage: {
    width: '100%',
    height: 140,
  },
  scoreBadge: {
    position: 'absolute',
    top: SPACING.sm,
    right: SPACING.sm,
    backgroundColor: COLORS.teal,
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: RADIUS.full,
  },
  scoreBadgeText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontFamily: FONTS.sans,
    fontWeight: '600',
  },
  scorePredictedText: {
    fontSize: 8,
    fontFamily: FONTS.sans,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginTop: 2,
    textAlign: 'center',
  },
  cardBody: {
    padding: 12,
  },
  cardNameRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: SPACING.xs,
    marginBottom: SPACING.xs,
  },
  cardCountry: {
    flex: 1,
    fontSize: 18,
    ...TYPE.serifStrong,
    color: COLORS.ink,
  },
  cardCapital: {
    fontSize: 12,
    ...TYPE.serifItalic,
    color: COLORS.muted,
  },
  cardTagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: SPACING.xs,
    marginBottom: SPACING.sm,
  },
  cardTag: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingVertical: 3,
    paddingHorizontal: 8,
  },
  cardTagText: {
    fontSize: 11,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
  },
  cardReasonBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    backgroundColor: COLORS.tagBg,
    borderRadius: RADIUS.sm,
    paddingVertical: 7,
    paddingHorizontal: 8,
  },
  cardReasonText: {
    flex: 1,
    fontSize: 11,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    lineHeight: 15,
  },

  /* Full map modal */
  mapModalSafe: {
    flex: 1,
    backgroundColor: COLORS.cream,
    paddingHorizontal: SPACING.md,
  },
  mapModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: SPACING.md,
    paddingBottom: SPACING.md,
  },
  mapModalTitleWrap: {
    flex: 1,
    paddingRight: SPACING.md,
  },
  mapModalLabel: {
    fontSize: 10,
    color: COLORS.teal,
    fontFamily: 'JetBrainsMono_400Regular',
    letterSpacing: 1.4,
    marginBottom: 6,
  },
  mapModalTitle: {
    fontSize: 24,
    color: COLORS.ink,
    ...TYPE.serifItalic,
  },
  mapCloseBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  mapModalHint: {
    fontSize: 12,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    lineHeight: 18,
    textAlign: 'center',
    paddingTop: 12,
  },

  /* Animated country modal */
  modalBackdrop: {
    backgroundColor: 'rgba(26,22,20,0.7)',
  },
  modalCard: {
    position: 'absolute',
    left: 20,
    right: 20,
    top: SCREEN_HEIGHT * 0.2,
    backgroundColor: '#F5F1EA',
    borderRadius: 20,
    padding: 24,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  modalFlag: {
    fontSize: 28,
  },
  modalCountryName: {
    ...TYPE.serifItalic,
    fontSize: 24,
    color: COLORS.ink,
  },
  modalPredictedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 4,
  },
  modalPredictedScore: {
    fontFamily: FONTS.sans,
    fontSize: 12,
    color: COLORS.muted,
    fontWeight: '500',
  },
  modalConfidencePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderRadius: RADIUS.full,
    paddingVertical: 3,
    paddingHorizontal: 8,
  },
  modalConfidenceDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  modalConfidenceText: {
    fontFamily: FONTS.sans,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  modalClose: {
    fontSize: 16,
    color: '#888780',
    paddingLeft: 8,
  },
  modalTagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 16,
  },
  modalTag: {
    backgroundColor: COLORS.sage + '22',
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  modalTagText: {
    fontSize: 11,
    color: COLORS.sage,
    fontFamily: FONTS.sans,
  },
  modalDesc: {
    fontSize: 13,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    lineHeight: 20,
    marginBottom: 14,
  },
  modalExplainBox: {
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: RADIUS.md,
    backgroundColor: '#FFFFFF',
    padding: 12,
    marginBottom: 18,
  },
  modalExplainHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  modalExplainTitle: {
    fontSize: 12,
    color: COLORS.ink,
    fontFamily: FONTS.sansSemi,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  modalReasonItem: {
    gap: 4,
    marginBottom: 10,
  },
  modalReasonTag: {
    alignSelf: 'flex-start',
    fontSize: 10,
    color: COLORS.teal,
    fontFamily: 'JetBrainsMono_400Regular',
    textTransform: 'uppercase',
  },
  modalReasonText: {
    fontSize: 12,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    lineHeight: 17,
  },
  modalPlanBtn: {
    backgroundColor: COLORS.teal,
    borderRadius: 24,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalPlanBtnText: {
    fontSize: 14,
    color: '#fff',
    fontFamily: FONTS.sans,
    fontWeight: '500',
  },

  /* Side-by-side small cards */
  sideBySide: {
    flexDirection: 'row',
    gap: SPACING.md,
  },
  smallCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: RADIUS.md,
    overflow: 'hidden',
    padding: SPACING.xs,
    ...SHADOWS.sm,
  },
  smallCardImage: {
    width: '100%',
    height: 100,
    borderRadius: SPACING.sm,
    marginBottom: SPACING.xs,
  },
  smallCardName: {
    fontSize: 15,
    ...TYPE.serifStrong,
    color: COLORS.ink,
    marginBottom: 2,
  },
  smallCardDesc: {
    fontSize: 12,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    lineHeight: 17,
    marginBottom: SPACING.xs,
  },

  /* Avatar bottom sheet */
  menuBackdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  menuSheet: {
    backgroundColor: '#F5F1EA',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
  },
  menuDragHandle: {
    width: 36,
    height: 3,
    backgroundColor: '#C8C4BC',
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 14,
  },
  menuItemText: {
    fontSize: 15,
    fontFamily: FONTS.sans,
    color: COLORS.ink,
  },
  menuItemSignOut: {
    color: COLORS.teal,
  },
  menuSep: {
    height: 0.5,
    backgroundColor: '#E0DAD0',
  },
  menuCancel: {
    marginTop: 8,
    alignItems: 'center',
    paddingVertical: 12,
  },
  menuCancelText: {
    fontSize: 13,
    color: '#888780',
    fontFamily: FONTS.sans,
  },


});
