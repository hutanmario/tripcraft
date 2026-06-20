import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Stack } from 'expo-router';
import { View } from 'react-native';
import { useFonts } from 'expo-font';
import { AuthProvider } from '../context/AuthContext';
import { COLORS } from '../constants/theme';
import { NAV_TRANSITION } from '../constants/navigation';

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    Inter_400Regular: require('@expo-google-fonts/inter/400Regular/Inter_400Regular.ttf'),
    Inter_500Medium: require('@expo-google-fonts/inter/500Medium/Inter_500Medium.ttf'),
    Inter_600SemiBold: require('@expo-google-fonts/inter/600SemiBold/Inter_600SemiBold.ttf'),
    Inter_700Bold: require('@expo-google-fonts/inter/700Bold/Inter_700Bold.ttf'),

    InstrumentSerif_400Regular: require('@expo-google-fonts/instrument-serif/400Regular/InstrumentSerif_400Regular.ttf'),
    InstrumentSerif_400Regular_Italic: require('@expo-google-fonts/instrument-serif/400Regular_Italic/InstrumentSerif_400Regular_Italic.ttf'),
    JetBrainsMono_400Regular: require('@expo-google-fonts/jetbrains-mono/400Regular/JetBrainsMono_400Regular.ttf'),
  });

  if (!fontsLoaded) {
    return <View style={{ flex: 1, backgroundColor: COLORS.cream }} />;
  }

  return (
    <SafeAreaProvider>
      <AuthProvider>
        <Stack screenOptions={NAV_TRANSITION}>
        </Stack>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
