import {
  useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  View,
  Text,
  TextInput,
  StyleSheet
} from 'react-native';
import TouchableOpacity from '../../components/ui/SmoothTouchable';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import apiClient from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { COLORS, FONTS, SPACING, RADIUS, TYPE } from '../../constants/theme';

export default function RegisterScreen() {
  const router = useRouter();
  const { login } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [focused, setFocused] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleRegister() {
    setError('');
    if (!name.trim()) { setError('Please enter your full name'); return; }
    if (!email.trim()) { setError('Please enter your email'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    if (!agreed) { setError('Please agree to the terms'); return; }

    setLoading(true);
    try {
      await apiClient.post('/auth/register', {
        full_name: name.trim(),
        username: email.split('@')[0],
        email: email.trim(),
        password,
      });
      const { data } = await apiClient.post('/auth/login', {
        email: email.trim(),
        password,
      });
      router.replace('/(auth)/greeting');
      await login(data.access_token, data.user);
    } catch (err) {
      if (err.response?.status === 409) setError('Email already in use');
      else setError(err.response?.data?.detail || err.response?.data?.message || JSON.stringify(err.response?.data) || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Top row: back + step */}
          <View style={styles.topRow}>
            <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
              <Text style={styles.backArrow}>←</Text>
            </TouchableOpacity>
            <Text style={styles.step}>STEP 1 / 2</Text>
          </View>

          {/* Header */}
          <Text style={styles.sectionLabel}>CREATE ACCOUNT</Text>
          <Text style={styles.title}>
            {'Tell us your '}
            <Text style={styles.italic}>name.</Text>
          </Text>
          <Text style={styles.subtitle}>Three quick fields. We'll never share them.</Text>

          {/* Fields */}
          <View style={styles.fields}>
            <View style={styles.fieldWrap}>
              <Text style={styles.fieldLabel}>FULL NAME</Text>
              <TextInput
                style={[styles.field, focused === 'name' && styles.fieldFocused]}
                value={name}
                onChangeText={setName}
                onFocus={() => setFocused('name')}
                onBlur={() => setFocused(null)}
                placeholder="Sofia Ardelean"
                placeholderTextColor={COLORS.muted}
                autoCapitalize="words"
              />
            </View>
            <View style={styles.fieldWrap}>
              <Text style={styles.fieldLabel}>EMAIL</Text>
              <TextInput
                style={[styles.field, focused === 'email' && styles.fieldFocused]}
                value={email}
                onChangeText={setEmail}
                onFocus={() => setFocused('email')}
                onBlur={() => setFocused(null)}
                placeholder="sofia@hello.travel"
                placeholderTextColor={COLORS.muted}
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>
            <View style={styles.fieldWrap}>
              <Text style={styles.fieldLabel}>PASSWORD</Text>
              <View
                style={[
                  styles.field,
                  styles.passwordWrap,
                  focused === 'pass' && styles.fieldFocused,
                ]}
              >
                <TextInput
                  style={styles.passwordInput}
                  value={password}
                  onChangeText={setPassword}
                  onFocus={() => setFocused('pass')}
                  onBlur={() => setFocused(null)}
                  placeholder="At least 8 characters"
                  placeholderTextColor={COLORS.muted}
                  secureTextEntry={!showPassword}
                />
                <TouchableOpacity
                  onPress={() => setShowPassword((v) => !v)}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <Text style={styles.showToggle}>{showPassword ? 'hide' : 'show'}</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>

          {/* Checkbox */}
          <TouchableOpacity
            style={styles.checkRow}
            activeOpacity={0.8}
            onPress={() => setAgreed((v) => !v)}
          >
            <View style={[styles.checkbox, agreed && styles.checkboxOn]}>
              {agreed && <Text style={styles.checkmark}>✓</Text>}
            </View>
            <Text style={styles.checkLabel}>
              {'I agree to the '}
              <Text style={styles.checkLink}>terms</Text>
              {' and '}
              <Text style={styles.checkLink}>privacy policy</Text>
              {'.'}
            </Text>
          </TouchableOpacity>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          {/* CTA */}
          <TouchableOpacity
            style={[styles.inkBtn, loading && styles.inkBtnDisabled]}
            activeOpacity={0.88}
            onPress={handleRegister}
            disabled={loading}
          >
            <Text style={styles.inkBtnLabel}>
              {loading ? 'Creating account…' : 'Create account'}
            </Text>
            <View style={styles.inkBtnDot}>
              <Text style={styles.inkBtnArrow}>→</Text>
            </View>
          </TouchableOpacity>

          {/* Footer */}
          <View style={styles.footerRow}>
            <Text style={styles.footerText}>Already have an account? </Text>
            <TouchableOpacity onPress={() => router.replace('/(auth)/login')}>
              <Text style={styles.footerLink}>Sign in</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.cream },
  scroll: {
    paddingHorizontal: SPACING.md,
    paddingBottom: SPACING.xxl,
  },

  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: SPACING.sm,
    marginBottom: SPACING.lg,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  backArrow: { fontSize: 16, color: COLORS.ink },
  step: {
    fontSize: 11,
    letterSpacing: 1,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    textTransform: 'uppercase',
  },

  sectionLabel: {
    fontSize: 11,
    letterSpacing: 1.5,
    color: COLORS.teal,
    fontFamily: FONTS.sans,
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: SPACING.xs,
  },
  title: {
    fontSize: 30,
    ...TYPE.serif,
    color: COLORS.ink,
    lineHeight: 38,
    marginBottom: SPACING.xs,
  },
  italic: {
    ...TYPE.serifItalic,
    color: COLORS.teal,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    marginBottom: SPACING.lg,
  },

  fields: { gap: SPACING.md, marginBottom: SPACING.md },
  fieldWrap: { gap: 6 },
  fieldLabel: {
    fontSize: 10,
    letterSpacing: 1.2,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  field: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.sm,
    paddingVertical: 14,
    paddingHorizontal: SPACING.md,
    fontSize: 15,
    fontFamily: FONTS.sans,
    color: COLORS.ink,
    backgroundColor: '#FFFFFF',
  },
  fieldFocused: { borderColor: COLORS.ink },
  passwordWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 0,
    paddingHorizontal: SPACING.md,
  },
  passwordInput: {
    flex: 1,
    paddingVertical: 14,
    fontSize: 15,
    fontFamily: FONTS.sans,
    color: COLORS.ink,
  },
  showToggle: {
    fontSize: 13,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
  },

  checkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    marginBottom: SPACING.md,
    marginTop: SPACING.xs,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
  },
  checkboxOn: {
    backgroundColor: COLORS.ink,
    borderColor: COLORS.ink,
  },
  checkmark: { color: '#FFFFFF', fontSize: 11, fontWeight: '700' },
  checkLabel: {
    flex: 1,
    fontSize: 13,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
    lineHeight: 18,
  },
  checkLink: {
    color: COLORS.ink,
    textDecorationLine: 'underline',
  },

  error: {
    fontSize: 13,
    color: '#D94F3D',
    fontFamily: FONTS.sans,
    marginBottom: SPACING.sm,
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
    marginBottom: SPACING.md,
  },
  inkBtnDisabled: { opacity: 0.6 },
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

  footerRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: SPACING.xs,
  },
  footerText: { fontSize: 14, color: COLORS.muted, fontFamily: FONTS.sans },
  footerLink: {
    fontSize: 14,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    textDecorationLine: 'underline',
  },
});
