import { useEffect, useRef } from "react";

export default function LandingPage({ onEnter }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    let raf = 0;
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const nodes = Array.from({ length: 60 }, () => {
      const roll = Math.random();
      let color = "#1e3a5f";
      if (roll > 0.9) color = "#7c3aed";
      else if (roll > 0.7) color = "#00d4ff";
      return {
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        r: 1.5 + Math.random() * 1.5,
        color,
        opacity: 0.4 + Math.random() * 0.4,
      };
    });

    const step = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx.fillStyle = "#0a0a0f";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#1a1a2e";
      ctx.globalAlpha = 0.35;
      ctx.fillRect(0, 0, w, h);
      ctx.globalAlpha = 1;

      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 0 || n.x > w) {
          n.vx *= -1;
          n.x = Math.max(0, Math.min(w, n.x));
        }
        if (n.y < 0 || n.y > h) {
          n.vy *= -1;
          n.y = Math.max(0, Math.min(h, n.y));
        }
      }

      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist < 120 && dist > 0) {
            const t = 1 - dist / 120;
            const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 800 + i + j);
            ctx.strokeStyle = `rgba(0, 212, 255, ${0.08 * t * pulse})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      for (const n of nodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.globalAlpha = n.opacity * (0.85 + 0.15 * Math.sin(Date.now() / 1200 + n.x * 0.01));
        ctx.fill();
        ctx.globalAlpha = 1;
      }

      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        minHeight: "100vh",
        background: "#0a0a0f",
        overflow: "hidden",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 0,
          display: "block",
        }}
        aria-hidden
      />
      <div
        style={{
          position: "relative",
          zIndex: 10,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px 20px 32px",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            border: "1px solid rgba(0,212,255,0.3)",
            background: "rgba(0,212,255,0.05)",
            color: "#00d4ff",
            fontSize: 12,
            letterSpacing: 2,
            textTransform: "uppercase",
            borderRadius: 20,
            padding: "6px 16px",
            marginBottom: 28,
          }}
        >
          CMPE 273 · Enterprise Distributed Systems · SJSU
        </div>
        <h1
          style={{
            margin: 0,
            fontWeight: 700,
            fontSize: "clamp(48px, 8vw, 72px)",
            color: "#ffffff",
            textAlign: "center",
            lineHeight: 1.05,
          }}
        >
          SemCache AI
        </h1>
        <div
          style={{
            marginTop: 20,
            maxWidth: 520,
            textAlign: "center",
            fontSize: 18,
            color: "rgba(255,255,255,0.55)",
            lineHeight: 1.8,
          }}
        >
          <div>
            Semantic caching layer that makes LLMs 10× faster by remembering what they know.
          </div>
          <div>Quality-aware decisions. Zero redundant inference.</div>
        </div>
        <button
          type="button"
          onClick={() => onEnter?.()}
          style={{
            marginTop: 36,
            background: "#00d4ff",
            color: "#0a0a0f",
            border: "none",
            borderRadius: 8,
            padding: "14px 36px",
            fontSize: 15,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#00bfe8";
            e.currentTarget.style.transform = "scale(1.02)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#00d4ff";
            e.currentTarget.style.transform = "scale(1)";
          }}
        >
          Launch Application →
        </button>
        <div
          style={{
            marginTop: 48,
            fontSize: 11,
            color: "rgba(255,255,255,0.2)",
            letterSpacing: 1.5,
            textTransform: "uppercase",
            textAlign: "center",
            maxWidth: 560,
          }}
        >
          Agentic Decision Layer · Feedback Loop Learning · False Hit Detection
        </div>
      </div>
    </div>
  );
}
