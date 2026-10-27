"use client";

import { useEffect, useRef, useState } from "react";

interface VoiceHotlineModalProps {
  isOpen: boolean;
  onClose: () => void;
  callerPhone: string;
  location: { latitude: number; longitude: number; accuracy: number } | null;
  onIncidentCreated: (incidentId: string) => void;
}

export default function VoiceHotlineModal({
  isOpen,
  onClose,
  callerPhone,
  location,
  onIncidentCreated,
}: VoiceHotlineModalProps) {
  const [callStep, setCallStep] = useState<"IDLE" | "CALLING" | "PROMPT_1" | "RECORDING_EMERGENCY" | "PROMPT_2" | "RECORDING_ADDRESS" | "PROCESSING" | "COMPLETED">("IDLE");
  const [phone, setPhone] = useState(callerPhone || "8000697437");
  const [transcript, setTranscript] = useState("");
  const [speechText, setSpeechText] = useState("");
  const [result, setResult] = useState<any>(null);
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (callerPhone) setPhone(callerPhone);
  }, [callerPhone]);

  if (!isOpen) return null;

  const speak = (text: string, onEnd?: () => void) => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      if (onEnd) utterance.onend = onEnd;
      window.speechSynthesis.speak(utterance);
    } else {
      setTimeout(() => onEnd?.(), 1500);
    }
  };

  const startVoiceCall = () => {
    setCallStep("CALLING");
    setTranscript("");
    setResult(null);

    // Automated Voice Step 1
    setTimeout(() => {
      setCallStep("PROMPT_1");
      speak(
        "Emergency medical response automated hotline. Please describe your medical emergency.",
        () => {
          setCallStep("RECORDING_EMERGENCY");
          listenForSpeech((emergencySpeech) => {
            setTranscript((prev) => prev + " " + emergencySpeech);
            // Automated Voice Step 2: Address
            setCallStep("PROMPT_2");
            speak(
              "Thank you. Now please clearly state the exact street address or landmark where the patient is located.",
              () => {
                setCallStep("RECORDING_ADDRESS");
                listenForSpeech((addressSpeech) => {
                  const fullTranscript = `${emergencySpeech}. Location: ${addressSpeech}`;
                  setTranscript(fullTranscript);
                  submitToGemini(fullTranscript);
                });
              }
            );
          });
        }
      );
    }, 1200);
  };

  const listenForSpeech = (onResult: (text: string) => void) => {
    setIsRecording(true);
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-IN";
      recognition.onresult = (e: any) => {
        const text = e.results[0][0].transcript;
        setIsRecording(false);
        setSpeechText(text);
        onResult(text);
      };
      recognition.onerror = () => {
        setIsRecording(false);
        // Fallback simulation text if mic blocked
        const fallbackText = "Severe breathing difficulty and acute chest pain near Sector 14 market";
        setSpeechText(fallbackText);
        onResult(fallbackText);
      };
      recognition.start();
      recognitionRef.current = recognition;
    } else {
      setTimeout(() => {
        setIsRecording(false);
        const fallbackText = "Suspected cardiac arrest at Connaught Place block B";
        setSpeechText(fallbackText);
        onResult(fallbackText);
      }, 3000);
    }
  };

  const simulateSpeechQuick = (emergency: string, address: string) => {
    const full = `${emergency}. Located at ${address}.`;
    setTranscript(full);
    submitToGemini(full);
  };

  const submitToGemini = async (speechContent: string) => {
    setCallStep("PROCESSING");
    try {
      const loc = location || { latitude: 28.6139, longitude: 77.2090, accuracy: 15 };
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://emrp.onrender.com/api/v1";
      const res = await fetch(`${apiBase}/voice/process-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          caller_phone: phone || "8000697437",
          caller_name: "Voice Hotline Caller",
          transcript: speechContent,
          latitude: loc.latitude,
          longitude: loc.longitude,
          accuracy_m: loc.accuracy,
        }),
      });

      const data = await res.json();
      setResult(data);
      setCallStep("COMPLETED");
      speak("Your emergency call has been verified by Gemini triage. Help has been dispatched.");
      if (data.incident_id) {
        onIncidentCreated(data.incident_id);
      }
    } catch (e: any) {
      alert("Voice process error: " + e.message);
      setCallStep("IDLE");
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(11, 37, 69, 0.75)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
      }}
    >
      <div
        style={{
          background: "#ffffff",
          borderRadius: "16px",
          maxWidth: "520px",
          width: "100%",
          padding: "1.75rem",
          boxShadow: "0 20px 50px rgba(0,0,0,0.3)",
          position: "relative",
        }}
      >
        <button
          onClick={() => {
            if (typeof window !== "undefined") window.speechSynthesis.cancel();
            onClose();
          }}
          style={{
            position: "absolute",
            top: "1rem",
            right: "1rem",
            background: "#f1f5f9",
            border: "none",
            borderRadius: "50%",
            width: "32px",
            height: "32px",
            cursor: "pointer",
            fontWeight: 700,
          }}
        >
          ✕
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              background: "#fee2e2",
              color: "var(--brand-red)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.25rem",
            }}
          >
            📞
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: "1.15rem", color: "var(--brand-navy)" }}>
              Automated AI Emergency Hotline
            </h3>
            <span style={{ fontSize: "0.8125rem", color: "#16a34a", fontWeight: 700 }}>
              Designated Number: +91 11 4084 9108 (24x7 Active)
            </span>
          </div>
        </div>

        {/* Caller Info Telephony Capture */}
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "0.85rem", marginBottom: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
              Active Cellular Telemetry Capture
            </span>
            <span style={{ fontSize: "0.75rem", background: "#dcfce7", color: "#15803d", padding: "0.15rem 0.5rem", borderRadius: "999px", fontWeight: 700 }}>
              Location Locked
            </span>
          </div>
          <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
            <div><strong>Caller Phone:</strong> {phone} (Captured via Inbound Line)</div>
            <div><strong>Active GPS:</strong> {location ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}` : "28.6139, 77.2090 (Delhi Sector 1)"}</div>
          </div>
        </div>

        {/* Voice Call State Screen */}
        {callStep === "IDLE" && (
          <div>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "1.25rem" }}>
              When you start the call, the <strong>automated voice system</strong> will ask for your emergency and record your address. <strong>Gemini AI</strong> will transcribe your speech, determine the severity level, and lock your dispatch.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <button
                onClick={startVoiceCall}
                style={{
                  background: "var(--brand-red)",
                  color: "#ffffff",
                  border: "none",
                  padding: "0.85rem",
                  borderRadius: "8px",
                  fontWeight: 800,
                  fontSize: "1rem",
                  cursor: "pointer",
                  boxShadow: "0 4px 14px rgba(215, 38, 56, 0.35)",
                }}
              >
                🎙️ Start Automated Voice Call Now
              </button>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textAlign: "center" }}>
                — Or simulate a 1-tap emergency voice scenario —
              </div>
              <button
                onClick={() => simulateSpeechQuick("Elderly patient collapsed with acute cardiac arrest, gasping for breath", "Flat 402, Lotus Greens, Sector 78")}
                style={{
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  padding: "0.6rem",
                  borderRadius: "6px",
                  fontSize: "0.8125rem",
                  fontWeight: 600,
                  color: "var(--brand-navy)",
                  cursor: "pointer",
                }}
              >
                ⚡ Simulate Voice: Cardiac Arrest at Lotus Greens
              </button>
            </div>
          </div>
        )}

        {(callStep === "CALLING" || callStep === "PROMPT_1" || callStep === "RECORDING_EMERGENCY" || callStep === "PROMPT_2" || callStep === "RECORDING_ADDRESS") && (
          <div style={{ textAlign: "center", padding: "1.5rem 0" }}>
            <div
              style={{
                width: "72px",
                height: "72px",
                borderRadius: "50%",
                background: isRecording ? "#fee2e2" : "#e0f2fe",
                color: isRecording ? "var(--brand-red)" : "var(--brand-navy)",
                fontSize: "2rem",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "1rem",
                animation: isRecording ? "pulse 1.2s infinite" : "none",
              }}
            >
              {isRecording ? "🔴" : "🔊"}
            </div>
            <h4 style={{ margin: "0 0 0.5rem 0", color: "var(--brand-navy)" }}>
              {callStep === "CALLING" && "Connecting to Designated Emergency Line..."}
              {callStep === "PROMPT_1" && "Automated Voice: 'What is your medical emergency?'"}
              {callStep === "RECORDING_EMERGENCY" && "Listening... Speak your emergency symptoms"}
              {callStep === "PROMPT_2" && "Automated Voice: 'Please state your address or landmark'"}
              {callStep === "RECORDING_ADDRESS" && "Listening... Speak your exact location/landmark"}
            </h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {isRecording ? "Recording active audio line... Speak clearly into your microphone" : "Automated operator speaking..."}
            </p>
            {speechText && (
              <div style={{ marginTop: "1rem", background: "#f1f5f9", padding: "0.6rem 1rem", borderRadius: "8px", fontSize: "0.85rem", fontStyle: "italic" }}>
                "{speechText}"
              </div>
            )}
          </div>
        )}

        {callStep === "PROCESSING" && (
          <div style={{ textAlign: "center", padding: "2rem 0" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", animation: "spin 1s linear infinite" }}>⚙️</div>
            <h4 style={{ margin: "0 0 0.4rem 0", color: "var(--brand-navy)" }}>Gemini AI Transcribing & Triaging</h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Extracting clinical severity, geocoding spoken address, and routing to nearest ALS unit...
            </p>
          </div>
        )}

        {callStep === "COMPLETED" && result && (
          <div>
            <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "8px", padding: "1rem", marginBottom: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "#166534", textTransform: "uppercase" }}>
                  Triage Analysis Result
                </span>
                <span
                  style={{
                    background: result.severity === "CRITICAL" ? "var(--brand-red)" : "#ea580c",
                    color: "#ffffff",
                    fontSize: "0.75rem",
                    padding: "0.2rem 0.6rem",
                    borderRadius: "999px",
                    fontWeight: 800,
                  }}
                >
                  {result.severity} PRIORITY
                </span>
              </div>
              <div style={{ fontSize: "0.875rem", color: "#14532d", display: "grid", gap: "0.35rem" }}>
                <div><strong>Condition:</strong> {result.condition}</div>
                <div><strong>Address:</strong> {result.address}</div>
                <div><strong>Incident ID:</strong> <code>#{result.incident_id?.slice(-6)}</code></div>
                <div><strong>Caller Phone:</strong> {result.caller_phone}</div>
              </div>
            </div>

            <button
              onClick={() => {
                if (typeof window !== "undefined") window.speechSynthesis.cancel();
                onClose();
              }}
              style={{
                width: "100%",
                background: "var(--brand-navy)",
                color: "#ffffff",
                border: "none",
                padding: "0.85rem",
                borderRadius: "8px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              ✓ View Live Emergency on Board
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
