export const COLORS = {
  cream: '#F5F1EA',
  paper: '#FAFAF7',
  surface: '#FFFFFF',
  ink: '#1A1A2E',
  dark: '#1A1614',
  primary: '#2A9D8F',
  primaryDark: '#1F7A6E',
  teal: '#2A9D8F',
  sage: '#6B7C5A',
  muted: '#888780',
  sub: '#6B7280',
  border: '#E0DAD0',
  borderSoft: 'rgba(26,26,46,0.12)',
  tagBg: '#E6F4F2',
  navy: '#0D1B2A',
  error: '#E76F51',
};

export const FONTS = {
  serif: 'InstrumentSerif_400Regular',
  serifItalic: 'InstrumentSerif_400Regular_Italic',
  mono: 'JetBrainsMono_400Regular',
  sans: 'Inter_400Regular',
  sansMedium: 'Inter_500Medium',
  sansSemi: 'Inter_600SemiBold',
  sansBold: 'Inter_700Bold',
};

export const TYPE = {
  serif: {
    fontFamily: FONTS.serif,
  },
  serifItalic: {
    fontFamily: FONTS.serifItalic,
  },
  serifStrong: {
    fontFamily: FONTS.serif,
    fontWeight: '700',
  },
  serifStrongItalic: {
    fontFamily: FONTS.serifItalic,
    fontWeight: '700',
  },
};

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const RADIUS = {
  sm: 8,
  md: 16,
  lg: 24,
  full: 999,
};

export const SHADOWS = {
  sm: {
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
  },
  md: {
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 4,
  },
  lg: {
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.16,
    shadowRadius: 8,
  },
};
