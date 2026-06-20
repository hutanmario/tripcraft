import { Text, StyleSheet } from 'react-native';
import TouchableOpacity from './SmoothTouchable';
import { COLORS, SPACING, RADIUS } from '../../constants/theme';

export default function Button({ label, onPress, variant = 'primary', disabled = false, fullWidth = false }) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      disabled={disabled}
      style={[
        styles.base,
        styles[variant],
        fullWidth && styles.fullWidth,
        disabled && styles.disabled,
      ]}
    >
      <Text style={[styles.text, styles[`${variant}Text`]]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: RADIUS.full,
    paddingVertical: 14,
    paddingHorizontal: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fullWidth: {
    width: '100%',
  },
  disabled: {
    opacity: 0.4,
  },

  primary: {
    backgroundColor: COLORS.teal,
  },
  secondary: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: COLORS.ink,
  },
  ghost: {
    backgroundColor: 'transparent',
  },

  text: {
    fontSize: 15,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  primaryText: {
    color: '#FFFFFF',
  },
  secondaryText: {
    color: COLORS.ink,
  },
  ghostText: {
    color: COLORS.teal,
  },
});
