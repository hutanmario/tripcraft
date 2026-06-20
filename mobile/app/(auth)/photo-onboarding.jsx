import { View, Text, StyleSheet, ScrollView, Image, ActivityIndicator, Alert, StatusBar, Linking } from 'react-native'
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { useRouter } from 'expo-router'
import { useState } from 'react'
import * as ImagePicker from 'expo-image-picker'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import apiClient, { BASE_URL } from '../../services/api'
import { COLORS, FONTS, RADIUS, SHADOWS, TYPE } from '../../constants/theme'
import { savePhotoReviewDraft } from '../../services/photoReviewDraft'

const UPLOAD_TIMEOUT_MS = 30000
const POLL_INTERVAL_MS = 3000
const FIRST_RUN_HINT_MS = 30000
const ANALYSIS_TIMEOUT_MS = 300000
const MAX_PHOTOS = 5

function apiErrorMessage(error, fallback = 'Could not analyze photos.') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map(item => item.msg || item.message).filter(Boolean).join(', ')
  }
  return detail || error?.message || fallback
}

export default function PhotoOnboardingScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const [images, setImages] = useState([])
  const [status, setStatus] = useState(null)
  const [statusMessage, setStatusMessage] = useState(null)
  const [permissionDenied, setPermissionDenied] = useState(false)

  async function pickImages() {
    if (images.length >= MAX_PHOTOS || status) return

    const { status: perm } = await ImagePicker.requestMediaLibraryPermissionsAsync()
    if (perm !== 'granted') {
      setPermissionDenied(true)
      Alert.alert('Permission needed', 'Please allow access to your photos.')
      return
    }
    setPermissionDenied(false)

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      selectionLimit: MAX_PHOTOS - images.length,
      quality: 0.7,
      base64: true,
    })
    if (!result.canceled) {
      setImages(prev => [...prev, ...result.assets].slice(0, MAX_PHOTOS))
    }
  }

  function removeImage(index) {
    setImages(prev => prev.filter((_, i) => i !== index))
  }

  function buildPayload() {
    return {
      files: images.map((img, i) => {
        if (!img.base64) {
          throw new Error('Could not read one of the selected photos. Please choose it again.')
        }
        return {
          data: img.base64,
          name: `photo_${i}.jpg`,
        }
      }),
    }
  }

  async function openPhotoReview(analysisResult) {
    const photoUris = images
      .map(img => img.uri)
      .filter(Boolean)
      .slice(0, MAX_PHOTOS)

    const draftId = await savePhotoReviewDraft({
      photos: photoUris,
      result: analysisResult,
      createdAt: new Date().toISOString(),
    })

    router.push({
      pathname: '/photo-review',
      params: {
        draft: draftId,
      },
    })
  }

  function pollAnalysis(jobId) {
    return new Promise((resolve, reject) => {
      let intervalId = null
      let hintTimerId = null
      let timeoutTimerId = null
      let settled = false

      const cleanup = () => {
        if (intervalId) clearInterval(intervalId)
        if (hintTimerId) clearTimeout(hintTimerId)
        if (timeoutTimerId) clearTimeout(timeoutTimerId)
      }

      const finish = (callback, value) => {
        if (settled) return
        settled = true
        cleanup()
        callback(value)
      }

      const poll = async () => {
        try {
          const { data } = await apiClient.get(`/ml/analyze-status/${jobId}`, {
            timeout: UPLOAD_TIMEOUT_MS,
          })

          if (data.status === 'done') {
            finish(resolve, data.result)
          } else if (data.status === 'error') {
            finish(reject, new Error(data.detail || 'Processing failed'))
          }
        } catch (error) {
          finish(reject, new Error(apiErrorMessage(error, 'Processing failed')))
        }
      }

      intervalId = setInterval(poll, POLL_INTERVAL_MS)
      hintTimerId = setTimeout(() => {
        setStatusMessage('First run downloads the AI model.\nThis may take a few minutes...')
      }, FIRST_RUN_HINT_MS)
      timeoutTimerId = setTimeout(() => {
        finish(reject, new Error('Analysis timed out. Please try again.'))
      }, ANALYSIS_TIMEOUT_MS)

      poll()
    })
  }

  async function analyzePhotos() {
    if (images.length === 0) {
      Alert.alert('No photos', 'Please add at least one photo.')
      return
    }
    if (!BASE_URL) {
      Alert.alert('Error', 'API URL is not configured.')
      return
    }

    try {
      setStatus('uploading')
      setStatusMessage(null)

      const { data: uploadData } = await apiClient.post('/ml/analyze-photos-b64', buildPayload(), {
        timeout: UPLOAD_TIMEOUT_MS,
      })

      const jobId = uploadData?.job_id
      if (!jobId) {
        throw new Error('Server returned no analysis job.')
      }

      setStatus('processing')
      const result = await pollAnalysis(jobId)
      const { session_id } = result || {}
      if (!session_id) {
        throw new Error('Analysis finished without a session id.')
      }

      await openPhotoReview(result)
    } catch (error) {
      Alert.alert('Error', apiErrorMessage(error))
    } finally {
      setStatus(null)
      setStatusMessage(null)
    }
  }

  const photoSlots = Array.from({ length: MAX_PHOTOS }, (_, index) => ({
    index,
    image: images[index],
  }))

  const canContinue = images.length > 0 && !status
  const filledSlots = images.length
  const progressWidth = `${(filledSlots / MAX_PHOTOS) * 100}%`

  const buttonLabel =
    status === 'uploading' ? 'Uploading photos...'
    : status === 'processing' ? 'Analyzing with AI...'
    : images.length === 0 ? 'Add at least one photo'
    : 'Analyze and review'

  return (
    <View style={styles.root}>
      <StatusBar barStyle="dark-content" />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, { paddingTop: insets.top + 16 }]}
      >
        <View style={styles.header}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => router.canGoBack() ? router.back() : router.replace('/(app)/quiz/start')}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Ionicons name="arrow-back" size={20} color={COLORS.ink} />
          </TouchableOpacity>

          <View style={styles.headerCopy}>
            <Text style={styles.eyebrow}>PHOTO SETUP</Text>
            <Text style={styles.title}>Choose your travel photos</Text>
            <Text style={styles.subtitle}>Pick up to five photos that feel close to trips you would actually take.</Text>
          </View>
        </View>

        <View style={styles.counterPanel}>
          <View>
            <Text style={styles.counterLabel}>Selected photos</Text>
            <Text style={styles.counterValue}>{filledSlots}/{MAX_PHOTOS}</Text>
          </View>
          <View style={styles.progressWrap}>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: progressWidth }]} />
            </View>
            <View style={styles.progressDots}>
              {photoSlots.map(slot => (
                <View
                  key={`dot-${slot.index}`}
                  style={[styles.progressDot, slot.index < filledSlots && styles.progressDotActive]}
                />
              ))}
            </View>
          </View>
        </View>

        <View style={styles.grid}>
          {photoSlots.map(slot => {
            const isNextEmptySlot = slot.index === images.length && images.length < MAX_PHOTOS

            if (slot.image) {
              return (
                <View key={`photo-${slot.index}`} style={styles.photoCell}>
                  <Image source={{ uri: slot.image.uri }} style={styles.image} resizeMode="cover" />
                  <View style={styles.photoNumber}>
                    <Text style={styles.photoNumberText}>{slot.index + 1}</Text>
                  </View>
                  <TouchableOpacity
                    style={styles.removeBtn}
                    onPress={() => removeImage(slot.index)}
                    hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                    disabled={!!status}
                  >
                    <Ionicons name="close" size={15} color={COLORS.surface} />
                  </TouchableOpacity>
                </View>
              )
            }

            return (
              <TouchableOpacity
                key={`empty-${slot.index}`}
                style={[
                  styles.emptyCell,
                  !isNextEmptySlot && styles.emptyCellQuiet,
                  (images.length >= MAX_PHOTOS || !!status) && styles.emptyCellDisabled,
                ]}
                onPress={pickImages}
                disabled={images.length >= MAX_PHOTOS || !!status}
              >
                <View style={[styles.emptyIcon, !isNextEmptySlot && styles.emptyIconQuiet]}>
                  <Ionicons name="add" size={22} color={COLORS.primary} />
                </View>
                {isNextEmptySlot && (
                  <Text style={styles.emptyLabel}>
                    {images.length === 0 ? 'Add photos' : 'Add more'}
                  </Text>
                )}
                <Text style={styles.emptyIndex}>{slot.index + 1}</Text>
              </TouchableOpacity>
            )
          })}
        </View>

        {permissionDenied && (
          <View style={styles.permissionCard}>
            <View style={styles.permissionIcon}>
              <Ionicons name="lock-closed-outline" size={17} color={COLORS.error} />
            </View>
            <View style={styles.permissionCopy}>
              <Text style={styles.permissionTitle}>Photo access is blocked</Text>
              <Text style={styles.permissionText}>Enable gallery access to choose photos from your device.</Text>
            </View>
            <TouchableOpacity style={styles.settingsButton} onPress={() => Linking.openSettings?.()}>
              <Ionicons name="settings-outline" size={16} color={COLORS.primary} />
            </TouchableOpacity>
          </View>
        )}

        <View style={styles.privacyCard}>
          <View style={styles.privacyIcon}>
            <Ionicons name="shield-checkmark-outline" size={17} color={COLORS.primary} />
          </View>
          <Text style={styles.privacyText}>Used only to personalize your trip style.</Text>
        </View>

        {status === 'processing' && (
          <View style={styles.statusCard}>
            <ActivityIndicator color={COLORS.primary} size="small" />
            <Text style={styles.processingHint}>
              {statusMessage || 'Detecting visual interests and matching tags...'}
            </Text>
          </View>
        )}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 14) }]}>
        <TouchableOpacity
          style={[styles.analyzeBtn, !canContinue && styles.analyzeBtnDisabled]}
          activeOpacity={0.85}
          onPress={analyzePhotos}
          disabled={!canContinue}
        >
          {status ? (
            <ActivityIndicator color={COLORS.surface} size="small" />
          ) : (
            <Ionicons name={canContinue ? 'sparkles-outline' : 'image-outline'} size={18} color={COLORS.surface} />
          )}
          <Text style={styles.analyzeBtnText}>{buttonLabel}</Text>
        </TouchableOpacity>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },
  content: {
    paddingHorizontal: 20,
    paddingBottom: 150,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 14,
    marginBottom: 22,
  },
  backButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.surface,
    ...SHADOWS.sm,
  },
  headerCopy: {
    flex: 1,
  },
  eyebrow: {
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    letterSpacing: 0.8,
    color: COLORS.primary,
    marginBottom: 5,
  },
  title: {
    ...TYPE.serifItalic,
    fontSize: 31,
    lineHeight: 36,
    color: COLORS.ink,
  },
  subtitle: {
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: COLORS.muted,
    marginTop: 8,
    lineHeight: 20,
  },
  counterPanel: {
    minHeight: 82,
    borderRadius: RADIUS.lg,
    padding: 16,
    marginBottom: 18,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 18,
    ...SHADOWS.sm,
  },
  counterLabel: {
    fontFamily: FONTS.sansMedium,
    fontSize: 12,
    color: COLORS.muted,
    marginBottom: 3,
  },
  counterValue: {
    fontFamily: FONTS.sansBold,
    fontSize: 26,
    color: COLORS.ink,
  },
  progressWrap: {
    flex: 1,
    gap: 11,
  },
  progressTrack: {
    height: 5,
    borderRadius: 3,
    overflow: 'hidden',
    backgroundColor: '#ECE7DE',
  },
  progressFill: {
    height: 5,
    borderRadius: 3,
    backgroundColor: COLORS.primary,
  },
  progressDots: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  progressDot: {
    width: 9,
    height: 9,
    borderRadius: 5,
    backgroundColor: '#DDD8CF',
  },
  progressDotActive: {
    backgroundColor: COLORS.primary,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  photoCell: {
    width: '48.25%',
    aspectRatio: 1,
    borderRadius: RADIUS.md,
    overflow: 'hidden',
    backgroundColor: COLORS.paper,
    ...SHADOWS.sm,
  },
  image: {
    width: '100%',
    height: '100%',
  },
  photoNumber: {
    position: 'absolute',
    left: 9,
    bottom: 9,
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(26,26,46,0.76)',
  },
  photoNumberText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    color: COLORS.surface,
  },
  removeBtn: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(26,26,46,0.55)',
  },
  emptyCell: {
    width: '48.25%',
    aspectRatio: 1,
    borderRadius: RADIUS.md,
    backgroundColor: COLORS.paper,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
  },
  emptyCellQuiet: {
    backgroundColor: 'rgba(250,250,247,0.58)',
  },
  emptyCellDisabled: {
    opacity: 0.55,
  },
  emptyIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.tagBg,
  },
  emptyIconQuiet: {
    opacity: 0.64,
  },
  emptyLabel: {
    fontFamily: FONTS.sansSemi,
    fontSize: 12,
    color: COLORS.primary,
  },
  emptyIndex: {
    position: 'absolute',
    left: 9,
    bottom: 9,
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    color: COLORS.muted,
  },
  permissionCard: {
    minHeight: 74,
    borderRadius: RADIUS.md,
    padding: 13,
    marginBottom: 12,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: 'rgba(231,111,81,0.25)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  permissionIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(231,111,81,0.12)',
  },
  permissionCopy: {
    flex: 1,
  },
  permissionTitle: {
    fontFamily: FONTS.sansSemi,
    fontSize: 13,
    color: COLORS.ink,
    marginBottom: 3,
  },
  permissionText: {
    fontFamily: FONTS.sans,
    fontSize: 12,
    lineHeight: 17,
    color: COLORS.muted,
  },
  settingsButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.tagBg,
  },
  privacyCard: {
    minHeight: 52,
    borderRadius: RADIUS.md,
    paddingHorizontal: 14,
    marginBottom: 14,
    backgroundColor: COLORS.tagBg,
    borderWidth: 1,
    borderColor: 'rgba(42,157,143,0.18)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  privacyIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.surface,
  },
  privacyText: {
    flex: 1,
    fontFamily: FONTS.sansMedium,
    fontSize: 12,
    color: COLORS.primaryDark,
  },
  statusCard: {
    minHeight: 52,
    borderRadius: RADIUS.md,
    paddingHorizontal: 14,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  footer: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 0,
    alignItems: 'center',
    paddingTop: 10,
    paddingHorizontal: 8,
    borderTopLeftRadius: 30,
    borderTopRightRadius: 30,
    backgroundColor: 'rgba(250,250,247,0.96)',
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    ...SHADOWS.md,
  },
  analyzeBtn: {
    width: '100%',
    backgroundColor: COLORS.primary,
    borderRadius: 24,
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  analyzeBtnDisabled: {
    backgroundColor: '#A5B7B3',
  },
  analyzeBtnText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 15,
    color: COLORS.surface,
  },
  processingHint: {
    flex: 1,
    fontFamily: FONTS.sans,
    fontSize: 12,
    lineHeight: 17,
    color: COLORS.muted,
  },
})
