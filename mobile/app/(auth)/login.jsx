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
import AsyncStorage from '@react-native-async-storage/async-storage';
import apiClient from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { COLORS, FONTS, SPACING, RADIUS, TYPE } from '../../constants/theme';

export default function LoginScreen() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [focused, setFocused] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin() {
    setError('');
    setLoading(true);
    try {
      const { data } = await apiClient.post('/auth/login', {
        email: email.trim(),
        password,
      });
      await login(data.access_token, data.user);
      router.replace('/(app)/dashboard');
    } catch (err) {
      setError('Invalid email or password');
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
          {/* Back */}
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <Text style={styles.backArrow}>←</Text>
          </TouchableOpacity>

          {/* Header */}
          <Text style={styles.sectionLabel}>SIGN IN</Text>
          <Text style={styles.title}>
            {'Welcome '}
            <Text style={styles.italic}>back.</Text>
          </Text>
          <Text style={styles.subtitle}>Where we left off, exactly.</Text>

          {/* Fields */}
          <View style={styles.fields}>
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
                  placeholder="••••••••••"
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
              <TouchableOpacity style={styles.forgotWrap}>
                <Text style={styles.forgot}>Forgot password?</Text>
              </TouchableOpacity>
            </View>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          {/* Sign in CTA */}
          <TouchableOpacity
            style={[styles.inkBtn, loading && styles.inkBtnDisabled]}
            activeOpacity={0.88}
            onPress={handleLogin}
            disabled={loading}
          >
            <Text style={styles.inkBtnLabel}>{loading ? 'Signing in…' : 'Sign in'}</Text>
            <View style={styles.inkBtnDot}>
              <Text style={styles.inkBtnArrow}>→</Text>
            </View>
          </TouchableOpacity>

          {/* Footer */}
          <View style={styles.footerRow}>
            <Text style={styles.footerText}>No account? </Text>
            <TouchableOpacity onPress={() => router.push('/(auth)/register')}>
              <Text style={styles.footerLink}>Create one</Text>
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

  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: SPACING.sm,
    marginBottom: SPACING.lg,
    alignSelf: 'flex-start',
  },
  backArrow: { fontSize: 16, color: COLORS.ink },

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
  forgotWrap: { alignSelf: 'flex-end', marginTop: 6 },
  forgot: {
    fontSize: 13,
    color: COLORS.muted,
    fontFamily: FONTS.sans,
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
  },
  footerText: { fontSize: 14, color: COLORS.muted, fontFamily: FONTS.sans },
  footerLink: {
    fontSize: 14,
    color: COLORS.ink,
    fontFamily: FONTS.sans,
    textDecorationLine: 'underline',
  },
});
