import { Stack } from 'expo-router';
import { FLOW_TRANSITION } from '../../../constants/navigation';

export default function ItineraryLayout() {
  return <Stack screenOptions={FLOW_TRANSITION} />;
}
