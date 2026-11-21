import { ImageResponse } from "next/og";

export const alt = "PaisaProof — Learn to read the signal";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        backgroundColor: "#f6f3ea",
        padding: "36px",
        fontFamily: "sans-serif",
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "row",
          alignItems: "stretch",
          justifyContent: "space-between",
          backgroundColor: "#fbfaf7",
          border: "2px solid rgba(31, 77, 58, 0.16)",
          borderRadius: "28px",
          padding: "44px 48px",
        }}
      >
        <div
          style={{
            width: "610px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", flexDirection: "row", alignItems: "center" }}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="56"
              height="56"
              viewBox="0 0 64 64"
              fill="none"
            >
              <rect width="64" height="64" rx="15" fill="#1f4d3a" />
              <rect
                x="4.5"
                y="4.5"
                width="55"
                height="55"
                rx="11.5"
                stroke="#f6f3ea"
                strokeOpacity="0.18"
                strokeWidth="1.5"
              />
              <path
                d="M19 19H43M19 27.5H40M23.5 19C29.5 19 33 22.4 33 27.5C33 32.8 29 36.2 22.5 36.2H19.5L32.5 47"
                stroke="#f6f3ea"
                strokeWidth="4.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M36.5 41.5L41.5 46.5L51 35.5"
                stroke="#d6b265"
                strokeWidth="4.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <div
              style={{
                marginLeft: "18px",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <span
                style={{
                  fontSize: "34px",
                  fontWeight: 700,
                  fontFamily: "Georgia, serif",
                  color: "#1f4d3a",
                  letterSpacing: "-0.02em",
                }}
              >
                PaisaProof
              </span>
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "#536157",
                  letterSpacing: "0.14em",
                  marginTop: "2px",
                }}
              >
                INVESTOR LITERACY &amp; VERIFIER
              </span>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                fontSize: "62px",
                lineHeight: 1.08,
                fontWeight: 700,
                fontFamily: "Georgia, serif",
                color: "#14291f",
                letterSpacing: "-0.025em",
                display: "flex",
              }}
            >
              Learn to read the signal
            </div>
            <div
              style={{
                marginTop: "18px",
                fontSize: "22px",
                lineHeight: 1.4,
                color: "#435348",
                display: "flex",
              }}
            >
              Calibration-first lessons and deterministic claim verification — never buy or sell
              advice.
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "row", alignItems: "center" }}>
            <div
              style={{
                display: "flex",
                padding: "10px 18px",
                borderRadius: "999px",
                backgroundColor: "#eaf1eb",
                border: "1px solid rgba(31, 77, 58, 0.16)",
                color: "#1f4d3a",
                fontSize: "16px",
                fontWeight: 700,
                marginRight: "12px",
              }}
            >
              Brier Calibration
            </div>
            <div
              style={{
                display: "flex",
                padding: "10px 18px",
                borderRadius: "999px",
                backgroundColor: "#eaf1eb",
                border: "1px solid rgba(31, 77, 58, 0.16)",
                color: "#1f4d3a",
                fontSize: "16px",
                fontWeight: 700,
                marginRight: "12px",
              }}
            >
              Red-Flag Checks
            </div>
            <div
              style={{
                display: "flex",
                padding: "10px 18px",
                borderRadius: "999px",
                backgroundColor: "#eaf1eb",
                border: "1px solid rgba(31, 77, 58, 0.16)",
                color: "#1f4d3a",
                fontSize: "16px",
                fontWeight: 700,
              }}
            >
              NSE &amp; Nasdaq
            </div>
          </div>
        </div>

        <div
          style={{
            width: "390px",
            height: "100%",
            borderRadius: "24px",
            backgroundColor: "#1f4d3a",
            padding: "26px 28px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "0.14em",
                color: "#d6b265",
              }}
            >
              SIGNAL OVER NOISE
            </span>
            <span
              style={{
                padding: "5px 12px",
                borderRadius: "999px",
                backgroundColor: "rgba(246, 243, 234, 0.12)",
                color: "#f6f3ea",
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "0.08em",
              }}
            >
              VERIFIED
            </span>
          </div>

          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="334"
            height="310"
            viewBox="0 0 334 310"
            fill="none"
          >
            <line x1="16" y1="62" x2="318" y2="62" stroke="#f6f3ea" strokeOpacity="0.1" />
            <line x1="16" y1="124" x2="318" y2="124" stroke="#f6f3ea" strokeOpacity="0.1" />
            <line x1="16" y1="186" x2="318" y2="186" stroke="#f6f3ea" strokeOpacity="0.1" />
            <line x1="16" y1="248" x2="318" y2="248" stroke="#f6f3ea" strokeOpacity="0.1" />
            <line x1="74" y1="24" x2="74" y2="278" stroke="#f6f3ea" strokeOpacity="0.08" />
            <line x1="167" y1="24" x2="167" y2="278" stroke="#f6f3ea" strokeOpacity="0.08" />
            <line x1="260" y1="24" x2="260" y2="278" stroke="#f6f3ea" strokeOpacity="0.08" />

            <path
              d="M22 222 L54 148 L84 246 L116 116 L146 218 L178 134 L212 204 L244 162 L278 214 L312 184"
              stroke="#f6f3ea"
              strokeOpacity="0.28"
              strokeWidth="3"
              strokeDasharray="7 7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            <path
              d="M24 236 C74 226 102 186 146 168 C190 150 222 104 294 64"
              stroke="#d6b265"
              strokeWidth="6.5"
              strokeLinecap="round"
            />

            <circle cx="74" cy="215" r="7" fill="#1f4d3a" stroke="#f6f3ea" strokeWidth="3" />
            <circle cx="146" cy="168" r="7" fill="#1f4d3a" stroke="#f6f3ea" strokeWidth="3" />
            <circle cx="222" cy="112" r="7" fill="#1f4d3a" stroke="#f6f3ea" strokeWidth="3" />
            <circle cx="294" cy="64" r="18" fill="#d6b265" />
            <path
              d="M286 64 L291.5 69.5 L303 58"
              stroke="#1f4d3a"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <div
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
              borderTop: "1px solid rgba(246, 243, 234, 0.16)",
              paddingTop: "14px",
            }}
          >
            <span style={{ fontSize: "14px", color: "rgba(246, 243, 234, 0.78)" }}>
              Educational only
            </span>
            <span style={{ fontSize: "14px", fontWeight: 700, color: "#f6f3ea" }}>
              aadha-ps.vercel.app
            </span>
          </div>
        </div>
      </div>
    </div>,
    size,
  );
}
