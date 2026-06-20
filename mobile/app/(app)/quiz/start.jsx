import { View, Text, StyleSheet, SafeAreaView, ActivityIndicator } from 'react-native';
import TouchableOpacity from '../../../components/ui/SmoothTouchable';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { COLORS, FONTS, SPACING, RADIUS, TYPE } from '../../../constants/theme';
import { Body, Label } from '../../../components/ui/Typography';
import { useQuiz } from '../../../context/QuizContext';


export default function QuizStartScreen() {
  const router = useRouter();
  const { startQuiz } = useQuiz();
  const [loading, setLoading] = useState(false);
  const [startError, setStartError] = useState('');

  const handleStart = async () => {
    setLoading(true);
    setStartError('');
    try {
      await startQuiz();
      router.push('/(app)/quiz/swipe');
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Could not start quiz. Try again.';
      setStartError(typeof msg === 'string' ? msg : 'Could not start quiz. Try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.logoRow}>
          <View style={styles.logoDot} />
          <Text style={styles.logoText}>TripCraft</Text>
        </View>
        <Text style={styles.progressText}>0 OF 12</Text>
      </View>

      <View style={styles.progressTrack}>
        <View style={styles.progressFill} />
      </View>

      <View style={styles.content}>
        <Label color={COLORS.teal}>A 2-MINUTE QUIZ</Label>

        <View style={styles.titleBlock}>
          <Text style={styles.titleLine1}>Let's find your</Text>
          <Text style={styles.titleLine2}>kind of trip.</Text>
        </View>

        <Body color={COLORS.muted} style={styles.bodyText}>
          Swipe through moods, places and pacing. We'll shape a shortlist around you — no algorithm gossip, just better instincts.
        </Body>

        <Text style={styles.adaptiveText}>Adapts to your answers.</Text>
      </View>

      <View style={styles.footer}>
        {startError ? (
          <Text style={styles.errorText}>{startError}</Text>
        ) : null}

        <TouchableOpacity
          style={styles.startButton}
          onPress={handleStart}
          disabled={loading}
          activeOpacity={0.85}
        >
          {loading ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <>
              <Text style={styles.startButtonText}>Start the quiz</Text>
              <View style={styles.arrowCircle}>
                <Text style={styles.arrowText}>→</Text>
              </View>
            </>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.photoBtn}
          activeOpacity={0.85}
          onPress={() => router.push('/photo-onboarding')}
        >
          <Ionicons name="images-outline" size={16} color="#2A9D8F" />
          <Text style={styles.photoBtnText}>Use my travel photos instead</Text>
        </TouchableOpacity>

        <Text style={styles.signInRow}>
          Already have an account?{' '}
          <Text style={styles.signInLink} onPress={() => router.push('/(auth)/login')}>Sign in</Text>
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: SPACING.lg,
    paddingTop: SPACING.md,
    paddingBottom: SPACING.sm,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.teal,
  },
  logoText: {
    ...TYPE.serifStrong,
    fontSize: 18,
    color: COLORS.ink,
    letterSpacing: -0.3,
  },
  progressText: {
    fontFamily: FONTS.sans,
    fontSize: 11,
    fontWeight: '600',
    color: COLORS.muted,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },

  // Progress bar
  progressTrack: {
    height: 2,
    backgroundColor: COLORS.border,
    marginHorizontal: 0,
  },
  progressFill: {
    height: 2,
    width: '0%',
    backgroundColor: COLORS.teal,
  },

  // Content
  content: {
    flex: 1,
    paddingHorizontal: SPACING.lg,
    paddingTop: SPACING.xxl,
  },
  titleBlock: {
    marginTop: SPACING.sm,
    marginBottom: SPACING.lg,
  },
  titleLine1: {
    ...TYPE.serifStrong,
    fontSize: 40,
    color: COLORS.ink,
    lineHeight: 48,
    letterSpacing: -1,
  },
  titleLine2: {
    ...TYPE.serifItalic,
    fontSize: 40,
    color: COLORS.teal,
    lineHeight: 48,
    letterSpacing: -1,
  },
  bodyText: {
    lineHeight: 24,
    fontSize: 15,
    color: COLORS.muted,
  },

  adaptiveText: {
    ...TYPE.serifItalic,
    fontSize: 15,
    color: COLORS.muted,
    marginTop: SPACING.sm,
  },

  // Footer
  footer: {
    paddingHorizontal: SPACING.lg,
    paddingBottom: SPACING.xl,
    gap: SPACING.md,
    alignItems: 'center',
  },
  startButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.ink,
    borderRadius: RADIUS.full,
    paddingVertical: 16,
    paddingHorizontal: SPACING.xl,
    gap: 12,
  },
  startButtonText: {
    fontFamily: FONTS.sans,
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },
  arrowCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: COLORS.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrowText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 16,
  },

  // Photo onboarding
  photoBtn: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    borderWidth: 1.5,
    borderColor: '#2A9D8F',
    borderRadius: RADIUS.full,
    height: 48,
    marginTop: 12,
  },
  photoBtnText: {
    fontSize: 13,
    color: '#2A9D8F',
    fontFamily: FONTS.sans,
  },

  // Sign in
  signInRow: {
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: COLORS.muted,
  },
  signInLink: {
    color: COLORS.ink,
    fontWeight: '600',
    textDecorationLine: 'underline',
  },
  errorText: {
    width: '100%',
    textAlign: 'center',
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: '#FFFFFF',
    backgroundColor: '#C0392B',
    borderRadius: RADIUS.full,
    paddingVertical: 10,
    paddingHorizontal: 16,
    overflow: 'hidden',
  },
});
