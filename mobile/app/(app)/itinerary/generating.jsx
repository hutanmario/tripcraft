import { useEffect, useRef, useState } from 'react'
import { View, Text, StyleSheet, Animated, Alert } from 'react-native'
import { useRouter, useLocalSearchParams } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import apiClient from '../../../services/api'

const STEPS = [
  { label: 'Scoring attractions for your taste', delay: 0 },
  { label: 'Optimizing route', delay: 1200 },
  { label: 'Allocating days per city', delay: 2400 },
  { label: 'Building your itinerary', delay: 3400 },
]

export default function ItineraryLoadingScreen() {
  const router = useRouter()
  const { plan_id, group_trip_id } = useLocalSearchParams()
  const progressAnim = useRef(new Animated.Value(0)).current
  const [activeStep, setActiveStep] = useState(0)
  const [fetchDone, setFetchDone] = useState(false)
  const [minTimeDone, setMinTimeDone] = useState(false)
  const fetchedPlanId = useRef(null)

  useEffect(() => {
    Animated.timing(progressAnim, {
      toValue: 0.85,
      duration: 3500,
      useNativeDriver: false,
    }).start()

    const stepTimers = STEPS.map((step, i) =>
      setTimeout(() => setActiveStep(i + 1), step.delay)
    )

    const minTimer = setTimeout(() => setMinTimeDone(true), 4000)

    apiClient.get(`/itinerary/plan/${plan_id}/full`)
      .then(() => {
        fetchedPlanId.current = plan_id
        setFetchDone(true)
      })
      .catch((e) => {
        Alert.alert('Error', e.response?.data?.detail || e.message || 'Something went wrong')
        router.back()
      })

    return () => {
      stepTimers.forEach(clearTimeout)
      clearTimeout(minTimer)
    }
  }, [])

  useEffect(() => {
    if (fetchDone && minTimeDone) {
      Animated.timing(progressAnim, {
        toValue: 1,
        duration: 200,
        useNativeDriver: false,
      }).start(() => {
        router.replace(
          '/(app)/generated-itinerary?plan_id=' +
          (fetchedPlanId.current ?? plan_id) +
          (group_trip_id ? '&group_trip_id=' + group_trip_id : '')
        )
      })
    }
  }, [fetchDone, minTimeDone])

  const progressWidth = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  })

  return (
    <View style={styles.root}>
      <View style={styles.iconCircle}>
        <Ionicons name="map-outline" size={28} color="#2A9D8F" />
      </View>

      <Text style={styles.title}>Building your itinerary</Text>
      <Text style={styles.subtitle}>Finding the best route across cities</Text>

      <View style={styles.progressTrack}>
        <Animated.View style={[styles.progressFill, { width: progressWidth }]} />
      </View>

      <View style={styles.stepsList}>
        {STEPS.map((step, i) => {
          const done = activeStep > i + 1
          const active = activeStep === i + 1
          return (
            <View key={i} style={styles.stepRow}>
              <View style={[
                styles.dot,
                done && styles.dotDone,
                active && styles.dotActive,
              ]} />
              <Text style={[
                styles.stepText,
                done && styles.stepDone,
                active && styles.stepActive,
              ]}>
                {step.label}
              </Text>
            </View>
          )
        })}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#1A1614',
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(42,157,143,0.15)',
    borderWidth: 1.5,
    borderColor: '#2A9D8F',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontFamily: 'InstrumentSerif_400Regular_Italic',
    fontSize: 22,
    color: '#F5F1EA',
    marginTop: 20,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 12,
    color: '#888780',
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 32,
  },
  progressTrack: {
    width: 200,
    height: 3,
    backgroundColor: '#2A2320',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: 3,
    backgroundColor: '#2A9D8F',
    borderRadius: 2,
  },
  stepsList: {
    marginTop: 28,
    alignSelf: 'stretch',
    paddingHorizontal: 40,
    gap: 12,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#2A2320',
  },
  dotDone: {
    backgroundColor: '#6B7C5A',
  },
  dotActive: {
    backgroundColor: '#2A9D8F',
  },
  stepText: {
    fontSize: 11,
    color: '#444',
  },
  stepDone: {
    color: '#6B7C5A',
  },
  stepActive: {
    color: '#F5F1EA',
  },
})
