import { forwardRef, useRef } from 'react'
import { Animated, TouchableOpacity } from 'react-native'

const AnimatedTouchable = Animated.createAnimatedComponent(TouchableOpacity)

const SmoothTouchable = forwardRef(function SmoothTouchable(
  {
    children,
    disabled,
    activeOpacity = 0.9,
    pressScale = 0.975,
    style,
    onPressIn,
    onPressOut,
    ...props
  },
  ref,
) {
  const scale = useRef(new Animated.Value(1)).current

  function animate(toValue, config = {}) {
    Animated.spring(scale, {
      toValue,
      useNativeDriver: true,
      speed: 28,
      bounciness: 5,
      ...config,
    }).start()
  }

  return (
    <AnimatedTouchable
      ref={ref}
      activeOpacity={activeOpacity}
      disabled={disabled}
      onPressIn={(event) => {
        if (!disabled) animate(pressScale)
        onPressIn?.(event)
      }}
      onPressOut={(event) => {
        if (!disabled) animate(1, { speed: 32, bounciness: 6 })
        onPressOut?.(event)
      }}
      style={[style, { transform: [{ scale }] }]}
      {...props}
    >
      {children}
    </AnimatedTouchable>
  )
})

export default SmoothTouchable
