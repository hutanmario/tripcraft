import { useEffect, useRef } from 'react';
import { Animated, View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { COLORS, FONTS, SPACING, RADIUS, TYPE } from '../../constants/theme';
import { useAuth } from '../../context/AuthContext';

export default function SplashScreen() {
  const router = useRouter();
  const { isLoading, isAuthenticated } = useAuth();
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(16)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 700, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: 0, duration: 700, useNativeDriver: true }),
    ]).start();
    const t = setTimeout(() => {
      if (isLoading) return;
      router.replace(isAuthenticated ? '/(app)/dashboard' : '/(auth)/welcome');
    }, 2000);
    return () => clearTimeout(t);
  }, [isLoading, isAuthenticated]);

  return (
    <SafeAreaView style={styles.safe}>
      <Animated.View style={[styles.center, { opacity, transform: [{ translateY }] }]}>
        <View style={styles.logoCircle}>
          <Text style={styles.logoLetter}>T</Text>
        </View>
        <View style={styles.brandRow}>
          <Text style={styles.brandTrip}>Trip</Text>
          <Text style={styles.brandCraft}>Craft</Text>
        </View>
        <Text style={styles.tagline}>Your next trip, shaped around you.</Text>
      </Animated.View>

      <View style={styles.dotsRow}>
        <View style={[styles.dot, styles.dotActive]} />
        <View style={styles.dot} />
        <View style={styles.dot} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.cream },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: COLORS.teal,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: SPACING.md,
  },
  logoLetter: {
    fontSize: 32,
    ...TYPE.serifItalic,
    color: '#FFFFFF',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: SPACING.sm,
  },
  brandTrip: {
    fontSize: 36,
    ...TYPE.serifItalic,
    color: COLORS.teal,
  },
  brandCraft: {
    fontSize: 36,
    ...TYPE.serif,
    color: COLORS.ink,
  },
  tagline: {
    fontSize: 14,
    fontFamily: FONTS.sans,
    color: COLORS.muted,
    marginTop: SPACING.xs,
  },
  dotsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
    paddingBottom: SPACING.xl,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: COLORS.teal,
  },
  dotActive: { backgroundColor: COLORS.teal },
});
