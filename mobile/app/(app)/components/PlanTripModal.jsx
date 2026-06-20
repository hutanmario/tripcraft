import {
  useState } from 'react'
import { Modal,
  View,
  Text,
  StyleSheet,
  Alert,
  ActivityIndicator
} from 'react-native';
import TouchableOpacity from '../../../components/ui/SmoothTouchable';

import { useRouter } from 'expo-router'
import Slider from '@react-native-community/slider'
import { Ionicons } from '@expo/vector-icons'
import apiClient from '../../../services/api'
import { getCurrentUserSessionId } from '../../../services/session'
import { COLORS } from '../../../constants/theme'
import { useAuth } from '../../../context/AuthContext'

export default function PlanTripModal({ visible, country, onClose }) {
  const router = useRouter()
  const { user } = useAuth()
  const [numDays, setNumDays] = useState(5)
  const [loading, setLoading] = useState(false)

  const citiesCount = numDays > 7 ? '5' : numDays > 3 ? '3' : '2'

  async function handleGenerate() {
    setLoading(true)
    try {
      const session_id = await getCurrentUserSessionId(user)
      if (!session_id) {
        Alert.alert('Error', 'Could not find your quiz session. Please retake the quiz.')
        return
      }

      const { data } = await apiClient.post('/itinerary/generate', {
        country_id: country.id,
        nr_zile: numDays,
        session_id,
      })
      onClose()
      router.push({
        pathname: '/(app)/itinerary/generating',
        params: { plan_id: String(data.plan_id) },
      })
    } catch (e) {
      Alert.alert('Error', e.response?.data?.detail || e.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal animationType="slide" transparent={true} visible={visible}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={styles.dragHandle} />

          <View style={styles.header}>
            <View style={styles.countryRow}>
              <Text style={styles.flag}>{country?.flag_emoji}</Text>
              <Text style={styles.countryName}>{country?.name}</Text>
            </View>
            <Text style={styles.subtitle}>How many days are you planning to stay?</Text>
          </View>

          <View style={styles.daysSelector}>
            <View style={styles.daysRow}>
              <TouchableOpacity
                style={styles.btnMinus}
                onPress={() => setNumDays(d => Math.max(3, d - 1))}
              >
                <Text style={styles.btnMinusText}>−</Text>
              </TouchableOpacity>

              <Text style={styles.daysNumber}>{numDays}</Text>

              <TouchableOpacity
                style={styles.btnPlus}
                onPress={() => setNumDays(d => Math.min(10, d + 1))}
              >
                <Text style={styles.btnPlusText}>+</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.daysLabel}>DAYS</Text>
          </View>

          <View style={styles.sliderContainer}>
            <Slider
              minimumValue={3}
              maximumValue={10}
              step={1}
              value={numDays}
              onValueChange={setNumDays}
              thumbTintColor={COLORS.teal}
              minimumTrackTintColor={COLORS.teal}
              maximumTrackTintColor="#D3D1C7"
              style={styles.slider}
            />
          </View>

          <View style={styles.infoStrip}>
            <Ionicons name="calendar-outline" size={14} color="#6B7C5A" />
            <Text style={styles.infoText}>
              We'll plan across {citiesCount} cities based on your taste.
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.generateBtn, loading && styles.generateBtnDisabled]}
            onPress={handleGenerate}
            disabled={loading}
            activeOpacity={0.85}
          >
            <View style={styles.generateBtnRow}>
              {loading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Ionicons name="navigate-outline" size={16} color="#fff" />
              )}
              <Text style={styles.generateBtnText}>
                {loading ? 'Generating...' : 'Generate Itinerary'}
              </Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.interactiveBtn}
            activeOpacity={0.85}
            onPress={() => {
              onClose();
              router.push({
                pathname: '/(app)/interactive-mode',
                params: {
                  country: country?.name,
                  country_id: country?.id ? String(country.id) : '',
                  country_name: country?.name || '',
                  days: String(numDays),
                },
              });
            }}
          >
            <Text style={styles.interactiveBtnText}>✦ Fully Interactive Mode</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.cancelBtn} onPress={onClose}>
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  )
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(26,22,20,0.6)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: '#EFEAE0',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 24,
    paddingTop: 0,
    paddingBottom: 20,
  },
  dragHandle: {
    width: 36,
    height: 3,
    backgroundColor: '#888780',
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: 12,
    marginBottom: 14,
  },
  header: {
    marginBottom: 0,
  },
  countryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  flag: {
    fontSize: 28,
  },
  countryName: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 24,
    color: '#1A1614',
  },
  subtitle: {
    fontSize: 13,
    color: '#888780',
    marginTop: 4,
  },
  daysSelector: {
    marginTop: 12,
    alignItems: 'center',
  },
  daysRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 24,
  },
  btnMinus: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: COLORS.teal,
    justifyContent: 'center',
    alignItems: 'center',
  },
  btnMinusText: {
    fontSize: 20,
    color: COLORS.teal,
  },
  daysNumber: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 42,
    color: '#1A1614',
  },
  btnPlus: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: COLORS.teal,
    justifyContent: 'center',
    alignItems: 'center',
  },
  btnPlusText: {
    fontSize: 20,
    color: '#fff',
  },
  daysLabel: {
    fontFamily: 'JetBrainsMono_400Regular',
    fontSize: 9,
    color: '#888780',
    letterSpacing: 1.5,
    marginTop: 4,
    alignSelf: 'center',
  },
  sliderContainer: {
    marginTop: 6,
  },
  slider: {
    width: '100%',
  },
  infoStrip: {
    marginTop: 8,
    backgroundColor: '#F5F1EA',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  infoText: {
    fontSize: 11,
    color: '#888780',
  },
  generateBtn: {
    marginTop: 14,
    backgroundColor: COLORS.teal,
    borderRadius: 26,
    height: 52,
    justifyContent: 'center',
    alignItems: 'center',
  },
  generateBtnDisabled: {
    opacity: 0.6,
  },
  generateBtnRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  generateBtnText: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '500',
  },
  interactiveBtn: {
    marginTop: 10,
    height: 52,
    borderRadius: 100,
    borderWidth: 1.5,
    borderColor: '#2A9D8F',
    backgroundColor: 'transparent',
    justifyContent: 'center',
    alignItems: 'center',
  },
  interactiveBtnText: {
    fontSize: 14,
    color: '#2A9D8F',
    fontWeight: '600',
  },
  cancelBtn: {
    marginTop: 10,
    marginBottom: 4,
    alignItems: 'center',
    paddingVertical: 6,
  },
  cancelText: {
    fontSize: 12,
    color: '#888780',
    textAlign: 'center',
  },
})
