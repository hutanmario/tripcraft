import { View, Text, StyleSheet, ActivityIndicator, Alert, ScrollView, TextInput, Dimensions } from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';

import { useLocalSearchParams, useRouter } from 'expo-router'
import { useState, useEffect } from 'react'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { Image as ExpoImage } from 'expo-image'
import apiClient from '../../services/api'
import { getCurrentUserSessionId } from '../../services/session'
import { useAuth } from '../../context/AuthContext'

const { width: SCREEN_WIDTH } = Dimensions.get('window')

const firstParam = (value) => Array.isArray(value) ? value[0] : value
const decodeParamPart = (value) => {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export default function GroupTripScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { user } = useAuth()
  const { friend_ids, friend_names } = useLocalSearchParams()

  const friendIdsParam = firstParam(friend_ids) || ''
  const friendNamesParam = firstParam(friend_names) || ''
  const friendIdList = friendIdsParam.split(',').map(Number).filter(Boolean)
  const friendNameList = friendNamesParam.split(',').map(decodeParamPart).filter(Boolean)

  const [countries, setCountries] = useState([])
  const [selectedCountry, setSelectedCountry] = useState(null)
  const [numDays, setNumDays] = useState(5)
  const [tripName, setTripName] = useState('')
  const [loading, setLoading] = useState(false)
  const [interactiveLoading, setInteractiveLoading] = useState(false)
  const [loadingCountries, setLoadingCountries] = useState(true)
  const [includedMembers, setIncludedMembers] = useState([])
  const [excludedMembers, setExcludedMembers] = useState([])
  const [groupConflicts, setGroupConflicts] = useState([])
  const [recommendationError, setRecommendationError] = useState('')
  const [pendingGroupTripId, setPendingGroupTripId] = useState(null)

  useEffect(() => {
    fetchCountries()
  }, [user?.id, friendIdsParam])

  useEffect(() => {
    setPendingGroupTripId(null)
  }, [selectedCountry?.country_id, numDays, tripName, friendIdsParam])

  async function fetchCountries() {
    if (!user?.id) { setLoadingCountries(false); return }
    setLoadingCountries(true)
    setRecommendationError('')
    try {
      const currentSessionId = await getCurrentUserSessionId(user)
      const { data } = await apiClient.post('/social/group-recommendations', {
        member_ids: friendIdList,
        current_session_id: currentSessionId,
      })
      setCountries(data.top_countries?.slice(0, 6) || [])
      setIncludedMembers(data.included_members || [])
      setExcludedMembers(data.excluded_members || [])
      setGroupConflicts(data.conflicts || [])
    } catch (e) {
      setCountries([])
      setIncludedMembers([])
      setExcludedMembers([])
      setGroupConflicts([])
      setRecommendationError(e.response?.data?.detail || 'Could not calculate group recommendations.')
    } finally {
      setLoadingCountries(false)
    }
  }

  async function handleGenerate() {
    setLoading(true)
    try {
      let tripData = { trip_id: pendingGroupTripId }
      if (!pendingGroupTripId) {
        const currentSessionId = await getCurrentUserSessionId(user)
        const response = await apiClient.post('/social/group-trip', {
          name: tripName || 'Group Trip',
          country_id: selectedCountry.country_id,
          nr_zile: numDays,
          member_ids: friendIdList,
          current_session_id: currentSessionId,
        })
        tripData = response.data
        setPendingGroupTripId(tripData.trip_id)
        setIncludedMembers(tripData.included_members || includedMembers)
        setExcludedMembers(tripData.excluded_members || excludedMembers)
        setGroupConflicts(tripData.conflicts || groupConflicts)
      }
      const { data: genData } = await apiClient.post('/social/group-trip/' + tripData.trip_id + '/generate')
      setPendingGroupTripId(null)
      setGroupConflicts(genData.conflicts || tripData.conflicts || groupConflicts)
      router.push({
        pathname: '/(app)/itinerary/generating',
        params: {
          plan_id: String(genData.plan_id),
          group_trip_id: String(tripData.trip_id),
        },
      })
    } catch (e) {
      Alert.alert('Error', e.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  async function handleOpenInteractiveMode() {
    if (!selectedCountry) return
    setInteractiveLoading(true)
    try {
      const currentSessionId = await getCurrentUserSessionId(user)
      const { data } = await apiClient.post('/social/group-interactive-session', {
        name: tripName || 'Group Interactive Trip',
        country_id: selectedCountry.country_id,
        nr_zile: numDays,
        member_ids: friendIdList,
        current_session_id: currentSessionId,
      })
      setIncludedMembers(data.included_members || includedMembers)
      setExcludedMembers(data.excluded_members || excludedMembers)
      setGroupConflicts(data.conflicts || groupConflicts)
      router.push({
        pathname: '/(app)/interactive-mode',
        params: {
          country: data.country_name,
          country_name: data.country_name,
          country_id: String(data.country_id),
          days: String(data.days),
          session_id: data.session_id,
          group_trip_id: String(data.group_trip_id),
          mode: 'group',
        },
      })
    } catch (e) {
      Alert.alert('Error', e.response?.data?.detail || 'Could not open interactive mode')
    } finally {
      setInteractiveLoading(false)
    }
  }

  const initials = (name) => (name ? name[0].toUpperCase() : '?')
  const memberLabel = (member) => member.full_name || member.username || `User ${member.user_id}`
  const conflictMemberNames = (members = []) => members.map(member => member.name || member.full_name || member.username).filter(Boolean).join(', ')
  const conflictTone = (severity) => {
    if (severity === 'high') return { color: '#A33A2D', bg: '#F3DED9', icon: 'alert-circle-outline' }
    if (severity === 'medium') return { color: '#9A6A2F', bg: '#F3E8D2', icon: 'git-compare-outline' }
    return { color: '#5F5A52', bg: '#EFEAE0', icon: 'information-circle-outline' }
  }
  const goodFitCount = (country) => (country.individual_scores || []).filter(member => member.score >= 0.45).length
  const hasPerMemberBreakdown = countries.some(country => (country.individual_scores || []).length > 0)
  const selectedMemberScores = selectedCountry?.individual_scores || []
  const selectedFitCount = selectedCountry ? goodFitCount(selectedCountry) : 0
  const fitColor = (score) => {
    if (score >= 0.7) return '#2A9D8F'
    if (score >= 0.45) return '#C9A227'
    return '#B05A4A'
  }
  const cardWidth = (SCREEN_WIDTH - 58) / 2
  const isBusy = loading || interactiveLoading

  return (
    <View style={styles.root}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <TouchableOpacity onPress={() => router.canGoBack() ? router.back() : router.replace('/(app)/friends')}>
          <View style={styles.backBtn}>
            <Ionicons name="chevron-back" size={18} color="#1A1614" />
          </View>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Group Trip</Text>
        <View style={styles.travelersBadge}>
          <Text style={styles.travelersBadgeText}>{friendIdList.length + 1} Travellers</Text>
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 190 }}>
        {/* Travelling With */}
        <View style={{ marginHorizontal: 24, marginTop: 20 }}>
          <View style={styles.sectionHeaderRow}>
            <View style={styles.sectionHeaderLeft}>
              <View style={[styles.dot, { backgroundColor: '#6B7C5A' }]} />
              <Text style={styles.monoLabel}>TRAVELLING WITH</Text>
            </View>
            <Text style={styles.monoLabel}>{friendIdList.length + 1} TRAVELLERS</Text>
          </View>

          {/* Overlapping avatars */}
          <View style={styles.avatarsRow}>
            <View style={{ alignItems: 'center' }}>
              <View style={[styles.avatarCircle, { backgroundColor: '#1A1614' }]}>
                <Text style={styles.avatarInitial}>{initials(user?.username)}</Text>
              </View>
              <Text style={styles.avatarLabel}>YOU</Text>
            </View>
            {friendNameList.map((name, i) => (
              <View key={i} style={{ alignItems: 'center', marginLeft: -8 }}>
                <View style={[styles.avatarCircle, { backgroundColor: '#2A2320' }]}>
                  <Text style={styles.avatarInitial}>{initials(name)}</Text>
                </View>
                <Text style={styles.avatarLabel}>{name.split(' ')[0]}</Text>
              </View>
            ))}
          </View>

          <Text style={styles.blendText}>
            We'll blend your travel styles into one perfect route.
          </Text>

          {includedMembers.length > 0 && (
            <View style={styles.profileStatusRow}>
              <Ionicons name="checkmark-circle-outline" size={15} color="#2A9D8F" />
              <Text style={styles.profileStatusText}>
                {includedMembers.length} profile{includedMembers.length === 1 ? '' : 's'} included in the blend
              </Text>
            </View>
          )}

          {excludedMembers.length > 0 && (
            <View style={[styles.profileStatusRow, styles.profileWarningRow]}>
              <Ionicons name="warning-outline" size={15} color="#9A6A2F" />
              <Text style={styles.profileWarningText}>
                {excludedMembers.map(m => m.full_name || m.username).join(', ')} need a completed quiz or photo profile.
              </Text>
            </View>
          )}

          {groupConflicts.length > 0 && (
            <View style={styles.conflictPanel}>
              <View style={styles.conflictHeader}>
                <Ionicons name="git-compare-outline" size={15} color="#9A6A2F" />
                <Text style={styles.conflictHeaderText}>
                  {groupConflicts.length} preference conflict{groupConflicts.length === 1 ? '' : 's'} detected
                </Text>
              </View>
              {groupConflicts.slice(0, 4).map((conflict) => {
                const tone = conflictTone(conflict.severity)
                const groupA = conflict.group_a?.members || conflict.groups?.[0]?.members || []
                const groupB = conflict.group_b?.members || conflict.groups?.[1]?.members || []
                return (
                  <View key={conflict.type} style={[styles.conflictItem, { backgroundColor: tone.bg }]}>
                    <View style={styles.conflictTitleRow}>
                      <Ionicons name={tone.icon} size={14} color={tone.color} />
                      <Text style={[styles.conflictTitle, { color: tone.color }]}>{conflict.title}</Text>
                      <Text style={[styles.conflictSeverity, { color: tone.color }]}>{conflict.severity}</Text>
                    </View>
                    <Text style={styles.conflictMessage}>{conflict.message}</Text>
                    {(groupA.length > 0 || groupB.length > 0) && (
                      <Text style={styles.conflictMembers} numberOfLines={2}>
                        {[conflictMemberNames(groupA), conflictMemberNames(groupB)].filter(Boolean).join(' vs ')}
                      </Text>
                    )}
                  </View>
                )
              })}
            </View>
          )}
        </View>

        {/* Trip Name */}
        <View style={{ marginHorizontal: 24, marginTop: 24 }}>
          <View style={[styles.sectionHeaderRow, { marginBottom: 8 }]}>
            <View style={styles.sectionHeaderLeft}>
              <View style={[styles.dot, { backgroundColor: '#6B7C5A' }]} />
              <Text style={styles.monoLabel}>TRIP NAME</Text>
            </View>
            <Text style={styles.monoLabel}>{tripName.length}/40</Text>
          </View>
          <TextInput
            value={tripName}
            onChangeText={(t) => setTripName(t.slice(0, 40))}
            placeholder="e.g. Summer with the crew"
            placeholderTextColor="#C4BDB5"
            style={[
              styles.tripNameInput,
              { borderBottomColor: tripName.length > 0 ? '#2A9D8F' : '#E0DAD0' },
            ]}
          />
        </View>

        {/* Choose Destination */}
        <View style={{ marginHorizontal: 24, marginTop: 24 }}>
          <View style={[styles.sectionHeaderRow, { marginBottom: 4 }]}>
            <View style={styles.sectionHeaderLeft}>
              <View style={[styles.dot, { backgroundColor: '#6B7C5A' }]} />
              <Text style={styles.monoLabel}>CHOOSE DESTINATION</Text>
            </View>
            <Text style={styles.monoLabel}>{countries.length} MATCHES</Text>
          </View>
          <Text style={styles.subLabel}>Based on your combined preferences.</Text>

          {!loadingCountries && countries.length > 0 && (
            <View style={styles.groupSummaryPanel}>
              <View style={styles.groupSummaryRow}>
                <Ionicons name="people-outline" size={15} color="#2A9D8F" />
                <Text style={styles.groupSummaryTitle}>
                  {hasPerMemberBreakdown
                    ? 'Per-traveller fit is active'
                    : `${includedMembers.length || friendIdList.length + 1} profiles blended`}
                </Text>
              </View>
              <Text style={styles.groupSummaryText}>
                {hasPerMemberBreakdown
                  ? 'Cards show how many travellers fit each destination. Tap one to compare everyone.'
                  : 'Showing a combined group score for each destination.'}
              </Text>
            </View>
          )}

          {recommendationError ? (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle-outline" size={16} color="#A33A2D" />
              <Text style={styles.errorText}>{recommendationError}</Text>
            </View>
          ) : null}

          {selectedCountry && (
            <View style={styles.selectedFitPanel}>
              <View style={styles.selectedFitHeader}>
                <Ionicons name="people-outline" size={15} color="#2A9D8F" />
                <Text style={styles.selectedFitTitle}>Group fit for {selectedCountry.country_name}</Text>
                <View style={styles.selectedScorePill}>
                  <Text style={styles.selectedScorePillText}>{Math.round(selectedCountry.score * 100)}%</Text>
                </View>
              </View>

              {selectedMemberScores.length > 0 ? (
                <>
                  <Text style={styles.selectedFitMeta}>
                    {selectedFitCount}/{selectedMemberScores.length} travellers are a good fit.
                  </Text>
                  {selectedMemberScores.map((member) => (
                    <View key={member.user_id} style={styles.memberScoreRow}>
                      <Text style={styles.memberScoreName} numberOfLines={1}>
                        {memberLabel(member)}
                      </Text>
                      <View style={styles.memberScoreTrack}>
                        <View
                          style={[
                            styles.memberScoreFill,
                            {
                              width: `${Math.max(4, Math.min(100, Math.round(member.score * 100)))}%`,
                              backgroundColor: fitColor(member.score),
                            },
                          ]}
                        />
                      </View>
                      <Text style={styles.memberScoreValue}>{Math.round(member.score * 100)}%</Text>
                    </View>
                  ))}
                </>
              ) : (
                <Text style={styles.selectedFitMeta}>
                  This recommendation is based on the blended group profile.
                </Text>
              )}

              {selectedCountry.group_explanation && (
                <View style={styles.explanationBox}>
                  <View style={styles.explanationHeader}>
                    <Ionicons name="sparkles-outline" size={14} color="#2A9D8F" />
                    <Text style={styles.explanationTitle}>Why this works</Text>
                  </View>
                  <Text style={styles.explanationSummary}>
                    {selectedCountry.group_explanation.summary}
                  </Text>

                  {selectedCountry.group_explanation.top_group_reasons?.length > 0 && (
                    <View style={styles.reasonList}>
                      {selectedCountry.group_explanation.top_group_reasons.slice(0, 3).map((reason, index) => (
                        <View key={`${reason.tag || reason.label}-${index}`} style={styles.reasonPill}>
                          <Text style={styles.reasonPillText}>{reason.label}</Text>
                        </View>
                      ))}
                    </View>
                  )}

                  {selectedCountry.group_explanation.tradeoffs?.length > 0 && (
                    <View style={styles.tradeoffBox}>
                      <Ionicons name="warning-outline" size={13} color="#9A6A2F" />
                      <Text style={styles.tradeoffText}>
                        {selectedCountry.group_explanation.tradeoffs[0].message}
                      </Text>
                    </View>
                  )}
                </View>
              )}
            </View>
          )}

          {loadingCountries ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color="#2A9D8F" size="small" />
              <Text style={styles.loadingText}>Calculating group preferences...</Text>
            </View>
          ) : countries.length === 0 ? (
            <View style={styles.emptyMatches}>
              <Text style={styles.emptyMatchesTitle}>No group matches yet</Text>
              <Text style={styles.emptyMatchesText}>Finish the quiz or photo onboarding before planning a group trip.</Text>
            </View>
          ) : (
            <View style={styles.grid}>
              {countries.map((country) => {
                const isSelected = selectedCountry?.country_id === country.country_id
                const memberScores = country.individual_scores || []
                const fitCount = goodFitCount(country)
                return (
                  <TouchableOpacity
                    key={country.country_id}
                    activeOpacity={0.85}
                    onPress={() => setSelectedCountry(country)}
                    style={[styles.countryCard, { width: cardWidth }]}
                  >
                    <ExpoImage
                      source={{ uri: country.image_url }}
                      style={StyleSheet.absoluteFill}
                      contentFit="cover"
                    />
                    <View style={[StyleSheet.absoluteFill, styles.cardOverlay]} />

                    {isSelected && (
                      <>
                        <View style={[StyleSheet.absoluteFill, styles.cardSelectedBorder]} />
                        <View style={styles.checkBadge}>
                          <Ionicons name="checkmark" size={12} color="#fff" />
                        </View>
                      </>
                    )}

                    <View style={styles.memberFitBadge}>
                      <Ionicons name="people-outline" size={11} color="#fff" />
                      <Text style={styles.memberFitBadgeText}>
                        {memberScores.length > 0 ? `${fitCount}/${memberScores.length} fit` : 'Group'}
                      </Text>
                    </View>

                    {!isSelected && (
                      <View style={styles.scoreBadge}>
                        <Text style={styles.scoreBadgeText}>
                          • {Math.round(country.score * 100)}%
                        </Text>
                      </View>
                    )}

                    <View style={styles.cardBottom}>
                      <Text style={styles.cardCountryName}>{country.country_name}</Text>
                      <Text style={styles.cardCapital}>{country.capital}</Text>
                    </View>
                  </TouchableOpacity>
                )
              })}
            </View>
          )}

        </View>

        {/* Days Selector */}
        <View style={{ marginHorizontal: 24, marginTop: 28 }}>
          <View style={[styles.sectionHeaderLeft, { marginBottom: 16 }]}>
            <View style={[styles.dot, { backgroundColor: '#6B7C5A' }]} />
            <Text style={styles.monoLabel}>HOW MANY DAYS?</Text>
          </View>

          <View style={styles.daysRow}>
            <TouchableOpacity
              style={styles.daysBtnMinus}
              onPress={() => setNumDays(d => Math.max(3, d - 1))}
            >
              <Text style={styles.daysBtnMinusText}>−</Text>
            </TouchableOpacity>

            <Text style={styles.daysNumber}>{numDays}</Text>

            <TouchableOpacity
              style={styles.daysBtnPlus}
              onPress={() => setNumDays(d => Math.min(10, d + 1))}
            >
              <Text style={styles.daysBtnPlusText}>+</Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.daysLabel}>DAYS</Text>
        </View>
      </ScrollView>

      {/* Generate Button */}
      <View style={[styles.generateContainer, { bottom: 32 }]}>
        <TouchableOpacity
          style={[
            styles.generateBtn,
            { backgroundColor: !selectedCountry ? '#D3D1C7' : '#2A9D8F' },
          ]}
          disabled={!selectedCountry || isBusy}
          activeOpacity={0.85}
          onPress={handleGenerate}
        >
          {loading ? (
            <ActivityIndicator color="#fff" size="small" />
          ) : (
            <Ionicons name="people-outline" size={18} color="#fff" />
          )}
          <Text style={styles.generateBtnText}>
            {loading ? 'Generating...' : 'Generate group itinerary'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.interactiveBtn,
            (!selectedCountry || isBusy) && styles.interactiveBtnDisabled,
          ]}
          disabled={!selectedCountry || isBusy}
          activeOpacity={0.85}
          onPress={handleOpenInteractiveMode}
        >
          {interactiveLoading ? (
            <ActivityIndicator color="#2A9D8F" size="small" />
          ) : (
            <Ionicons name="map-outline" size={18} color="#2A9D8F" />
          )}
          <Text style={styles.interactiveBtnText}>
            {interactiveLoading ? 'Opening interactive...' : 'Fully interactive mode'}
          </Text>
        </TouchableOpacity>

        {!selectedCountry && (
          <Text style={styles.pickHint}>PICK A DESTINATION TO CONTINUE</Text>
        )}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#F5F1EA',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
  backBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#EFEAE0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 24,
    color: '#1A1614',
  },
  travelersBadge: {
    backgroundColor: '#EFEAE0',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  travelersBadgeText: {
    fontSize: 11,
    color: '#888780',
    fontWeight: '500',
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  sectionHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  monoLabel: {
    fontFamily: 'JetBrainsMono_400Regular',
    fontSize: 10,
    color: '#888780',
    letterSpacing: 1.5,
  },
  avatarsRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  avatarCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#F5F1EA',
  },
  avatarInitial: {
    fontSize: 18,
    color: '#fff',
    fontWeight: '600',
  },
  avatarLabel: {
    fontSize: 9,
    color: '#888780',
    textAlign: 'center',
    marginTop: 4,
  },
  blendText: {
    fontSize: 12,
    color: '#888780',
    fontStyle: 'italic',
    marginTop: 8,
  },
  profileStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  profileWarningRow: {
    alignItems: 'flex-start',
  },
  profileStatusText: {
    flex: 1,
    fontSize: 11,
    color: '#2A9D8F',
  },
  profileWarningText: {
    flex: 1,
    fontSize: 11,
    color: '#9A6A2F',
    lineHeight: 15,
  },
  conflictPanel: {
    marginTop: 12,
    gap: 8,
  },
  conflictHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  conflictHeaderText: {
    fontSize: 11,
    color: '#9A6A2F',
    fontWeight: '700',
  },
  conflictItem: {
    borderRadius: 12,
    padding: 10,
  },
  conflictTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  conflictTitle: {
    flex: 1,
    fontSize: 11,
    fontWeight: '800',
  },
  conflictSeverity: {
    fontSize: 9,
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  conflictMessage: {
    marginTop: 5,
    fontSize: 10,
    color: '#5F5A52',
    lineHeight: 14,
  },
  conflictMembers: {
    marginTop: 5,
    fontSize: 10,
    color: '#1A1614',
    fontWeight: '700',
  },
  tripNameInput: {
    backgroundColor: '#EFEAE0',
    borderRadius: 16,
    padding: 14,
    fontSize: 15,
    color: '#1A1614',
    borderBottomWidth: 2,
  },
  subLabel: {
    fontSize: 11,
    color: '#888780',
    marginBottom: 12,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 20,
  },
  loadingText: {
    fontSize: 12,
    color: '#888780',
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 7,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 12,
    backgroundColor: '#F3DED9',
    marginBottom: 12,
  },
  errorText: {
    flex: 1,
    fontSize: 11,
    lineHeight: 15,
    color: '#A33A2D',
  },
  emptyMatches: {
    paddingVertical: 18,
    paddingHorizontal: 14,
    borderRadius: 14,
    backgroundColor: '#EFEAE0',
  },
  emptyMatchesTitle: {
    fontFamily: 'Inter_500Medium',
    fontSize: 13,
    color: '#1A1614',
  },
  emptyMatchesText: {
    fontSize: 11,
    color: '#888780',
    lineHeight: 16,
    marginTop: 4,
  },
  groupSummaryPanel: {
    marginBottom: 12,
    borderRadius: 12,
    backgroundColor: '#E7F1EC',
    padding: 11,
  },
  groupSummaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  groupSummaryTitle: {
    fontSize: 12,
    color: '#1F6F63',
    fontWeight: '800',
  },
  groupSummaryText: {
    marginTop: 5,
    fontSize: 10,
    color: '#5F5A52',
    lineHeight: 14,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  countryCard: {
    aspectRatio: 1.2,
    borderRadius: 16,
    overflow: 'hidden',
    justifyContent: 'flex-end',
    padding: 10,
  },
  cardOverlay: {
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  cardSelectedBorder: {
    borderWidth: 2,
    borderColor: '#2A9D8F',
    borderRadius: 16,
  },
  checkBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#2A9D8F',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: 'rgba(42,157,143,0.85)',
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  scoreBadgeText: {
    fontSize: 11,
    color: '#fff',
    fontWeight: '600',
  },
  memberFitBadge: {
    position: 'absolute',
    top: 8,
    left: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    backgroundColor: 'rgba(26,22,20,0.72)',
    borderRadius: 12,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  memberFitBadgeText: {
    fontSize: 10,
    color: '#fff',
    fontWeight: '700',
  },
  cardBottom: {
    position: 'absolute',
    bottom: 10,
    left: 10,
  },
  cardCountryName: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 18,
    color: '#fff',
  },
  cardCapital: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop: 2,
  },
  selectedFitPanel: {
    marginTop: 12,
    borderRadius: 12,
    backgroundColor: '#EFEAE0',
    padding: 12,
  },
  selectedFitHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  selectedFitTitle: {
    flex: 1,
    fontSize: 12,
    fontWeight: '700',
    color: '#1A1614',
  },
  selectedScorePill: {
    borderRadius: 999,
    backgroundColor: '#2A9D8F',
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  selectedScorePillText: {
    fontSize: 10,
    color: '#fff',
    fontWeight: '800',
  },
  selectedFitMeta: {
    fontSize: 11,
    lineHeight: 15,
    color: '#5F5A52',
    marginBottom: 4,
  },
  memberScoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 7,
  },
  memberScoreName: {
    width: 86,
    fontSize: 11,
    color: '#5F5A52',
    fontWeight: '600',
  },
  memberScoreTrack: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#D8D2C8',
    overflow: 'hidden',
  },
  memberScoreFill: {
    height: 6,
    borderRadius: 3,
  },
  memberScoreValue: {
    width: 34,
    textAlign: 'right',
    fontSize: 11,
    color: '#1A1614',
    fontWeight: '700',
  },
  explanationBox: {
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#D8D2C8',
  },
  explanationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginBottom: 6,
  },
  explanationTitle: {
    fontSize: 11,
    color: '#2A9D8F',
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  explanationSummary: {
    fontSize: 11,
    lineHeight: 16,
    color: '#5F5A52',
  },
  reasonList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 9,
  },
  reasonPill: {
    borderRadius: 999,
    backgroundColor: '#DDECE6',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  reasonPillText: {
    fontSize: 10,
    color: '#1F6F63',
    fontWeight: '700',
  },
  tradeoffBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: 10,
    padding: 8,
    borderRadius: 10,
    backgroundColor: '#F3E8D2',
  },
  tradeoffText: {
    flex: 1,
    fontSize: 10,
    lineHeight: 14,
    color: '#9A6A2F',
    fontWeight: '600',
  },
  daysRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 24,
    marginBottom: 4,
  },
  daysBtnMinus: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: '#2A9D8F',
    alignItems: 'center',
    justifyContent: 'center',
  },
  daysBtnMinusText: {
    fontSize: 20,
    color: '#2A9D8F',
    lineHeight: 24,
  },
  daysNumber: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 52,
    color: '#1A1614',
  },
  daysBtnPlus: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#2A9D8F',
    alignItems: 'center',
    justifyContent: 'center',
  },
  daysBtnPlusText: {
    fontSize: 20,
    color: '#fff',
    lineHeight: 24,
  },
  daysLabel: {
    fontFamily: 'JetBrainsMono_400Regular',
    fontSize: 9,
    color: '#888780',
    letterSpacing: 1.5,
    textAlign: 'center',
    marginBottom: 12,
  },
  generateContainer: {
    position: 'absolute',
    left: 24,
    right: 24,
    gap: 8,
  },
  generateBtn: {
    borderRadius: 28,
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  generateBtnText: {
    fontFamily: 'Inter_500Medium',
    fontSize: 15,
    color: '#fff',
  },
  interactiveBtn: {
    borderRadius: 28,
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#F5F1EA',
    borderWidth: 1.5,
    borderColor: '#2A9D8F',
  },
  interactiveBtnDisabled: {
    borderColor: '#D3D1C7',
    opacity: 0.65,
  },
  interactiveBtnText: {
    fontFamily: 'Inter_500Medium',
    fontSize: 15,
    color: '#2A9D8F',
  },
  pickHint: {
    fontFamily: 'JetBrainsMono_400Regular',
    fontSize: 10,
    color: '#888780',
    letterSpacing: 1,
    textAlign: 'center',
    marginTop: 8,
  },
})
