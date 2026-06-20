import {
  useEffect,
  useState } from 'react';
import { View,
  Text,
  StyleSheet
} from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS, FONTS, SPACING, RADIUS, TYPE } from '../../constants/theme';

export default function GreetingLoginScreen() {
  const router = useRouter();
  const [firstName, setFirstName] = useState('');

  useEffect(() => {
    AsyncStorage.getItem('user_data').then((raw) => {
      if (!raw) return;
      const user = JSON.parse(raw);
      setFirstName(user.full_name?.split(' ')[0] || user.username || '');
    });
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.brandRow}>
          <View style={styles.brandDot} />
          <Text style={styles.brand}>TripCraft</Text>
        </View>
      </View>

      {/* Center */}
      <View style={styles.body}>
        <View style={styles.avatarWrap}>
          <View style={styles.avatarCircle}>
            <Text style={styles.avatarIcon}>☺</Text>
          </View>
          <View style={styles.sageDot} />
        </View>

        <Text style={styles.sectionLabel}>WELCOME BACK</Text>
        <Text style={styles.title}>
          {'Hey, '}
          <Text style={styles.italic}>{firstName ? `${firstName}.` : 'there.'}</Text>
        </Text>
        <Text style={styles.subtitle}>Ready to plan something?</Text>
        <Text style={styles.bodyText}>
          Your profile and preferences are right where you left them. Jump back into your shortlist
          or start a fresh trip.
        </Text>
      </View>

      {/* CTA */}
      <View style={styles.bottom}>
        <TouchableOpacity
          style={styles.inkBtn}
          activeOpacity={0.88}
          onPress={() => router.replace('/(app)/dashboard')}
        >
          <Text style={styles.inkBtnLabel}>Continue</Text>
          <View style={styles.inkBtnDot}>
            <Text style={styles.inkBtnArrow}>→</Text>
          </View>
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
  brand: { fontSize: 16, ...TYPE.serifItalic, color: COLORS.ink },

  body: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: SPACING.xl,
  },
  avatarWrap: {
    position: 'relative',
    marginBottom: SPACING.lg,
  },
  avatarCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: COLORS.teal,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarIcon: { color: '#FFFFFF', fontSize: 40 },
  sageDot: {
    position: 'absolute',
    bottom: 4,
    right: -2,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: COLORS.sage,
    borderWidth: 2,
    borderColor: COLORS.cream,
  },

  sectionLabel: {
    fontSize: 11,
    letterSpacing: 1.5,
    color: COLORS.teal,
    fontFamily: FONTS.sans,
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: SPACING.xs,
    textAlign: 'center',
  },
  title: {
    fontSize: 34,
    ...TYPE.serif,
    color: COLORS.ink,
    textAlign: 'center',
    marginBottom: SPACING.xs,
  },
  italic: { ...TYPE.serifItalic, color: COLORS.teal },
  subtitle: {
    fontSize: 18,
    ...TYPE.serifItalic,
    color: COLORS.ink,
    textAlign: 'center',
    marginBottom: SPACING.md,
  },
  bodyText: {
    fontSize: 14,
    fontFamily: FONTS.sans,
    color: COLORS.muted,
    textAlign: 'center',
    lineHeight: 22,
  },

  bottom: {
    paddingHorizontal: SPACING.md,
    paddingBottom: SPACING.xl,
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
});
