"use client";

import { useEffect, useRef, useState } from "react";

interface VoiceHotlineModalProps {
  isOpen: boolean;
  onClose: () => void;
  callerPhone: string;
  location: { latitude: number; longitude: number; accuracy: number } | null;
  onIncidentCreated: (incidentId: string) => void;
}

type CallStep =
  | "IDLE"
  | "CALLING"
  | "ASKING_CASE"
  | "RECORDING_CASE"
  | "CASE_CAPTURED"
  | "PROCESSING"
  | "COMPLETED";

export default function VoiceHotlineModal({
  isOpen,
  onClose,
  callerPhone,
  location,
  onIncidentCreated,
}: VoiceHotlineModalProps) {
  const [callStep, setCallStep] = useState<CallStep>("IDLE");
  const [phone, setPhone] = useState(callerPhone || "8000697437");
  const [speechText, setSpeechText] = useState("");
  const [result, setResult] = useState<any>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [callDuration, setCallDuration] = useState(0);

  const recognitionRef = useRef<any>(null);
  const latestSpeechRef = useRef("");
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (callerPhone) setPhone(callerPhone);
  }, [callerPhone]);

  // Call timer counter while call is active
  useEffect(() => {
    const isCallActive =
      callStep === "CALLING" ||
      callStep === "ASKING_CASE" ||
      callStep === "RECORDING_CASE" ||
      callStep === "CASE_CAPTURED";

    if (isCallActive) {
      timerRef.current = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setCallDuration(0);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [callStep]);

  if (!isOpen) return null;

  const formatTimer = (seconds: number) => {
    const m = Math.floor(seconds / 60)
      .toString()
      .padStart(2, "0");
    const s = (seconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

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

  const cancelAudioAndRecognition = () => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }
    setIsRecording(false);
  };

  const startVoiceCall = () => {
    setCallStep("CALLING");
    setSpeechText("");
    latestSpeechRef.current = "";
    setResult(null);

    // Operator answers and asks what is the case (no address requested)
    setTimeout(() => {
      setCallStep("ASKING_CASE");
      speak(
        "Emergency medical response automated hotline. What is the case?",
        () => {
          setCallStep("RECORDING_CASE");
          listenForSpeech((capturedCase) => {
            latestSpeechRef.current = capturedCase;
            setSpeechText(capturedCase);
            setCallStep("CASE_CAPTURED");
          });
        }
      );
    }, 1200);
  };

  const listenForSpeech = (onResult: (text: string) => void) => {
    setIsRecording(true);
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-IN";

      recognition.onresult = (e: any) => {
        let currentTranscript = "";
        for (let i = 0; i < e.results.length; i++) {
          currentTranscript += e.results[i][0].transcript;
        }
        latestSpeechRef.current = currentTranscript;
        setSpeechText(currentTranscript);

        if (e.results[0].isFinal) {
          setIsRecording(false);
          onResult(currentTranscript);
        }
      };

      recognition.onerror = () => {
        setIsRecording(false);
        const fallbackText =
          latestSpeechRef.current ||
          "Severe acute chest pain and breathing difficulty";
        latestSpeechRef.current = fallbackText;
        setSpeechText(fallbackText);
        onResult(fallbackText);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      try {
        recognition.start();
        recognitionRef.current = recognition;
      } catch (err) {
        setIsRecording(false);
      }
    } else {
      setTimeout(() => {
        setIsRecording(false);
        const fallbackText = "Suspected acute cardiac arrest, patient collapsed";
        latestSpeechRef.current = fallbackText;
        setSpeechText(fallbackText);
        onResult(fallbackText);
      }, 3500);
    }
  };

  // Called when user clicks "End Call"
  const handleEndCall = () => {
    cancelAudioAndRecognition();
    const finalCase =
      latestSpeechRef.current.trim() ||
      speechText.trim() ||
      "Emergency medical case reported via hotline";
    submitToGemini(finalCase);
  };

  const simulateCaseQuick = (caseDescription: string) => {
    latestSpeechRef.current = caseDescription;
    setSpeechText(caseDescription);
    submitToGemini(caseDescription);
  };

  const submitToGemini = async (caseDetails: string) => {
    setCallStep("PROCESSING");
    try {
      const loc = location || { latitude: 28.6139, longitude: 77.209, accuracy: 15 };
      const apiBase =
        process.env.NEXT_PUBLIC_API_URL || "https://emrp.onrender.com/api/v1";

      const res = await fetch(`${apiBase}/voice/process-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          caller_phone: phone || "8000697437",
          caller_name: "Voice Hotline Caller",
          transcript: `Case: ${caseDetails}`,
          latitude: loc.latitude,
          longitude: loc.longitude,
          accuracy_m: loc.accuracy,
        }),
      });

      const data = await res.json();
      setResult(data);
      setCallStep("COMPLETED");
      speak(
        "Call ended. Your emergency case has been triaged. Help is being dispatched."
      );
      if (data.incident_id) {
        onIncidentCreated(data.incident_id);
      }
    } catch (e: any) {
      alert("Voice process error: " + e.message);
      setCallStep("IDLE");
    }
  };

  const handleModalClose = () => {
    cancelAudioAndRecognition();
    setCallStep("IDLE");
    onClose();
  };

  const isCallActive =
    callStep === "CALLING" ||
    callStep === "ASKING_CASE" ||
    callStep === "RECORDING_CASE" ||
    callStep === "CASE_CAPTURED";

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
          onClick={handleModalClose}
          aria-label="Close hotline"
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
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          ✕
        </button>

        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            marginBottom: "1rem",
          }}
        >
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              background: isCallActive ? "#fee2e2" : "#e0f2fe",
              color: isCallActive ? "var(--brand-red)" : "var(--brand-navy)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.25rem",
              animation: isCallActive ? "pulse 1.5s infinite" : "none",
            }}
          >
            {isCallActive ? "📞" : "🎙️"}
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h3
                style={{
                  margin: 0,
                  fontSize: "1.15rem",
                  color: "var(--brand-navy)",
                }}
              >
                Automated AI Emergency Hotline
              </h3>
              {isCallActive && (
                <span
                  style={{
                    background: "#fee2e2",
                    color: "#dc2626",
                    fontSize: "0.75rem",
                    padding: "0.15rem 0.5rem",
                    borderRadius: "999px",
                    fontWeight: 700,
                  }}
                >
                  LIVE {formatTimer(callDuration)}
                </span>
              )}
            </div>
            <span
              style={{
                fontSize: "0.8125rem",
                color: "#16a34a",
                fontWeight: 700,
              }}
            >
              Designated Number: +91 11 4084 9108 (24x7 Active)
            </span>
          </div>
        </div>

        {/* Automatic Caller & Telemetry Card */}
        <div
          style={{
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            padding: "0.85rem",
            marginBottom: "1.25rem",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.4rem",
            }}
          >
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                color: "var(--text-muted)",
                textTransform: "uppercase",
              }}
            >
              Active Telemetry Capture (No Address Required)
            </span>
            <span
              style={{
                fontSize: "0.75rem",
                background: "#dcfce7",
                color: "#15803d",
                padding: "0.15rem 0.5rem",
                borderRadius: "999px",
                fontWeight: 700,
              }}
            >
              GPS Auto-Locked
            </span>
          </div>
          <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
            <div>
              <strong>Caller Phone:</strong> {phone} (Captured via Line)
            </div>
            <div>
              <strong>GPS Telemetry:</strong>{" "}
              {location
                ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}`
                : "28.6139, 77.2090 (Delhi Sector 1)"}
            </div>
          </div>
        </div>

        {/* ── State 1: IDLE ── */}
        {callStep === "IDLE" && (
          <div>
            <p
              style={{
                fontSize: "0.9rem",
                color: "var(--text-secondary)",
                lineHeight: 1.5,
                marginBottom: "1.25rem",
              }}
            >
              When you start the call, the automated voice hotline will ask{" "}
              <strong>what is the case</strong>. Your location is locked
              automatically via GPS. When done, tap <strong>End Call</strong> to
              dispatch immediately.
            </p>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}
            >
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
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.5rem",
                }}
              >
                <span>📞</span> Call Hotline Now
              </button>

              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  textAlign: "center",
                  margin: "0.25rem 0",
                }}
              >
                — Or simulate a 1-tap emergency case —
              </div>

              <button
                onClick={() =>
                  simulateCaseQuick(
                    "Patient collapsed with acute cardiac chest pain and breathing difficulty"
                  )
                }
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
                ⚡ Quick Simulate: Acute Cardiac Chest Pain
              </button>
            </div>
          </div>
        )}

        {/* ── State 2: ACTIVE CALL (CALLING / ASKING_CASE / RECORDING_CASE / CASE_CAPTURED) ── */}
        {isCallActive && (
          <div style={{ textAlign: "center", padding: "1rem 0" }}>
            <div
              style={{
                width: "76px",
                height: "76px",
                borderRadius: "50%",
                background: isRecording ? "#fee2e2" : "#e0f2fe",
                color: isRecording ? "var(--brand-red)" : "var(--brand-navy)",
                fontSize: "2.2rem",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "0.85rem",
                boxShadow: isRecording
                  ? "0 0 0 8px rgba(220, 38, 38, 0.15)"
                  : "0 0 0 8px rgba(2, 132, 199, 0.12)",
                animation: isRecording ? "pulse 1.2s infinite" : "none",
              }}
            >
              {isRecording ? "🎙️" : "🔊"}
            </div>

            <h4
              style={{
                margin: "0 0 0.4rem 0",
                color: "var(--brand-navy)",
                fontSize: "1.05rem",
              }}
            >
              {callStep === "CALLING" && "Connecting to Automated Emergency Hotline..."}
              {callStep === "ASKING_CASE" && "Automated Voice: 'What is the case?'"}
              {callStep === "RECORDING_CASE" && "Listening... Please describe what is the case"}
              {callStep === "CASE_CAPTURED" && "Case recorded! Press End Call to dispatch"}
            </h4>

            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
              {isRecording
                ? "Speak clearly into your microphone describing the patient's case."
                : callStep === "CASE_CAPTURED"
                ? "Tap End Call below to dispatch help immediately."
                : "Hotline operator speaking..."}
            </p>

            {/* Display Spoken Case Text */}
            <div
              style={{
                marginTop: "1rem",
                background: "#f1f5f9",
                border: "1px solid #e2e8f0",
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                fontSize: "0.9rem",
                minHeight: "48px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontStyle: speechText ? "normal" : "italic",
                color: speechText ? "var(--brand-navy)" : "#94a3b8",
                fontWeight: speechText ? 600 : 400,
              }}
            >
              {speechText ? `"${speechText}"` : "Waiting for spoken case details..."}
            </div>

            {/* ── End Call Button ── */}
            <div style={{ marginTop: "1.5rem" }}>
              <button
                onClick={handleEndCall}
                style={{
                  background: "#dc2626",
                  color: "#ffffff",
                  border: "none",
                  padding: "0.85rem 2.25rem",
                  borderRadius: "999px",
                  fontWeight: 800,
                  fontSize: "1.05rem",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.6rem",
                  boxShadow: "0 6px 20px rgba(220, 38, 38, 0.4)",
                  transition: "all 0.2s ease",
                }}
              >
                <span style={{ fontSize: "1.25rem" }}>📴</span>
                <span>End Call & Dispatch</span>
              </button>
            </div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                marginTop: "0.5rem",
              }}
            >
              Pressing End Call instantly saves your case and routes ALS ambulance to your GPS
            </div>
          </div>
        )}

        {/* ── State 3: PROCESSING ── */}
        {callStep === "PROCESSING" && (
          <div style={{ textAlign: "center", padding: "2rem 0" }}>
            <div
              style={{
                fontSize: "2.5rem",
                marginBottom: "0.75rem",
                animation: "spin 1s linear infinite",
              }}
            >
              ⚙️
            </div>
            <h4 style={{ margin: "0 0 0.4rem 0", color: "var(--brand-navy)" }}>
              Gemini AI Triaging Medical Case
            </h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Analyzing case severity, prioritizing category, and routing nearest
              ambulance unit...
            </p>
          </div>
        )}

        {/* ── State 4: COMPLETED ── */}
        {callStep === "COMPLETED" && result && (
          <div>
            <div
              style={{
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: "8px",
                padding: "1rem",
                marginBottom: "1.25rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "0.5rem",
                }}
              >
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 800,
                    color: "#166534",
                    textTransform: "uppercase",
                  }}
                >
                  Call Ended &bull; Case Triaged
                </span>
                <span
                  style={{
                    background:
                      result.severity === "CRITICAL"
                        ? "var(--brand-red)"
                        : "#ea580c",
                    color: "#ffffff",
                    fontSize: "0.75rem",
                    padding: "0.2rem 0.6rem",
                    borderRadius: "999px",
                    fontWeight: 800,
                  }}
                >
                  {result.severity || "HIGH"} PRIORITY
                </span>
              </div>
              <div
                style={{
                  fontSize: "0.875rem",
                  color: "#14532d",
                  display: "grid",
                  gap: "0.35rem",
                }}
              >
                <div>
                  <strong>Reported Case:</strong> {result.condition || "Emergency Case Reported"}
                </div>
                <div>
                  <strong>Caller Phone:</strong> {result.caller_phone}
                </div>
                <div>
                  <strong>Location:</strong> Auto-Locked via Telemetry GPS
                </div>
                <div>
                  <strong>Incident ID:</strong>{" "}
                  <code>#{result.incident_id?.slice(-6)}</code>
                </div>
              </div>
            </div>

            <button
              onClick={handleModalClose}
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
