import {
  View,
  Text,
  Pressable,
  ScrollView,
  StyleSheet,
  StatusBar,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { COLORS, FONTS, SPACING, RADIUS, TYPE } from '../../../constants/theme';
import { useQuiz } from '../../../context/QuizContext';
import TouchableOpacity from '../../../components/ui/SmoothTouchable';

const MAX_CARDS = 20;

const FALLBACK_QUESTION = {
  id: 'travel_style',
  question: "Who's on this trip with you?",
  options: [
    { value: 'solo', label: 'Solo' },
    { value: 'pair', label: 'A pair' },
    { value: 'group', label: 'Small group' },
  ],
};

function OptionCard({ option, selected, onPress }) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.92}
      style={[
        styles.card,
        selected && styles.cardSelected,
      ]}
    >
      <View style={styles.cardText}>
        <Text style={[styles.cardTitle, selected && styles.cardTitleSelected]}>
          {option.label}
        </Text>
      </View>

      <View style={[styles.arrowCircle, selected && styles.arrowCircleSelected]}>
        <Text style={[styles.arrowIcon, selected && styles.arrowIconSelected]}>→</Text>
      </View>
    </TouchableOpacity>
  );
}

export default function QuizClarifyScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { questions: contextQuestions, answer, cardCount } = useQuiz();

  const [questionQueue, setQuestionQueue] = useState(() =>
    contextQuestions?.length > 0 ? contextQuestions : [FALLBACK_QUESTION]
  );
  const [qIndex, setQIndex] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [answerError, setAnswerError] = useState('');

  const activeQuestion = questionQueue[qIndex] ?? FALLBACK_QUESTION;

  const handleSelect = async (optionValue) => {
    if (submitting) return;
    setSelectedId(optionValue);
    setAnswerError('');
    setSubmitting(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    await new Promise(r => setTimeout(r, 160));

    try {
      const result = await answer(activeQuestion.id, optionValue);

      if (result.phase === 'completed' || result.results_ready) {
        router.push('/(app)/quiz/complete');
        return;
      }

      if (result.next_question) {
        setQuestionQueue(prev => [...prev, result.next_question]);
        setQIndex(prev => prev + 1);
        setSelectedId(null);
        return;
      }

      if (qIndex + 1 < questionQueue.length) {
        setQIndex(prev => prev + 1);
        setSelectedId(null);
        return;
      }

      router.push('/(app)/quiz/complete');
    } catch (err) {
      setSelectedId(null);
      setAnswerError('Could not save answer. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const totalSteps = MAX_CARDS + questionQueue.length;
  const currentStep = (cardCount || MAX_CARDS) + qIndex + 1;
  const progressPct = `${Math.min(100, Math.round((currentStep / totalSteps) * 100))}%`;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" />

      {/* Header */}
      <View style={styles.header}>
        <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={8}>
          <Text style={styles.backIcon}>←</Text>
        </Pressable>
        <Text style={styles.headerLabel}>ALMOST THERE</Text>
        <Text style={styles.headerCount}>{qIndex + 1} OF {questionQueue.length}</Text>
      </View>

      {/* Progress bar */}
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: progressPct }]} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + 64 }]}
        showsVerticalScrollIndicator={false}
      >
        {/* Badge */}
        <View style={styles.badge}>
          <View style={styles.badgeDot} />
          <Text style={styles.badgeText}>QUICK CLARIFY</Text>
        </View>

        {/* Title */}
        <Text style={styles.titleText}>{activeQuestion.question}</Text>

        {/* Options */}
        <View style={styles.optionsList}>
          {activeQuestion.options.map((option) => (
            <OptionCard
              key={option.value}
              option={option}
              selected={selectedId === option.value}
              onPress={() => handleSelect(option.value)}
            />
          ))}
        </View>

        {answerError ? (
          <Text style={styles.errorText}>{answerError}</Text>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.cream,
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: SPACING.lg,
    paddingVertical: SPACING.sm,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(0,0,0,0.06)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  backIcon: {
    fontSize: 16,
    color: COLORS.ink,
    fontWeight: '600',
  },
  headerLabel: {
    flex: 1,
    textAlign: 'center',
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

  // Badge
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: COLORS.teal,
    borderRadius: RADIUS.full,
    paddingVertical: 6,
    paddingHorizontal: 12,
    marginBottom: SPACING.lg,
    gap: 6,
  },
  badgeDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: COLORS.teal,
  },
  badgeText: {
    fontFamily: FONTS.sans,
    fontSize: 11,
    fontWeight: '700',
    color: COLORS.teal,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },

  // Title
  titleText: {
    ...TYPE.serifStrong,
    fontSize: 36,
    color: COLORS.ink,
    lineHeight: 44,
    letterSpacing: -0.5,
    marginBottom: SPACING.xl,
  },

  // Options list
  optionsList: {
    gap: SPACING.sm,
  },

  // Card
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingVertical: SPACING.lg,
    paddingHorizontal: SPACING.lg,
  },
  cardSelected: {
    backgroundColor: COLORS.teal,
    borderColor: COLORS.teal,
  },
  cardPressed: {
    opacity: 0.75,
  },

  // Card text
  cardText: {
    flex: 1,
  },
  cardTitle: {
    ...TYPE.serifStrong,
    fontSize: 22,
    color: COLORS.ink,
    lineHeight: 28,
  },
  cardTitleSelected: {
    color: '#FFFFFF',
  },

  // Arrow
  arrowCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.border,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  arrowCircleSelected: {
    backgroundColor: '#FFFFFF',
  },
  arrowIcon: {
    fontSize: 14,
    color: COLORS.muted,
    fontWeight: '600',
  },
  arrowIconSelected: {
    color: COLORS.teal,
  },

  errorText: {
    marginTop: SPACING.lg,
    textAlign: 'center',
    fontFamily: FONTS.sans,
    fontSize: 13,
    color: COLORS.error,
    backgroundColor: 'rgba(231,111,81,0.1)',
    borderRadius: RADIUS.md,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
});
