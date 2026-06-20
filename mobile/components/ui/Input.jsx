import { useState } from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { COLORS, SPACING, RADIUS } from '../../constants/theme';

export default function Input({
  label,
  value,
  onChangeText,
  placeholder,
  secureTextEntry = false,
  error,
  keyboardType = 'default',
  autoCapitalize = 'sentences',
}) {
  const [focused, setFocused] = useState(false);

  return (
    <View style={styles.container}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={COLORS.muted}
        secureTextEntry={secureTextEntry}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={[styles.input, focused && styles.inputFocused, error && styles.inputError]}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: SPACING.md,
  },
  label: {
    fontSize: 13,
    color: COLORS.ink,
    fontWeight: '500',
    marginBottom: 6,
  },
  input: {
    backgroundColor: COLORS.paper,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    borderRadius: RADIUS.md,
    padding: SPACING.md,
    fontSize: 15,
    color: COLORS.ink,
  },
  inputFocused: {
    borderColor: COLORS.teal,
  },
  inputError: {
    borderColor: '#E05252',
  },
  error: {
    fontSize: 12,
    color: '#E05252',
    marginTop: 4,
  },
});
