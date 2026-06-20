import { View, Text, ScrollView, StyleSheet } from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { C } from '../../constants/interactive';

export default function DaySwitch({ active, total, onChange }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {Array.from({ length: total }, (_, i) => i + 1).map((d) => (
        <TouchableOpacity
          key={d}
          style={[styles.pill, active === d && styles.pillActive]}
          activeOpacity={0.8}
          onPress={() => onChange(d)}
        >
          <Text style={[styles.text, active === d && styles.textActive]}>Day {d}</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { gap: 6, paddingHorizontal: 4 },
  pill: {
    paddingVertical: 5,
    paddingHorizontal: 14,
    borderRadius: 100,
    backgroundColor: 'rgba(255,255,255,0.22)',
  },
  pillActive: { backgroundColor: '#FFFFFF' },
  text: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.85)',
    fontFamily: 'Inter_400Regular',
    fontWeight: '500',
  },
  textActive: {
    color: C.primary,
    fontWeight: '700',
  },
});
