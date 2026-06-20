import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Image, ScrollView, StatusBar, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import apiClient, { BASE_URL } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { setCurrentUserSessionId } from '../../services/session';
import { clearPhotoReviewDraft, loadPhotoReviewDraft } from '../../services/photoReviewDraft';
import { COLORS, FONTS, RADIUS, SHADOWS, TYPE } from '../../constants/theme';

const SAMPLE_TAGS = [
  { slug: 'sandy-beaches', name: 'Sandy beaches', score: 0.94, level: 'Strong' },
  { slug: 'food-markets', name: 'Food markets', score: 0.91, level: 'Strong' },
  { slug: 'castles-palaces', name: 'Castles & palaces', score: 0.86, level: 'Strong' },
  { slug: 'historical-sites', name: 'Historical sites', score: 0.74, level: 'Medium' },
  { slug: 'farmers-markets', name: 'Farmers markets', score: 0.68, level: 'Medium' },
  { slug: 'coastal-walks', name: 'Coastal walks', score: 0.55, level: 'Light' },
];

const SUGGESTED_TAGS = [
  { slug: 'hiking', name: 'Hiking' },
  { slug: 'contemporary-art', name: 'Contemporary art' },
  { slug: 'wine-vineyards', name: 'Wine regions' },
  { slug: 'rooftop-views', name: 'Rooftop views' },
];

const SAMPLE_PHOTOS = [
  {
    file: 'sandy-beaches.jpg',
    label: 'Coast',
    icon: 'sunny-outline',
    colors: ['#BDE8E1', '#F7DCA8'],
  },
  {
    file: 'street-food.jpg',
    label: 'Markets',
    icon: 'basket-outline',
    colors: ['#F3C985', '#D86945'],
  },
  {
    file: 'castles-palaces.jpg',
    label: 'Heritage',
    icon: 'business-outline',
    colors: ['#C7D6B6', '#8B7860'],
  },
];

const SELECTED_PHOTO_FALLBACKS = [
  {
    label: 'Photo 1',
    icon: 'image-outline',
    colors: ['#BDE8E1', '#F7DCA8'],
  },
  {
    label: 'Photo 2',
    icon: 'images-outline',
    colors: ['#F3C985', '#D86945'],
  },
  {
    label: 'Photo 3',
    icon: 'camera-outline',
    colors: ['#C7D6B6', '#8B7860'],
  },
  {
    label: 'Photo 4',
    icon: 'aperture-outline',
    colors: ['#D8D4C9', '#87917B'],
  },
  {
    label: 'Photo 5',
    icon: 'scan-outline',
    colors: ['#C8E8DE', '#2A9D8F'],
  },
];

function paramValue(value) {
  return Array.isArray(value) ? value[0] : value;
}

function decodePhotoUris(value) {
  const raw = paramValue(value);
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(uri => typeof uri === 'string' && uri.length > 0)
      .slice(0, 5);
  } catch {
    return [];
  }
}

function slugToName(slug) {
  return String(slug || '')
    .split('-')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function levelForScore(score) {
  if (score >= 0.78) return 'Strong';
  if (score >= 0.55) return 'Medium';
  return 'Light';
}

function tagsFromScores(scores) {
  return Object.entries(scores || {})
    .map(([slug, value]) => {
      const score = Number(value);
      if (!Number.isFinite(score)) return null;
      return {
        slug,
        name: slugToName(slug),
        score: Math.max(0.05, Math.min(score, 1)),
        level: levelForScore(score),
      };
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score)
    .slice(0, 15);
}

function apiErrorMessage(error, fallback = 'Could not save your photo profile.') {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map(item => item.msg || item.message).filter(Boolean).join(', ');
  }
  return detail || error?.message || fallback;
}

function normalizeClarifyQuestion(question) {
  if (!question?.id || !question?.question || !Array.isArray(question?.options)) {
    return null;
  }

  const options = question.options
    .map(option => ({
      ...option,
      value: String(option?.value ?? ''),
      label: String(option?.label || option?.value || ''),
    }))
    .filter(option => option.value && option.label)
    .slice(0, 4);

  if (options.length < 2) return null;

  return {
    ...question,
    id: String(question.id),
    question: String(question.question),
    options,
  };
}

function tagImageUrl(file) {
  return BASE_URL ? `${BASE_URL}/static/quiz_images/${file}` : null;
}

function scoreTone(score) {
  if (score >= 0.8) return { color: COLORS.primary, bg: COLORS.tagBg, icon: 'checkmark-circle' };
  if (score >= 0.62) return { color: COLORS.sage, bg: 'rgba(107,124,90,0.12)', icon: 'ellipse' };
  return { color: COLORS.muted, bg: '#EFEAE0', icon: 'ellipse-outline' };
}

function PhotoThumb({ photo, index }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);
  const uri = photo.uri || tagImageUrl(photo.file);

  return (
    <View style={styles.photoThumb}>
      <LinearGradient colors={photo.colors} style={styles.photoFallback}>
        <View style={styles.photoFallbackIcon}>
          <Ionicons name={photo.icon} size={20} color={COLORS.surface} />
        </View>
        <Text style={styles.photoFallbackText}>{photo.label}</Text>
      </LinearGradient>

      {uri && !hasError && (
        <Image
          source={{ uri }}
          style={[styles.photoImage, !isLoaded && styles.photoImageHidden]}
          resizeMode="cover"
          onLoad={() => setIsLoaded(true)}
          onError={() => setHasError(true)}
        />
      )}

      <View style={styles.photoBadge}>
        <Text style={styles.photoBadgeText}>{index + 1}</Text>
      </View>
    </View>
  );
}

export default function PhotoReviewScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const draftId = paramValue(params.draft);
  const [analysisDraft, setAnalysisDraft] = useState(null);
  const [isDraftLoading, setIsDraftLoading] = useState(!!draftId);
  const [isConfirming, setIsConfirming] = useState(false);
  const [tags, setTags] = useState(SAMPLE_TAGS);
  const [clarifyQuestion, setClarifyQuestion] = useState(null);
  const [selectedClarifyAnswer, setSelectedClarifyAnswer] = useState(null);
  const [isClarifyLoading, setIsClarifyLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadDraft() {
      if (!draftId) {
        setIsDraftLoading(false);
        return;
      }

      try {
        const draft = await loadPhotoReviewDraft(draftId);
        if (!isMounted) return;

        setAnalysisDraft(draft);
        setClarifyQuestion(null);
        setSelectedClarifyAnswer(null);
        const detectedTags = tagsFromScores(
          draft?.result?.matched_db_tags || draft?.result?.detected_tags,
        );
        if (detectedTags.length > 0) {
          setTags(detectedTags);
        }
        setIsDraftLoading(false);

        const sessionId = draft?.result?.session_id;
        if (sessionId) {
          setIsClarifyLoading(true);
          try {
            const { data } = await apiClient.get(`/ml/photo-clarify/${sessionId}`, {
              timeout: 30000,
            });
            if (!isMounted) return;

            const question = normalizeClarifyQuestion(data?.question);
            setClarifyQuestion(question);
            setSelectedClarifyAnswer(question?.options?.[0]?.value || null);
          } catch {
            if (isMounted) {
              setClarifyQuestion(null);
              setSelectedClarifyAnswer(null);
            }
          } finally {
            if (isMounted) setIsClarifyLoading(false);
          }
        }
      } catch (error) {
        if (isMounted) {
          Alert.alert('Error', 'Could not load the photo analysis result.');
        }
      } finally {
        if (isMounted) setIsDraftLoading(false);
      }
    }

    loadDraft();
    return () => {
      isMounted = false;
    };
  }, [draftId]);

  const selectedPhotoUris = useMemo(() => {
    const draftPhotos = Array.isArray(analysisDraft?.photos) ? analysisDraft.photos : [];
    return draftPhotos.length > 0 ? draftPhotos : decodePhotoUris(params.photos);
  }, [analysisDraft, params.photos]);

  const reviewPhotos = useMemo(() => {
    if (selectedPhotoUris.length === 0) return SAMPLE_PHOTOS;

    return selectedPhotoUris.map((uri, index) => ({
      ...SELECTED_PHOTO_FALLBACKS[index],
      uri,
    }));
  }, [selectedPhotoUris]);

  const usedSlugs = useMemo(() => new Set(tags.map(tag => tag.slug)), [tags]);
  const suggested = SUGGESTED_TAGS.filter(tag => !usedSlugs.has(tag.slug));
  const isBackendAnalysis = !!analysisDraft?.result?.session_id;

  function removeTag(slug) {
    setTags(current => current.filter(tag => tag.slug !== slug));
  }

  function addTag(tag) {
    setTags(current => [
      ...current,
      { ...tag, score: 0.58, level: 'Added' },
    ]);
  }

  async function confirmProfile() {
    if (!isBackendAnalysis) {
      router.replace('/(app)/dashboard');
      return;
    }
    if (tags.length === 0) {
      Alert.alert('No interests', 'Keep at least one interest before continuing.');
      return;
    }

    try {
      setIsConfirming(true);
      const tagScores = Object.fromEntries(
        tags.map(tag => [tag.slug, Number(tag.score) || 0.5]),
      );

      const { data } = await apiClient.post('/ml/confirm-photo-analysis', {
        session_id: analysisDraft.result.session_id,
        tag_scores: tagScores,
        clarification: clarifyQuestion && selectedClarifyAnswer ? {
          question_id: clarifyQuestion.id,
          answer: selectedClarifyAnswer,
        } : null,
      }, {
        timeout: 30000,
      });

      await setCurrentUserSessionId(user, data?.session_id || analysisDraft.result.session_id);
      await clearPhotoReviewDraft(draftId);
      router.replace('/(app)/dashboard');
    } catch (error) {
      Alert.alert('Error', apiErrorMessage(error));
    } finally {
      setIsConfirming(false);
    }
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="dark-content" />

      <ScrollView
        contentContainerStyle={[
          styles.content,
          { paddingTop: Math.max(insets.top + 18, 38) },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => router.back()}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Ionicons name="arrow-back" size={20} color={COLORS.ink} />
          </TouchableOpacity>

          <View style={styles.headerCopy}>
            <Text style={styles.eyebrow}>PHOTO PROFILE</Text>
            <Text style={styles.title}>Your travel style</Text>
            <Text style={styles.subtitle}>
              {isBackendAnalysis
                ? 'Review the interests detected from your photos.'
                : 'A few interests stood out from your photos.'}
            </Text>
          </View>
        </View>

        <ScrollView
          horizontal
          style={styles.photoStrip}
          contentContainerStyle={styles.photoStripContent}
          showsHorizontalScrollIndicator={false}
        >
          {reviewPhotos.map((photo, index) => (
            <PhotoThumb key={photo.uri || photo.file} photo={photo} index={index} />
          ))}
        </ScrollView>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Detected interests</Text>
          <View style={styles.countPill}>
            <Text style={styles.countText}>{tags.length}</Text>
          </View>
        </View>

        {isDraftLoading ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator color={COLORS.primary} size="small" />
            <Text style={styles.loadingText}>Loading detected interests...</Text>
          </View>
        ) : (
          <View style={styles.tagList}>
            {tags.map(tag => {
            const tone = scoreTone(tag.score);
            return (
              <View key={tag.slug} style={styles.tagRow}>
                <View style={[styles.tagIcon, { backgroundColor: tone.bg }]}>
                  <Ionicons name={tone.icon} size={17} color={tone.color} />
                </View>
                <View style={styles.tagBody}>
                  <Text style={styles.tagName} numberOfLines={1}>{tag.name}</Text>
                  <View style={styles.strengthTrack}>
                    <View style={[styles.strengthFill, { width: `${Math.round(tag.score * 100)}%`, backgroundColor: tone.color }]} />
                  </View>
                </View>
                <Text style={[styles.tagLevel, { color: tone.color }]} numberOfLines={1}>{tag.level}</Text>
                <TouchableOpacity
                  style={styles.removeButton}
                  onPress={() => removeTag(tag.slug)}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <Ionicons name="close" size={16} color={COLORS.muted} />
                </TouchableOpacity>
              </View>
            );
            })}
          </View>
        )}

        {suggested.length > 0 && (
          <>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Add interest</Text>
            </View>
            <View style={styles.suggestions}>
              {suggested.map(tag => (
                <TouchableOpacity key={tag.slug} style={styles.suggestionChip} onPress={() => addTag(tag)}>
                  <Ionicons name="add" size={15} color={COLORS.primary} />
                  <Text style={styles.suggestionText}>{tag.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </>
        )}

        {(isClarifyLoading || clarifyQuestion) && (
          <View style={styles.clarifyBox}>
            <View style={styles.clarifyHeader}>
              <View style={styles.clarifyIcon}>
                <Ionicons name="git-compare-outline" size={16} color={COLORS.primary} />
              </View>
              <Text style={styles.clarifyTitle}>Quick clarify</Text>
            </View>

            {isClarifyLoading ? (
              <View style={styles.clarifyLoading}>
                <ActivityIndicator color={COLORS.primary} size="small" />
                <Text style={styles.loadingText}>Preparing one smart question...</Text>
              </View>
            ) : (
              <>
                <Text style={styles.clarifyQuestion}>{clarifyQuestion.question}</Text>
                <View style={styles.segment}>
                  {clarifyQuestion.options.map(option => {
                    const isSelected = selectedClarifyAnswer === option.value;
                    return (
                      <TouchableOpacity
                        key={option.value}
                        style={[styles.segmentButton, isSelected && styles.segmentButtonActive]}
                        onPress={() => setSelectedClarifyAnswer(option.value)}
                      >
                        <Ionicons
                          name={isSelected ? 'checkmark' : 'ellipse-outline'}
                          size={15}
                          color={isSelected ? COLORS.surface : COLORS.primary}
                        />
                        <Text
                          style={[styles.segmentText, isSelected && styles.segmentTextActive]}
                          numberOfLines={2}
                        >
                          {option.label}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </>
            )}
          </View>
        )}
      </ScrollView>

      <View style={[styles.footer, { bottom: Math.max(insets.bottom + 10, 22) }]}>
        <TouchableOpacity style={styles.secondaryButton} onPress={() => router.back()}>
          <Ionicons name="images-outline" size={17} color={COLORS.primary} />
          <Text style={styles.secondaryText} numberOfLines={1}>Change photos</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.primaryButton, (isConfirming || isClarifyLoading || tags.length === 0) && styles.primaryButtonDisabled]}
          onPress={confirmProfile}
          disabled={isConfirming || isClarifyLoading || tags.length === 0}
        >
          {isConfirming ? (
            <ActivityIndicator color={COLORS.surface} size="small" />
          ) : (
            <Ionicons name="checkmark" size={18} color={COLORS.surface} />
          )}
          <Text style={styles.primaryText} numberOfLines={1}>
            {isConfirming ? 'Saving...' : 'Looks good'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },
  content: {
    paddingBottom: 128,
  },
  header: {
    width: '90%',
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 14,
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
    fontSize: 32,
    color: COLORS.ink,
  },
  subtitle: {
    fontFamily: FONTS.sans,
    fontSize: 13,
    lineHeight: 20,
    color: COLORS.muted,
    marginTop: 6,
  },
  photoStrip: {
    marginTop: 26,
    marginBottom: 28,
  },
  photoStripContent: {
    paddingHorizontal: 20,
    gap: 10,
  },
  photoThumb: {
    width: 110,
    aspectRatio: 1,
    borderRadius: RADIUS.md,
    overflow: 'hidden',
    backgroundColor: COLORS.surface,
    ...SHADOWS.sm,
  },
  photoImage: {
    ...StyleSheet.absoluteFillObject,
    width: '100%',
    height: '100%',
  },
  photoImageHidden: {
    opacity: 0,
  },
  photoFallback: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
  },
  photoFallbackIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(26,26,46,0.18)',
  },
  photoFallbackText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    color: COLORS.surface,
  },
  photoBadge: {
    position: 'absolute',
    left: 8,
    bottom: 8,
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(26,26,46,0.76)',
  },
  photoBadgeText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    color: COLORS.surface,
  },
  sectionHeader: {
    width: '90%',
    alignSelf: 'center',
    minHeight: 28,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  sectionTitle: {
    fontFamily: FONTS.sansSemi,
    fontSize: 14,
    color: COLORS.ink,
  },
  countPill: {
    minWidth: 28,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.tagBg,
  },
  countText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 12,
    color: COLORS.primary,
  },
  tagList: {
    width: '90%',
    alignSelf: 'center',
    gap: 9,
    marginBottom: 24,
  },
  loadingBox: {
    width: '90%',
    alignSelf: 'center',
    minHeight: 74,
    borderRadius: RADIUS.md,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 10,
    marginBottom: 24,
  },
  loadingText: {
    fontFamily: FONTS.sansMedium,
    fontSize: 13,
    color: COLORS.muted,
  },
  tagRow: {
    minHeight: 62,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 10,
    borderRadius: RADIUS.md,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  tagIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tagBody: {
    flex: 1,
    minWidth: 0,
    gap: 7,
  },
  tagName: {
    fontFamily: FONTS.sansMedium,
    fontSize: 14,
    color: COLORS.ink,
  },
  strengthTrack: {
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
    backgroundColor: '#ECE7DE',
  },
  strengthFill: {
    height: 4,
    borderRadius: 2,
  },
  tagLevel: {
    width: 46,
    fontFamily: FONTS.sansSemi,
    fontSize: 11,
    textAlign: 'right',
    flexShrink: 0,
  },
  removeButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.paper,
  },
  suggestions: {
    width: '90%',
    alignSelf: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 9,
    marginBottom: 24,
  },
  suggestionChip: {
    height: 36,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.tagBg,
    borderWidth: 1,
    borderColor: 'rgba(42,157,143,0.18)',
  },
  suggestionText: {
    fontFamily: FONTS.sansMedium,
    fontSize: 12,
    color: COLORS.primary,
  },
  clarifyBox: {
    width: '90%',
    alignSelf: 'center',
    padding: 16,
    borderRadius: RADIUS.lg,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: 'rgba(42,157,143,0.18)',
  },
  clarifyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  clarifyIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.tagBg,
  },
  clarifyTitle: {
    fontFamily: FONTS.sansSemi,
    fontSize: 13,
    color: COLORS.primary,
  },
  clarifyQuestion: {
    fontFamily: FONTS.sansSemi,
    fontSize: 16,
    color: COLORS.ink,
    marginBottom: 14,
  },
  clarifyLoading: {
    minHeight: 42,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  segment: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  segmentButton: {
    flexGrow: 1,
    flexBasis: '47%',
    minHeight: 42,
    borderRadius: 21,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: COLORS.tagBg,
  },
  segmentButtonActive: {
    backgroundColor: COLORS.primary,
  },
  segmentText: {
    flexShrink: 1,
    fontFamily: FONTS.sansSemi,
    fontSize: 13,
    lineHeight: 16,
    color: COLORS.primary,
    textAlign: 'center',
  },
  segmentTextActive: {
    color: COLORS.surface,
  },
  footer: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 22,
    flexDirection: 'row',
    gap: 8,
    padding: 7,
    borderRadius: 32,
    backgroundColor: 'rgba(250,250,247,0.94)',
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    ...SHADOWS.md,
  },
  secondaryButton: {
    flex: 1.12,
    minWidth: 0,
    height: 48,
    borderRadius: 24,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    backgroundColor: COLORS.tagBg,
  },
  secondaryText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 12,
    color: COLORS.primary,
    flexShrink: 1,
  },
  primaryButton: {
    flex: 0.98,
    minWidth: 0,
    height: 48,
    borderRadius: 24,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    backgroundColor: COLORS.primary,
  },
  primaryButtonDisabled: {
    backgroundColor: '#A5B7B3',
  },
  primaryText: {
    fontFamily: FONTS.sansSemi,
    fontSize: 12,
    color: COLORS.surface,
    flexShrink: 1,
  },
});
