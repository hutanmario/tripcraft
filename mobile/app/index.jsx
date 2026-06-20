import { Redirect } from 'expo-router';
import { useAuth } from '../context/AuthContext';

export default function Index() {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) return <Redirect href="/(auth)/splash" />;
  if (isAuthenticated) return <Redirect href="/(app)/dashboard" />;
  return <Redirect href="/(auth)/welcome" />;
}
