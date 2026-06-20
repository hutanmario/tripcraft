import { Redirect, Stack, useSegments } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { FLOW_TRANSITION, NAV_TRANSITION } from '../../constants/navigation';

const AUTHENTICATED_AUTH_ROUTES = new Set([
  'greeting',
  'greeting-login',
  'photo-onboarding',
  'photo-review',
]);

export default function AuthLayout() {
  const { isLoading, isAuthenticated } = useAuth();
  const segments = useSegments();
  const routeName = segments[1];
  const isAuthenticatedAuthRoute = AUTHENTICATED_AUTH_ROUTES.has(routeName);

  if (isLoading && routeName !== 'splash') return null;
  if (isLoading) {
    return (
      <Stack screenOptions={NAV_TRANSITION}>
        <Stack.Screen name="splash" options={{ animation: 'fade' }} />
      </Stack>
    );
  }
  if (isAuthenticated && !isAuthenticatedAuthRoute) {
    return <Redirect href="/(app)/dashboard" />;
  }
  if (!isAuthenticated && isAuthenticatedAuthRoute) {
    return <Redirect href="/(auth)/welcome" />;
  }

  return (
    <Stack screenOptions={FLOW_TRANSITION}>
      <Stack.Screen name="splash" options={{ animation: 'fade' }} />
      <Stack.Screen name="welcome" options={{ animation: 'fade' }} />
      <Stack.Screen name="register" />
      <Stack.Screen name="login" />
      <Stack.Screen name="greeting" />
      <Stack.Screen name="greeting-login" />
      <Stack.Screen name="photo-onboarding" />
      <Stack.Screen name="photo-review" />
    </Stack>
  );
}
