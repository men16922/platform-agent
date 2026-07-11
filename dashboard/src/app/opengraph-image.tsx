import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt =
  "Platform Agent — Multi-Cloud Operations Dashboard covering AWS, GCP, Azure, and On-Premise";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "72px",
          background: "linear-gradient(145deg, #292a2d, #202124)",
          fontFamily: "system-ui, sans-serif",
          color: "#f1f3f4",
        }}
      >
        {/* Accent glow */}
        <div
          style={{
            position: "absolute",
            top: "-120px",
            right: "-80px",
            width: "480px",
            height: "480px",
            borderRadius: "50%",
            background: "rgba(138, 180, 248, 0.12)",
            filter: "blur(80px)",
          }}
        />

        {/* Eyebrow */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              background: "#81c995",
              boxShadow: "0 0 12px rgba(56, 217, 150, 0.7)",
            }}
          />
          <span
            style={{
              fontSize: "16px",
              fontWeight: 700,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "#bdc1c6",
            }}
          >
            Autonomous Operations
          </span>
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: "56px",
            fontWeight: 700,
            lineHeight: 1.15,
            margin: "0 0 20px 0",
            maxWidth: "800px",
          }}
        >
          Platform Agent
        </h1>

        {/* Subtitle */}
        <p
          style={{
            fontSize: "22px",
            color: "#bdc1c6",
            margin: 0,
            maxWidth: "700px",
            lineHeight: 1.5,
          }}
        >
          Multi-Cloud Operations Dashboard — provision, deploy, detect, analyze,
          decide, execute across AWS, GCP, Azure &amp; On-Premise.
        </p>

        {/* Pipeline steps */}
        <div
          style={{
            display: "flex",
            gap: "12px",
            marginTop: "40px",
          }}
        >
          {["Detect", "Analyze", "Decide", "Execute"].map((step) => (
            <div
              key={step}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                border: "1px solid rgba(138, 180, 248, 0.25)",
                borderRadius: "10px",
                padding: "10px 18px",
                background: "rgba(138, 180, 248, 0.08)",
                fontSize: "16px",
                fontWeight: 600,
                color: "#c4ddff",
              }}
            >
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: "#81c995",
                }}
              />
              {step}
            </div>
          ))}
        </div>

        {/* Provider badges */}
        <div
          style={{
            display: "flex",
            gap: "10px",
            marginTop: "28px",
          }}
        >
          {["AWS", "GCP", "Azure", "On-Premise"].map((p) => (
            <span
              key={p}
              style={{
                fontSize: "13px",
                fontWeight: 600,
                padding: "6px 14px",
                borderRadius: "6px",
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#bdc1c6",
              }}
            >
              {p}
            </span>
          ))}
        </div>
      </div>
    ),
    { ...size },
  );
}
