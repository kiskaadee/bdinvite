import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  radius: number;
  baseOpacity: number;
  blur: number;
  goldR: number;
  goldG: number;
  goldB: number;
  vx: number;
  vy: number;
  twinkleSpeed: number;
  twinklePhase: number;
}

export function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    let width = canvas.width;
    let height = canvas.height;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const particleCount = width > 768 ? 120 : 80;
    const particles: Particle[] = [];

    function createParticle(): Particle {
      const bias = Math.random();
      let x = 0;
      let y = 0;

      if (bias < 0.4) {
        // Upper-left quadrant
        x = Math.random() * width * 0.55;
        y = Math.random() * height * 0.45;
      } else if (bias < 0.8) {
        // Lower-right quadrant
        x = width * 0.45 + Math.random() * width * 0.55;
        y = height * 0.55 + Math.random() * height * 0.45;
      } else {
        // Sparse center
        x = Math.random() * width;
        y = Math.random() * height;
      }

      // Golden hues: amber, champagne, warm gold
      const goldPalette = [
        { r: 212, g: 168, b: 67 }, // Classic gold #d4a843
        { r: 240, g: 214, b: 138 }, // Light gold #f0d68a
        { r: 255, g: 223, b: 140 }, // Bright champagne
        { r: 180, g: 140, b: 50 }, // Deep amber
      ];
      const color = goldPalette[Math.floor(Math.random() * goldPalette.length)];

      return {
        x,
        y,
        radius: 1.5 + Math.random() * 5.5,
        baseOpacity: 0.15 + Math.random() * 0.55,
        blur: 2 + Math.random() * 8,
        goldR: color.r,
        goldG: color.g,
        goldB: color.b,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
        twinkleSpeed: 0.006 + Math.random() * 0.018,
        twinklePhase: Math.random() * Math.PI * 2,
      };
    }

    for (let i = 0; i < particleCount; i++) {
      particles.push(createParticle());
    }

    function renderFrame() {
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);

      for (const p of particles) {
        p.twinklePhase += p.twinkleSpeed;
        const currentOpacity = Math.max(
          0.05,
          p.baseOpacity + Math.sin(p.twinklePhase) * 0.25,
        );

        ctx.save();
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);

        // Soft bokeh glow
        ctx.shadowBlur = p.blur;
        ctx.shadowColor = `rgba(${p.goldR}, ${p.goldG}, ${p.goldB}, ${currentOpacity})`;
        ctx.fillStyle = `rgba(${p.goldR}, ${p.goldG}, ${p.goldB}, ${currentOpacity})`;
        ctx.fill();
        ctx.restore();

        if (!prefersReducedMotion) {
          p.x += p.vx;
          p.y += p.vy;

          // Wrap edges
          if (p.x < -10) p.x = width + 10;
          if (p.x > width + 10) p.x = -10;
          if (p.y < -10) p.y = height + 10;
          if (p.y > height + 10) p.y = -10;
        }
      }

      if (!prefersReducedMotion) {
        animationFrameId = requestAnimationFrame(renderFrame);
      }
    }

    // Initial render
    renderFrame();

    function handleResize() {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      width = canvas.width;
      height = canvas.height;
      if (prefersReducedMotion) {
        renderFrame();
      }
    }

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 0,
      }}
    />
  );
}
