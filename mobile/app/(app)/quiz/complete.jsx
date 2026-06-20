import {
  View,
  Text,
  Pressable,
  ScrollView,
  StyleSheet,
  StatusBar,
  ActivityIndicator
} from 'react-native';
import TouchableOpacity from '../../../components/ui/SmoothTouchable';
import { useRouter } from 'expo-router';
import { useState, useEffect } from 'react';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { COLORS, FONTS, SPACING, RADIUS, SHADOWS, TYPE } from '../../../constants/theme';
import { useQuiz } from '../../../context/QuizContext';
import apiClient from '../../../services/api';

const STEP = 12;
const TOTAL = 12;

const DOT_COLORS = [COLORS.sage, COLORS.teal, COLORS.ink, COLORS.muted];

const slugToLabel = (slug) => {
  const s = slug.replace(/-/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
};

function TagChip({ label, dot }) {
  return (
    <View style={styles.chip}>
      <View style={[styles.chipDot, { backgroundColor: dot }]} />
      <Text style={styles.chipText}>{label}</Text>
    </View>
  );
}

export default function QuizCompleteScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { getResults, sessionId } = useQuiz();
  const [results, setResults] = useState(null);
  const [profileTags, setProfileTags] = useState([]);

  useEffect(() => {
    getResults().catch(() => {});
    if (sessionId) {
      apiClient.get(`/quiz/v4/profile/${sessionId}`)
        .then(({ data }) => {
          const tags = (data.profile ?? [])
            .filter(t => (t.score ?? 0) > 0)
            .slice(0, 8)
            .map((t, i) => ({
              id: t.slug ?? t.name,
              label: t.name ?? slugToLabel(t.slug ?? ''),
              dot: DOT_COLORS[i % DOT_COLORS.length],
            }));
          setProfileTags(tags);
          setResults(data);
        })
        .catch(() => {});
    }
  }, [sessionId]);

  // Profile tags from /quiz/v4/profile — what the user actually showed preference for
  const topTags = profileTags;

  if (!results) {
    return (
      <View style={[styles.root, styles.centered, { paddingTop: insets.top }]}>
        <StatusBar barStyle="dark-content" />
        <ActivityIndicator size="large" color={COLORS.teal} />
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" />

      {/* Header — no back button */}
      <View style={styles.header}>
        <Text style={styles.headerLabel}>COMPLETE</Text>
        <Text style={styles.headerCount}>{STEP} OF {TOTAL}</Text>
      </View>

      {/* Progress bar — full width */}
      <View style={styles.progressTrack}>
        <View style={styles.progressFill} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + 32 }]}
        showsVerticalScrollIndicator={false}
      >
        {/* Check circle with teal dot badge */}
        <View style={styles.checkWrapper}>
          <View style={styles.checkCircle}>
            <Text style={styles.checkMark}>✓</Text>
          </View>
          <View style={styles.checkBadge} />
        </View>

        {/* Wrap label */}
        <Text style={styles.wrapLabel}>THAT'S A WRAP</Text>

        {/* Title */}
        <Text style={styles.titleText}>
          {'Your travel\n'}
          <Text style={styles.titleItalic}>fingerprint.</Text>
        </Text>

        <Text style={styles.subtitle}>
          Eight tags shape the rest of TripCraft — edit any of them later from your profile.
        </Text>

        {/* Tags card */}
        <View style={styles.tagsCard}>
          <View style={styles.tagsHeader}>
            <Text style={styles.tagsLabel}>YOUR TAGS</Text>
            <Text style={styles.tagsCount}>{topTags.length} SELECTED</Text>
          </View>

          <View style={styles.tagsGrid}>
            {topTags.map((tag) => (
              <TagChip key={tag.id} label={tag.label} dot={tag.dot} />
            ))}
          </View>
        </View>

        {/* Primary CTA */}
        <TouchableOpacity
          style={styles.ctaBtn}
          activeOpacity={0.85}
          onPress={() => router.replace('/(app)/dashboard')}
        >
          <Text style={styles.ctaText}>Go to dashboard</Text>
        </TouchableOpacity>

        {/* See all destinations */}
        <TouchableOpacity
          style={styles.seeAllBtn}
          activeOpacity={0.7}
          onPress={() => router.push('/(app)/destinations')}
        >
          <Text style={styles.seeAllText}>See all destinations →</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },
  centered: {
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: SPACING.lg,
    paddingVertical: SPACING.sm,
  },
  headerLabel: {
    flex: 1,
    fontFamily: FONTS.sans,
    fontSize: 11,
    fontWeight: '700',
    color: COLORS.muted,
    letterSpacing: 1.8,
    textTransform: 'uppercase',
  },
  headerCount: {
    fontFamily: FONTS.sans,
    fontSize: 11,
    fontWeight: '600',
    color: COLORS.muted,
    letterSpacing: 1,
  },

  // Progress bar
  progressTrack: {
    height: 2,
    backgroundColor: COLORS.border,
  },
  progressFill: {
    height: 2,
    width: '100%',
    backgroundColor: COLORS.teal,
    borderRadius: 1,
  },

  // Scroll
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: SPACING.lg,
    paddingTop: SPACING.xl,
  },

  // Check circle
  checkWrapper: {
    alignSelf: 'flex-start',
    marginBottom: SPACING.lg,
  },
  checkCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: COLORS.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkMark: {
    fontSize: 28,
    color: '#FFFFFF',
    fontWeight: '700',
  },
  checkBadge: {
    position: 'absolute',
    top: 2,
    right: 2,
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: COLORS.teal,
    borderWidth: 2,
    borderColor: COLORS.cream,
  },

  // Wrap label
  wrapLabel: {
    fontFamily: FONTS.sans,
    fontSize: 11,
    fontWeight: '700',
    color: COLORS.teal,
    letterSpacing: 2,
    textTransform: 'uppercase',
    marginBottom: SPACING.sm,
  },

  // Title
  titleText: {
    ...TYPE.serifStrong,
    fontSize: 40,
    color: COLORS.ink,
    lineHeight: 48,
    letterSpacing: -0.5,
    marginBottom: SPACING.sm,
  },
  titleItalic: {
    ...TYPE.serifItalic,
    fontSize: 40,
    color: COLORS.ink,
    lineHeight: 48,
  },
  subtitle: {
    fontFamily: FONTS.sans,
    fontSize: 14,
    color: COLORS.muted,
    lineHeight: 21,
    marginBottom: SPACING.xl,
  },

  // Tags card
  tagsCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: RADIUS.lg,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: SPACING.md,
    marginBottom: SPACING.lg,
    ...SHADOWS.sm,
  },
  tagsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: SPACING.md,
  },
  tagsLabel: {
    fontFamily: FONTS.sans,
    fontSize: 10,
    fontWeight: '700',
    color: COLORS.muted,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
  tagsCount: {
    fontFamily: FONTS.sans,
    fontSize: 10,
    fontWeight: '600',
    color: COLORS.muted,
    letterSpacing: 1,
  },
  tagsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: SPACING.sm,
  },

  // Chip
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.cream,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingVertical: 7,
    paddingHorizontal: 12,
    gap: 6,
  },
  chipDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  chipText: {
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: COLORS.ink,
    fontWeight: '500',
  },

  // CTA button
  ctaBtn: {
    backgroundColor: '#2A9D8F',
    borderRadius: 24,
    height: 52,
    marginHorizontal: 24,
    marginBottom: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: {
    fontFamily: FONTS.sans,
    fontSize: 14,
    fontWeight: '500',
    color: '#FFFFFF',
  },
  seeAllBtn: {
    marginHorizontal: 24,
    marginBottom: 16,
    alignItems: 'center',
  },
  seeAllText: {
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: '#2A9D8F',
  },
});
