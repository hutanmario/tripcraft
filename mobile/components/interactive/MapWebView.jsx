import {
  useEffect,
  useRef,
  useState } from 'react';
import { ActivityIndicator,
  StyleSheet,
  Text,
  View
} from 'react-native';
import TouchableOpacity from '../ui/SmoothTouchable';

import { WebView } from 'react-native-webview';
import { C } from '../../constants/interactive';
import { FONTS, TYPE } from '../../constants/theme';

function markerVisualScore(marker) {
  const raw = Number(marker.marker_score ?? marker.score_pct ?? marker.score ?? 80);
  if (!Number.isFinite(raw)) return 80;
  return raw <= 1 ? Math.round(raw * 100) : raw;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"'`\\]/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '`': '&#96;',
    '\\': '&#92;',
  }[char]));
}

function safeNumber(value, fallback = 0) {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}

function safeJsLiteral(value) {
  return JSON.stringify(value ?? null).replace(/<\/script/gi, '<\\/script');
}

function buildHtml(markers, center, zoom, mode) {
  const rawCenter = center || { lat: 46.8, lng: 2.35 };
  const safeCenter = {
    lat: safeNumber(rawCenter.lat, 46.8),
    lng: safeNumber(rawCenter.lng, 2.35),
  };
  const safeZoom = Math.max(1, Math.min(safeNumber(zoom, 6), 18));
  const isCity = mode === 'city';
  const hasLabels = markers.length > 0 && markers[0].label !== undefined;
  const visualScores = markers.map(markerVisualScore);
  const maxScore = visualScores.length > 0 ? Math.max(...visualScores) : 100;

  const markerDefs = markers.map((m) => {
    const lat = safeNumber(m.lat, safeCenter.lat);
    const lng = safeNumber(m.lng, safeCenter.lng);
    const markerId = safeJsLiteral(m.id);
    let iconHtml;
    let size;
    let anchor;

    if (hasLabels) {
      size = 32;
      anchor = 16;
      iconHtml = JSON.stringify(`<div style="width:32px;height:32px;border-radius:50%;background:#2A9D8F;border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;font-weight:700;font-family:sans-serif;box-sizing:border-box;">${escapeHtml(m.label)}</div>`);
    } else if (isCity) {
      size = 12;
      anchor = 6;
      iconHtml = JSON.stringify('<div style="width:12px;height:12px;border-radius:50%;background:#2A9D8F;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);"></div>');
    } else {
      const visualScore = markerVisualScore(m);
      size = Math.round(16 + (Math.max(0, Math.min(visualScore, 100)) / 100) * 18);
      anchor = Math.round(size / 2);
      const border = visualScore === maxScore ? 'border: 2px solid #fff;' : '';
      iconHtml = JSON.stringify(`<div style="width:${size}px;height:${size}px;border-radius:50%;background:#2A9D8F;${border}opacity:0.92;box-shadow:0 2px 8px rgba(0,0,0,0.25);"></div>`);
    }

    return `
      (function(){
        var icon = L.divIcon({
          className: '',
          html: ${iconHtml},
          iconSize: [${size}, ${size}],
          iconAnchor: [${anchor}, ${anchor}],
        });
        L.marker([${lat}, ${lng}], { icon: icon })
          .addTo(map)
          .on('click', function(){
            window.ReactNativeWebView.postMessage(JSON.stringify({type:'markerPress',id:${markerId}}));
          });
      })();`;
  }).join('\n');

  return `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; width:100%; height:100%; background:#E8ECEF; }
  #map { width:100vw; height:100vh; }
</style>
</head>
<body>
<div id="map"></div>
<script>
  function notify(type, payload) {
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify(Object.assign({type:type}, payload || {})));
    }
  }
  try {
    var map = L.map('map', { zoomControl:false, attributionControl:false })
                .setView([${safeCenter.lat}, ${safeCenter.lng}], ${safeZoom});
    var tileFailures = 0;
    var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png');
    tiles.on('tileerror', function(){
      tileFailures += 1;
      if (tileFailures >= 4) notify('mapError', {message:'Map tiles could not load.'});
    });
    tiles.addTo(map);
    map.whenReady(function(){ notify('mapReady'); });
    map.on('click', function(){ notify('mapPress'); });
    ${markerDefs}
  } catch (e) {
    notify('mapError', {message:e.message || 'Map could not start.'});
  }
</script>
</body>
</html>`;
}

function buildRouteUpdateJS(points, mode, routeStyle) {
  if (points.length < 2) {
    return `
      if (window._routeLayer) { map.removeLayer(window._routeLayer); window._routeLayer = null; }
      if (window._routeDots) { window._routeDots.forEach(function(d) { map.removeLayer(d); }); window._routeDots = []; }
      if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify({type:'routeReady'}));
      true;
    `;
  }

  const coords = points.map((p) => `${p.lng},${p.lat}`).join(';');
  const pointsJSON = JSON.stringify(points);
  const dashArray = routeStyle === 'dashed' ? ', dashArray: "8 10"' : '';

  return `
    (function() {
      var url = 'https://router.project-osrm.org/route/v1/${mode}/${coords}?overview=full&geometries=geojson';
      var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var timeout = setTimeout(function() {
        if (controller) controller.abort();
      }, 8000);
      fetch(url, controller ? { signal: controller.signal } : undefined)
        .then(function(r) {
          if (!r.ok) throw new Error('Route service unavailable');
          return r.json();
        })
        .then(function(data) {
          if (!data.routes || !data.routes[0]) throw new Error('No route found');
          var latlngs = data.routes[0].geometry.coordinates.map(function(c) {
            return [c[1], c[0]];
          });
          if (window._routeLayer) map.removeLayer(window._routeLayer);
          if (window._routeDots) window._routeDots.forEach(function(d) { map.removeLayer(d); });
          window._routeLayer = L.polyline(latlngs, {
            color: '#2A9D8F', weight: 4, opacity: 0.85, lineJoin: 'round'${dashArray}
          }).addTo(map);
          window._routeDots = ${pointsJSON}.map(function(p) {
            return L.circleMarker([p.lat, p.lng], {
              radius: 6, color: '#fff', weight: 2,
              fillColor: '#2A9D8F', fillOpacity: 1
            }).addTo(map);
          });
          if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify({type:'routeReady'}));
        })
        .catch(function(e) {
          if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify({type:'routeError', message:e.message || 'Route could not load.'}));
        })
        .finally(function() {
          clearTimeout(timeout);
        });
    })();
    true;
  `;
}

function buildViewportUpdateJS(center, zoom) {
  if (!center || center.lat == null || center.lng == null) return 'true;';
  return `
    (function() {
      if (typeof map !== 'undefined') {
        map.flyTo([${center.lat}, ${center.lng}], ${zoom}, { animate: true, duration: 0.65 });
      }
    })();
    true;
  `;
}

function buildActiveMarkerJS(activeId) {
  return `
    (function() {
      document.querySelectorAll('[id^="nm-"]').forEach(function(el) {
        var id = parseInt(el.id.replace('nm-', ''));
        if (id === ${activeId}) {
          el.style.border = '3px solid #fff';
          el.style.boxShadow = '0 0 0 6px rgba(42,157,143,0.3), 0 2px 8px rgba(0,0,0,0.3)';
        } else {
          el.style.border = '2px solid #fff';
          el.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
        }
      });
    })();
    true;
  `;
}

export default function MapWebView({
  markers = [],
  center,
  zoom = 5,
  mode = 'country',
  routePoints = [],
  routeMode = 'foot',
  routeStyle,
  activeMarkerId = null,
  onMarkerPress,
  onMapPress,
}) {
  const webViewRef = useRef(null);
  const readyRef = useRef(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState('');
  const [routeError, setRouteError] = useState('');

  function injectMapState() {
    if (!webViewRef.current) return;
    webViewRef.current.injectJavaScript(buildViewportUpdateJS(center, zoom));
    webViewRef.current.injectJavaScript(buildRouteUpdateJS(routePoints, routeMode, routeStyle));
    if (activeMarkerId != null) {
      webViewRef.current.injectJavaScript(buildActiveMarkerJS(activeMarkerId));
    }
  }

  useEffect(() => {
    readyRef.current = false;
    setMapReady(false);
    setMapError('');
    setRouteError('');
    const timeout = setTimeout(() => {
      if (!readyRef.current) {
        setMapError('Map is taking too long to load. Check your connection and retry.');
      }
    }, 9000);
    return () => clearTimeout(timeout);
  }, [reloadKey, center?.lat, center?.lng, zoom, mode, markers.length]);

  useEffect(() => {
    if (!webViewRef.current) return;
    webViewRef.current.injectJavaScript(buildViewportUpdateJS(center, zoom));
  }, [center?.lat, center?.lng, zoom]);

  useEffect(() => {
    if (!webViewRef.current) return;
    setRouteError('');
    webViewRef.current.injectJavaScript(buildRouteUpdateJS(routePoints, routeMode, routeStyle));
  }, [routePoints, routeMode, routeStyle]);

  useEffect(() => {
    if (!webViewRef.current || activeMarkerId == null) return;
    webViewRef.current.injectJavaScript(buildActiveMarkerJS(activeMarkerId));
  }, [activeMarkerId]);

  function handleMessage(e) {
    try {
      const msg = JSON.parse(e.nativeEvent.data);
      if (msg.type === 'markerPress' && onMarkerPress) onMarkerPress(msg.id);
      if (msg.type === 'mapPress' && onMapPress) onMapPress();
      if (msg.type === 'mapReady') {
        readyRef.current = true;
        setMapReady(true);
        setMapError('');
      }
      if (msg.type === 'mapError') setMapError(msg.message || 'Map could not load.');
      if (msg.type === 'routeReady') setRouteError('');
      if (msg.type === 'routeError') setRouteError(msg.message || 'Route could not load.');
    } catch {}
  }

  function retryMap() {
    readyRef.current = false;
    setReloadKey((value) => value + 1);
  }

  return (
    <View style={styles.wrapper}>
      <WebView
        key={reloadKey}
        ref={webViewRef}
        style={styles.map}
        source={{ html: buildHtml(markers, center, zoom, mode) }}
        originWhitelist={['*']}
        onLoadEnd={injectMapState}
        onError={() => setMapError('Map WebView failed to load.')}
        onHttpError={() => setMapError('Map resources failed to load.')}
        onMessage={handleMessage}
        scrollEnabled={false}
        javaScriptEnabled
      />

      {!mapReady && !mapError ? (
        <View style={styles.loadingOverlay} pointerEvents="none">
          <ActivityIndicator color={C.primary} />
          <Text style={styles.loadingText}>Loading map...</Text>
        </View>
      ) : null}

      {mapError ? (
        <View style={styles.errorOverlay}>
          <Text style={styles.errorTitle}>Map could not load</Text>
          <Text style={styles.errorText}>{mapError}</Text>
          <TouchableOpacity style={styles.retryBtn} activeOpacity={0.85} onPress={retryMap}>
            <Text style={styles.retryText}>Retry map</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {!mapError && routeError ? (
        <View style={styles.routeBanner}>
          <Text style={styles.routeBannerText}>Route unavailable right now. Stops are still saved.</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { flex: 1, backgroundColor: '#E8ECEF' },
  map: { flex: 1 },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(248,249,250,0.76)',
    gap: 10,
  },
  loadingText: {
    fontSize: 12,
    color: C.sub,
    fontFamily: 'Inter_400Regular',
  },
  errorOverlay: {
    position: 'absolute',
    left: 24,
    right: 24,
    top: '28%',
    borderRadius: 18,
    padding: 18,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
    shadowColor: C.navy,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 20,
    elevation: 8,
  },
  errorTitle: {
    fontSize: 18,
    color: C.ink,
    ...TYPE.serifItalic,
  },
  errorText: {
    marginTop: 6,
    fontSize: 12,
    color: C.sub,
    textAlign: 'center',
    lineHeight: 18,
  },
  retryBtn: {
    marginTop: 14,
    height: 40,
    paddingHorizontal: 18,
    borderRadius: 100,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retryText: {
    fontSize: 13,
    color: '#FFFFFF',
    fontWeight: '700',
  },
  routeBanner: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 12,
    borderRadius: 100,
    paddingVertical: 9,
    paddingHorizontal: 14,
    backgroundColor: 'rgba(13,27,42,0.78)',
    alignItems: 'center',
  },
  routeBannerText: {
    fontSize: 11,
    color: '#FFFFFF',
    fontWeight: '600',
  },
});
