import { useMemo, useCallback } from 'react'
import { View, Text, StyleSheet } from 'react-native'
import Svg, { Path, Circle, Text as SvgText, Rect } from 'react-native-svg'
import { EUROPE_MAP_PATHS } from './europeMapPaths'

const EU_ISOS = new Set([
  'AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES',
  'FI','FR','GB','GR','HR','HU','IE','IS','IT','LT','LU','LV','MD',
  'ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','UA','XK',
])

const LEGEND_COLORS = ['#A8D4CC', '#5CBFB0', '#2A9D8F', '#1A7B6C', '#0C5A4E']

const FULL_VIEWBOX = '118 32 258 286'
const COMPACT_VIEWBOX = '118 145 220 168'

function buildColorMap(countries, topCount) {
  const sorted = [...(countries || [])]
    .filter(c => c?.iso2 && (c.score || 0) > 0)
    .sort((a, b) => (b.score || 0) - (a.score || 0))

  const topSet = new Set(sorted.slice(0, topCount).map(c => c.iso2.toUpperCase()))
  const scores = {}
  sorted.forEach(c => { scores[c.iso2.toUpperCase()] = c.score || 0 })

  const vals = sorted.map(c => c.score)
  const minS = vals.length ? Math.min(...vals) : 0
  const maxS = vals.length ? Math.max(...vals) : 1

  const colorMap = {}
  EU_ISOS.forEach(iso => {
    const score = scores[iso] || 0
    if (!score)          { colorMap[iso] = '#8AADA5'; return }
    if (topSet.has(iso)) { colorMap[iso] = '#0C5A4E'; return }
    const t = maxS === minS ? 0.5 : (score - minS) / (maxS - minS)
    if (t < 0.25)      colorMap[iso] = '#A8D4CC'
    else if (t < 0.50) colorMap[iso] = '#5CBFB0'
    else if (t < 0.75) colorMap[iso] = '#2A9D8F'
    else               colorMap[iso] = '#1A7B6C'
  })
  return colorMap
}

export default function EuropeHeatmap({
  countries = [],
  onCountryPress,
  height = 300,
  showLegend = true,
  compact = false,
  highlightedIso2,
  selectedIso2,
  topCount = 5,
}) {
  const legendHeight = showLegend ? 42 : 0
  const mapHeight    = Math.max(120, height - legendHeight)

  const colorMap = useMemo(
    () => buildColorMap(countries, topCount),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(countries), topCount]
  )

  const highlighted = (highlightedIso2 || '').toUpperCase()
  const selected    = (selectedIso2   || '').toUpperCase()
  const viewBox     = compact ? COMPACT_VIEWBOX : FULL_VIEWBOX
  const markerR     = compact ? 5.5 : 7
  const labelSz     = compact ? 8   : 10

  const handlePress = useCallback((iso2) => {
    if (!onCountryPress) return
    const match = countries.find(c => (c.iso2 || '').toUpperCase() === iso2)
    if (match) onCountryPress(match)
  }, [countries, onCountryPress])

  const topShape = EUROPE_MAP_PATHS.find(s => s.iso2 === highlighted)
  const selShape = selected && selected !== highlighted
    ? EUROPE_MAP_PATHS.find(s => s.iso2 === selected) : null

  return (
    <View style={[styles.container, { height, borderRadius: compact ? 10 : 12 }]}>
      <View
        style={[styles.mapWrap, { height: mapHeight }]}
      >
        <Svg
          width="100%"
          height="100%"
          viewBox={viewBox}
          preserveAspectRatio="xMidYMid meet"
        >
          <Rect x="0" y="0" width="430" height="330" fill="#C8E4DE" />

          {EUROPE_MAP_PATHS.map(shape => {
            const iso    = shape.iso2
            const fill   = colorMap[iso] || '#8AADA5'
            const isSel  = iso === selected
            const isHigh = iso === highlighted
            return (
              <Path
                key={iso}
                d={shape.d}
                fill={fill}
                stroke={isSel ? '#1A1614' : isHigh ? '#FFFFFF' : '#B8D0CC'}
                strokeWidth={isSel ? 1.8 : isHigh ? 1.4 : 0.5}
                onPress={() => handlePress(iso)}
              />
            )
          })}

          {topShape && (
            <>
              <Circle
                cx={topShape.x} cy={topShape.y}
                r={markerR}
                fill="#2A9D8F" stroke="#FFFFFF" strokeWidth={2}
              />
              <SvgText
                x={topShape.x} y={topShape.y - markerR - 3}
                textAnchor="middle"
                fontSize={labelSz} fontWeight="700" fill="#1A1614"
              >
                TOP
              </SvgText>
            </>
          )}

          {selShape && (
            <Circle
              cx={selShape.x} cy={selShape.y}
              r={markerR}
              fill="#1A1614" stroke="#FFFFFF" strokeWidth={2}
            />
          )}
        </Svg>
      </View>

      {showLegend && (
        <View style={styles.legend}>
          <Text style={styles.legendText}>Weak</Text>
          <View style={styles.legendRamp}>
            {LEGEND_COLORS.map(color => (
              <View key={color} style={[styles.legendStep, { backgroundColor: color }]} />
            ))}
          </View>
          <Text style={styles.legendText}>Strong</Text>
          <View style={styles.legendDivider} />
          <View style={styles.legendItem}>
            <View style={styles.topSwatch} />
            <Text style={styles.legendText}>Top pick</Text>
          </View>
        </View>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  container: { overflow: 'hidden', backgroundColor: '#C8E4DE' },
  mapWrap:   { width: '100%', backgroundColor: '#C8E4DE' },
  legend: {
    height: 42, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', paddingHorizontal: 10,
    backgroundColor: '#F5F1EA',
    borderTopWidth: 1, borderTopColor: 'rgba(26,26,46,0.08)',
  },
  legendRamp:    { flexDirection: 'row', overflow: 'hidden', borderRadius: 999, width: 104, height: 8 },
  legendStep:    { flex: 1 },
  legendDivider: { width: 1, height: 16, backgroundColor: 'rgba(26,26,46,0.12)' },
  legendItem:    { flexDirection: 'row', alignItems: 'center', gap: 5 },
  topSwatch: {
    width: 10, height: 10, borderRadius: 5,
    backgroundColor: '#0C5A4E', borderWidth: 2, borderColor: '#F8F1E2',
  },
  legendText: { fontSize: 10, color: '#888780', fontFamily: 'Inter_400Regular' },
})
