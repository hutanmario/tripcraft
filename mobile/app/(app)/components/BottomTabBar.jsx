import { View, Text, StyleSheet } from 'react-native'
import TouchableOpacity from '../../../components/ui/SmoothTouchable';
import { useRouter, usePathname } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

export default function BottomTabBar() {
  const router = useRouter()
  const pathname = usePathname()
  const insets = useSafeAreaInsets()

  const tabs = [
    { name: 'Home', icon: 'home', route: '/(app)/dashboard' },
    { name: 'Friends', icon: 'people', route: '/(app)/friends' },
    { name: 'Profile', icon: 'person', route: '/(app)/profile' },
  ]

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + 8 }]}>
      {tabs.map(tab => {
        const isActive = pathname.includes(tab.name.toLowerCase())
        return (
          <TouchableOpacity
            key={tab.name}
            style={styles.tab}
            onPress={() => router.push(tab.route)}
          >
            <Ionicons
              name={isActive ? tab.icon : tab.icon + '-outline'}
              size={24}
              color={isActive ? '#2A9D8F' : '#888780'}
            />
            <Text style={[styles.label, { color: isActive ? '#2A9D8F' : '#888780' }]}>
              {tab.name}
            </Text>
          </TouchableOpacity>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    backgroundColor: '#F5F1EA',
    borderTopWidth: 0.5,
    borderTopColor: '#E0DAD0',
    paddingTop: 10,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    gap: 2,
  },
  label: {
    fontSize: 10,
  },
})
