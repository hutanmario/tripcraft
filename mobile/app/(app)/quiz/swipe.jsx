import {
  View,
  Text,
  StyleSheet,
  Animated,
  PanResponder,
  Dimensions,
  StatusBar,
  ActivityIndicator,
  Alert,
  BackHandler
} from 'react-native';
import TouchableOpacity from '../../../components/ui/SmoothTouchable';
import { Image as ExpoImage } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { useRouter, useFocusEffect } from 'expo-router';
import { useRef, useState, useCallback } from 'react';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { FONTS, SPACING, RADIUS } from '../../../constants/theme';
import { useQuiz } from '../../../context/QuizContext';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const SWIPE_THRESHOLD = 80;
const MAX_VISIBLE_CARDS = 20;

export default function QuizSwipeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { currentCard, cardCount, entropy, swipe } = useQuiz();

  // Convert Bayesian entropy to profile certainty percentage.
  // entropy=999 means no data yet; entropy near 0 means fully converged.
  const certaintyPct = entropy >= 100
    ? Math.min(100, Math.round((cardCount / 20) * 100))
    : Math.max(0, Math.min(100, Math.round((1 - Math.min(entropy, 3) / 3) * 100)));

  const confidenceLabel =
    certaintyPct >= 80 ? 'High confidence' :
    certaintyPct >= 50 ? 'Learning your style' :
    'Gathering signals';
  const [swipesDone, setSwipesDone] = useState(0);
  const [loadingNext, setLoadingNext] = useState(false);
  const [swipeError, setSwipeError] = useState('');
  const translateX = useRef(new Animated.Value(0)).current;
  const cardOpacity = useRef(new Animated.Value(1)).current;
  const isAnimating = useRef(false);

  // derived from translateX for overlay and hint
  const likeOpacity = translateX.interpolate({ inputRange: [20, 100], outputRange: [0, 1], extrapolate: 'clamp' });
  const nopeOpacity = translateX.interpolate({ inputRange: [-100, -20], outputRange: [1, 0], extrapolate: 'clamp' });

  const handleBack = useCallback(() => {
    Alert.alert('Abandon quiz?', 'Your progress will be lost.', [
      { text: 'Keep going', style: 'cancel' },
      { text: 'Quit', style: 'destructive', onPress: () => router.replace('/dashboard') },
    ]);
  }, [router]);

  useFocusEffect(
    useCallback(() => {
      const onBackPress = () => {
        handleBack();
        return true;
      };
      const subscription = BackHandler.addEventListener('hardwareBackPress', onBackPress);
      return () => subscription.remove();
    }, [handleBack])
  );

  const afterSwipeAnimation = useCallback(async (direction) => {
    if (!currentCard) return;
    setLoadingNext(true);
    setSwipeError('');
    Haptics.impactAsync(direction === 'right' ? Haptics.ImpactFeedbackStyle.Medium : Haptics.ImpactFeedbackStyle.Light);
    try {
      const result = await swipe(currentCard.tag_slug, direction);
      setSwipesDone(prev => prev + 1);
      cardOpacity.setValue(1);
      translateX.setValue(0);
      isAnimating.current = false;
      setLoadingNext(false);
      if (result.phase === 'clarify') router.replace('/quiz/clarify');
    } catch {
      isAnimating.current = false;
      translateX.setValue(0);
      cardOpacity.setValue(1);
      setLoadingNext(false);
      setSwipeError('Could not save swipe. Try again.');
    }
  }, [currentCard, swipe, cardOpacity, translateX, router]);

  // Always points to the latest afterSwipeAnimation so panResponder (created once) stays current
  const afterSwipeRef = useRef(afterSwipeAnimation);
  afterSwipeRef.current = afterSwipeAnimation;

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,
      onMoveShouldSetPanResponder: (_, gestureState) =>
        !isAnimating.current && Math.abs(gestureState.dx) > 8 && Math.abs(gestureState.dy) < 40,
      onPanResponderMove: (_, gestureState) => {
        if (isAnimating.current) return;
        translateX.setValue(gestureState.dx);
      },
      onPanResponderRelease: (_, gestureState) => {
        if (isAnimating.current) return;
        if (Math.abs(gestureState.dx) > SWIPE_THRESHOLD) {
          const direction = gestureState.dx > 0 ? 'right' : 'left';
          const toX = gestureState.dx > 0 ? SCREEN_WIDTH * 1.3 : -SCREEN_WIDTH * 1.3;
          isAnimating.current = true;
          Animated.timing(translateX, {
            toValue: toX,
            duration: 200,
            useNativeDriver: true,
          }).start(() => afterSwipeRef.current?.(direction));
        } else {
          Animated.spring(translateX, {
            toValue: 0,
            useNativeDriver: true,
            tension: 120,
            friction: 10,
          }).start();
        }
      },
    })
  ).current;

  const handleLike = () => {
    if (!currentCard || isAnimating.current) return;
    isAnimating.current = true;
    Animated.timing(translateX, {
      toValue: SCREEN_WIDTH * 1.3,
      duration: 220,
      useNativeDriver: true,
    }).start(() => afterSwipeRef.current?.('right'));
  };

  const handleDislike = () => {
    if (!currentCard || isAnimating.current) return;
    isAnimating.current = true;
    Animated.timing(translateX, {
      toValue: -SCREEN_WIDTH * 1.3,
      duration: 220,
      useNativeDriver: true,
    }).start(() => afterSwipeRef.current?.('left'));
  };

  const handleSkip = () => {
    if (!currentCard || isAnimating.current) return;
    isAnimating.current = true;
    afterSwipeRef.current?.('skip');
  };

  if (!currentCard) {
    return (
      <View style={[styles.root, { alignItems: 'center', justifyContent: 'center' }]}>
        <StatusBar barStyle="light-content" />
        <ActivityIndicator size="large" color="#FFFFFF" />
      </View>
    );
  }

  const currentStep = Math.max(cardCount || 1, swipesDone + 1);
  const progressPercent = `${Math.min(100, Math.round((currentStep / MAX_VISIBLE_CARDS) * 100))}%`;
  const imageKey = String(currentCard.image_id || currentCard.image_url || currentCard.tag_slug);
  const photoCredit = currentCard.image_credit || currentCard.credit || 'Unsplash';

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />

      <Animated.View
        style={[
          styles.card,
          { transform: [{ translateX }], opacity: cardOpacity },
        ]}
        {...panResponder.panHandlers}
      >
        <ExpoImage
          key={imageKey}
          recyclingKey={imageKey}
          source={{ uri: currentCard.image_url }}
          style={styles.backgroundImage}
          contentFit="cover"
          transition={0}
          cachePolicy="memory-disk"
          priority="high"
        />

        <View style={styles.textureOverlay} />
        <LinearGradient
          colors={['transparent', 'rgba(0,0,0,0.72)']}
          style={styles.gradientOverlay}
        />

        {/* Like overlay */}
        <Animated.View style={[styles.likeOverlay, { opacity: likeOpacity }]}>
          <Text style={styles.likeLabel}>LIKE</Text>
        </Animated.View>

        {/* Nope overlay */}
        <Animated.View style={[styles.nopeOverlay, { opacity: nopeOpacity }]}>
          <Text style={styles.nopeLabel}>NOPE</Text>
        </Animated.View>

        <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
          <TouchableOpacity style={styles.backBtn} onPress={handleBack} activeOpacity={0.7}>
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerLabel}>VIBES</Text>
          <Text style={styles.headerCount}>{currentStep} OF {MAX_VISIBLE_CARDS}</Text>
        </View>

        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: progressPercent }]} />
        </View>

        {/* Certainty bar — Bayesian profile confidence */}
        <View style={styles.certaintyRow}>
          <View style={styles.certaintyTrack}>
            <View style={[styles.certaintyFill, { width: `${certaintyPct}%` }]} />
          </View>
          <Text style={styles.certaintyLabel}>{confidenceLabel} · {certaintyPct}%</Text>
        </View>

        <View style={[styles.cardCreditWrap, { bottom: insets.bottom + 98 }]}>
          <View style={styles.creditPill}>
            <Text style={styles.photoCredit} numberOfLines={1}>Photo: {photoCredit}</Text>
          </View>
        </View>
      </Animated.View>

      {loadingNext && (
        <View pointerEvents="none" style={styles.nextLoadingOverlay}>
          <ActivityIndicator size="small" color="#FFFFFF" />
        </View>
      )}

      <View style={[styles.actionsWrapper, { paddingBottom: insets.bottom + 16 }]}>
        {swipeError ? <Text style={styles.errorText}>{swipeError}</Text> : null}

        <View style={styles.actionsRow}>
          <TouchableOpacity style={styles.btnReject} onPress={handleDislike} activeOpacity={0.8} disabled={loadingNext}>
            <Text style={styles.btnRejectIcon}>✕</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.btnSkip} onPress={handleSkip} activeOpacity={0.8} disabled={loadingNext}>
            <Text style={styles.btnSkipIcon}>↺</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.btnLike} onPress={handleLike} activeOpacity={0.8} disabled={loadingNext}>
            <Text style={styles.btnLikeIcon}>✓</Text>
          </TouchableOpacity>
        </View>

        {swipesDone < 3 && (
          <Text style={styles.swipeHint}>OR SWIPE ← / →</Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#111',
  },

  card: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#1a1a1a',
  },

  backgroundImage: {
    ...StyleSheet.absoluteFillObject,
  },

  nextLoadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.18)',
  },

  textureOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.12)',
  },

  gradientOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: '65%',
  },

  likeOverlay: {
    position: 'absolute',
    top: 80,
    left: 24,
    borderWidth: 3,
    borderColor: '#4A7C59',
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 14,
    transform: [{ rotate: '-15deg' }],
  },
  likeLabel: {
    fontFamily: FONTS.sans,
    fontSize: 22,
    fontWeight: '800',
    color: '#4A7C59',
    letterSpacing: 2,
  },
  nopeOverlay: {
    position: 'absolute',
    top: 80,
    right: 24,
    borderWidth: 3,
    borderColor: '#E05C5C',
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 14,
    transform: [{ rotate: '15deg' }],
  },
  nopeLabel: {
    fontFamily: FONTS.sans,
    fontSize: 22,
    fontWeight: '800',
    color: '#E05C5C',
    letterSpacing: 2,
  },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: SPACING.lg,
    paddingBottom: SPACING.sm,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  backIcon: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  headerLabel: {
    flex: 1,
    textAlign: 'center',
    fontFamily: FONTS.sans,
    fontSize: 11,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: 1.8,
    textTransform: 'uppercase',
  },
  headerCount: {
    fontFamily: FONTS.sans,
    fontSize: 11,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.6)',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },

  progressTrack: {
    height: 1.5,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginHorizontal: SPACING.lg,
    borderRadius: 1,
  },
  progressFill: {
    height: 1.5,
    backgroundColor: 'rgba(255,255,255,0.7)',
    borderRadius: 1,
  },

  certaintyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: SPACING.lg,
    marginTop: SPACING.sm,
    gap: SPACING.sm,
  },
  certaintyTrack: {
    flex: 1,
    height: 3,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  certaintyFill: {
    height: 3,
    backgroundColor: '#2A9D8F',
    borderRadius: 2,
  },
  certaintyLabel: {
    fontFamily: FONTS.sans,
    fontSize: 9,
    color: 'rgba(255,255,255,0.55)',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    flexShrink: 0,
  },

  cardCreditWrap: {
    position: 'absolute',
    left: SPACING.lg,
    right: SPACING.lg,
    paddingHorizontal: SPACING.lg,
    alignItems: 'flex-start',
  },
  creditPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    maxWidth: '86%',
    backgroundColor: 'rgba(0,0,0,0.38)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
    borderRadius: RADIUS.full,
    paddingVertical: 5,
    paddingHorizontal: 10,
    marginBottom: SPACING.sm,
  },
  photoCredit: {
    fontFamily: FONTS.sans,
    fontSize: 10,
    fontWeight: '500',
    color: 'rgba(255,255,255,0.76)',
    letterSpacing: 0.4,
  },
  actionsWrapper: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    alignItems: 'center',
    gap: SPACING.sm,
  },
  actionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.lg,
  },
  errorText: {
    maxWidth: '86%',
    textAlign: 'center',
    fontFamily: FONTS.sans,
    fontSize: 12,
    fontWeight: '600',
    color: '#FFD0D0',
    backgroundColor: 'rgba(120,0,0,0.42)',
    borderRadius: RADIUS.full,
    paddingVertical: 7,
    paddingHorizontal: 12,
  },
  btnReject: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: 'rgba(40,30,30,0.85)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnRejectIcon: {
    color: '#E05C5C',
    fontSize: 20,
    fontWeight: '700',
  },
  btnSkip: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: 'rgba(40,40,40,0.8)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnSkipIcon: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 20,
  },
  btnLike: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#4A7C59',
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnLikeIcon: {
    color: '#FFFFFF',
    fontSize: 22,
    fontWeight: '700',
  },
  swipeHint: {
    fontFamily: FONTS.sans,
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.45)',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
});
