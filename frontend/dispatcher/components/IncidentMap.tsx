"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

interface RouteMetrics {
  distance_km: number;
  eta_seconds: number;
}

interface IncidentMapProps {
  latitude: number;
  longitude: number;
  accuracy_m?: number;
  incidentId: string;
  ambulanceCoords?: [number, number]; // [lon, lat]
  ambulanceReg?: string;
  ambulanceStatus?: string;
  hospitalCoords?: [number, number]; // [lon, lat]
  hospitalName?: string;
  leg1Metrics?: RouteMetrics;
  leg2Metrics?: RouteMetrics;
  totalEtaSeconds?: number;
}

const DEFAULT_MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

function formatMinutes(seconds?: number): string {
  if (!seconds || seconds <= 0) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs > 0 ? `${secs}s` : ""}`;
}

export default function IncidentMap({
  latitude,
  longitude,
  accuracy_m = 15,
  incidentId,
  ambulanceCoords,
  ambulanceReg = "DL-01-AMB-1081",
  ambulanceStatus = "AVAILABLE",
  hospitalCoords = [77.2088, 28.5672],
  hospitalName = "AIIMS Apex Trauma Center",
  leg1Metrics,
  leg2Metrics,
  totalEtaSeconds,
}: IncidentMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const incMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const ambMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const hospMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const [mapStyle, setMapStyle] = useState<string>("mapbox://styles/mapbox/streets-v12");

  const effectiveAmbCoords: [number, number] = ambulanceCoords || [longitude + 0.018, latitude + 0.012];
  const effectiveHospCoords: [number, number] = hospitalCoords || [77.2088, 28.5672];

  // 1. Initialize map ONCE on mount
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    mapboxgl.accessToken = DEFAULT_MAPBOX_TOKEN;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: mapStyle,
      center: [longitude, latitude],
      zoom: 13,
      pitch: 30,
    });

    map.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), "top-right");

    map.on("load", () => {
      // 🚨 Incident Scene Marker
      const incEl = document.createElement("div");
      incEl.style.width = "32px";
      incEl.style.height = "32px";
      incEl.style.borderRadius = "50%";
      incEl.style.background = "#d72638";
      incEl.style.border = "3px solid #ffffff";
      incEl.style.boxShadow = "0 0 16px rgba(215, 38, 56, 0.9)";
      incEl.style.display = "flex";
      incEl.style.alignItems = "center";
      incEl.style.justifyContent = "center";
      incEl.style.fontSize = "15px";
      incEl.innerHTML = "🚨";

      const incPopup = new mapboxgl.Popup({ offset: 25 }).setHTML(`
        <div style="font-family: sans-serif; padding: 4px;">
          <strong style="color: #0b2545; font-size: 13px;">Incident #${incidentId.slice(-6)}</strong>
          <div style="font-size: 11px; color: #d72638; font-weight: 800; margin-top: 2px;">EMERGENCY SCENE</div>
        </div>
      `);

      incMarkerRef.current = new mapboxgl.Marker(incEl)
        .setLngLat([longitude, latitude])
        .setPopup(incPopup)
        .addTo(map);

      // 🚑 Ambulance Marker
      const ambEl = document.createElement("div");
      ambEl.style.width = "32px";
      ambEl.style.height = "32px";
      ambEl.style.borderRadius = "50%";
      ambEl.style.background = "#16a34a";
      ambEl.style.border = "3px solid #ffffff";
      ambEl.style.boxShadow = "0 0 14px rgba(22, 163, 74, 0.8)";
      ambEl.style.display = "flex";
      ambEl.style.alignItems = "center";
      ambEl.style.justifyContent = "center";
      ambEl.style.fontSize = "15px";
      ambEl.innerHTML = "🚑";

      ambMarkerRef.current = new mapboxgl.Marker(ambEl)
        .setLngLat(effectiveAmbCoords)
        .addTo(map);

      // 🏥 Hospital Marker
      const hospEl = document.createElement("div");
      hospEl.style.width = "30px";
      hospEl.style.height = "30px";
      hospEl.style.borderRadius = "50%";
      hospEl.style.background = "#0284c7";
      hospEl.style.border = "3px solid #ffffff";
      hospEl.style.boxShadow = "0 0 14px rgba(2, 132, 199, 0.8)";
      hospEl.style.display = "flex";
      hospEl.style.alignItems = "center";
      hospEl.style.justifyContent = "center";
      hospEl.style.fontSize = "14px";
      hospEl.innerHTML = "🏥";

      hospMarkerRef.current = new mapboxgl.Marker(hospEl)
        .setLngLat(effectiveHospCoords)
        .addTo(map);

      // Route Corridor Lines
      map.addSource("route-leg1", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: [effectiveAmbCoords, [longitude, latitude]],
          },
        },
      });

      map.addLayer({
        id: "route-leg1-line",
        type: "line",
        source: "route-leg1",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#16a34a", "line-width": 3.5, "line-dasharray": [2, 1.5] },
      });

      map.addSource("route-leg2", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: [[longitude, latitude], effectiveHospCoords],
          },
        },
      });

      map.addLayer({
        id: "route-leg2-line",
        type: "line",
        source: "route-leg2",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#0284c7", "line-width": 3, "line-opacity": 0.85 },
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // 2. Smoothly update positions without tearing down the map
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    // Update marker coordinates smoothly
    if (incMarkerRef.current) incMarkerRef.current.setLngLat([longitude, latitude]);
    if (ambMarkerRef.current) ambMarkerRef.current.setLngLat(effectiveAmbCoords);
    if (hospMarkerRef.current) hospMarkerRef.current.setLngLat(effectiveHospCoords);

    // Update route lines
    const leg1Source = map.getSource("route-leg1") as mapboxgl.GeoJSONSource | undefined;
    if (leg1Source) {
      leg1Source.setData({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: [effectiveAmbCoords, [longitude, latitude]] },
      });
    }

    const leg2Source = map.getSource("route-leg2") as mapboxgl.GeoJSONSource | undefined;
    if (leg2Source) {
      leg2Source.setData({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: [[longitude, latitude], effectiveHospCoords] },
      });
    }

    // Adjust camera view
    const bounds = new mapboxgl.LngLatBounds();
    bounds.extend([longitude, latitude]);
    bounds.extend(effectiveAmbCoords);
    bounds.extend(effectiveHospCoords);
    map.fitBounds(bounds, { padding: 45, maxZoom: 14.5, duration: 600 });
  }, [latitude, longitude, effectiveAmbCoords[0], effectiveAmbCoords[1], effectiveHospCoords[0], effectiveHospCoords[1]]);

  return (
    <div
      style={{
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
        border: "1px solid var(--border)",
        background: "#ffffff",
        position: "relative",
      }}
    >
      {/* Map Header Toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "0.5rem 0.85rem",
          background: "#f8fafc",
          borderBottom: "1px solid var(--border)",
          fontSize: "0.75rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              background: "#dcfce7",
              color: "#15803d",
              padding: "0.15rem 0.5rem",
              borderRadius: "999px",
              fontWeight: 800,
              fontSize: "0.7rem",
            }}
          >
            ● LIVE CORRIDOR
          </span>
          <span style={{ fontWeight: 700, color: "var(--brand-navy)" }}>
            Scene: {latitude.toFixed(4)}, {longitude.toFixed(4)}
          </span>
        </div>

        {/* Mapbox Layer Switcher */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          {[
            { label: "Streets", style: "mapbox://styles/mapbox/streets-v12" },
            { label: "Satellite", style: "mapbox://styles/mapbox/satellite-streets-v12" },
            { label: "Navigation", style: "mapbox://styles/mapbox/navigation-day-v1" },
          ].map((l) => (
            <button
              key={l.label}
              onClick={() => {
                setMapStyle(l.style);
                if (mapRef.current) mapRef.current.setStyle(l.style);
              }}
              style={{
                background: mapStyle === l.style ? "var(--brand-navy)" : "#ffffff",
                color: mapStyle === l.style ? "#ffffff" : "var(--text-secondary)",
                border: "1px solid #cbd5e1",
                borderRadius: "4px",
                padding: "0.18rem 0.5rem",
                fontSize: "0.68rem",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              {l.label}
            </button>
          ))}
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`}
            target="_blank"
            rel="noreferrer"
            style={{
              color: "var(--brand-red)",
              fontWeight: 700,
              textDecoration: "none",
              fontSize: "0.72rem",
              marginLeft: "4px",
            }}
          >
            Google Maps ↗
          </a>
        </div>
      </div>

      {/* Mapbox Canvas Container */}
      <div
        ref={mapContainerRef}
        style={{
          width: "100%",
          height: "340px",
          background: "#f1f5f9",
        }}
      />

      {/* Real-Time Timings & Routing HUD */}
      <div
        style={{
          background: "#0b2545",
          color: "#ffffff",
          padding: "0.65rem 0.85rem",
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: "0.65rem",
          fontSize: "0.78rem",
          borderTop: "1px solid #1e3a8a",
        }}
      >
        {/* Leg 1: Ambulance to Location */}
        <div style={{ borderRight: "1px solid rgba(255,255,255,0.15)", paddingRight: "0.5rem" }}>
          <div style={{ color: "#86efac", fontWeight: 800, fontSize: "0.68rem", textTransform: "uppercase" }}>
            🚑 Leg 1: To Location
          </div>
          <div style={{ fontSize: "1rem", fontWeight: 800, marginTop: "1px" }}>
            ⏱ {formatMinutes(leg1Metrics?.eta_seconds || 320)}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.7rem" }}>
            {ambulanceReg} • {leg1Metrics?.distance_km ? `${leg1Metrics.distance_km} km` : "3.2 km"}
          </div>
        </div>

        {/* Leg 2: Location to Hospital */}
        <div style={{ borderRight: "1px solid rgba(255,255,255,0.15)", paddingRight: "0.5rem" }}>
          <div style={{ color: "#7dd3fc", fontWeight: 800, fontSize: "0.68rem", textTransform: "uppercase" }}>
            🏥 Leg 2: To Trauma ER
          </div>
          <div style={{ fontSize: "1rem", fontWeight: 800, marginTop: "1px" }}>
            ⏱ {formatMinutes(leg2Metrics?.eta_seconds || 650)}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.7rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {hospitalName.split(" ")[0]} • {leg2Metrics?.distance_km ? `${leg2Metrics.distance_km} km` : "6.8 km"}
          </div>
        </div>

        {/* Total Mission Corridor */}
        <div>
          <div style={{ color: "#fde047", fontWeight: 800, fontSize: "0.68rem", textTransform: "uppercase" }}>
            ⚡ Total Mission Time
          </div>
          <div style={{ fontSize: "1rem", fontWeight: 800, color: "#fde047", marginTop: "1px" }}>
            ⏱ {formatMinutes(totalEtaSeconds || (leg1Metrics?.eta_seconds || 320) + (leg2Metrics?.eta_seconds || 650))}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.7rem" }}>
            Trauma Alert Active
          </div>
        </div>
      </div>
    </div>
  );
}
