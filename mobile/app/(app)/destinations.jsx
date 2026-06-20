import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Modal,
  Animated,
  Dimensions
} from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { useRouter } from 'expo-router'
import { useState, useEffect, useRef } from 'react'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { Image as ExpoImage } from 'expo-image'
import apiClient from '../../services/api'
import { getCurrentUserSessionId } from '../../services/session'
import { useAuth } from '../../context/AuthContext'
import PlanTripModal from './components/PlanTripModal'

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window')

function slugToLabel(slug) {
  return slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

export default function DestinationsScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { user } = useAuth()
  const [countries, setCountries] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCountry, setSelectedCountry] = useState(null)
  const [selectedCard, setSelectedCard] = useState(null)
  const [showCardModal, setShowCardModal] = useState(false)
  const backdropOpacity = useRef(new Animated.Value(0)).current
  const cardScale = useRef(new Animated.Value(0.92)).current
  const cardTranslateY = useRef(new Animated.Value(40)).current
  const cardOpacity = useRef(new Animated.Value(0)).current

  useEffect(() => {
    async function load() {
      try {
        setLoading(true)
        const sessionId = await getCurrentUserSessionId(user)
        if (!sessionId) {
          setCountries([])
          return
        }
        const { data } = await apiClient.get('/quiz/v4/results/' + sessionId)
        const list = data.top_countries || []
        const sorted = list.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        setCountries(sorted.slice(0, 10))
      } catch {
        setCountries([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [user?.id])

  function handleCardPress(item) {
    setSelectedCard(item)
    setShowCardModal(true)
    cardTranslateY.setValue(40)
    Animated.parallel([
      Animated.timing(backdropOpacity, { toValue: 1, duration: 300, useNativeDriver: true }),
      Animated.spring(cardScale, { toValue: 1, tension: 80, friction: 8, useNativeDriver: true }),
      Animated.timing(cardTranslateY, { toValue: 0, duration: 300, useNativeDriver: true }),
      Animated.timing(cardOpacity, { toValue: 1, duration: 250, useNativeDriver: true }),
    ]).start()
  }

  function handleCardClose() {
    Animated.parallel([
      Animated.timing(backdropOpacity, { toValue: 0, duration: 200, useNativeDriver: true }),
      Animated.timing(cardScale, { toValue: 0.92, duration: 200, useNativeDriver: true }),
      Animated.timing(cardTranslateY, { toValue: 40, duration: 200, useNativeDriver: true }),
      Animated.timing(cardOpacity, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => {
      setShowCardModal(false)
      setSelectedCard(null)
    })
  }

  function handlePlanTrip() {
    handleCardClose()
    setTimeout(() => {
      setSelectedCountry({
        id: selectedCard?.country_id,
        name: selectedCard?.country_name,
        flag_emoji: selectedCard?.flag_emoji || selectedCard?.iso2,
      })
    }, 300)
  }

  const renderItem = ({ item }) => {
    const matchPct = Math.round((item.score ?? 0) * 100)
    const tags = (item.matching_tags || []).slice(0, 3)

    return (
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.88}
        onPress={() => handleCardPress(item)}
      >
        <View style={styles.heroWrap}>
          <ExpoImage
            source={{ uri: item.image_url }}
            style={styles.heroImage}
            contentFit="cover"
          />
          <View style={styles.scoreBadge}>
            <Text style={styles.scoreText}>• {matchPct}%</Text>
          </View>
        </View>

        <View style={styles.cardContent}>
          <View style={styles.cardNameRow}>
            <Text style={styles.cardName}>{item.country_name}</Text>
            {(item.flag_emoji || item.iso2) ? (
              <Text style={styles.cardFlag}>{item.flag_emoji || item.iso2}</Text>
            ) : null}
          </View>
          <View style={styles.tagsRow}>
            {tags.map((tag, i) => (
              <View key={i} style={styles.tag}>
                <Text style={styles.tagText}>{slugToLabel(tag)}</Text>
              </View>
            ))}
          </View>
        </View>
      </TouchableOpacity>
    )
  }

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + 16 }]}>
        <TouchableOpacity
          onPress={() => router.canGoBack() ? router.back() : router.replace('/(app)/dashboard')}
        >
          <View style={styles.backBtn}>
            <Ionicons name="arrow-back" size={20} color="#1A1614" />
          </View>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>All destinations</Text>
      </View>

      {loading ? (
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color="#2A9D8F" />
        </View>
      ) : (
        <FlatList
          data={countries}
          keyExtractor={(item, i) => item.country_id ? String(item.country_id) : String(i)}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      )}

      {/* Animated modal */}
      <Modal visible={showCardModal} transparent animationType="none" onRequestClose={handleCardClose}>
        <Animated.View style={[StyleSheet.absoluteFillObject, styles.modalBackdrop, { opacity: backdropOpacity }]}>
          <TouchableOpacity style={{ flex: 1 }} onPress={handleCardClose} activeOpacity={1} />
        </Animated.View>

        <Animated.View style={[styles.modalCard, { transform: [{ scale: cardScale }, { translateY: cardTranslateY }], opacity: cardOpacity }]}>
          <View style={styles.modalHeader}>
            <View style={styles.modalTitleRow}>
              <Text style={styles.modalFlag}>{selectedCard?.flag_emoji || selectedCard?.iso2}</Text>
              <Text style={styles.modalCountryName}>{selectedCard?.country_name}</Text>
            </View>
            <TouchableOpacity onPress={handleCardClose} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
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

          {(selectedCard?.matching_reasons || []).length > 0 && (
            <View style={styles.modalReasons}>
              <Text style={styles.modalReasonsTitle}>Why it fits</Text>
              {(selectedCard.matching_reasons || []).slice(0, 2).map((reason) => (
                <Text key={reason.tag_slug} style={styles.modalReasonText} numberOfLines={2}>
                  {reason.reason}
                </Text>
              ))}
            </View>
          )}

          <TouchableOpacity
            style={styles.modalPlanBtn}
            activeOpacity={0.85}
            onPress={handlePlanTrip}
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
    gap: 12,
    paddingHorizontal: 24,
    paddingBottom: 16,
    borderBottomWidth: 0.5,
    borderBottomColor: '#E0DAD0',
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#EFEAE0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 24,
    color: '#1A1A2E',
  },
  loadingWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  listContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 32,
  },

  /* Cards */
  card: {
    backgroundColor: '#fff',
    borderRadius: 20,
    overflow: 'hidden',
    marginBottom: 16,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
  },
  heroWrap: {
    position: 'relative',
  },
  heroImage: {
    width: '100%',
    height: 160,
  },
  scoreBadge: {
    position: 'absolute',
    top: 12,
    right: 12,
    backgroundColor: 'rgba(42,157,143,0.85)',
    borderRadius: 20,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  scoreText: {
    fontSize: 12,
    color: '#fff',
    fontWeight: '600',
  },
  cardContent: {
    padding: 16,
  },
  cardNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  cardName: {
    fontSize: 18,
    color: '#1A1A2E',
    fontWeight: '600',
    flex: 1,
  },
  cardFlag: {
    fontSize: 22,
    marginLeft: 8,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  tag: {
    backgroundColor: 'rgba(107,124,90,0.13)',
    borderRadius: 20,
    paddingVertical: 3,
    paddingHorizontal: 10,
  },
  tagText: {
    fontSize: 11,
    color: '#6B7C5A',
  },

  /* Animated modal */
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
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 24,
    color: '#1A1A2E',
    flex: 1,
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
    backgroundColor: 'rgba(107,124,90,0.13)',
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  modalTagText: {
    fontSize: 11,
    color: '#6B7C5A',
  },
  modalDesc: {
    fontSize: 13,
    color: '#888780',
    lineHeight: 20,
    marginBottom: 16,
  },
  modalReasons: {
    borderTopWidth: 1,
    borderTopColor: '#E0DAD0',
    paddingTop: 12,
    marginBottom: 20,
    gap: 6,
  },
  modalReasonsTitle: {
    fontSize: 10,
    letterSpacing: 1.1,
    color: '#888780',
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  modalReasonText: {
    fontSize: 12,
    color: '#1A1A2E',
    lineHeight: 17,
  },
  modalPlanBtn: {
    backgroundColor: '#2A9D8F',
    borderRadius: 24,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalPlanBtnText: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '500',
  },
})
