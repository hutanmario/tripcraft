import { View, StyleSheet, Dimensions } from 'react-native';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

export default function BottomPanel({ heightPercent = 0.45, children }) {
  return (
    <View style={[styles.panel, { height: SCREEN_HEIGHT * heightPercent }]}>
      <View style={styles.handle} />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    shadowColor: '#0D1B2A',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.10,
    shadowRadius: 16,
    elevation: 12,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 100,
    backgroundColor: 'rgba(26,26,46,0.15)',
    alignSelf: 'center',
    marginTop: 12,
    marginBottom: 8,
  },
});
