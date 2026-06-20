import { View, Text, ScrollView, StyleSheet, ActivityIndicator, Alert } from 'react-native'
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { useRouter } from 'expo-router'
import { useState, useEffect } from 'react'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import apiClient from '../../services/api'
import { getCurrentUserSessionId } from '../../services/session'
import { useAuth } from '../../context/AuthContext'
import BottomTabBar from './components/BottomTabBar'
import { COLORS, FONTS, RADIUS, SHADOWS, TYPE } from '../../constants/theme'
import { countryFlag } from '../../constants/flags'

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }).toUpperCase()
}

function displayName(member) {
  return member?.full_name || member?.username || 'Traveler'
}

function creationModeLabel(plan) {
  return plan?.source === 'fim' ? 'Interactive Mode' : 'Generated'
}

function creationModeIcon(plan) {
  return plan?.source === 'fim' ? 'map-outline' : 'sparkles-outline'
}

function memberInitial(member) {
  return displayName(member).charAt(0).toUpperCase() || '?'
}

function planTimestamp(plan) {
  const time = Date.parse(plan?.saved_at || plan?.created_at || '')
  return Number.isFinite(time) ? time : 0
}

function latestSavedPlan(soloPlans, groupPlans) {
  return [...soloPlans, ...groupPlans]
    .sort((a, b) => planTimestamp(b) - planTimestamp(a))[0] || null
}

function continueTitle(plan) {
  const name = plan?.trip_name || plan?.country_name || 'your trip'
  return plan?.is_group ? `Continue your ${name} group trip` : `Continue your ${name} itinerary`
}

function continueSubtitle(plan) {
  const pieces = [
    plan?.nr_zile ? `${plan.nr_zile} days` : null,
    plan?.nr_cities ? `${plan.nr_cities} cities` : null,
    plan?.total_stops ? `${plan.total_stops} stops` : null,
  ].filter(Boolean)
  return pieces.join(' / ')
}

function topProfileTags(profile, limit = 3) {
  return (profile?.profile || [])
    .filter(tag => tag?.name && (tag.score ?? 0) > 0)
    .slice(0, limit)
}

function travelStyleSummary(profile) {
  const tags = topProfileTags(profile, 3).map(tag => tag.name)
  if (tags.length === 0) {
    return 'Complete the quiz to unlock your travel style.'
  }
  if (tags.length === 1) {
    return `${tags[0]} is your strongest travel signal.`
  }
  if (tags.length === 2) {
    return `You lean toward ${tags[0]} and ${tags[1]}.`
  }
  return `You lean toward ${tags[0]}, ${tags[1]} and ${tags[2]}.`
}

function leafProfileTags(profile, limit = 4) {
  return (profile?.profile || [])
    .filter(tag => tag?.name && tag.is_leaf && (tag.score ?? 0) > 0)
    .slice(0, limit)
}

function travelDnaInsight(profile) {
  const topTags = topProfileTags(profile, 3).map(tag => tag.name)
  if (topTags.length === 0) {
    return 'Your Travel DNA will become clearer after a completed quiz.'
  }
  if (topTags.length === 1) {
    return `Your recommendations are mostly driven by ${topTags[0]}.`
  }
  return `Your recommendations lean toward ${topTags.join(', ').replace(/, ([^,]*)$/, ' and $1')}.`
}

function profileConfidence(profile) {
  const swipes = profile?.card_count || 0
  if (swipes >= 18) return 'High confidence'
  if (swipes >= 12) return 'Good confidence'
  if (swipes > 0) return 'Early signal'
  return 'No signal yet'
}

export default function ProfileScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { user, logout } = useAuth()

  const [profile, setProfile] = useState(null)
  const [travelInsights, setTravelInsights] = useState(null)
  const [savedItineraries, setSavedItineraries] = useState([])
  const [groupTrips, setGroupTrips] = useState([])
  const [activeTab, setActiveTab] = useState('solo')
  const [deletingPlanId, setDeletingPlanId] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      try {
        setLoading(true)
        const sessionId = await getCurrentUserSessionId(user)
        const [profileRes, savedRes, insightsRes] = await Promise.allSettled([
          sessionId ? apiClient.get(`/quiz/v4/profile/${sessionId}`) : Promise.resolve(null),
          apiClient.get('/itinerary/saved'),
          apiClient.get('/itinerary/travel-insights'),
        ])
        if (profileRes.status === 'fulfilled' && profileRes.value) setProfile(profileRes.value.data)
        if (insightsRes.status === 'fulfilled') setTravelInsights(insightsRes.value.data)
        if (savedRes.status === 'fulfilled') {
          const plans = savedRes.value.data?.plans || []
          setSavedItineraries(plans.filter(p => !p.is_group))
          setGroupTrips(plans.filter(p => p.is_group))
        }
      } catch {
        // silently fail
      } finally {
        setLoading(false)
      }
    })()
  }, [user?.id])

  async function handleLogout() {
    await logout()
    router.replace('/(auth)/welcome')
  }

  function openSavedPlan(plan) {
    if (plan.source === 'fim') {
      router.push({
        pathname: '/(app)/interactive-mode',
        params: { planId: plan.plan_id, country: plan.country_name, readOnly: 'true' },
      })
      return
    }
    const groupTripId = plan.group_trip_id
    router.push({
      pathname: '/(app)/generated-itinerary',
      params: {
        plan_id: String(plan.plan_id),
        ...(groupTripId ? { group_trip_id: String(groupTripId) } : {}),
      },
    })
  }

  function groupCompanionNames(plan) {
    return groupCompanions(plan).map(displayName).join(', ')
  }

  function groupCompanions(plan) {
    return plan.companions?.length
      ? plan.companions
      : (plan.group_members || []).filter(member => !member.is_current_user)
  }

  function removePlanFromState(plan) {
    if (plan.is_group) {
      setGroupTrips(prev => prev.filter(item => item.plan_id !== plan.plan_id))
    } else {
      setSavedItineraries(prev => prev.filter(item => item.plan_id !== plan.plan_id))
    }
  }

  function restorePlanInState(plan) {
    if (plan.is_group) {
      setGroupTrips(prev => [plan, ...prev])
    } else {
      setSavedItineraries(prev => [plan, ...prev])
    }
  }

  function handleDeletePlan(plan) {
    if (plan.can_delete === false) {
      Alert.alert('Cannot remove trip', 'Only the creator can remove this saved group trip.')
      return
    }

    Alert.alert(
      'Remove saved trip?',
      `${plan.trip_name || plan.country_name} will be removed from your profile.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            setDeletingPlanId(plan.plan_id)
            removePlanFromState(plan)
            try {
              await apiClient.delete(`/itinerary/plan/${plan.plan_id}/save`)
            } catch (e) {
              restorePlanInState(plan)
              Alert.alert('Could not remove trip', e.response?.data?.detail || 'Please try again.')
            } finally {
              setDeletingPlanId(null)
            }
          },
        },
      ]
    )
  }

  const initial =
    user?.username?.charAt(0)?.toUpperCase() ||
    user?.full_name?.charAt(0)?.toUpperCase() ||
    '?'

  const topProfileList = (profile?.profile || []).slice(0, 5)
  const maxProfileScore = topProfileList.reduce((m, t) => Math.max(m, t.score || 0), 0.01)

  const stats = [
    { value: savedItineraries.length + groupTrips.length, label: 'TRIPS' },
    { value: profile?.profile?.length || 0, label: 'TAGS' },
    { value: profile?.card_count || 0, label: 'SWIPES' },
  ]
  const headerTags = topProfileTags(profile, 3)
  const dnaTags = topProfileTags(profile, 3)
  const specificTags = leafProfileTags(profile, 4)
  const latestPlan = latestSavedPlan(savedItineraries, groupTrips)

  if (loading) {
    return (
      <View style={styles.loadingWrap}>
        <ActivityIndicator size="large" color={COLORS.primary} />
      </View>
    )
  }

  return (
    <View style={styles.root}>
      <ScrollView showsVerticalScrollIndicator={false}>

        {/* ── HEADER ── */}
        <View style={[styles.headerSection, { paddingTop: insets.top + 24 }]}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initial}</Text>
          </View>
          <Text style={styles.username}>@{user?.username || user?.full_name || 'user'}</Text>
          <Text style={styles.email}>{user?.email || ''}</Text>

          <View style={styles.travelStyleCard}>
            <View style={styles.travelStyleHeader}>
              <Ionicons name="compass-outline" size={15} color={COLORS.primary} />
              <Text style={styles.travelStyleLabel}>TRAVEL STYLE</Text>
            </View>
            <Text style={styles.travelStyleText}>{travelStyleSummary(profile)}</Text>
            {headerTags.length > 0 ? (
              <View style={styles.travelStyleChips}>
                {headerTags.map(tag => (
                  <View key={tag.slug || tag.name} style={styles.travelStyleChip}>
                    <Text style={styles.travelStyleChipText}>{tag.name}</Text>
                  </View>
                ))}
              </View>
            ) : null}
          </View>

          <View style={styles.statsRow}>
            {stats.map((stat, i) => (
              <View key={stat.label} style={styles.statGroup}>
                {i > 0 && <View style={styles.statSep} />}
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>{stat.value}</Text>
                  <Text style={styles.statLabel}>{stat.label}</Text>
                </View>
              </View>
            ))}
          </View>

          {latestPlan ? (
            <TouchableOpacity
              style={styles.continueCard}
              activeOpacity={0.86}
              onPress={() => openSavedPlan(latestPlan)}
            >
              <View style={styles.continueIconWrap}>
                <Ionicons name="play" size={16} color={COLORS.surface} />
              </View>
              <View style={styles.continueTextWrap}>
                <Text style={styles.continueLabel}>RESUME RECENT TRIP</Text>
                <Text style={styles.continueTitle} numberOfLines={2}>
                  {continueTitle(latestPlan)}
                </Text>
                <View style={styles.continueMetaRow}>
                  <Text style={styles.continueMetaText}>{continueSubtitle(latestPlan)}</Text>
                  <View style={styles.continueModePill}>
                    <Ionicons
                      name={creationModeIcon(latestPlan)}
                      size={11}
                      color={COLORS.primary}
                    />
                    <Text style={styles.continueModeText}>{creationModeLabel(latestPlan)}</Text>
                  </View>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={18} color={COLORS.primary} />
            </TouchableOpacity>
          ) : null}
        </View>

        <View style={styles.separator} />

        {/* ── TRAVEL DNA ── */}
        <View style={styles.section}>
          <View style={styles.dnaHeaderRow}>
            <View style={styles.rowCenter}>
              <View style={styles.dot} />
              <Text style={styles.sectionLabel}>YOUR TRAVEL DNA</Text>
            </View>
            <Text style={styles.sectionLabel}>TOP 5</Text>
          </View>

          <Text style={styles.dnaTitle}>
            {'What makes '}
            <Text style={styles.dnaTitleHighlight}>you travel.</Text>
          </Text>

          <View style={styles.dnaInsightCard}>
            <View style={styles.dnaInsightTop}>
              <View style={styles.rowCenter}>
                <Ionicons name="analytics-outline" size={15} color={COLORS.primary} />
                <Text style={styles.dnaInsightLabel}>{profileConfidence(profile)}</Text>
              </View>
              <Text style={styles.dnaInsightSwipes}>{profile?.card_count || 0} swipes</Text>
            </View>
            <Text style={styles.dnaInsightText}>{travelDnaInsight(profile)}</Text>

            {specificTags.length > 0 ? (
              <View style={styles.dnaSignalBlock}>
                <Text style={styles.dnaSignalLabel}>Specific tastes</Text>
                <View style={styles.dnaSignalChips}>
                  {specificTags.map(tag => (
                    <View key={tag.slug || tag.name} style={styles.dnaSignalChip}>
                      <Text style={styles.dnaSignalChipText}>{tag.name}</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : dnaTags.length > 0 ? (
              <View style={styles.dnaSignalBlock}>
                <Text style={styles.dnaSignalLabel}>Strongest signals</Text>
                <View style={styles.dnaSignalChips}>
                  {dnaTags.map(tag => (
                    <View key={tag.slug || tag.name} style={styles.dnaSignalChip}>
                      <Text style={styles.dnaSignalChipText}>{tag.name}</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}
          </View>

          {travelInsights ? (
            <View style={styles.learningCard}>
              <View style={styles.learningTopRow}>
                <View style={styles.rowCenter}>
                  <Ionicons name="git-branch-outline" size={15} color={COLORS.primary} />
                  <Text style={styles.learningLabel}>PROFILE LEARNING</Text>
                </View>
                <Text style={styles.learningCount}>
                  {travelInsights.ratings_count || 0} rating{travelInsights.ratings_count === 1 ? '' : 's'}
                </Text>
              </View>

              {(travelInsights.profile_explanation || []).length > 0 ? (
                <Text style={styles.learningText}>
                  TripCraft currently explains your fit mostly through {(travelInsights.profile_explanation || [])
                    .slice(0, 3)
                    .map(item => item.name)
                    .join(', ')
                    .replace(/, ([^,]*)$/, ' and $1')}.
                </Text>
              ) : (
                <Text style={styles.learningText}>
                  Rate saved trips to show how your profile changes after real feedback.
                </Text>
              )}

              {(travelInsights.learning_impact || []).length > 0 ? (
                <View style={styles.impactList}>
                  {(travelInsights.learning_impact || []).slice(0, 4).map(item => (
                    <View key={item.slug} style={styles.impactRow}>
                      <View style={styles.impactNameRow}>
                        <Ionicons
                          name={item.direction === 'down' ? 'trending-down-outline' : 'trending-up-outline'}
                          size={14}
                          color={item.direction === 'down' ? COLORS.error : COLORS.primary}
                        />
                        <Text style={styles.impactName}>{item.name}</Text>
                      </View>
                      <Text style={[
                        styles.impactValue,
                        item.direction === 'down' && styles.impactValueDown,
                      ]}>
                        {item.impact > 0 ? '+' : ''}{item.impact}
                      </Text>
                    </View>
                  ))}
                </View>
              ) : null}

              {travelInsights.pace_preference ? (
                <View style={styles.learningPill}>
                  <Ionicons name="speedometer-outline" size={12} color={COLORS.primary} />
                  <Text style={styles.learningPillText}>Pace tuned to {travelInsights.pace_preference}</Text>
                </View>
              ) : null}
            </View>
          ) : null}

          {topProfileList.map((tag, i) => (
            <View key={tag.slug || i} style={styles.tagRow}>
              <Text style={styles.tagName}>{tag.name}</Text>
              <View style={styles.tagRight}>
                <View style={styles.barBg}>
                  <View style={[styles.barFill, { width: Math.round(((tag.score || 0) / maxProfileScore) * 120) }]} />
                </View>
                <Text style={styles.tagPct}>{Math.round((tag.score || 0) * 100)}%</Text>
              </View>
            </View>
          ))}

          <Text style={styles.basedOn}>Based on {profile?.card_count || 0} swipes.</Text>
        </View>

        <View style={[styles.separator, { marginTop: 24 }]} />

        {/* ── SAVED ITINERARIES ── */}
        <View style={styles.section}>
          <View style={[styles.rowCenter, { marginBottom: 16 }]}>
            <View style={styles.dot} />
            <Text style={styles.sectionLabel}>SAVED ITINERARIES</Text>
          </View>

          {/* Tab switcher */}
          <View style={[styles.rowCenter, { gap: 8, marginBottom: 16 }]}>
            {[
              { key: 'solo', label: 'Solo', count: savedItineraries.length },
              { key: 'group', label: 'Group', count: groupTrips.length },
            ].map(tab => {
              const active = activeTab === tab.key
              return (
                <TouchableOpacity key={tab.key} onPress={() => setActiveTab(tab.key)} activeOpacity={0.8}>
                  <View style={[styles.tabPill, active && styles.tabPillActive]}>
                    <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>{tab.label}</Text>
                    <View style={[styles.tabBadge, active && styles.tabBadgeActive]}>
                      <Text style={[styles.tabBadgeText, active && styles.tabBadgeTextActive]}>{tab.count}</Text>
                    </View>
                  </View>
                </TouchableOpacity>
              )
            })}
          </View>

          {activeTab === 'solo' ? (
            savedItineraries.length === 0 ? (
              <View style={styles.emptyWrap}>
                <Ionicons name="map-outline" size={28} color={COLORS.border} style={{ marginBottom: 8 }} />
                <Text style={styles.emptyText}>No saved itineraries yet</Text>
              </View>
            ) : (
              savedItineraries.map(plan => (
                <View key={plan.plan_id} style={styles.planCard}>
                  <View style={styles.planCardTop}>
                    <View style={[styles.rowCenter, { gap: 8 }]}>
                      <Text style={styles.planFlag}>{countryFlag(plan.country_name)}</Text>
                      <View>
                        <Text style={styles.planCountry}>{plan.country_name}</Text>
                        <Text style={styles.planCapital}>{plan.capital}</Text>
                      </View>
                    </View>
                    <View style={styles.planActions}>
                      <Text style={styles.planDate}>{formatDate(plan.saved_at)}</Text>
                      <TouchableOpacity
                        style={[styles.deletePlanBtn, deletingPlanId === plan.plan_id && styles.deletePlanBtnDisabled]}
                        activeOpacity={0.75}
                        disabled={deletingPlanId === plan.plan_id}
                        onPress={() => handleDeletePlan(plan)}
                      >
                        <Ionicons name="trash-outline" size={15} color={COLORS.error} />
                      </TouchableOpacity>
                    </View>
                  </View>

                  <View style={[styles.rowCenter, { gap: 6, marginBottom: 10, flexWrap: 'wrap' }]}>
                    <View style={styles.sagePill}>
                      <Ionicons name="business-outline" size={12} color={COLORS.sage} />
                      <Text style={styles.sagePillText}>{plan.nr_cities} cities</Text>
                    </View>
                    <View style={styles.sagePill}>
                      <Ionicons name="calendar-outline" size={12} color={COLORS.sage} />
                      <Text style={styles.sagePillText}>{plan.nr_zile} days</Text>
                    </View>
                    <View style={styles.sagePill}>
                      <Ionicons name="location-outline" size={12} color={COLORS.sage} />
                      <Text style={styles.sagePillText}>{plan.total_stops || 0} stops</Text>
                    </View>
                    <View style={[styles.modePill, plan.source === 'fim' ? styles.modePillInteractive : styles.modePillGenerated]}>
                      <Ionicons
                        name={creationModeIcon(plan)}
                        size={12}
                        color={plan.source === 'fim' ? COLORS.primary : COLORS.sage}
                      />
                      <Text style={[styles.modePillText, plan.source === 'fim' ? styles.modePillTextInteractive : styles.modePillTextGenerated]}>
                        {creationModeLabel(plan)}
                      </Text>
                    </View>
                  </View>

                  <View style={styles.planCardBottom}>
                    <View style={styles.planSummaryLeft}>
                      <Ionicons name="bookmark-outline" size={13} color={COLORS.muted} />
                      <Text style={styles.planSummaryText}>Saved trip</Text>
                    </View>
                    <TouchableOpacity onPress={() => openSavedPlan(plan)}>
                      <Text style={styles.viewLink}>View itinerary →</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))
            )
          ) : (
            groupTrips.length === 0 ? (
              <View style={styles.emptyWrap}>
                <Ionicons name="people-outline" size={28} color={COLORS.border} style={{ marginBottom: 8 }} />
                <Text style={styles.emptyText}>No group trips yet</Text>
              </View>
            ) : (
              groupTrips.map(plan => (
                <View key={plan.plan_id} style={styles.planCard}>
                  <View style={styles.planCardTop}>
                    <View style={[styles.rowCenter, { gap: 8 }]}>
                      <Text style={styles.planFlag}>{countryFlag(plan.country_name)}</Text>
                      <View>
                        {plan.trip_name ? (
                          <Text style={styles.planCountry}>{plan.trip_name}</Text>
                        ) : null}
                        <Text style={plan.trip_name ? styles.planCapital : styles.planCountry}>
                          {plan.country_name}
                        </Text>
                        {plan.capital ? <Text style={styles.planCapital}>{plan.capital}</Text> : null}
                        {groupCompanionNames(plan) ? (
                          <Text style={styles.planWith} numberOfLines={1}>
                            With {groupCompanionNames(plan)}
                          </Text>
                        ) : null}
                      </View>
                    </View>
                    <View style={styles.planActions}>
                      <Text style={styles.planDate}>{formatDate(plan.saved_at)}</Text>
                      <TouchableOpacity
                        style={[styles.deletePlanBtn, deletingPlanId === plan.plan_id && styles.deletePlanBtnDisabled]}
                        activeOpacity={0.75}
                        disabled={deletingPlanId === plan.plan_id}
                        onPress={() => handleDeletePlan(plan)}
                      >
                        <Ionicons name="trash-outline" size={15} color={COLORS.error} />
                      </TouchableOpacity>
                    </View>
                  </View>

                  <View style={[styles.rowCenter, { gap: 6, marginBottom: 10, flexWrap: 'wrap' }]}>
                    <View style={styles.sagePill}>
                      <Ionicons name="business-outline" size={12} color={COLORS.sage} />
                      <Text style={styles.sagePillText}>{plan.nr_cities} cities</Text>
                    </View>
                    <View style={styles.sagePill}>
                      <Ionicons name="calendar-outline" size={12} color={COLORS.sage} />
                      <Text style={styles.sagePillText}>{plan.nr_zile} days</Text>
                    </View>
                    <View style={styles.sagePill}>
                      <Ionicons name="location-outline" size={12} color={COLORS.sage} />
                      <Text style={styles.sagePillText}>{plan.total_stops || 0} stops</Text>
                    </View>
                    <View style={[styles.modePill, plan.source === 'fim' ? styles.modePillInteractive : styles.modePillGenerated]}>
                      <Ionicons
                        name={creationModeIcon(plan)}
                        size={12}
                        color={plan.source === 'fim' ? COLORS.primary : COLORS.sage}
                      />
                      <Text style={[styles.modePillText, plan.source === 'fim' ? styles.modePillTextInteractive : styles.modePillTextGenerated]}>
                        {creationModeLabel(plan)}
                      </Text>
                    </View>
                  </View>

                  <View style={styles.planCardBottom}>
                    <View style={styles.memberStackRow}>
                      <View style={styles.memberStack}>
                        {groupCompanions(plan).slice(0, 3).map((member, index) => (
                          <View
                            key={member.id || member.username || index}
                            style={[styles.memberBubble, index > 0 && styles.memberBubbleOverlap]}
                          >
                            <Text style={styles.memberBubbleText}>{memberInitial(member)}</Text>
                          </View>
                        ))}
                        {groupCompanions(plan).length > 3 ? (
                          <View style={[styles.memberBubble, styles.memberBubbleOverlap, styles.memberMoreBubble]}>
                            <Text style={styles.memberBubbleText}>+{groupCompanions(plan).length - 3}</Text>
                          </View>
                        ) : null}
                      </View>
                      <Text style={styles.planSummaryText}>
                        {groupCompanions(plan).length > 0
                          ? `${groupCompanions(plan).length} companion${groupCompanions(plan).length === 1 ? '' : 's'}`
                          : 'Group trip'}
                      </Text>
                    </View>
                    <TouchableOpacity onPress={() => openSavedPlan(plan)}>
                      <Text style={styles.viewLink}>View itinerary →</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))
            )
          )}
        </View>

        {/* ── ACCOUNT ── */}
        <View style={[styles.section, { marginBottom: 100 }]}>
          <View style={[styles.rowCenter, { marginTop: 28, marginBottom: 12 }]}>
            <View style={styles.dot} />
            <Text style={styles.sectionLabel}>ACCOUNT</Text>
          </View>

          <View style={styles.accountCard}>
            <TouchableOpacity
              style={styles.accountRow}
              activeOpacity={0.7}
              onPress={() => router.push('/(app)/quiz/start')}
            >
              <Ionicons name="refresh-outline" size={20} color={COLORS.sage} />
              <Text style={[styles.accountRowText, { flex: 1 }]}>Retake quiz</Text>
              <Ionicons name="chevron-forward" size={16} color={COLORS.border} />
            </TouchableOpacity>

            <View style={styles.accountSep} />

            <TouchableOpacity
              style={styles.accountRow}
              activeOpacity={0.7}
              onPress={handleLogout}
            >
              <Ionicons name="log-out-outline" size={20} color={COLORS.primary} />
              <Text style={[styles.accountRowText, { color: COLORS.primary }]}>Sign out</Text>
            </TouchableOpacity>
          </View>
        </View>

      </ScrollView>

      <BottomTabBar />
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },
  loadingWrap: {
    flex: 1,
    backgroundColor: COLORS.cream,
    justifyContent: 'center',
    alignItems: 'center',
  },

  /* Header */
  headerSection: {
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.dark,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    fontSize: 28,
    color: COLORS.surface,
    fontWeight: '600',
  },
  username: {
    fontSize: 18,
    color: COLORS.dark,
    fontWeight: '600',
    marginTop: 12,
  },
  email: {
    fontSize: 13,
    color: COLORS.muted,
    marginTop: 4,
  },
  travelStyleCard: {
    width: '100%',
    marginTop: 18,
    borderRadius: RADIUS.md,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: 14,
    ...SHADOWS.sm,
  },
  travelStyleHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginBottom: 8,
  },
  travelStyleLabel: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.primary,
    letterSpacing: 0,
  },
  travelStyleText: {
    ...TYPE.serifItalic,
    fontSize: 20,
    color: COLORS.dark,
    textAlign: 'center',
    lineHeight: 26,
  },
  travelStyleChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 6,
    marginTop: 12,
  },
  travelStyleChip: {
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.tagBg,
    paddingVertical: 5,
    paddingHorizontal: 10,
  },
  travelStyleChipText: {
    fontSize: 11,
    color: COLORS.primary,
    fontWeight: '600',
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 20,
  },
  statGroup: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statSep: {
    width: 0.5,
    height: 32,
    backgroundColor: COLORS.border,
    marginHorizontal: 16,
  },
  statItem: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 22,
    color: COLORS.dark,
    fontWeight: '700',
  },
  statLabel: {
    fontFamily: FONTS.mono,
    fontSize: 9,
    color: COLORS.sage,
    letterSpacing: 0,
    marginTop: 2,
  },
  continueCard: {
    width: '100%',
    marginTop: 20,
    borderRadius: RADIUS.lg,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    ...SHADOWS.sm,
  },
  continueIconWrap: {
    width: 36,
    height: 36,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  continueTextWrap: {
    flex: 1,
  },
  continueLabel: {
    fontFamily: FONTS.mono,
    fontSize: 9,
    color: COLORS.primary,
    letterSpacing: 0,
    marginBottom: 4,
  },
  continueTitle: {
    ...TYPE.serifItalic,
    fontSize: 20,
    color: COLORS.dark,
    lineHeight: 24,
  },
  continueMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 8,
  },
  continueMetaText: {
    fontSize: 11,
    color: COLORS.muted,
  },
  continueModePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.tagBg,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  continueModeText: {
    fontFamily: FONTS.mono,
    fontSize: 9,
    color: COLORS.primary,
  },

  separator: {
    height: 0.5,
    backgroundColor: COLORS.border,
  },

  /* Shared */
  section: {
    marginHorizontal: 24,
    marginTop: 24,
  },
  rowCenter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.sage,
  },
  sectionLabel: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.muted,
    letterSpacing: 0,
  },

  /* Travel DNA */
  dnaHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  dnaTitle: {
    ...TYPE.serifStrong,
    fontSize: 22,
    color: COLORS.dark,
    marginBottom: 16,
  },
  dnaTitleHighlight: {
    ...TYPE.serifStrongItalic,
    fontSize: 22,
    color: COLORS.primary,
  },
  dnaInsightCard: {
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: 14,
    marginBottom: 18,
    ...SHADOWS.sm,
  },
  dnaInsightTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  dnaInsightLabel: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.primary,
    letterSpacing: 0,
    textTransform: 'uppercase',
  },
  dnaInsightSwipes: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.muted,
  },
  dnaInsightText: {
    fontSize: 14,
    color: COLORS.dark,
    lineHeight: 20,
  },
  dnaSignalBlock: {
    marginTop: 12,
  },
  dnaSignalLabel: {
    fontFamily: FONTS.mono,
    fontSize: 9,
    color: COLORS.muted,
    letterSpacing: 0,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  dnaSignalChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  dnaSignalChip: {
    backgroundColor: COLORS.cream,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingVertical: 5,
    paddingHorizontal: 10,
  },
  dnaSignalChipText: {
    fontSize: 11,
    color: COLORS.dark,
    fontWeight: '500',
  },
  learningCard: {
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: 14,
    marginBottom: 18,
    ...SHADOWS.sm,
  },
  learningTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  learningLabel: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.primary,
    letterSpacing: 0,
  },
  learningCount: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.muted,
  },
  learningText: {
    fontSize: 13,
    color: COLORS.dark,
    lineHeight: 19,
  },
  impactList: {
    gap: 8,
    marginTop: 12,
  },
  impactRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderRadius: RADIUS.sm,
    backgroundColor: COLORS.cream,
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  impactNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flex: 1,
  },
  impactName: {
    fontSize: 12,
    color: COLORS.dark,
    fontWeight: '500',
    flex: 1,
  },
  impactValue: {
    fontFamily: FONTS.mono,
    fontSize: 11,
    color: COLORS.primary,
  },
  impactValueDown: {
    color: COLORS.error,
  },
  learningPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 5,
    marginTop: 12,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.tagBg,
    paddingVertical: 5,
    paddingHorizontal: 9,
  },
  learningPillText: {
    fontSize: 11,
    color: COLORS.primary,
    fontWeight: '600',
  },
  tagRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  tagName: {
    fontSize: 13,
    color: COLORS.dark,
    fontWeight: '500',
    flex: 1,
  },
  tagRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  barBg: {
    width: 120,
    height: 6,
    borderRadius: 3,
    backgroundColor: COLORS.border,
  },
  barFill: {
    height: 6,
    borderRadius: 3,
    backgroundColor: COLORS.primary,
  },
  tagPct: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: COLORS.muted,
    width: 32,
    textAlign: 'right',
  },
  basedOn: {
    fontSize: 11,
    color: COLORS.muted,
    fontStyle: 'italic',
    marginTop: 4,
  },

  /* Tabs */
  tabPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 20,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.border,
  },
  tabPillActive: {
    backgroundColor: COLORS.primary,
  },
  tabLabel: {
    fontSize: 13,
    color: COLORS.muted,
  },
  tabLabelActive: {
    color: COLORS.surface,
    fontWeight: '500',
  },
  tabBadge: {
    backgroundColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  tabBadgeActive: {
    backgroundColor: 'rgba(255,255,255,0.3)',
  },
  tabBadgeText: {
    fontSize: 11,
    color: COLORS.muted,
  },
  tabBadgeTextActive: {
    color: COLORS.surface,
  },

  /* Plan cards */
  planCard: {
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: 16,
    marginBottom: 10,
    ...SHADOWS.sm,
  },
  planCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  planFlag: {
    fontSize: 20,
  },
  planCountry: {
    ...TYPE.serifItalic,
    fontSize: 18,
    color: COLORS.dark,
  },
  planCapital: {
    fontSize: 11,
    color: COLORS.muted,
    marginTop: 1,
  },
  planWith: {
    fontSize: 11,
    color: COLORS.sage,
    marginTop: 3,
    maxWidth: 190,
  },
  planDate: {
    fontSize: 11,
    color: COLORS.muted,
  },
  planActions: {
    alignItems: 'flex-end',
    gap: 8,
  },
  deletePlanBtn: {
    width: 30,
    height: 30,
    borderRadius: RADIUS.full,
    backgroundColor: '#FFF1EC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  deletePlanBtnDisabled: {
    opacity: 0.45,
  },
  sagePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(107,124,90,0.13)',
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  sagePillText: {
    fontSize: 12,
    color: COLORS.sage,
    fontWeight: '500',
  },
  modePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  modePillGenerated: {
    backgroundColor: COLORS.border,
  },
  modePillInteractive: {
    backgroundColor: COLORS.tagBg,
  },
  modePillText: {
    fontFamily: FONTS.mono,
    fontSize: 10,
  },
  modePillTextGenerated: {
    color: COLORS.sage,
  },
  modePillTextInteractive: {
    color: COLORS.primary,
  },
  planCardBottom: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  planSummaryLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  planSummaryText: {
    fontSize: 11,
    color: COLORS.muted,
  },
  memberStackRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  memberStack: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  memberBubble: {
    width: 24,
    height: 24,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.dark,
    borderWidth: 1,
    borderColor: COLORS.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  memberBubbleOverlap: {
    marginLeft: -7,
  },
  memberMoreBubble: {
    backgroundColor: COLORS.primary,
  },
  memberBubbleText: {
    fontSize: 10,
    color: COLORS.surface,
    fontWeight: '700',
  },
  viewLink: {
    fontSize: 12,
    color: COLORS.primary,
    fontWeight: '500',
  },

  /* Empty state */
  emptyWrap: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  emptyText: {
    fontSize: 13,
    color: COLORS.muted,
  },

  /* Account */
  accountCard: {
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    overflow: 'hidden',
    ...SHADOWS.sm,
  },
  accountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 16,
    paddingHorizontal: 16,
  },
  accountRowText: {
    fontSize: 14,
    color: COLORS.dark,
  },
  accountSep: {
    height: 0.5,
    backgroundColor: COLORS.cream,
  },
})
