export const NAV_TRANSITION = {
  headerShown: false,
  animation: 'fade_from_bottom',
  animationDuration: 220,
  gestureEnabled: true,
  fullScreenGestureEnabled: true,
  contentStyle: {
    backgroundColor: '#F7F1E7',
  },
}

export const TAB_TRANSITION = {
  ...NAV_TRANSITION,
  animation: 'fade',
  animationDuration: 160,
}

export const FLOW_TRANSITION = {
  ...NAV_TRANSITION,
  animation: 'slide_from_right',
  animationDuration: 220,
}

export const MODAL_TRANSITION = {
  ...NAV_TRANSITION,
  animation: 'slide_from_bottom',
  presentation: 'modal',
  animationDuration: 240,
}
