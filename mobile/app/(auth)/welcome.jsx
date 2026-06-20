import { View, Text, StyleSheet } from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { COLORS, FONTS, SPACING, RADIUS, TYPE } from '../../constants/theme';

export default function WelcomeScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.brandRow}>
          <View style={styles.brandDot} />
          <Text style={styles.brand}>TripCraft</Text>
        </View>
      </View>

      {/* Body */}
      <View style={styles.body}>
        <Text style={styles.label}>WELCOME</Text>
        <Text style={styles.title}>
          <Text style={styles.titleItalic}>Where</Text>
          {' do\nyou want\nto go?'}
        </Text>
        <Text style={styles.bold}>Let's figure it out.</Text>
        <Text style={styles.bodyText}>
          TripCraft turns a quick conversation into a shortlist of places, stays and routes — tuned
          to how you actually travel.
        </Text>

        {/* Decorative circle */}
        <View style={styles.decorCircle} pointerEvents="none" />
      </View>

      {/* Buttons + footer */}
      <View style={styles.buttons}>
        <TouchableOpacity
          style={styles.inkBtn}
          activeOpacity={0.88}
          onPress={() => router.push('/(auth)/register')}
        >
          <Text style={styles.inkBtnLabel}>Create account</Text>
          <View style={styles.inkBtnDot}>
            <Text style={styles.inkBtnArrow}>→</Text>
          </View>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.outlineBtn}
          activeOpacity={0.88}
          onPress={() => router.push('/(auth)/login')}
        >
          <Text style={styles.outlineBtnText}>Sign in</Text>
        </TouchableOpacity>

      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.cream },

  header: {
    paddingHorizontal: SPACING.md,
    paddingTop: SPACING.sm,
    paddingBottom: SPACING.xs,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  brandDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: COLORS.teal,
  },
  brand: {
    fontSize: 16,
    ...TYPE.serifItalic,
    color: COLORS.ink,
  },

  body: {
    flex: 1,
    paddingHorizontal: SPACING.md,
    paddingTop: SPACING.lg,
    overflow: 'hidden',
  },
  label: {
    fontSize: 11,
    letterSpacing: 1.5,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    textTransform: 'uppercase',
    marginBottom: SPACING.sm,
  },
  title: {
    fontSize: 42,
    ...TYPE.serif,
    color: COLORS.ink,
    lineHeight: 50,
    marginBottom: SPACING.md,
  },
  titleItalic: {
    ...TYPE.serifItalic,
    color: COLORS.teal,
  },
  bold: {
    fontSize: 17,
    fontFamily: FONTS.sans,
    fontWeight: '700',
    color: COLORS.ink,
    marginBottom: SPACING.md,
  },
  bodyText: {
    fontSize: 14,
    fontFamily: FONTS.sans,
    color: COLORS.muted,
    lineHeight: 22,
    maxWidth: '75%',
  },
  decorCircle: {
    position: 'absolute',
    right: -40,
    top: 60,
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 1.5,
    borderColor: COLORS.teal,
    opacity: 0.25,
  },

  buttons: {
    paddingHorizontal: SPACING.md,
    paddingBottom: SPACING.xl,
    gap: SPACING.sm,
  },
  inkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: COLORS.ink,
    borderRadius: RADIUS.full,
    paddingVertical: 10,
    paddingLeft: SPACING.lg,
    paddingRight: 8,
  },
  inkBtnLabel: {
    color: '#FFFFFF',
    fontSize: 16,
    fontFamily: FONTS.sans,
    fontWeight: '600',
  },
  inkBtnDot: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: COLORS.teal,
    justifyContent: 'center',
    alignItems: 'center',
  },
  inkBtnArrow: { color: '#FFFFFF', fontSize: 18 },
  outlineBtn: {
    borderWidth: 1.5,
    borderColor: COLORS.ink,
    borderRadius: RADIUS.full,
    paddingVertical: 14,
    alignItems: 'center',
  },
  outlineBtnText: {
    color: COLORS.ink,
    fontSize: 16,
    fontFamily: FONTS.sans,
    fontWeight: '600',
  },
  footer: {
    fontSize: 13,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    textAlign: 'center',
    marginTop: SPACING.xs,
  },
});
