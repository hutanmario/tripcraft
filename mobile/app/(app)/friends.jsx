import { View, Text, ScrollView, TextInput, StyleSheet, ActivityIndicator, Alert } from 'react-native'
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { useRouter } from 'expo-router'
import { useState, useEffect, useRef } from 'react'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import apiClient from '../../services/api'
import { useAuth } from '../../context/AuthContext'
import BottomTabBar from './components/BottomTabBar'
import { COLORS, FONTS, RADIUS, SHADOWS, SPACING, TYPE } from '../../constants/theme'

const HEADER_HEIGHT = 64

function compatibilityTone(compatibility) {
  if (!compatibility || compatibility.score == null) {
    return { color: COLORS.muted, bg: '#EFEAE0', icon: 'help-circle-outline' }
  }
  if (compatibility.score >= 78) {
    return { color: COLORS.primary, bg: COLORS.tagBg, icon: 'sparkles-outline' }
  }
  if (compatibility.score >= 62) {
    return { color: COLORS.sage, bg: 'rgba(107,124,90,0.13)', icon: 'checkmark-circle-outline' }
  }
  if (compatibility.score >= 45) {
    return { color: '#B58B2E', bg: '#FFF6DF', icon: 'git-compare-outline' }
  }
  return { color: COLORS.error, bg: '#FFF1EC', icon: 'alert-circle-outline' }
}

export default function FriendsScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { user } = useAuth()
  const searchRef = useRef(null)

  const [friends, setFriends] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [pendingRequests, setPendingRequests] = useState([])
  const [selectedFriends, setSelectedFriends] = useState([])
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [removingFriendId, setRemovingFriendId] = useState(null)

  const headerTotalHeight = insets.top + 8 + HEADER_HEIGHT

  useEffect(() => {
    if (user === undefined) return
    if (user?.id) loadFriends()
    else setLoading(false)
  }, [user])

  useEffect(() => {
    const q = searchQuery.trim()
    if (q.length < 2) {
      setSearchResults([])
      setSearching(false)
      return undefined
    }

    let cancelled = false
    setSearching(true)
    const timer = setTimeout(async () => {
      try {
        const { data } = await apiClient.get('/social/users/search?q=' + encodeURIComponent(q))
        if (!cancelled) {
          setSearchResults((data.users || []).filter(u => u.id !== user?.id))
        }
      } catch {
        if (!cancelled) setSearchResults([])
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [searchQuery, user?.id])

  async function loadFriends() {
    try {
      const [friendsRes, pendingRes] = await Promise.all([
        apiClient.get('/social/friends'),
        apiClient.get('/social/friends/pending'),
      ])
      setFriends(friendsRes.data.friends || [])
      setPendingRequests(pendingRes.data.requests || [])
    } catch {
      setFriends([])
      setPendingRequests([])
    } finally {
      setLoading(false)
    }
  }

  function handleSearch(q) {
    setSearchQuery(q)
  }

  async function sendRequest(receiverId) {
    try {
      await apiClient.post('/social/friends/request', { receiver_id: receiverId })
      setSearchResults(prev => prev.map(result =>
        result.id === receiverId
          ? {
              ...result,
              friendship_status: 'request_sent',
              can_send_request: false,
              status_label: 'Request sent',
            }
          : result
      ))
    } catch (e) {
      Alert.alert('Error', e.response?.data?.detail || 'Could not send request.')
    }
  }

  async function acceptRequest(friendshipId) {
    try {
      await apiClient.put('/social/friends/accept/' + friendshipId)
      loadFriends()
      return true
    } catch (e) {
      Alert.alert('Error', 'Could not accept request.')
      return false
    }
  }

  async function declineRequest(friendshipId) {
    try {
      await apiClient.put('/social/friends/decline/' + friendshipId)
      loadFriends()
      return true
    } catch (e) {
      Alert.alert('Error', 'Could not decline request.')
      return false
    }
  }

  function removeFriend(friend) {
    Alert.alert(
      'Remove friend?',
      `${friend.full_name || friend.username} will be removed from your friends list.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            setRemovingFriendId(friend.id)
            try {
              await apiClient.delete('/social/friends/' + friend.id)
              setFriends(prev => prev.filter(item => item.id !== friend.id))
              setSelectedFriends(prev => prev.filter(item => item.id !== friend.id))
            } catch (e) {
              Alert.alert('Error', e.response?.data?.detail || 'Could not remove friend.')
            } finally {
              setRemovingFriendId(null)
            }
          },
        },
      ]
    )
  }

  function toggleFriend(friend) {
    setSelectedFriends(prev =>
      prev.find(f => f.id === friend.id)
        ? prev.filter(f => f.id !== friend.id)
        : [...prev, friend]
    )
  }

  function navigateToGroupTrip() {
    const ids = selectedFriends.map(f => f.id).join(',')
    const names = selectedFriends
      .map(f => encodeURIComponent(f.full_name || f.username))
      .join(',')
    router.push(
      '/group-trip?friend_ids=' + ids + '&friend_names=' + names
    )
  }

  function renderCompatibility(friend) {
    const compatibility = friend.compatibility
    if (!compatibility) return null
    const tone = compatibilityTone(compatibility)
    const ready = compatibility.status === 'ready' && compatibility.score != null
    const sharedTags = compatibility.shared_tags || []

    return (
      <View style={styles.compatibilityWrap}>
        <View style={styles.compatibilityTop}>
          <View style={[styles.compatibilityPill, { backgroundColor: tone.bg }]}>
            <Ionicons name={tone.icon} size={12} color={tone.color} />
            <Text style={[styles.compatibilityPillText, { color: tone.color }]}>
              {ready ? `${compatibility.score}%` : 'No profile'}
            </Text>
          </View>
          <Text style={[styles.compatibilityLabel, { color: tone.color }]} numberOfLines={1}>
            {compatibility.label}
          </Text>
        </View>

        <Text style={styles.compatibilitySummary} numberOfLines={2}>
          {compatibility.summary}
        </Text>

        {sharedTags.length > 0 && (
          <View style={styles.sharedTagsRow}>
            {sharedTags.slice(0, 3).map(tag => (
              <View key={tag.slug} style={styles.sharedTag}>
                <Text style={styles.sharedTagText}>{tag.name}</Text>
              </View>
            ))}
          </View>
        )}

        {compatibility.conflict && (
          <View style={styles.conflictPill}>
            <Ionicons name="warning-outline" size={11} color={COLORS.error} />
            <Text style={styles.conflictText} numberOfLines={1}>
              {compatibility.conflict.title}
            </Text>
          </View>
        )}
      </View>
    )
  }

  function renderSearchAction(result) {
    const status = result.friendship_status || 'none'
    if (status === 'request_received' && result.friendship_id) {
      return (
        <TouchableOpacity
          style={[styles.searchStatusBtn, styles.searchStatusPrimary]}
          onPress={async () => {
            if (await acceptRequest(result.friendship_id)) {
              setSearchResults(prev => prev.map(item =>
                item.id === result.id
                  ? { ...item, friendship_status: 'friends', can_send_request: false, status_label: 'Friends' }
                  : item
              ))
            }
          }}
        >
          <Text style={styles.searchStatusPrimaryText}>Accept</Text>
        </TouchableOpacity>
      )
    }

    if (result.can_send_request !== false) {
      return (
        <TouchableOpacity style={styles.addBtn} onPress={() => sendRequest(result.id)}>
          <Text style={styles.addBtnText}>+ Add</Text>
        </TouchableOpacity>
      )
    }

    const label = status === 'request_sent'
      ? 'Sent'
      : status === 'friends'
        ? 'Friends'
        : result.status_label || 'Unavailable'
    return (
      <View style={styles.searchStatusBtn}>
        <Text style={styles.searchStatusText}>{label}</Text>
      </View>
    )
  }

  const initials = (name) => (name ? name[0].toUpperCase() : '?')
  const isSearching = searchQuery.length > 0

  return (
    <View style={styles.root}>
      {/* Absolute header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.headerRow}>
          <TouchableOpacity
            onPress={() => router.canGoBack() ? router.back() : router.replace('/(app)/dashboard')}
          >
            <View style={styles.backBtn}>
              <Ionicons name="chevron-back" size={18} color="#1A1614" />
            </View>
          </TouchableOpacity>

          <Text style={styles.headerTitle}>Friends</Text>

          <View style={styles.countBadge}>
            <Text style={styles.countBadgeText}>{friends.length}</Text>
          </View>
        </View>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.scroll, { paddingTop: headerTotalHeight + 16, paddingBottom: 160 }]}
        keyboardShouldPersistTaps="handled"
      >
        {!isSearching && (
          <View style={styles.heroCard}>
            <View style={styles.heroTopRow}>
              <View style={styles.heroIcon}>
                <Ionicons name="people-outline" size={22} color={COLORS.surface} />
              </View>
              <View style={styles.heroCopy}>
                <Text style={styles.heroLabel}>GROUP TRAVEL</Text>
                <Text style={styles.heroTitle}>Travel is better together.</Text>
                <Text style={styles.heroSubtitle}>
                  Pick friends and TripCraft will blend everyone's preferences into one route.
                </Text>
              </View>
            </View>

            <View style={styles.heroStatsRow}>
              <View style={styles.heroStat}>
                <Text style={styles.heroStatValue}>{friends.length}</Text>
                <Text style={styles.heroStatLabel}>Friends</Text>
              </View>
              <View style={styles.heroStatDivider} />
              <View style={styles.heroStat}>
                <Text style={styles.heroStatValue}>{pendingRequests.length}</Text>
                <Text style={styles.heroStatLabel}>Requests</Text>
              </View>
              <View style={styles.heroStatDivider} />
              <View style={styles.heroStat}>
                <Text style={styles.heroStatValue}>{selectedFriends.length}</Text>
                <Text style={styles.heroStatLabel}>Selected</Text>
              </View>
            </View>

            <TouchableOpacity
              style={styles.heroCta}
              activeOpacity={0.86}
              onPress={() => selectedFriends.length > 0 ? navigateToGroupTrip() : searchRef.current?.focus()}
            >
              <Text style={styles.heroCtaText}>
                {selectedFriends.length > 0 ? 'Build group trip' : 'Find travel partners'}
              </Text>
              <Ionicons name="arrow-forward" size={15} color={COLORS.surface} />
            </TouchableOpacity>
          </View>
        )}

        {!isSearching && (
          <View style={styles.groupStartCard}>
            <View style={styles.groupStartCopy}>
              <Text style={styles.groupStartLabel}>CREATE GROUP TRIP</Text>
              <Text style={styles.groupStartTitle}>
                {selectedFriends.length > 0
                  ? `${selectedFriends.length + 1} travellers ready`
                  : 'Choose your travel crew'}
              </Text>
              <Text style={styles.groupStartSubtitle}>
                {selectedFriends.length > 0
                  ? selectedFriends.map(friend => friend.full_name || friend.username).slice(0, 2).join(', ')
                  : friends.length > 0 ? 'Select friends below to start.' : 'Find friends first, then build a shared trip.'}
              </Text>
            </View>
            <TouchableOpacity
              style={[styles.groupStartBtn, selectedFriends.length === 0 && styles.groupStartBtnMuted]}
              activeOpacity={0.85}
              onPress={() => selectedFriends.length > 0 ? navigateToGroupTrip() : searchRef.current?.focus()}
            >
              <Ionicons
                name={selectedFriends.length > 0 ? 'arrow-forward' : 'search-outline'}
                size={15}
                color={selectedFriends.length > 0 ? COLORS.surface : COLORS.primary}
              />
            </TouchableOpacity>
          </View>
        )}

        {/* Search bar */}
        <View style={styles.searchBar}>
          <Ionicons name="search-outline" size={16} color="#888780" />
          <TextInput
            ref={searchRef}
            style={styles.searchInput}
            placeholder="Search users..."
            placeholderTextColor="#888780"
            value={searchQuery}
            onChangeText={handleSearch}
            autoCorrect={false}
            autoCapitalize="none"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => { setSearchQuery(''); setSearchResults([]) }}>
              <Ionicons name="close-circle" size={16} color="#888780" />
            </TouchableOpacity>
          )}
        </View>

        {/* Search results dropdown */}
        {isSearching && (
          <View style={styles.dropdown}>
            <View style={styles.dropdownHeader}>
              <Text style={styles.monoLabel}>SEARCH RESULTS</Text>
              {searching
                ? <ActivityIndicator size="small" color="#888780" />
                : <Text style={styles.monoLabel}>{searchResults.length} FOUND</Text>
              }
            </View>
            {searchResults.map((result, idx) => (
              <View key={result.id} style={[styles.dropdownRow, idx === 0 && { borderTopWidth: 0 }]}>
                <View style={[styles.avatarSm, { backgroundColor: '#2A9D8F' }]}>
                  <Text style={styles.avatarSmText}>{initials(result.username)}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.usernameSmall}>@{result.username}</Text>
                  <Text style={styles.fullNameSmall}>{result.full_name}</Text>
                </View>
                {renderSearchAction(result)}
              </View>
            ))}
            {!searching && searchQuery.trim().length >= 2 && searchResults.length === 0 && (
              <View style={styles.noSearchResults}>
                <Ionicons name="person-add-outline" size={22} color={COLORS.sage} />
                <Text style={styles.noSearchTitle}>No users found</Text>
                <Text style={styles.noSearchText}>Try a username, full name, or a shorter search.</Text>
              </View>
            )}
          </View>
        )}

        {!isSearching && selectedFriends.length > 0 && (
          <View style={styles.selectedTray}>
            <View style={styles.selectedTrayTop}>
              <View>
                <Text style={styles.selectedTrayLabel}>SELECTED CREW</Text>
                <Text style={styles.selectedTrayTitle} numberOfLines={2}>
                  You + {selectedFriends.map(friend => friend.full_name || friend.username).join(', ')}
                </Text>
              </View>
              <TouchableOpacity onPress={() => setSelectedFriends([])} style={styles.clearSelectionBtn}>
                <Text style={styles.clearSelectionText}>Clear</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.selectedAvatarRow}>
              <View style={styles.selectedAvatar}>
                <Text style={styles.selectedAvatarText}>Y</Text>
              </View>
              {selectedFriends.slice(0, 5).map(friend => (
                <View key={friend.id} style={[styles.selectedAvatar, styles.selectedAvatarOverlap]}>
                  <Text style={styles.selectedAvatarText}>{initials(friend.username)}</Text>
                </View>
              ))}
              {selectedFriends.length > 5 && (
                <View style={[styles.selectedAvatar, styles.selectedAvatarOverlap, styles.selectedMoreAvatar]}>
                  <Text style={styles.selectedAvatarText}>+{selectedFriends.length - 5}</Text>
                </View>
              )}
            </View>
          </View>
        )}

        {/* Pending requests */}
        {!isSearching && pendingRequests.length > 0 && (
          <>
            <View style={styles.sectionRow}>
              <View style={[styles.dot, { backgroundColor: '#2A9D8F' }]} />
              <Text style={styles.monoLabel}>REQUESTS</Text>
              <Text style={styles.requestsCount}>• {pendingRequests.length}</Text>
            </View>

            {pendingRequests.map(req => (
              <View key={req.id} style={styles.requestCard}>
                <View style={styles.requestTop}>
                  <View style={[styles.avatarMd, { backgroundColor: '#2A9D8F' }]}>
                    <Text style={styles.avatarMdText}>{initials(req.requester?.username)}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.usernameSmall}>@{req.requester?.username}</Text>
                    <Text style={styles.wantsToTravel}>wants to plan trips with you</Text>
                  </View>
                </View>
                {renderCompatibility(req.requester)}
                <View style={styles.requestActions}>
                  <TouchableOpacity style={styles.acceptBtn} onPress={() => acceptRequest(req.id)}>
                    <Ionicons name="checkmark" size={12} color="#fff" />
                    <Text style={styles.acceptBtnText}>Accept</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.declineBtn} onPress={() => declineRequest(req.id)}>
                    <Text style={styles.declineBtnText}>Decline</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </>
        )}

        {/* Friends section */}
        {!isSearching && (
          <>
            <View style={styles.friendsHeaderRow}>
              <View style={styles.friendsHeaderLeft}>
                <View style={[styles.dot, { backgroundColor: '#6B7C5A' }]} />
                <Text style={styles.monoLabel}>YOUR FRIENDS</Text>
                <Text style={styles.friendsCount}>• {friends.length}</Text>
              </View>
              {selectedFriends.length > 0 && (
                <Text style={styles.selectedCount}>{selectedFriends.length} SELECTED</Text>
              )}
            </View>

            {loading ? (
              <ActivityIndicator size="large" color="#2A9D8F" style={{ marginTop: 40 }} />
            ) : friends.length === 0 ? (
              <View style={styles.emptyState}>
                <View style={styles.emptyIcon}>
                  <Ionicons name="people-outline" size={32} color="#6B7C5A" />
                </View>
                <Text style={styles.emptyTitle}>Start your travel circle.</Text>
                <Text style={styles.emptySubtitle}>
                  Add friends, compare travel styles, then build group trips from shared preferences.
                </Text>
                <View style={styles.emptyChecklist}>
                  {[
                    'Search by username',
                    'Send a friend request',
                    'Create a group trip',
                  ].map((item) => (
                    <View key={item} style={styles.emptyChecklistItem}>
                      <Ionicons name="checkmark-circle-outline" size={14} color={COLORS.primary} />
                      <Text style={styles.emptyChecklistText}>{item}</Text>
                    </View>
                  ))}
                </View>
                <TouchableOpacity
                  style={styles.findFriendsBtn}
                  onPress={() => searchRef.current?.focus()}
                >
                  <Ionicons name="search-outline" size={15} color={COLORS.surface} />
                  <Text style={styles.findFriendsBtnText}>Find friends</Text>
                </TouchableOpacity>
              </View>
            ) : (
              friends.map(friend => {
                const isSelected = !!selectedFriends.find(f => f.id === friend.id)
                return (
                  <TouchableOpacity
                    key={friend.id}
                    activeOpacity={0.7}
                    onPress={() => toggleFriend(friend)}
                    style={[styles.friendCard, isSelected && styles.friendCardSelected]}
                  >
                    <View style={styles.avatarLg}>
                      <Text style={styles.avatarLgText}>{initials(friend.username)}</Text>
                    </View>
                    <View style={styles.friendInfo}>
                      <View style={styles.friendNameRow}>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.friendUsername}>@{friend.username}</Text>
                          <Text style={styles.friendFullName}>{friend.full_name}</Text>
                        </View>
                        <TouchableOpacity
                          style={[styles.manageFriendBtn, removingFriendId === friend.id && styles.manageFriendBtnDisabled]}
                          disabled={removingFriendId === friend.id}
                          onPress={(event) => {
                            event.stopPropagation?.()
                            removeFriend(friend)
                          }}
                          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                        >
                          <Ionicons name="trash-outline" size={14} color={COLORS.error} />
                        </TouchableOpacity>
                      </View>
                      {renderCompatibility(friend)}
                    </View>
                    {isSelected ? (
                      <View style={styles.checkboxSelected}>
                        <Ionicons name="checkmark" size={14} color="#fff" />
                      </View>
                    ) : (
                      <View style={styles.checkboxEmpty} />
                    )}
                  </TouchableOpacity>
                )
              })
            )}
          </>
        )}
      </ScrollView>

      {/* Floating plan trip button */}
      {selectedFriends.length > 0 && (
        <TouchableOpacity
          style={styles.floatingBtn}
          activeOpacity={0.85}
          onPress={navigateToGroupTrip}
        >
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Ionicons name="people-outline" size={18} color="#fff" />
            <Text style={styles.floatingBtnText}>
              Plan trip with {selectedFriends.length + 1} people
            </Text>
          </View>
          <View style={styles.floatingArrow}>
            <Ionicons name="arrow-forward" size={16} color="#fff" />
          </View>
        </TouchableOpacity>
      )}

      <BottomTabBar />
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#F5F1EA',
  },
  header: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 10,
    backgroundColor: '#F5F1EA',
    paddingBottom: 12,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
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
  countBadge: {
    backgroundColor: '#2A9D8F',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  countBadgeText: {
    fontSize: 12,
    color: '#fff',
    fontWeight: '500',
  },
  scroll: {
    flexGrow: 1,
  },
  heroCard: {
    marginHorizontal: 24,
    marginBottom: 14,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.lg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: SPACING.md,
    ...SHADOWS.sm,
  },
  heroTopRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: SPACING.md,
  },
  heroIcon: {
    width: 44,
    height: 44,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroCopy: {
    flex: 1,
  },
  heroLabel: {
    fontFamily: FONTS.sansSemi,
    fontSize: 10,
    color: COLORS.primary,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  heroTitle: {
    ...TYPE.serifItalic,
    fontSize: 24,
    color: COLORS.dark,
    lineHeight: 28,
  },
  heroSubtitle: {
    marginTop: 7,
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: COLORS.muted,
    lineHeight: 19,
  },
  heroStatsRow: {
    marginTop: SPACING.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: COLORS.cream,
    borderRadius: RADIUS.md,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  heroStat: {
    flex: 1,
    alignItems: 'center',
  },
  heroStatValue: {
    fontFamily: FONTS.sansSemi,
    fontSize: 16,
    color: COLORS.dark,
  },
  heroStatLabel: {
    marginTop: 2,
    fontFamily: FONTS.sans,
    fontSize: 10,
    color: COLORS.muted,
  },
  heroStatDivider: {
    width: 1,
    height: 28,
    backgroundColor: COLORS.border,
  },
  heroCta: {
    marginTop: SPACING.md,
    height: 44,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  heroCtaText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 14,
    color: COLORS.surface,
  },
  groupStartCard: {
    marginHorizontal: 24,
    marginBottom: 14,
    backgroundColor: COLORS.dark,
    borderRadius: RADIUS.md,
    padding: SPACING.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.md,
    ...SHADOWS.sm,
  },
  groupStartCopy: {
    flex: 1,
  },
  groupStartLabel: {
    fontFamily: FONTS.sansSemi,
    fontSize: 10,
    color: COLORS.tagBg,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  groupStartTitle: {
    ...TYPE.serifItalic,
    fontSize: 21,
    color: COLORS.surface,
    lineHeight: 25,
  },
  groupStartSubtitle: {
    marginTop: 5,
    fontFamily: FONTS.sans,
    fontSize: 12,
    color: '#D8D5CE',
  },
  groupStartBtn: {
    width: 42,
    height: 42,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  groupStartBtnMuted: {
    backgroundColor: COLORS.surface,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#EFEAE0',
    borderRadius: 22,
    height: 44,
    paddingHorizontal: 14,
    marginHorizontal: 24,
    marginBottom: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: '#1A1614',
  },
  dropdown: {
    backgroundColor: '#fff',
    borderRadius: 16,
    marginHorizontal: 24,
    marginTop: 4,
    marginBottom: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
    overflow: 'hidden',
  },
  dropdownHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  dropdownRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderTopWidth: 0.5,
    borderTopColor: '#F5F1EA',
  },
  avatarSm: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarSmText: {
    fontSize: 15,
    color: '#fff',
    fontWeight: '600',
  },
  usernameSmall: {
    fontFamily: 'Inter_500Medium',
    fontSize: 13,
    color: '#1A1614',
  },
  fullNameSmall: {
    fontFamily: 'Inter_400Regular',
    fontSize: 11,
    color: '#888780',
  },
  addBtn: {
    borderWidth: 1,
    borderColor: '#6B7C5A',
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 5,
    backgroundColor: 'transparent',
  },
  addBtnText: {
    fontFamily: 'Inter_400Regular',
    fontSize: 12,
    color: '#6B7C5A',
  },
  searchStatusBtn: {
    borderRadius: RADIUS.full,
    paddingHorizontal: 11,
    paddingVertical: 6,
    backgroundColor: COLORS.cream,
  },
  searchStatusPrimary: {
    backgroundColor: COLORS.primary,
  },
  searchStatusText: {
    fontFamily: FONTS.sansMedium,
    fontSize: 11,
    color: COLORS.muted,
  },
  searchStatusPrimaryText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    color: COLORS.surface,
  },
  noSearchResults: {
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 18,
    gap: 5,
  },
  noSearchTitle: {
    fontFamily: FONTS.sansSemi,
    fontSize: 13,
    color: COLORS.dark,
  },
  noSearchText: {
    fontFamily: FONTS.sans,
    fontSize: 12,
    color: COLORS.muted,
    textAlign: 'center',
  },
  selectedTray: {
    marginHorizontal: 24,
    marginTop: 8,
    marginBottom: 10,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: SPACING.md,
    ...SHADOWS.sm,
  },
  selectedTrayTop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: SPACING.sm,
  },
  selectedTrayLabel: {
    fontFamily: FONTS.sansSemi,
    fontSize: 10,
    color: COLORS.primary,
    textTransform: 'uppercase',
    marginBottom: 3,
  },
  selectedTrayTitle: {
    fontFamily: FONTS.sansMedium,
    fontSize: 13,
    color: COLORS.dark,
    maxWidth: 230,
  },
  clearSelectionBtn: {
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.cream,
    paddingVertical: 5,
    paddingHorizontal: 10,
  },
  clearSelectionText: {
    fontFamily: FONTS.sansMedium,
    fontSize: 11,
    color: COLORS.muted,
  },
  selectedAvatarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: SPACING.sm,
  },
  selectedAvatar: {
    width: 30,
    height: 30,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.dark,
    borderWidth: 1,
    borderColor: COLORS.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  selectedAvatarOverlap: {
    marginLeft: -8,
  },
  selectedMoreAvatar: {
    backgroundColor: COLORS.primary,
  },
  selectedAvatarText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    color: COLORS.surface,
  },
  sectionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginHorizontal: 24,
    marginTop: 20,
    marginBottom: 8,
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
    letterSpacing: 1,
  },
  requestsCount: {
    fontSize: 10,
    color: '#2A9D8F',
    fontWeight: '600',
  },
  requestCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 14,
    marginHorizontal: 24,
    marginBottom: 8,
  },
  requestTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  avatarMd: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarMdText: {
    fontSize: 16,
    color: '#fff',
    fontWeight: '600',
  },
  wantsToTravel: {
    fontFamily: 'Inter_400Regular',
    fontSize: 11,
    color: '#888780',
    fontStyle: 'italic',
    marginTop: 2,
  },
  requestActions: {
    flexDirection: 'row',
    gap: 8,
  },
  acceptBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    backgroundColor: '#6B7C5A',
    borderRadius: 12,
    paddingVertical: 8,
  },
  acceptBtnText: {
    fontFamily: 'Inter_500Medium',
    fontSize: 12,
    color: '#fff',
  },
  declineBtn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EFEAE0',
    borderRadius: 12,
    paddingVertical: 8,
  },
  declineBtnText: {
    fontFamily: 'Inter_400Regular',
    fontSize: 12,
    color: '#888780',
  },
  friendsHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: 24,
    marginTop: 20,
    marginBottom: 8,
  },
  friendsHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  friendsCount: {
    fontSize: 10,
    color: '#6B7C5A',
    fontWeight: '600',
  },
  selectedCount: {
    fontFamily: 'JetBrainsMono_400Regular',
    fontSize: 10,
    color: '#2A9D8F',
    letterSpacing: 1,
  },
  emptyState: {
    alignItems: 'center',
    marginTop: 60,
  },
  emptyIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#EFEAE0',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  emptyTitle: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 20,
    color: '#1A1614',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontFamily: 'Inter_400Regular',
    fontSize: 13,
    color: '#888780',
    textAlign: 'center',
    paddingHorizontal: 32,
    marginBottom: 14,
    lineHeight: 19,
  },
  emptyChecklist: {
    alignSelf: 'stretch',
    marginHorizontal: 32,
    marginBottom: 22,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    padding: 12,
    gap: 8,
  },
  emptyChecklistItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  emptyChecklistText: {
    fontFamily: FONTS.sans,
    fontSize: 12,
    color: COLORS.dark,
  },
  findFriendsBtn: {
    backgroundColor: '#2A9D8F',
    borderRadius: 24,
    paddingVertical: 12,
    paddingHorizontal: 28,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  findFriendsBtnText: {
    fontFamily: 'Inter_500Medium',
    fontSize: 14,
    color: '#fff',
  },
  friendCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    backgroundColor: '#EFEAE0',
    borderRadius: 16,
    padding: 14,
    marginHorizontal: 24,
    marginBottom: 10,
  },
  friendCardSelected: {
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.primary,
    ...SHADOWS.sm,
  },
  avatarLg: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#1A1614',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarLgText: {
    fontSize: 16,
    color: '#fff',
    fontWeight: '600',
  },
  friendInfo: {
    flex: 1,
  },
  friendNameRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  manageFriendBtn: {
    width: 28,
    height: 28,
    borderRadius: RADIUS.full,
    backgroundColor: '#FFF1EC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  manageFriendBtnDisabled: {
    opacity: 0.45,
  },
  friendUsername: {
    fontFamily: 'Inter_500Medium',
    fontSize: 14,
    color: '#1A1614',
  },
  friendFullName: {
    fontFamily: 'Inter_400Regular',
    fontSize: 12,
    color: '#888780',
    marginTop: 2,
  },
  compatibilityWrap: {
    marginTop: 9,
    gap: 6,
  },
  compatibilityTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  compatibilityPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  compatibilityPillText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 10,
  },
  compatibilityLabel: {
    flex: 1,
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
  },
  compatibilitySummary: {
    fontFamily: FONTS.sans,
    fontSize: 11,
    color: COLORS.muted,
    lineHeight: 16,
  },
  sharedTagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
  },
  sharedTag: {
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    paddingVertical: 3,
    paddingHorizontal: 8,
  },
  sharedTagText: {
    fontFamily: FONTS.sansMedium,
    fontSize: 10,
    color: COLORS.dark,
  },
  conflictPill: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#FFF1EC',
    borderRadius: RADIUS.full,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  conflictText: {
    maxWidth: 180,
    fontFamily: FONTS.sansMedium,
    fontSize: 10,
    color: COLORS.error,
  },
  checkboxSelected: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#2A9D8F',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxEmpty: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#D3D1C7',
  },
  floatingBtn: {
    position: 'absolute',
    bottom: 80,
    left: 24,
    right: 24,
    backgroundColor: '#2A9D8F',
    borderRadius: 28,
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
  },
  floatingBtnText: {
    fontFamily: 'Inter_500Medium',
    fontSize: 15,
    color: '#fff',
  },
  floatingArrow: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
})
