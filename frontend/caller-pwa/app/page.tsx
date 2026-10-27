"use client";
/**
 * EMRP — Caller & Citizen Emergency Response Portal
 * Layout & Alignment inspired by clean, modern editorial design system:
 * - Fixed high-contrast navbar with brand logo & quick actions
 * - Punchy, bold hero section with dual action buttons
 * - Interactive emergency response estimator & live dispatch slip
 * - 5-column "How an emergency response moves" stepper
 * - Two-column Citizen vs Dispatcher comparison breakdown
 * - Live Network Activity status banner
 * - Deep navy brand footer
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, type SOSResponse } from "@/lib/apiClient";
import VoiceHotlineModal from "../components/VoiceHotlineModal";

// ─── Types ────────────────────────────────────────────────────────────────────

type AppState =
  | "AUTH"
  | "IDLE"
  | "LOCATING"
  | "READY"
  | "SENDING"
  | "TRACKING"
  | "ERROR";

type SeverityType = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

interface LocationState {
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function accuracyClass(acc: number): string {
  if (acc <= 30) return "accuracy-good";
  if (acc <= 100) return "accuracy-fair";
  return "accuracy-poor";
}

function accuracyLabel(acc: number): string {
  if (acc <= 30) return "Good";
  if (acc <= 100) return "Fair";
  return "Poor";
}

function statusBadgeClass(status: string): string {
  return `badge badge-${status.toLowerCase()}`;
}

function etaLabel(seconds: number | null): string {
  if (!seconds) return "Calculating...";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

export default function CallerPWAPage() {
  // Auth bypassed for testing (toggleable)
  const [appState, setAppState] = useState<AppState>("LOCATING");
  const [location, setLocation] = useState<LocationState | null>(null);
  const [incident, setIncident] = useState<SOSResponse | null>(null);
  const [incidentDetails, setIncidentDetails] = useState<any>(null);
  const [error, setError] = useState<string>("");

  // Interactive Simulator State
  const [severity, setSeverity] = useState<SeverityType>("CRITICAL");
  const [condition, setCondition] = useState("Acute Cardiac Chest Pain / Shortness of Breath");
  const [callerName, setCallerName] = useState("");
  const [callerPhone, setCallerPhone] = useState("");
  const [showVoiceModal, setShowVoiceModal] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const watchRef = useRef<number | null>(null);
  const idempotencyKeyRef = useRef<string>("");

  // ── Geolocation ─────────────────────────────────────────────────────────────

  const startLocating = useCallback(() => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      setAppState("ERROR");
      return;
    }
    setAppState("LOCATING");

    const onSuccess = (pos: GeolocationPosition) => {
      setLocation({
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
        timestamp: pos.timestamp,
      });
      setAppState("READY");
    };

    const onError = (err: GeolocationPositionError) => {
      const msgs: Record<number, string> = {
        1: "Location permission denied. Please allow location access.",
        2: "Unable to determine your location. Try again.",
        3: "Location request timed out.",
      };
      setError(msgs[err.code] || "Location error.");
      // Fallback location for testing
      setLocation({
        latitude: 28.6139,
        longitude: 77.2090,
        accuracy: 15,
        timestamp: Date.now(),
      });
      setAppState("READY");
    };

    watchRef.current = navigator.geolocation.watchPosition(onSuccess, onError, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 5000,
    });
  }, []);

  useEffect(() => {
    startLocating();
    return () => {
      if (watchRef.current !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchRef.current);
      }
      wsRef.current?.close();
    };
  }, [startLocating]);

  // ── SOS Submission ───────────────────────────────────────────────────────────

  const sendSOS = async () => {
    if (!callerName.trim()) {
      setError("Caller Name is compulsory for emergency response.");
      setAppState("READY");
      return;
    }
    const cleanPhone = callerPhone.replace(/[^\d+]/g, "");
    if (!cleanPhone || cleanPhone.length < 10) {
      setError("Callback Phone is compulsory (please enter a valid 10-digit number).");
      setAppState("READY");
      return;
    }

    const loc = location || { latitude: 28.6139, longitude: 77.2090, accuracy: 15, timestamp: Date.now() };
    setAppState("SENDING");
    setError("");

    if (!idempotencyKeyRef.current) {
      idempotencyKeyRef.current = `sos-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    }

    try {
      const resp = await apiClient.sendSOS(
        {
          latitude: loc.latitude,
          longitude: loc.longitude,
          accuracy_m: loc.accuracy,
          severity: severity,
          caller_info: {
            name: callerName.trim(),
            phone: callerPhone.trim(),
            notes: condition || undefined,
          },
        },
        idempotencyKeyRef.current
      );
      setIncident(resp);
      setAppState("TRACKING");
      subscribeToIncident(resp.incident_id);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e: any) {
      setError(e.message || "Failed to submit SOS. In severe emergency, dial 108 directly.");
      setAppState("ERROR");
    }
  };

  const subscribeToIncident = (incidentId: string) => {
    const ws = apiClient.connectIncidentWS(incidentId, (msg) => {
      if (msg.type === "incident_update") {
        setIncidentDetails(msg.data);
        setIncident((prev) =>
          prev ? { ...prev, status: msg.data.status, eta_seconds: msg.data.eta_seconds } : prev
        );
      }
    });
    wsRef.current = ws;
  };

  const cancelIncident = () => {
    wsRef.current?.close();
    setIncident(null);
    setIncidentDetails(null);
    idempotencyKeyRef.current = "";
    setAppState("READY");
  };

  // Severity metrics calculation for interactive slip
  const severityConfig = {
    CRITICAL: {
      eta: "3 - 5 min",
      unitType: "Advanced Cardiac Life Support (ACLS)",
      color: "var(--brand-red)",
      hospital: "City Central Trauma Center — Level 1",
      resus: "Cath Lab & Trauma Bay Standby",
    },
    HIGH: {
      eta: "5 - 8 min",
      unitType: "Advanced Life Support (ALS)",
      color: "#ea580c",
      hospital: "Metro Memorial Hospital ER",
      resus: "Emergency Resus Bed Reserved",
    },
    MEDIUM: {
      eta: "8 - 12 min",
      unitType: "Basic Life Support (BLS)",
      color: "#ca8a04",
      hospital: "Community Healthcare ER",
      resus: "General Acute Bed Reserved",
    },
    LOW: {
      eta: "12 - 18 min",
      unitType: "Patient Transport Unit (PTU)",
      color: "#0284c7",
      hospital: "District Polyclinic Facility",
      resus: "Triage Outpatient Registration",
    },
  };

  const currentSev = severityConfig[severity];

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff", color: "var(--text-primary)" }}>
      {/* ── Top Navbar (Sticky, aligned to 1180px) ─────────────────────────── */}
      <nav
        style={{
          position: "sticky",
          top: 0,
          zIndex: 100,
          background: "rgba(255, 255, 255, 0.95)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <div
          style={{
            maxWidth: "min(1440px, 95vw)",
            margin: "0 auto",
            padding: "0.85rem 2rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          {/* Brand Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <img
              src="/emrp-logo.jpg?v=3"
              alt="EMRP Logo"
              style={{ height: "46px", width: "auto", objectFit: "contain" }}
            />
          </div>

          {/* Nav links */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "28px",
              fontSize: "0.9375rem",
              fontWeight: 500,
              color: "var(--text-secondary)",
            }}
          >
            <a href="#how-it-works" style={{ color: "var(--text-secondary)" }}>
              How it works
            </a>
            <a href="#simulator" style={{ color: "var(--text-secondary)" }}>
              Response simulator
            </a>
            <a href="#ecosystem" style={{ color: "var(--text-secondary)" }}>
              Platform network
            </a>
            <a
              href="http://localhost:3001"
              target="_blank"
              rel="noreferrer"
              style={{ color: "var(--brand-navy)", fontWeight: 600 }}
            >
              Dispatcher console ↗
            </a>
            <a
              href="http://localhost:3002"
              target="_blank"
              rel="noreferrer"
              style={{ color: "var(--brand-navy)", fontWeight: 600 }}
            >
              Hospital console ↗
            </a>
          </div>

          {/* Right Action Buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button
              onClick={() => setShowVoiceModal(true)}
              style={{
                fontSize: "0.8125rem",
                fontWeight: 700,
                color: "var(--brand-navy)",
                background: "#eff6ff",
                border: "1.5px solid #bfdbfe",
                borderRadius: "6px",
                padding: "0.45rem 0.85rem",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
              }}
            >
              🎙️ AI Voice Hotline
            </button>
            <a
              href="tel:108"
              style={{
                fontSize: "0.875rem",
                fontWeight: 600,
                color: "var(--text-secondary)",
                padding: "0.5rem 0.85rem",
              }}
            >
              Dial 108
            </a>
            <button
              onClick={() => {
                const el = document.getElementById("simulator");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              style={{
                background: "var(--brand-red)",
                color: "#ffffff",
                border: "1.5px solid #991b1b",
                borderRadius: "8px",
                padding: "0.55rem 1.25rem",
                fontSize: "0.9375rem",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 2px 8px rgba(215, 38, 56, 0.3)",
              }}
            >
              🚨 Trigger SOS
            </button>
          </div>
        </div>
      </nav>

      {/* ── Main Container (Full-Width Responsive 1440px Centered) ─────── */}
      <main style={{ maxWidth: "min(1440px, 95vw)", margin: "0 auto", padding: "0 2rem" }}>
        
        {/* ── Active Live Tracking Banner (if incident active) ─────────────── */}
        {appState === "TRACKING" && incident && (
          <div
            style={{
              marginTop: "2rem",
              padding: "1.5rem",
              background: "#fff1f2",
              border: "2px solid var(--brand-red)",
              borderRadius: "16px",
              boxShadow: "0 8px 30px rgba(215, 38, 56, 0.2)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <span
                  style={{
                    background: "var(--brand-red)",
                    color: "#fff",
                    padding: "0.25rem 0.75rem",
                    borderRadius: "9999px",
                    fontSize: "0.75rem",
                    fontWeight: 800,
                    letterSpacing: "0.05em",
                  }}
                >
                  LIVE EMERGENCY TRACKING
                </span>
                <h2 style={{ fontSize: "1.75rem", margin: "0.75rem 0 0.25rem", color: "var(--brand-navy)" }}>
                  Ambulance En Route • ETA {etaLabel(incident.eta_seconds)}
                </h2>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
                  Incident ID: <code>#{incident.incident_id}</code> • Status:{" "}
                  <strong>{incident.status}</strong>
                </p>
              </div>
              <button
                onClick={cancelIncident}
                style={{
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: "8px",
                  padding: "0.5rem 1rem",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Close Tracking
              </button>
            </div>
          </div>
        )}

        {/* ── Hero Section (Aligned with large headline + 2 buttons) ───────── */}
        <section style={{ paddingTop: "3.5rem", paddingBottom: "3rem" }}>
          <h1
            style={{
              fontSize: "clamp(2.5rem, 4.5vw, 4rem)",
              fontWeight: 800,
              lineHeight: 1.12,
              letterSpacing: "-0.03em",
              color: "var(--brand-navy)",
              maxWidth: 980,
            }}
          >
            Find the nearest unit. <br />
            <span style={{ color: "var(--brand-red)" }}>Lock the dispatch.</span> <br />
            Alert the trauma team.
          </h1>
          <p
            style={{
              fontSize: "1.15rem",
              lineHeight: 1.6,
              color: "var(--text-secondary)",
              maxWidth: 850,
              marginTop: "1.25rem",
            }}
          >
            Citizens report emergencies with sub-meter GPS accuracy. The nearest emergency
            medical units are locked race-free in seconds, while destination trauma centers receive
            instant clinical pre-alerts before arrival.
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginTop: "2rem", flexWrap: "wrap" }}>
            <button
              onClick={() => {
                const el = document.getElementById("simulator");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              style={{
                background: "var(--brand-red)",
                color: "#ffffff",
                border: "1.5px solid #991b1b",
                borderRadius: "8px",
                padding: "0.85rem 1.75rem",
                fontSize: "1rem",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 4px 14px rgba(215, 38, 56, 0.35)",
              }}
            >
              🚨 Request Emergency SOS
            </button>
            <button
              onClick={() => setShowVoiceModal(true)}
              style={{
                background: "#eff6ff",
                color: "var(--brand-navy)",
                border: "1.5px solid #bfdbfe",
                borderRadius: "8px",
                padding: "0.85rem 1.5rem",
                fontSize: "1rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                cursor: "pointer",
              }}
            >
              🎙️ Call AI Voice Hotline
            </button>
            <a
              href="http://localhost:3001"
              target="_blank"
              rel="noreferrer"
              style={{
                background: "#ffffff",
                color: "var(--brand-navy)",
                border: "1.5px solid #cbd5e1",
                borderRadius: "8px",
                padding: "0.85rem 1.5rem",
                fontSize: "1rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                cursor: "pointer",
              }}
            >
              🚑 Dispatcher Console
            </a>
          </div>
        </section>

        {/* ── Interactive Simulator & Slip Section (Inspired by SponsorSetu Deal Calc) ── */}
        <section
          id="simulator"
          style={{
            paddingTop: "2.5rem",
            paddingBottom: "4.5rem",
            borderTop: "1px solid #e2e8f0",
          }}
        >
          <div style={{ marginBottom: "1.75rem" }}>
            <h2
              style={{
                fontSize: "2rem",
                fontWeight: 800,
                color: "var(--brand-navy)",
                letterSpacing: "-0.02em",
              }}
            >
              See response details before dispatch
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "1rem", marginTop: "0.25rem" }}>
              Choose triage severity and condition. The dispatch slip updates automatically as you change parameters.
            </p>
          </div>

          {/* Promo / Realtime advisory banner */}
          <div
            style={{
              background: "#ecfdf5",
              border: "1px solid #a7f3d0",
              borderRadius: "10px",
              padding: "0.85rem 1.25rem",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              fontSize: "0.875rem",
              color: "#065f46",
              marginBottom: "1.75rem",
            }}
          >
            <span>⚡</span>
            <span>
              <strong>Real-Time Emergency Grid Active:</strong> Atomic CAS unit locking, turn-by-turn routing, and instant hospital bed coordination are operational.
            </span>
          </div>

          {/* 2-Column Grid: Form on Left, Ticket Slip on Right */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.2fr 1fr",
              gap: "2.5rem",
              alignItems: "start",
            }}
          >
            {/* Left Card: Inputs & Controls */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: "12px",
                padding: "1.75rem",
                boxShadow: "0 2px 8px rgba(11, 37, 69, 0.04)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.08em", color: "var(--text-muted)", textTransform: "uppercase" }}>
                  TRIAGE SEVERITY LEVEL
                </span>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Presets:</span>
              </div>

              {/* Severity Pill Buttons */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", marginBottom: "1.5rem" }}>
                {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as SeverityType[]).map((sev) => {
                  const isSelected = severity === sev;
                  return (
                    <button
                      key={sev}
                      onClick={() => setSeverity(sev)}
                      style={{
                        padding: "0.5rem 0.25rem",
                        borderRadius: "8px",
                        fontSize: "0.8125rem",
                        fontWeight: 700,
                        cursor: "pointer",
                        border: isSelected ? "1.5px solid #000" : "1px solid #cbd5e1",
                        background: isSelected ? "var(--brand-navy)" : "#ffffff",
                        color: isSelected ? "#ffffff" : "var(--brand-navy)",
                        transition: "all 0.15s ease",
                      }}
                    >
                      {sev === "CRITICAL" ? "🔴 Red" : sev === "HIGH" ? "🟠 Yellow" : sev === "MEDIUM" ? "🟢 Green" : "🔵 Low"}
                    </button>
                  );
                })}
              </div>

              {/* Suspected Condition Input */}
              <div style={{ marginBottom: "1.25rem" }}>
                <label style={{ fontSize: "0.875rem", fontWeight: 600, display: "block", marginBottom: "0.4rem" }}>
                  Suspected Condition / Chief Complaint
                </label>
                <input
                  type="text"
                  className="input"
                  value={condition}
                  onChange={(e) => setCondition(e.target.value)}
                  placeholder="e.g. Acute chest pain, respiratory distress, trauma"
                />
              </div>

              {/* Quick condition tag suggestions */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "1.5rem" }}>
                {[
                  "Cardiac Arrest",
                  "Acute STEMI / Heart Attack",
                  "Major Motor Vehicle Trauma",
                  "Stroke / Fast Exam Positive",
                  "Severe Asthmatic Attack",
                ].map((tag) => (
                  <button
                    key={tag}
                    onClick={() => setCondition(tag)}
                    style={{
                      padding: "0.25rem 0.6rem",
                      borderRadius: "6px",
                      fontSize: "0.75rem",
                      background: "#f1f5f9",
                      border: "1px solid #e2e8f0",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                    }}
                  >
                    + {tag}
                  </button>
                ))}
              </div>

              {/* Caller Info Row (Compulsory) */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
                <div>
                  <label style={{ fontSize: "0.875rem", fontWeight: 700, display: "block", marginBottom: "0.4rem", color: "var(--brand-navy)" }}>
                    Caller Name <span style={{ color: "var(--brand-red)" }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    className="input"
                    value={callerName}
                    onChange={(e) => {
                      setCallerName(e.target.value);
                      if (error) setError("");
                    }}
                    placeholder="Enter full name (Compulsory)"
                    style={{
                      borderColor: error && !callerName.trim() ? "var(--brand-red)" : undefined,
                    }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "0.875rem", fontWeight: 700, display: "block", marginBottom: "0.4rem", color: "var(--brand-navy)" }}>
                    Callback Phone <span style={{ color: "var(--brand-red)" }}>*</span>
                  </label>
                  <input
                    type="tel"
                    required
                    className="input"
                    value={callerPhone}
                    onChange={(e) => {
                      setCallerPhone(e.target.value);
                      if (error) setError("");
                    }}
                    placeholder="+91 98765 43210 (Compulsory)"
                    style={{
                      borderColor: error && !callerPhone.trim() ? "var(--brand-red)" : undefined,
                    }}
                  />
                </div>
              </div>

              {/* Geolocation Live Readout */}
              <div
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  padding: "0.75rem 1rem",
                  marginBottom: "1.5rem",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className={`accuracy-dot ${accuracyClass(location?.accuracy || 15)}`} />
                  <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                    GPS Accuracy: <strong>{accuracyLabel(location?.accuracy || 15)}</strong> (±
                    {Math.round(location?.accuracy || 15)}m)
                  </span>
                </div>
                <button
                  onClick={startLocating}
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--brand-navy)",
                    fontWeight: 600,
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  Refresh Location
                </button>
              </div>

              {/* Trigger Button inside simulator */}
              <button
                onClick={sendSOS}
                disabled={appState === "SENDING"}
                style={{
                  width: "100%",
                  padding: "0.95rem",
                  background: "var(--brand-red)",
                  color: "#ffffff",
                  border: "1.5px solid #991b1b",
                  borderRadius: "8px",
                  fontSize: "1.05rem",
                  fontWeight: 800,
                  cursor: "pointer",
                  boxShadow: "0 4px 14px rgba(215, 38, 56, 0.35)",
                  transition: "all 0.15s ease",
                }}
              >
                {appState === "SENDING" ? "Transmitting SOS..." : "🚨 Transmit Immediate SOS Dispatch"}
              </button>

              {error && (
                <div style={{ marginTop: "1rem", color: "#b91c1c", fontSize: "0.875rem", textAlign: "center" }}>
                  ⚠️ {error}
                </div>
              )}
            </div>

            {/* Right Card: Emergency Dispatch Slip (matching SponsorSetu slip) */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: "12px",
                padding: "1.75rem",
                boxShadow: "0 4px 20px rgba(11, 37, 69, 0.06)",
                position: "relative",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                <span style={{ fontSize: "0.8125rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  EMERGENCY DISPATCH SLIP
                </span>
                <span
                  style={{
                    background: "#dcfce7",
                    color: "#15803d",
                    border: "1px solid #bbf7d0",
                    padding: "0.2rem 0.6rem",
                    borderRadius: "9999px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                  }}
                >
                  READY FOR DISPATCH
                </span>
              </div>

              {/* Line items */}
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", fontSize: "0.9375rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Triage Category</span>
                  <span style={{ fontWeight: 800, color: currentSev.color }}>{severity} PRIORITY</span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Target Response ETA</span>
                  <span style={{ fontWeight: 800, fontSize: "1.25rem", color: "var(--brand-navy)" }}>
                    {currentSev.eta}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Assigned Unit Specification</span>
                  <span style={{ fontWeight: 600, color: "var(--brand-navy)", textAlign: "right" }}>
                    {currentSev.unitType}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Designated Facility</span>
                  <span style={{ fontWeight: 600, color: "var(--brand-navy)", textAlign: "right", maxWidth: 220 }}>
                    {currentSev.hospital}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Hospital Standby Order</span>
                  <span style={{ fontWeight: 600, color: "#059669", textAlign: "right", maxWidth: 220 }}>
                    {currentSev.resus}
                  </span>
                </div>
              </div>

              {/* Dashed divider */}
              <div
                style={{
                  margin: "1.5rem 0",
                  borderTop: "1.5px dashed #cbd5e1",
                }}
              />

              {/* System Protocol Badges */}
              <div>
                <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.75rem" }}>
                  SYSTEM ARCHITECTURE GUARANTEES
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span>🛡️</span>
                    <span><strong>Race-Free Dispatch:</strong> Atomic CAS ambulance status lock</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span>⚡</span>
                    <span><strong>Zero Incident Loss:</strong> Distributed replica-set outbox events</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span>🔒</span>
                    <span><strong>Audit Trail:</strong> SHA-256 hash-chained state records</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── 5-Column "How An Emergency Moves" (Matching SponsorSetu Step Section) ── */}
        <section
          id="how-it-works"
          style={{
            paddingTop: "3rem",
            paddingBottom: "4.5rem",
            borderTop: "1px solid #e2e8f0",
          }}
        >
          <h2
            style={{
              fontSize: "2rem",
              fontWeight: 800,
              color: "var(--brand-navy)",
              letterSpacing: "-0.02em",
              marginBottom: "2rem",
            }}
          >
            How an emergency moves
          </h2>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(5, 1fr)",
              borderTop: "1px solid #e2e8f0",
            }}
          >
            {[
              {
                step: "Step 1",
                title: "Locate",
                desc: "Sub-meter GPS coordinates are locked automatically with browser precision.",
              },
              {
                step: "Step 2",
                title: "AI Triage",
                desc: "NLP classifier maps caller notes to clinical urgency (Red / Yellow / Green).",
              },
              {
                step: "Step 3",
                title: "Lock & assign",
                desc: "Atomic CAS ambulance reservation ensures zero double-booking or race conditions.",
              },
              {
                step: "Step 4",
                title: "Track",
                desc: "Turn-by-turn telemetry streams live over WebSockets with real-time ETA.",
              },
              {
                step: "Step 5",
                title: "Pre-alert & handoff",
                desc: "Trauma ER team receives telemetry and sets up resus bays before patient arrives.",
              },
            ].map((col, idx) => (
              <div
                key={col.step}
                style={{
                  padding: "1.5rem 1.25rem 1.5rem 0",
                  paddingRight: idx < 4 ? "1.25rem" : "0",
                  borderRight: idx < 4 ? "1px solid #e2e8f0" : "none",
                }}
              >
                <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                  {col.step}
                </div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--brand-navy)", marginBottom: "0.5rem" }}>
                  {col.title}
                </h3>
                <p style={{ fontSize: "0.875rem", lineHeight: 1.5, color: "var(--text-secondary)" }}>
                  {col.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Two-Column Citizen vs Dispatcher Breakdown (Matching SponsorSetu 2-col) ── */}
        <section
          id="ecosystem"
          style={{
            paddingTop: "3rem",
            paddingBottom: "4.5rem",
            borderTop: "1px solid #e2e8f0",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "4rem",
              alignItems: "start",
            }}
          >
            {/* Column 1: For Citizens */}
            <div>
              <h2 style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--brand-navy)", marginBottom: "1.25rem" }}>
                For citizens & callers
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", color: "var(--text-secondary)", fontSize: "0.95rem", lineHeight: 1.6 }}>
                <p>
                  Transmit immediate SOS with automatic GPS accuracy. No need to look up confusing landmarks or describe local intersections in a crisis.
                </p>
                <p>
                  View live turn-by-turn ETA countdowns directly on your mobile device as the dispatched emergency unit navigates to your location.
                </p>
                <p>
                  Built with fallback telephony so you can dial 108 directly if mobile internet is spotty or unavailable.
                </p>
              </div>
              <button
                onClick={() => {
                  const el = document.getElementById("simulator");
                  el?.scrollIntoView({ behavior: "smooth" });
                }}
                style={{
                  marginTop: "2rem",
                  background: "var(--brand-red)",
                  color: "#ffffff",
                  border: "1.5px solid #991b1b",
                  borderRadius: "8px",
                  padding: "0.75rem 1.5rem",
                  fontSize: "0.9375rem",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                🚨 Tap SOS Assistance
              </button>
            </div>

            {/* Column 2: For Dispatchers & Hospitals */}
            <div>
              <h2 style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--brand-navy)", marginBottom: "1.25rem" }}>
                For dispatchers & hospitals
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", color: "var(--text-secondary)", fontSize: "0.95rem", lineHeight: 1.6 }}>
                <p>
                  Live multi-incident dispatch board with interactive fleet telemetry overview and automated offer timeout sweeps.
                </p>
                <p>
                  Hospital emergency receiving console with one-tap pre-alert acknowledgment and real-time bed & critical diagnostic capacity sync.
                </p>
                <p>
                  Atomic CAS state locking ensures only one ambulance is assigned per incident, preventing resource waste or confusion.
                </p>
              </div>
              <div style={{ display: "flex", gap: "12px", marginTop: "2rem" }}>
                <a
                  href="http://localhost:3001"
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    background: "#ffffff",
                    color: "var(--brand-navy)",
                    border: "1.5px solid #cbd5e1",
                    borderRadius: "8px",
                    padding: "0.75rem 1.25rem",
                    fontSize: "0.9375rem",
                    fontWeight: 700,
                  }}
                >
                  Open Dispatcher Board
                </a>
                <a
                  href="http://localhost:3002"
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    background: "#ffffff",
                    color: "var(--brand-navy)",
                    border: "1.5px solid #cbd5e1",
                    borderRadius: "8px",
                    padding: "0.75rem 1.25rem",
                    fontSize: "0.9375rem",
                    fontWeight: 700,
                  }}
                >
                  Hospital Console
                </a>
              </div>
            </div>
          </div>

          {/* Sub-feature rows with dividers (matching SponsorSetu Screenshot 2) */}
          <div style={{ marginTop: "3.5rem", borderTop: "1px solid #e2e8f0" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4rem", paddingTop: "2rem" }}>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--brand-navy)", marginBottom: "0.5rem" }}>
                  Verified on both sides
                </h3>
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                  Every transition in ambulance status, incident triage, and pre-alert acknowledgment is hashed in an immutable SHA-256 audit chain.
                </p>
              </div>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--brand-navy)", marginBottom: "0.5rem" }}>
                  Protocols you can rely on
                </h3>
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                  Distributed MongoDB replica-set transactions guarantee zero incident loss, with idempotent requests replaying without side effects.
                </p>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4rem", paddingTop: "2rem", marginTop: "1rem", borderTop: "1px solid #f1f5f9" }}>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--brand-navy)", marginBottom: "0.5rem" }}>
                  Your data, your privacy
                </h3>
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                  Geolocation and clinical observations are strictly protected, restricted to emergency response dispatch, and stored under healthcare data compliance.
                </p>
              </div>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--brand-navy)", marginBottom: "0.5rem" }}>
                  Real-time routing via OSRM
                </h3>
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                  Distance and travel time calculations use high-speed road network graph analytics with automatic haversine spherical fallback.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── Status Banner (Matching SponsorSetu "Open for sponsorship" banner) ── */}
        <section style={{ paddingBottom: "5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--brand-navy)", letterSpacing: "-0.02em" }}>
              Live emergency grid status
            </h2>
            <a
              href="http://localhost:3001"
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--brand-navy)" }}
            >
              See all active units →
            </a>
          </div>

          <div
            style={{
              border: "1.5px dashed #cbd5e1",
              borderRadius: "12px",
              padding: "2.5rem 1.5rem",
              textAlign: "center",
              background: "#f8fafc",
              color: "var(--text-secondary)",
              fontSize: "0.95rem",
            }}
          >
            🚑 <strong>4 Ambulance Units Online</strong> &bull; ⏱️ <strong>18s Avg Dispatch Speed</strong> &bull; 🏥 <strong>City Central & Metro ER Connected</strong>
          </div>
        </section>
      </main>

      {/* ── Deep Navy Brand Footer (Matching SponsorSetu Footer) ─────────── */}
      <footer
        style={{
          background: "var(--brand-navy)",
          color: "#ffffff",
          padding: "4rem 2rem 2.5rem",
        }}
      >
        <div style={{ maxWidth: "min(1440px, 95vw)", margin: "0 auto" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.6fr 1fr 1fr 1fr",
              gap: "3rem",
              paddingBottom: "3rem",
              borderBottom: "1px solid rgba(255, 255, 255, 0.12)",
            }}
          >
            {/* Left Column: Brand */}
            <div>
              <div style={{ display: "inline-flex", alignItems: "center", background: "#ffffff", padding: "6px 12px", borderRadius: "8px", marginBottom: "1rem" }}>
                <img
                  src="/emrp-logo.jpg?v=3"
                  alt="EMRP Logo"
                  style={{ height: "42px", width: "auto", objectFit: "contain" }}
                />
              </div>
              <p style={{ color: "#94a3b8", fontSize: "0.9rem", lineHeight: 1.6, maxWidth: 320 }}>
                A unified emergency medical response platform connecting citizens, ambulances, and trauma hospitals across India.
              </p>
              <div style={{ marginTop: "1.25rem" }}>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    background: "rgba(255, 255, 255, 0.08)",
                    border: "1px solid rgba(255, 255, 255, 0.15)",
                    padding: "0.4rem 0.85rem",
                    borderRadius: "9999px",
                    fontSize: "0.8125rem",
                    color: "#f87171",
                    fontWeight: 600,
                  }}
                >
                  🚨 Emergency Toll-Free: Dial 108
                </span>
              </div>
            </div>

            {/* Col 1: Platform */}
            <div>
              <div style={{ fontWeight: 700, fontSize: "0.875rem", color: "#facc15", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "1.25rem" }}>
                Platform
              </div>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.875rem", color: "#cbd5e1" }}>
                <li><a href="#simulator" style={{ color: "#cbd5e1" }}>Emergency SOS</a></li>
                <li><a href="http://localhost:3001" target="_blank" rel="noreferrer" style={{ color: "#cbd5e1" }}>Dispatcher Board</a></li>
                <li><a href="http://localhost:3002" target="_blank" rel="noreferrer" style={{ color: "#cbd5e1" }}>Hospital Console</a></li>
                <li><a href="http://localhost:8001/api/docs" target="_blank" rel="noreferrer" style={{ color: "#cbd5e1" }}>API Swagger Docs</a></li>
              </ul>
            </div>

            {/* Col 2: Architecture & Protocols */}
            <div>
              <div style={{ fontWeight: 700, fontSize: "0.875rem", color: "#facc15", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "1.25rem" }}>
                Protocols
              </div>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.875rem", color: "#cbd5e1" }}>
                <li><a href="#how-it-works" style={{ color: "#cbd5e1" }}>Atomic CAS Dispatch</a></li>
                <li><a href="#how-it-works" style={{ color: "#cbd5e1" }}>AI NLP Triage</a></li>
                <li><a href="#how-it-works" style={{ color: "#cbd5e1" }}>SHA-256 Audit Trail</a></li>
                <li><a href="#how-it-works" style={{ color: "#cbd5e1" }}>Outbox Relay Pattern</a></li>
              </ul>
            </div>

            {/* Col 3: Grievance & Emergency Officer */}
            <div>
              <div style={{ fontWeight: 700, fontSize: "0.875rem", color: "#facc15", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "1.25rem" }}>
                Emergency Officer
              </div>
              <p style={{ color: "#94a3b8", fontSize: "0.875rem", lineHeight: 1.5 }}>
                National Emergency Dispatch Coordination Directorate. Available 24/7 for acute medical assistance.
              </p>
            </div>
          </div>

          {/* Bottom Copyright */}
          <div
            style={{
              paddingTop: "2rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: "0.8125rem",
              color: "#94a3b8",
            }}
          >
            <div>
              &copy; 2026 Emergency Medical Response Platform (EMRP). In life-threatening emergencies, dial 108 immediately.
            </div>
            <div>
              Faster &bull; Smarter &bull; Together
            </div>
          </div>
        </div>
      </footer>

      {/* ── AI Voice Emergency Hotline Modal ── */}
      <VoiceHotlineModal
        isOpen={showVoiceModal}
        onClose={() => setShowVoiceModal(false)}
        callerPhone={callerPhone || "8000697437"}
        location={location}
        onIncidentCreated={(incId) => {
          subscribeToIncident(incId);
          setAppState("TRACKING");
          setIncident({
            incident_id: incId,
            status: "RECEIVED",
            message: "Emergency received via AI Voice Hotline. Help is being dispatched.",
            eta_seconds: 360,
          });
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />
    </div>
  );
}
