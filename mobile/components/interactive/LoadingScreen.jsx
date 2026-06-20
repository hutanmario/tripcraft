import { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { FONTS, TYPE } from '../../constants/theme';

export default function LoadingScreen({ subtitle = 'Building your itinerary...' }) {
  const barAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(barAnim, { toValue: 1, duration: 1400, useNativeDriver: false }),
        Animated.timing(barAnim, { toValue: 0, duration: 0, useNativeDriver: false }),
      ])
    ).start();
  }, []);

  const barWidth = barAnim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });

  return (
    <View style={styles.container}>
      <Text style={styles.brand}>
        <Text style={styles.brandItalic}>Trip</Text>Craft
      </Text>
      <View style={styles.barTrack}>
        <Animated.View style={[styles.barFill, { width: barWidth }]} />
      </View>
      <Text style={styles.subtitle}>{subtitle}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D1B2A',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 20,
  },
  brand: {
    fontSize: 34,
    color: '#FFFFFF',
    ...TYPE.serif,
  },
  brandItalic: {
    ...TYPE.serifItalic,
  },
  barTrack: {
    width: 200,
    height: 4,
    borderRadius: 100,
    backgroundColor: 'rgba(255,255,255,0.12)',
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: 100,
    backgroundColor: '#2A9D8F',
  },
  subtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    fontFamily: 'Inter_400Regular',
  },
});
