/**
 * EMRP API Client — shared across all frontends
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001/api/v1";

export interface SOSRequest {
  latitude: number;
  longitude: number;
  accuracy_m: number;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  caller_info?: { name?: string; phone?: string; notes?: string };
}

export interface SOSResponse {
  incident_id: string;
  status: string;
  message: string;
  eta_seconds: number | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

class EMRPApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("emrp_token", token);
    }
  }

  loadToken() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("emrp_token");
    }
  }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
      ...extra,
    };
    if (this.token) h["Authorization"] = `Bearer ${this.token}`;
    return h;
  }

  async register(username: string, password: string, role = "caller"): Promise<TokenResponse> {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ username, password, role }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async login(username: string, password: string): Promise<TokenResponse> {
    const form = new URLSearchParams({ username, password, grant_type: "password" });
    const res = await fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async sendSOS(request: SOSRequest, idempotencyKey: string): Promise<SOSResponse> {
    const res = await fetch(`${API_BASE}/emergency/sos`, {
      method: "POST",
      headers: this.headers({ "Idempotency-Key": idempotencyKey }),
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async getIncident(incidentId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/emergency/${incidentId}`, {
      headers: this.headers(),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  connectIncidentWS(incidentId: string, onMessage: (data: any) => void): WebSocket {
    const ws = new WebSocket(`${WS_BASE}/emergency/${incidentId}/ws`);
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch {}
    };
    ws.onopen = () => {
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        else clearInterval(ping);
      }, 30000);
    };
    return ws;
  }

  // Fleet
  async listFleet(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/fleet/`, { headers: this.headers() });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async pushTelemetry(unitId: string, lat: number, lon: number, accuracy: number): Promise<void> {
    await fetch(`${API_BASE}/fleet/${unitId}/telemetry`, {
      method: "PATCH",
      headers: this.headers(),
      body: JSON.stringify({ latitude: lat, longitude: lon, accuracy_m: accuracy }),
    });
  }

  // Dispatcher
  async listActiveIncidents(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/dispatcher/incidents`, { headers: this.headers() });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  connectDispatcherWS(onMessage: (data: any) => void): WebSocket {
    const ws = new WebSocket(`${WS_BASE}/dispatcher/ws`);
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch {}
    };
    ws.onopen = () => {
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        else clearInterval(ping);
      }, 30000);
    };
    return ws;
  }

  // Hospitals
  async listHospitals(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/hospitals/`, { headers: this.headers() });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async updateCapacity(hospitalId: string, capacity: any): Promise<void> {
    await fetch(`${API_BASE}/hospitals/${hospitalId}/capacity`, {
      method: "PATCH",
      headers: this.headers(),
      body: JSON.stringify(capacity),
    });
  }

  async acknowledgePreAlert(hospitalId: string, alertId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/hospitals/${hospitalId}/pre-alerts/${alertId}/acknowledge`, {
      method: "POST",
      headers: this.headers(),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
}

export interface PreAlertData {
  alert_id: string;
  incident_id: string;
  ambulance_id: string;
  triage_category: "RED" | "YELLOW" | "GREEN";
  eta_seconds: number;
  suspected_condition: string;
  vitals?: {
    heart_rate?: number;
    blood_pressure?: string;
    spo2_pct?: number;
    respiratory_rate?: number;
    gcs?: number;
  };
  notes?: string;
  created_at: string;
  acknowledged_at?: string | null;
}

export const apiClient = new EMRPApiClient();
export const emrpApi = apiClient;

export const emrpWs = {
  connectHospital(
    hospitalId: string,
    onMessage: (data: any) => void,
    onOpen?: () => void,
    onClose?: () => void
  ) {
    if (typeof window === "undefined") return () => {};
    try {
      const ws = new WebSocket(`${WS_BASE}/hospitals/${hospitalId}/ws`);
      ws.onopen = () => { if (onOpen) onOpen(); };
      ws.onclose = () => { if (onClose) onClose(); };
      ws.onmessage = (e) => {
        try { onMessage(JSON.parse(e.data)); } catch {}
      };
      return () => ws.close();
    } catch {
      return () => {};
    }
  },
};

// Auto-load token on import (client side)
if (typeof window !== "undefined") {
  apiClient.loadToken();
}
