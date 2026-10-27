import { type SVGProps } from "react";

interface HeroArtworkProps extends SVGProps<SVGSVGElement> {
  className?: string;
}

/**
 * HeroArtwork: "The Geometry of Proven Knowledge"
 * Substantially enlarged, commanding sculptural visual metaphor.
 * Features expansive layered architectural folios spanning ~92% of viewBox,
 * a towering Deep Aubergine + Marigold faceted polyhedron core,
 * balanced satellite nodes, and refined editorial blueprint axes.
 *
 * Palette: Ice Silver (#F1F0EC), Deep Aubergine (#29152F, #49334E),
 * Warm Marigold (#E9A83A), Burnt Amber (#B96D2B), and Warm Ivory (#FAF8F3).
 */
export function HeroArtwork({ className = "", ...props }: HeroArtworkProps) {
  return (
    <div className={`hero-artwork-wrap ${className}`.trim()}>
      <svg
        viewBox="0 0 600 500"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="hero-artwork-svg"
        aria-hidden="true"
        role="img"
        {...props}
      >
        <defs>
          {/* Subtle Ambient Radial Glow */}
          <radialGradient
            id="ambientGlow"
            cx="50%"
            cy="46%"
            r="50%"
            fx="50%"
            fy="42%"
          >
            <stop offset="0%" stopColor="#E9A83A" stopOpacity="0.24" />
            <stop offset="50%" stopColor="#FAF8F3" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#FAF8F3" stopOpacity="0" />
          </radialGradient>

          {/* Deep Aubergine Facet Gradient */}
          <linearGradient id="aubergineFacet" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#4D3452" />
            <stop offset="60%" stopColor="#29152F" />
            <stop offset="100%" stopColor="#1B0C20" />
          </linearGradient>

          {/* Deep Aubergine Dark Shadow Facet */}
          <linearGradient id="aubergineDark" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#16081A" />
            <stop offset="100%" stopColor="#29152F" />
          </linearGradient>

          {/* Marigold Radiant Directional Highlight */}
          <linearGradient id="marigoldGlow" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#FCE39E" />
            <stop offset="35%" stopColor="#E9A83A" />
            <stop offset="85%" stopColor="#C97528" />
            <stop offset="100%" stopColor="#9C5216" />
          </linearGradient>

          {/* Ivory Folio Surface */}
          <linearGradient id="ivoryFolio" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="70%" stopColor="#FAF8F3" />
            <stop offset="100%" stopColor="#EFECE6" />
          </linearGradient>

          {/* Silver Base Plinth Folio */}
          <linearGradient id="silverFolio" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FAF8F3" />
            <stop offset="50%" stopColor="#F1F0EC" />
            <stop offset="100%" stopColor="#E0DAD3" />
          </linearGradient>

          {/* Burnt Amber Edge Accent */}
          <linearGradient id="burntAmberEdge" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#F9D77E" />
            <stop offset="45%" stopColor="#E9A83A" />
            <stop offset="100%" stopColor="#B96D2B" />
          </linearGradient>

          {/* Restrained Architectural Drop Shadow */}
          <filter id="heroShadow" x="-10%" y="-10%" width="125%" height="125%">
            <feDropShadow
              dx="0"
              dy="18"
              stdDeviation="22"
              floodColor="#29152F"
              floodOpacity="0.13"
            />
          </filter>
        </defs>

        {/* Ambient Warm Atmosphere */}
        <circle cx="300" cy="245" r="235" fill="url(#ambientGlow)" />

        {/* Background Architectural Blueprint Grid & Orbital Ellipses */}
        <g stroke="#E5DFD9" strokeWidth="0.8" strokeDasharray="3 4" opacity="0.85">
          <ellipse cx="300" cy="290" rx="265" ry="145" />
          <ellipse cx="300" cy="290" rx="195" ry="105" />
          <line x1="300" y1="35" x2="300" y2="465" />
          <line x1="35" y1="290" x2="565" y2="290" />
          {/* 45-degree faint reference lines */}
          <line x1="110" y1="100" x2="490" y2="480" strokeWidth="0.5" opacity="0.4" />
          <line x1="490" y1="100" x2="110" y2="480" strokeWidth="0.5" opacity="0.4" />
        </g>

        {/* Layered Architectural Folios (Metaphor: Structured Foundations) */}
        <g filter="url(#heroShadow)" className="floating-folio-group">
          {/* Base Lower Folio / Page 1 — Spanning 500px across the viewport */}
          <polygon
            points="50,330 300,402 550,330 300,268"
            fill="url(#silverFolio)"
            stroke="#DCD7D2"
            strokeWidth="1.2"
          />
          {/* Page 1 Beveled 3D Thickness Edge */}
          <polygon
            points="50,330 300,402 300,412 50,340"
            fill="#C9C2BA"
            opacity="0.7"
          />
          <polygon
            points="300,402 550,330 550,340 300,412"
            fill="#B8B0A8"
            opacity="0.85"
          />

          {/* Intermediate Stepped Folio / Page 2 */}
          <polygon
            points="85,286 300,348 515,286 300,232"
            fill="url(#ivoryFolio)"
            stroke="#E2DDD7"
            strokeWidth="1.2"
          />
          {/* Page 2 Thickness Edge */}
          <polygon
            points="85,286 300,348 300,356 85,294"
            fill="#DCD6CF"
            opacity="0.85"
          />
          <polygon
            points="300,348 515,286 515,294 300,356"
            fill="#CEC7BF"
            opacity="0.9"
          />

          {/* Upper Elevated Folio / Page 3 */}
          <polygon
            points="120,242 300,296 480,242 300,196"
            fill="#FFFFFF"
            stroke="#DDD8D8"
            strokeWidth="1.2"
          />
          {/* Page 3 Front Edge Highlight */}
          <polygon
            points="120,242 300,296 300,302 120,248"
            fill="#EAE5DE"
          />
          <polygon
            points="300,296 480,242 480,248 300,302"
            fill="#DDD6CE"
          />
        </g>

        {/* Central Geometric Knowledge Core (Aubergine + Marigold Faceted Polyhedron) */}
        <g className="sculpture-core" filter="url(#heroShadow)">
          {/* Left Aubergine Shadow Face */}
          <polygon
            points="300,55 175,185 300,285 300,55"
            fill="url(#aubergineFacet)"
            stroke="#4D3452"
            strokeWidth="0.8"
          />

          {/* Bottom Dark Aubergine Underside */}
          <polygon
            points="175,185 300,285 425,185 300,195"
            fill="url(#aubergineDark)"
            opacity="0.9"
          />

          {/* Right Illuminating Facet with Radiant Marigold Light */}
          <polygon
            points="300,55 425,185 300,285 300,55"
            fill="url(#marigoldGlow)"
            stroke="#FAF8F3"
            strokeWidth="0.75"
            opacity="0.96"
          />

          {/* Upper Crown Facet: Translucent Ivory Peak Crystal */}
          <polygon
            points="300,55 235,122 300,165 365,122"
            fill="#FFFFFF"
            opacity="0.92"
            stroke="#FAF8F3"
            strokeWidth="0.9"
          />

          {/* Dynamic Marigold Refraction Secondary Facet */}
          <polygon
            points="300,165 365,122 425,185 300,230"
            fill="url(#burntAmberEdge)"
            opacity="0.88"
          />

          {/* Translucent Left Core Refraction */}
          <polygon
            points="300,165 235,122 175,185 300,230"
            fill="#29152F"
            opacity="0.45"
          />

          {/* Sharp High-Key Golden Apex Beacon */}
          <polygon
            points="300,55 292,85 300,95 308,85"
            fill="#FFFFFF"
            opacity="0.95"
          />
        </g>

        {/* Floating Satellite Geometric Markers (Discover, Practice, Prove) */}
        <g className="floating-satellites">
          {/* Satellite 1: Top Left - Concept Diamond */}
          <g transform="translate(68, 125)">
            <rect
              x="-14"
              y="-14"
              width="28"
              height="28"
              rx="5"
              transform="rotate(45)"
              fill="#FAF8F3"
              stroke="#E9A83A"
              strokeWidth="1.8"
            />
            <circle cx="0" cy="0" r="3.5" fill="#29152F" />
          </g>

          {/* Satellite 2: Top Right - Verified Assessment Beacon */}
          <g transform="translate(532, 135)">
            <circle cx="0" cy="0" r="16" fill="#FFFFFF" stroke="#DDD8D8" strokeWidth="1.2" />
            <circle cx="0" cy="0" r="7.5" fill="#E9A83A" />
            <circle cx="0" cy="0" r="2.8" fill="#FFFFFF" />
          </g>

          {/* Satellite 3: Bottom Left - Practical Skill Pillar Node */}
          <g transform="translate(42, 382)">
            <line
              x1="0"
              y1="0"
              x2="38"
              y2="-22"
              stroke="#B96D2B"
              strokeWidth="1.5"
              strokeDasharray="2.5 2.5"
            />
            <circle cx="38" cy="-22" r="5" fill="#B96D2B" />
            <circle cx="38" cy="-22" r="2" fill="#FAF8F3" />
          </g>

          {/* Satellite 4: Right Milestone Mastery Needle */}
          <g transform="translate(558, 355)">
            <polygon
              points="0,-18 10,0 0,18 -10,0"
              fill="#29152F"
              opacity="0.9"
            />
            <circle cx="0" cy="0" r="3.2" fill="#E9A83A" />
          </g>
        </g>

        {/* Refined Blueprint Typography & Calibration Axes */}
        <g
          stroke="#918A91"
          strokeWidth="0.5"
          opacity="0.75"
          fontSize="9.5"
          fontFamily="ui-monospace, monospace"
        >
          <text x="42" y="458" fill="#706A72" letterSpacing="0.12em">
            PRAGYAX // FOUNDATION.GEOMETRY
          </text>
          <text x="430" y="458" fill="#E9A83A" fontWeight="600" letterSpacing="0.1em">
            NODE.01 / PROVE [ACTIVE]
          </text>
        </g>
      </svg>
    </div>
  );
}

export default HeroArtwork;
