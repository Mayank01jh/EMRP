"use client";
/**
 * Dispatcher Console — Streamlined Mission Operations (Zero Outer Scroll)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import IncidentMap from "../components/IncidentMap";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Incident {
  _id: string;
  status: string;
  severity: string;
  caller_id: string;
  location: { coordinates: [number, number] };
  accuracy_m: number;
  assigned_unit_id: string | null;
  eta_seconds: number | null;
  caller_info?: { name?: string; phone?: string; notes?: string };
  received_at: string;
  updated_at: string;
}

interface AmbulanceUnit {
  _id: string;
  registration: string;
  status: string;
  capabilities: string[];
  location: { coordinates: [number, number] } | null;
  last_seen_at?: string | null;
  active_incident_id: string | null;
}

interface RouteMetricsData {
  scene: { coordinates: [number, number]; accuracy_m: number };
  ambulance: { unit_id: string; registration: string; status: string; coordinates: [number, number] };
  hospital: { name: string; coordinates: [number, number] };
  leg1_ambulance_to_scene: { distance_km: number; eta_seconds: number };
  leg2_scene_to_hospital: { distance_km: number; eta_seconds: number };
  total_mission_eta_seconds: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function severityColor(sev: string): string {
  const map: Record<string, string> = {
    CRITICAL: "#d72638",
    HIGH: "#ea580c",
    MEDIUM: "#ca8a04",
    LOW: "#0284c7",
  };
  return map[sev] || "var(--text-secondary)";
}

function timeAgo(iso?: string | null): string {
  if (!iso) return "Just now";
  const date = new Date(iso);
  if (isNaN(date.getTime())) return "Just now";
  const diff = Math.max(0, (Date.now() - date.getTime()) / 1000);
  if (diff < 20) return "Just now";
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

function statusBadge(status: string) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{status.replace(/_/g, " ")}</span>;
}

// ─── Incident Row (No layout jumping on click) ────────────────────────────────

function IncidentRow({
  incident,
  isSelected,
  onClick,
}: {
  incident: Incident;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <div
      className="card"
      style={{
        padding: "0.75rem 1rem",
        cursor: "pointer",
        borderRadius: "var(--radius-md)",
        boxShadow: isSelected ? "0 0 0 2px var(--brand-navy)" : "0 0 0 1px var(--border)",
        background: isSelected ? "#f8fafc" : "#ffffff",
        transition: "box-shadow 0.12s ease, background 0.12s ease",
      }}
      onClick={onClick}
      id={`incident-row-${incident._id}`}
    >
      <div className="flex justify-between items-center" style={{ marginBottom: "0.35rem" }}>
        <div className="flex items-center gap-2">
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: severityColor(incident.severity),
              flexShrink: 0,
            }}
          />
          <code style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--brand-navy)" }}>
            #{incident._id.slice(-6)}
          </code>
        </div>
        {statusBadge(incident.status)}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.2rem", fontSize: "0.78rem" }}>
        <div><span className="text-muted">Severity</span></div>
        <div style={{ color: severityColor(incident.severity), fontWeight: 700 }}>{incident.severity}</div>

        <div><span className="text-muted">Received</span></div>
        <div>{timeAgo(incident.received_at)}</div>

        {incident.eta_seconds && (
          <>
            <div><span className="text-muted">ETA to Scene</span></div>
            <div style={{ color: "#16a34a", fontWeight: 700 }}>
              ⏱ {Math.round(incident.eta_seconds / 60)}m
            </div>
          </>
        )}

        {incident.assigned_unit_id && (
          <>
            <div><span className="text-muted">Unit</span></div>
            <div style={{ fontWeight: 600 }}>{incident.assigned_unit_id.slice(-6)}</div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Unit Card ────────────────────────────────────────────────────────────────

function UnitCard({
  unit,
  selectedIncident,
  onAssign,
  isAssigning,
}: {
  unit: AmbulanceUnit;
  selectedIncident: Incident | null;
  onAssign: (unitId: string) => void;
  isAssigning: boolean;
}) {
  const isAvailable = unit.status === "AVAILABLE";
  const needsAssignment = selectedIncident && !selectedIncident.assigned_unit_id;

  return (
    <div
      className="card"
      style={{
        padding: "0.75rem 0.85rem",
        borderRadius: "var(--radius-md)",
        background: isAvailable ? "#ffffff" : "#f8fafc",
      }}
      id={`unit-card-${unit._id}`}
    >
      <div className="flex justify-between items-center mb-1">
        <span style={{ fontWeight: 700, fontSize: "0.85rem" }}>🚑 {unit.registration}</span>
        {statusBadge(unit.status)}
      </div>

      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
        {unit.capabilities.join(" · ")}
      </div>

      {unit.location && (
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
          📍 {unit.location.coordinates[1].toFixed(4)}, {unit.location.coordinates[0].toFixed(4)}
        </div>
      )}

      <div style={{ fontSize: "0.7rem", color: "#16a34a", fontWeight: 600, marginTop: "0.15rem" }}>
        ● Online · {timeAgo(unit.last_seen_at)}
      </div>

      {/* Only show assign button if selected incident does NOT already have an assigned unit */}
      {needsAssignment && isAvailable && (
        <button
          onClick={() => onAssign(unit._id)}
          disabled={isAssigning}
          style={{
            marginTop: "0.5rem",
            width: "100%",
            background: "#16a34a",
            color: "#ffffff",
            border: "none",
            borderRadius: "6px",
            padding: "0.35rem 0.5rem",
            fontSize: "0.72rem",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          {isAssigning ? "Assigning..." : `⚡ Assign to #${selectedIncident._id.slice(-6)}`}
        </button>
      )}
    </div>
  );
}

// ─── Main Dispatcher Page ─────────────────────────────────────────────────────

export default function DispatcherPage() {
  const [authed, setAuthed] = useState(true);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [fleet, setFleet] = useState<AmbulanceUnit[]>([]);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [routeMetrics, setRouteMetrics] = useState<RouteMetricsData | null>(null);
  const [isAssigning, setIsAssigning] = useState(false);
  const [showReassign, setShowReassign] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [inc, fl] = await Promise.all([apiClient.listActiveIncidents(), apiClient.listFleet()]);
      setIncidents(inc);
      setFleet(fl);

      if (selected) {
        const fresh = inc.find((i: Incident) => i._id === selected._id);
        if (fresh && (fresh.status !== selected.status || fresh.assigned_unit_id !== selected.assigned_unit_id)) {
          setSelected(fresh);
        }
      } else if (inc.length > 0) {
        setSelected(inc[0]);
      }
    } catch (e) {
      console.error(e);
    }
  }, [selected]);

  const fetchRouteMetrics = useCallback(async (incId: string) => {
    try {
      const metrics = await apiClient.getRouteMetrics(incId);
      setRouteMetrics(metrics);
    } catch (e) {
      console.error("Failed to load route metrics", e);
    }
  }, []);

  useEffect(() => {
    if (selected) {
      fetchRouteMetrics(selected._id);
      setShowReassign(false);
    } else {
      setRouteMetrics(null);
    }
  }, [selected?._id, fetchRouteMetrics]);

  const connectWS = useCallback(() => {
    const ws = apiClient.connectDispatcherWS((msg) => {
      if (msg.type === "incident_update" || msg.type === "fleet_update") {
        fetchData();
      }
    });
    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    wsRef.current = ws;
  }, [fetchData]);

  useEffect(() => {
    fetchData();
    connectWS();
    const interval = setInterval(fetchData, 10000);
    return () => {
      wsRef.current?.close();
      clearInterval(interval);
    };
  }, [fetchData, connectWS]);

  // Status transitions
  const NEXT_STEPS: Record<string, string[]> = {
    RECEIVED: ["QUEUED", "CANCELLED"],
    VALIDATING: ["QUEUED", "CANCELLED"],
    QUEUED: ["ASSIGNED", "CANCELLED"],
    ASSIGNED: ["EN_ROUTE", "CANCELLED"],
    EN_ROUTE: ["ON_SCENE", "CANCELLED"],
    ON_SCENE: ["TRANSPORTING", "CLOSED"],
    TRANSPORTING: ["HANDED_OVER"],
    HANDED_OVER: ["CLOSED"],
  };

  const handleStatusTransition = async (targetStatus: string) => {
    if (!selected) return;
    try {
      const updated = await apiClient.updateIncidentStatus(selected._id, targetStatus);
      setSelected({ ...selected, ...updated });
      setIncidents((prev) =>
        prev.map((i) => (i._id === selected._id ? { ...i, ...updated } : i))
      );
      fetchRouteMetrics(selected._id);
    } catch (err: any) {
      alert("Status change error: " + (err.message || err));
    }
  };

  const handleAssignAmbulance = async (unitId: string) => {
    if (!selected) return;
    setIsAssigning(true);
    try {
      const updated = await apiClient.assignAmbulance(selected._id, unitId);
      setSelected(updated);
      setShowReassign(false);
      await fetchData();
      await fetchRouteMetrics(selected._id);
    } catch (err: any) {
      alert("Failed to assign ambulance: " + (err.message || err));
    } finally {
      setIsAssigning(false);
    }
  };

  const handleAutoAssign = async () => {
    if (!selected) return;
    setIsAssigning(true);
    try {
      const updated = await apiClient.autoAssignAmbulance(selected._id);
      setSelected(updated);
      setShowReassign(false);
      await fetchData();
      await fetchRouteMetrics(selected._id);
    } catch (err: any) {
      alert("Auto-dispatch error: " + (err.message || err));
    } finally {
      setIsAssigning(false);
    }
  };

  const stats = {
    active: incidents.filter((i) => !["CLOSED", "CANCELLED", "DUPLICATE_LINKED"].includes(i.status)).length,
    queued: incidents.filter((i) => ["RECEIVED", "VALIDATING", "QUEUED"].includes(i.status)).length,
    available: fleet.filter((u) => u.status === "AVAILABLE").length,
    total: fleet.length,
  };

  return (
    <main
      style={{
        height: "100vh",
        maxHeight: "100vh",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        background: "var(--bg-900)",
      }}
    >
      {/* ── Top Header (Compact 50px Height) ─────────────────────────────────── */}
      <header
        style={{
          flexShrink: 0,
          height: "50px",
          background: "#ffffff",
          borderBottom: "1px solid var(--border)",
          padding: "0 1.25rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxShadow: "var(--shadow-sm)",
          zIndex: 10,
        }}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <img
              src="/emrp-logo.jpg?v=3"
              alt="EMRP Logo"
              style={{ height: "30px", width: "auto", objectFit: "contain" }}
            />
            <span style={{ fontWeight: 800, fontSize: "0.95rem", color: "var(--brand-navy)" }}>
              EMRP Dispatch Console
            </span>
          </div>

          <div
            className="flex items-center gap-1.5"
            style={{
              background: wsConnected ? "#dcfce7" : "#fee2e2",
              padding: "0.15rem 0.5rem",
              borderRadius: "999px",
              border: `1px solid ${wsConnected ? "#bbf7d0" : "#fecaca"}`,
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: wsConnected ? "var(--green-500)" : "var(--red-500)",
              }}
            />
            <span
              className="text-xs"
              style={{ fontWeight: 600, color: wsConnected ? "var(--green-600)" : "var(--red-600)" }}
            >
              {wsConnected ? "Telemetry Connected" : "Connecting..."}
            </span>
          </div>
        </div>

        {/* Compact Metrics in Header */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: "0.8rem" }}>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Active Incidents: </span>
            <strong style={{ color: "var(--blue-400)" }}>{stats.active}</strong>
          </div>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Pending Queue: </span>
            <strong style={{ color: stats.queued > 0 ? "#ea580c" : "var(--text-primary)" }}>{stats.queued}</strong>
          </div>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Available Units: </span>
            <strong style={{ color: "var(--green-400)" }}>{stats.available}</strong>
          </div>
        </div>
      </header>

      {/* ── 3-Column Workspace (Fills exact remaining viewport without scroll) ─ */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: "grid",
          gridTemplateColumns: "310px 1fr 310px",
          overflow: "hidden",
        }}
      >
        {/* Column 1: Active Emergency Queue */}
        <div
          style={{
            height: "100%",
            overflowY: "auto",
            borderRight: "1px solid var(--border)",
            padding: "0.85rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
            <h3
              style={{
                fontSize: "0.8125rem",
                color: "var(--brand-navy)",
                fontWeight: 800,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              Emergency Queue ({incidents.length})
            </h3>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
            {incidents.length === 0 && (
              <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem 1rem", fontSize: "0.8125rem" }}>
                No active emergencies
              </div>
            )}
            {incidents.map((inc) => (
              <IncidentRow
                key={inc._id}
                incident={inc}
                isSelected={selected?._id === inc._id}
                onClick={() => setSelected(inc)}
              />
            ))}
          </div>
        </div>

        {/* Column 2: Selected Incident Center */}
        <div
          style={{
            height: "100%",
            overflowY: "auto",
            padding: "0.85rem 1rem",
            borderRight: "1px solid var(--border)",
          }}
        >
          {selected ? (
            <div>
              {/* Header */}
              <div className="flex justify-between items-center mb-2.5">
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--brand-navy)" }}>
                    Incident #{selected._id.slice(-6)}
                  </h2>
                  {statusBadge(selected.status)}
                </div>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setSelected(null)}
                  id="close-detail-btn"
                  style={{ fontSize: "0.9rem", cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>

              {/* ── Ambulance Status / Assign Section (Clean & Uncluttered) ── */}
              <div
                className="card mb-2.5"
                style={{
                  borderRadius: "var(--radius-md)",
                  border: "1px solid #bfdbfe",
                  background: "#eff6ff",
                  padding: "0.75rem 0.9rem",
                }}
              >
                {selected.assigned_unit_id && !showReassign ? (
                  /* Unit is ALREADY assigned: Clean status banner without unwanted assign buttons */
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontSize: "1.1rem" }}>🚑</span>
                      <div>
                        <div style={{ fontSize: "0.8125rem", fontWeight: 800, color: "#1e3a8a" }}>
                          Unit Assigned: {routeMetrics?.ambulance.registration || selected.assigned_unit_id.slice(-6)}
                        </div>
                        <div style={{ fontSize: "0.72rem", color: "#166534", fontWeight: 600 }}>
                          ● {selected.status.replace(/_/g, " ")} • Telemetry Active
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowReassign(true)}
                      style={{
                        background: "#ffffff",
                        border: "1px solid #93c5fd",
                        color: "#1e40af",
                        borderRadius: "4px",
                        padding: "0.25rem 0.6rem",
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      Reassign
                    </button>
                  </div>
                ) : (
                  /* Unit is PENDING assignment: Show quick dispatch options */
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <span style={{ fontSize: "0.72rem", fontWeight: 800, color: "#1e40af", textTransform: "uppercase" }}>
                        Ambulance Dispatch
                      </span>
                      {showReassign && (
                        <button
                          onClick={() => setShowReassign(false)}
                          style={{ fontSize: "0.7rem", color: "var(--text-muted)", background: "transparent", border: "none", cursor: "pointer" }}
                        >
                          Cancel Reassign
                        </button>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center" }}>
                      <button
                        onClick={handleAutoAssign}
                        disabled={isAssigning}
                        style={{
                          background: "#2563eb",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "6px",
                          padding: "0.45rem 0.8rem",
                          fontSize: "0.78rem",
                          fontWeight: 700,
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                      >
                        <span>🎯 {isAssigning ? "Dispatching..." : "Auto-Assign Nearest Unit"}</span>
                      </button>

                      {fleet.filter((u) => u.status === "AVAILABLE").map((u) => (
                        <button
                          key={u._id}
                          onClick={() => handleAssignAmbulance(u._id)}
                          disabled={isAssigning}
                          style={{
                            background: "#ffffff",
                            border: "1px solid #93c5fd",
                            color: "#1e3a8a",
                            borderRadius: "6px",
                            padding: "0.4rem 0.65rem",
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          ⚡ Assign {u.registration}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* ── Caller Channel ── */}
              <div
                className="card mb-2.5"
                style={{
                  borderRadius: "var(--radius-md)",
                  border: "1px solid #bbf7d0",
                  background: "#f0fdf4",
                  padding: "0.7rem 0.85rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
                  <span style={{ fontSize: "0.72rem", fontWeight: 800, color: "#166534", textTransform: "uppercase" }}>
                    Caller Contact
                  </span>
                  <a
                    href={`tel:${selected.caller_info?.phone || "108"}`}
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      color: "#16a34a",
                      textDecoration: "none",
                    }}
                  >
                    📞 Call Citizen ({selected.caller_info?.phone || "108"})
                  </a>
                </div>
                <div style={{ fontSize: "0.78rem", color: "#14532d" }}>
                  <strong>{selected.caller_info?.name || "Anonymous Citizen"}</strong>: {selected.caller_info?.notes || "Emergency medical request"}
                </div>
              </div>

              {/* ── Status Progression (Only relevant step) ── */}
              <div className="card mb-2.5" style={{ borderRadius: "var(--radius-md)", padding: "0.6rem 0.85rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                  {(NEXT_STEPS[selected.status] || []).map((step) => (
                    <button
                      key={step}
                      onClick={() => handleStatusTransition(step)}
                      style={{
                        padding: "0.35rem 0.65rem",
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        borderRadius: "5px",
                        cursor: "pointer",
                        border: "1px solid",
                        background: step === "CANCELLED" ? "#fef2f2" : "var(--brand-navy)",
                        color: step === "CANCELLED" ? "#b91c1c" : "#ffffff",
                        borderColor: step === "CANCELLED" ? "#fecaca" : "var(--brand-navy)",
                      }}
                    >
                      {step === "CANCELLED" ? "✕ Cancel" : `→ Advance to ${step.replace(/_/g, " ")}`}
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Zero-Flicker Live Mapbox Mission Map ── */}
              <IncidentMap
                incidentId={selected._id}
                latitude={selected.location.coordinates[1]}
                longitude={selected.location.coordinates[0]}
                accuracy_m={selected.accuracy_m}
                ambulanceCoords={routeMetrics?.ambulance.coordinates}
                ambulanceReg={routeMetrics?.ambulance.registration}
                ambulanceStatus={routeMetrics?.ambulance.status}
                hospitalCoords={routeMetrics?.hospital.coordinates}
                hospitalName={routeMetrics?.hospital.name}
                leg1Metrics={routeMetrics?.leg1_ambulance_to_scene}
                leg2Metrics={routeMetrics?.leg2_scene_to_hospital}
                totalEtaSeconds={routeMetrics?.total_mission_eta_seconds}
              />
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                color: "var(--text-muted)",
              }}
            >
              <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem", opacity: 0.3 }}>🗺️</div>
              <p className="text-sm font-semibold">Select an incident from the queue</p>
            </div>
          )}
        </div>

        {/* Column 3: Ambulance Fleet Panel */}
        <div
          style={{
            height: "100%",
            overflowY: "auto",
            padding: "0.85rem",
          }}
        >
          <h3
            style={{
              marginBottom: "0.6rem",
              fontSize: "0.8125rem",
              color: "var(--text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Ambulance Fleet ({fleet.length})
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
            {fleet.map((unit) => (
              <UnitCard
                key={unit._id}
                unit={unit}
                selectedIncident={selected}
                onAssign={handleAssignAmbulance}
                isAssigning={isAssigning}
              />
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
