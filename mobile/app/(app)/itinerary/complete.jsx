import { View, Text, StyleSheet, Dimensions, StatusBar, Alert, ActivityIndicator, Modal, Pressable, Animated } from 'react-native'
import TouchableOpacity from '../../../components/ui/SmoothTouchable';
import { useLocalSearchParams, useRouter } from 'expo-router'
import { useRef, useState } from 'react'
import { Ionicons } from '@expo/vector-icons'
import * as Haptics from 'expo-haptics'
import apiClient from '../../../services/api'
import { FONTS, TYPE } from '../../../constants/theme'

const { width: SCREEN_WIDTH } = Dimensions.get('window')

const ASPECTS = [
  { key: 'matches_style', label: 'Matches my style', positive: true },
  { key: 'good_cities',   label: 'Great city picks', positive: true },
  { key: 'too_many_stops', label: 'Too many stops',  positive: false },
  { key: 'wrong_vibe',    label: 'Wrong vibe',       positive: false },
]

export default function ItineraryEndScreen() {
  const { plan_id, num_cities, num_attractions, group_trip_id } = useLocalSearchParams()
  const router = useRouter()
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showRating, setShowRating] = useState(false)
  const [stars, setStars] = useState(0)
  const [aspects, setAspects] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const slideAnim = useRef(new Animated.Value(400)).current

  function openRating() {
    setStars(0); setAspects([])
    Animated.spring(slideAnim, { toValue: 0, tension: 60, friction: 10, useNativeDriver: true }).start()
    setShowRating(true)
  }

  function toggleAspect(key) {
    setAspects(prev => prev.includes(key) ? prev.filter(a => a !== key) : [...prev, key])
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)
  }

  async function submitRating() {
    if (stars === 0) return
    setSubmitting(true)
    try {
      await apiClient.post(`/itinerary/plan/${plan_id}/rate`, { rating: stars, aspects })
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)
      setShowRating(false)
      Alert.alert('Thank you!', 'Your feedback refines future recommendations.')
    } catch { setShowRating(false) }
    finally { setSubmitting(false) }
  }

  async function handleSave() {
    setSaving(true)
    try {
      await apiClient.post('/itinerary/plan/' + plan_id + '/save', {
        group_trip_id: group_trip_id || null,
      })
      setSaved(true)
      openRating()
    } catch (e) {
      Alert.alert('Error', 'Could not save itinerary.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />

      {/* Dots */}
      <View style={styles.dotsRow}>
        <View style={styles.dotInactive} />
        <View style={styles.dotInactive} />
        <View style={styles.dotActive} />
      </View>

      {/* Content */}
      <View style={styles.content}>
        <View style={styles.iconCircle}>
          <Ionicons name="sparkles-outline" size={26} color="#6B7C5A" />
        </View>

        <View style={styles.line} />

        <Text style={styles.title}>That's all.</Text>

        <Text style={styles.subtitle}>
          {num_cities} cities · {num_attractions} attractions · crafted for your taste
        </Text>

        <View style={styles.buttons}>
          <TouchableOpacity
            style={[styles.saveBtn, { backgroundColor: saved ? '#6B7C5A' : '#2A9D8F' }]}
            activeOpacity={0.85}
            onPress={saved ? null : handleSave}
            disabled={saved || saving}
          >
            {saving ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : saved ? (
              <>
                <Ionicons name="checkmark" size={16} color="#fff" />
                <Text style={styles.saveBtnText}>Saved!</Text>
              </>
            ) : (
              <>
                <Ionicons name="bookmark-outline" size={16} color="#fff" />
                <Text style={styles.saveBtnText}>Save itinerary</Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.backBtn}
            activeOpacity={0.85}
            onPress={() => router.replace('/dashboard')}
          >
            <Text style={styles.backBtnText}>Back to dashboard</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Rating modal */}
      <Modal visible={showRating} transparent animationType="fade" onRequestClose={() => setShowRating(false)}>
        <Pressable style={rStyles.backdrop} onPress={() => setShowRating(false)}>
          <Animated.View style={[rStyles.sheet, { transform: [{ translateY: slideAnim }] }]}
            onStartShouldSetResponder={() => true}>
            <View style={rStyles.handle} />
            <Text style={rStyles.title}>How does this plan feel?</Text>
            <View style={rStyles.stars}>
              {[1,2,3,4,5].map(n => (
                <TouchableOpacity key={n} onPress={() => { setStars(n); Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium) }}>
                  <Text style={[rStyles.star, n <= stars && rStyles.starOn]}>★</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={rStyles.aspectsLabel}>Quick feedback (optional)</Text>
            <View style={rStyles.aspectsGrid}>
              {ASPECTS.map(({ key, label, positive }) => {
                const sel = aspects.includes(key)
                return (
                  <TouchableOpacity key={key} onPress={() => toggleAspect(key)}
                    style={[rStyles.pill, sel && (positive ? rStyles.pillPos : rStyles.pillNeg)]}>
                    <Text style={[rStyles.pillText, sel && (positive ? rStyles.pillTextPos : rStyles.pillTextNeg)]}>
                      {sel ? (positive ? '✓ ' : '✗ ') : ''}{label}
                    </Text>
                  </TouchableOpacity>
                )
              })}
            </View>
            <View style={rStyles.actions}>
              <TouchableOpacity style={[rStyles.submit, stars === 0 && rStyles.submitOff]}
                disabled={stars === 0 || submitting} onPress={submitRating}>
                <Text style={rStyles.submitText}>{submitting ? 'Saving...' : 'Submit rating'}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => setShowRating(false)}>
                <Text style={rStyles.skip}>Skip</Text>
              </TouchableOpacity>
            </View>
            <Text style={rStyles.note}>Your rating refines your travel profile for future recommendations.</Text>
          </Animated.View>
        </Pressable>
      </Modal>
    </View>
  )
}

const rStyles = StyleSheet.create({
  backdrop:     { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet:        { backgroundColor: '#F5F1EA', borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingHorizontal: 24, paddingBottom: 40, paddingTop: 12 },
  handle:       { width: 36, height: 4, borderRadius: 2, backgroundColor: '#D0CBC0', alignSelf: 'center', marginBottom: 20 },
  title:        { ...TYPE.serifItalic, fontSize: 26, color: '#1A1614', marginBottom: 24 },
  stars:        { flexDirection: 'row', gap: 10, marginBottom: 24 },
  star:         { fontSize: 38, color: '#D0CBC0' },
  starOn:       { color: '#F4A50D' },
  aspectsLabel: { fontFamily: 'Inter_400Regular', fontSize: 11, color: '#888780', letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 12 },
  aspectsGrid:  { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 28 },
  pill:         { borderWidth: 1, borderColor: '#D0CBC0', borderRadius: 100, paddingVertical: 8, paddingHorizontal: 16, backgroundColor: '#FFFFFF' },
  pillPos:      { borderColor: '#2A9D8F', backgroundColor: '#E6F4F2' },
  pillNeg:      { borderColor: '#E76F51', backgroundColor: '#FDF0EC' },
  pillText:     { fontFamily: 'Inter_500Medium', fontSize: 13, color: '#1A1614' },
  pillTextPos:  { color: '#2A9D8F' },
  pillTextNeg:  { color: '#E76F51' },
  actions:      { gap: 12, alignItems: 'center' },
  submit:       { width: '100%', height: 52, borderRadius: 26, backgroundColor: '#1A1614', alignItems: 'center', justifyContent: 'center' },
  submitOff:    { backgroundColor: '#D0CBC0' },
  submitText:   { fontFamily: 'Inter_600SemiBold', fontSize: 15, color: '#FFFFFF' },
  skip:         { fontFamily: 'Inter_400Regular', fontSize: 13, color: '#888780' },
  note:         { fontFamily: 'Inter_400Regular', fontSize: 11, color: '#B0AB9F', textAlign: 'center', marginTop: 16, lineHeight: 16 },
})

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#1A1614',
  },
  dotsRow: {
    position: 'absolute',
    top: 52,
    alignSelf: 'center',
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
  },
  dotInactive: {
    width: 8,
    height: 3,
    borderRadius: 2,
    backgroundColor: 'rgba(255,255,255,0.35)',
  },
  dotActive: {
    width: 24,
    height: 3,
    borderRadius: 2,
    backgroundColor: '#fff',
  },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(107,124,90,0.1)',
    borderWidth: 1.5,
    borderColor: 'rgba(107,124,90,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  line: {
    width: 24,
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.15)',
    marginBottom: 16,
  },
  title: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 32,
    color: '#F5F1EA',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 13,
    color: '#888780',
    textAlign: 'center',
    marginBottom: 48,
    lineHeight: 20,
  },
  buttons: {
    width: '100%',
    gap: 12,
  },
  saveBtn: {
    borderRadius: 24,
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  saveBtnText: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '500',
  },
  backBtn: {
    borderWidth: 1,
    borderColor: '#333',
    borderRadius: 24,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backBtnText: {
    fontSize: 13,
    color: '#888780',
  },
})
