import { Image, View } from 'react-native';

export default function TripImage({ uri, width, height, borderRadius = 0, style }) {
  if (uri) {
    return (
      <Image
        source={{ uri }}
        style={[{ width, height, borderRadius }, style]}
        resizeMode="cover"
      />
    );
  }
  return (
    <View style={[{ width, height, borderRadius, backgroundColor: '#2A9D8F' }, style]} />
  );
}
