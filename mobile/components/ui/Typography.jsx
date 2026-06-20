import { Text, StyleSheet } from 'react-native';
import { COLORS, FONTS } from '../../constants/theme';

export const H1 = ({ children, style, color }) => (
  <Text style={[styles.h1, color && { color }, style]}>{children}</Text>
);

export const H2 = ({ children, style, color }) => (
  <Text style={[styles.h2, color && { color }, style]}>{children}</Text>
);

export const H3 = ({ children, style, color }) => (
  <Text style={[styles.h3, color && { color }, style]}>{children}</Text>
);

export const Body = ({ children, style, color }) => (
  <Text style={[styles.body, color && { color }, style]}>{children}</Text>
);

export const Caption = ({ children, style, color }) => (
  <Text style={[styles.caption, color && { color }, style]}>{children}</Text>
);

export const Label = ({ children, style, color }) => (
  <Text style={[styles.label, color && { color }, style]}>{children}</Text>
);

const styles = StyleSheet.create({
  h1: {
    fontSize: 32,
    fontWeight: '700',
    fontFamily: FONTS.sansBold,
    color: COLORS.ink,
    lineHeight: 38,
    letterSpacing: 0,
  },
  h2: {
    fontSize: 24,
    fontWeight: '700',
    fontFamily: FONTS.sansBold,
    color: COLORS.ink,
    lineHeight: 30,
  },
  h3: {
    fontSize: 18,
    fontWeight: '600',
    fontFamily: FONTS.sansSemi,
    color: COLORS.ink,
  },
  body: {
    fontSize: 15,
    fontFamily: FONTS.sans,
    color: COLORS.ink,
    lineHeight: 22,
  },
  caption: {
    fontSize: 12,
    fontFamily: FONTS.sans,
    color: COLORS.muted,
    lineHeight: 16,
  },
  label: {
    fontSize: 13,
    fontWeight: '500',
    fontFamily: FONTS.sansMedium,
    color: COLORS.muted,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
});
