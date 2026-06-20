import { Stack } from 'expo-router';
import { FLOW_TRANSITION } from '../../../constants/navigation';

export default function QuizLayout() {
  return <Stack screenOptions={FLOW_TRANSITION} />;
}
