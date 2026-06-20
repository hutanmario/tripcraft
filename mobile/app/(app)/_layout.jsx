import { Redirect, Stack } from 'expo-router';
import { QuizProvider } from '../../context/QuizContext';
import { useAuth } from '../../context/AuthContext';
import { FLOW_TRANSITION, TAB_TRANSITION } from '../../constants/navigation';

export default function AppLayout() {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) return null;
  if (!isAuthenticated) return <Redirect href="/(auth)/welcome" />;

  return (
    <QuizProvider>
      <Stack screenOptions={FLOW_TRANSITION}>
        <Stack.Screen name="dashboard" options={TAB_TRANSITION} />
        <Stack.Screen name="friends" options={TAB_TRANSITION} />
        <Stack.Screen name="profile" options={TAB_TRANSITION} />
        <Stack.Screen name="destinations" options={TAB_TRANSITION} />
        <Stack.Screen name="group-trip" />
      </Stack>
    </QuizProvider>
  );
}
