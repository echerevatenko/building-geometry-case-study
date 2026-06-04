import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { colors } from "../styles.js";

// Layer colours.
const SITE = 0x4a90d9; // plot boundary — blue outline
const BASE = 0x1a7f37; // buildable base — green fill on the ground
const FOOT = 0xe8810c; // massing — orange extruded volume
const FOOT_EDGE = 0x9a5300;
const GRID = 0xdcdce2;

// Pull a flat ring [[x, y], ...] out of either a bare `{coordinates: ring}` (how the
// frontend stores site_polygon) or a GeoJSON Polygon `{coordinates: [ring, ...]}`.
function ringOf(geom) {
  const c = geom?.coordinates;
  if (!Array.isArray(c) || c.length === 0) return null;
  const first = c[0];
  if (Array.isArray(first) && typeof first[0] === "number") return c;
  if (Array.isArray(first) && Array.isArray(first[0])) return first;
  return null;
}

function fitBounds(rings) {
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const ring of rings) {
    for (const [x, y] of ring) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null;
}

function niceStep(span) {
  const raw = span / 10 || 1;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / pow;
  return (f >= 5 ? 5 : f >= 2 ? 2 : 1) * pow;
}

// All geometry is authored in the XY plane; the parent group is tilted so XY lies
// flat on the ground and a shape extruded along +Z stands up.
const shapeFromRing = (ring) => new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y)));

function outline(ring, color, z) {
  const pts = ring.map(([x, y]) => new THREE.Vector3(x, y, z));
  if (pts.length) pts.push(pts[0].clone());
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color }));
  return line;
}

function fill(ring, color, opacity, z) {
  const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shapeFromRing(ring)), mat);
  mesh.position.z = z;
  return mesh;
}

function massing(ring, height) {
  const geo = new THREE.ExtrudeGeometry(shapeFromRing(ring), { depth: height, bevelEnabled: false });
  const mesh = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: FOOT, transparent: true, opacity: 0.9, roughness: 0.85, metalness: 0 }),
  );
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: FOOT_EDGE }));
  return [mesh, edges];
}

function grid(b) {
  const step = niceStep(Math.max(b.maxX - b.minX, b.maxY - b.minY));
  const x0 = Math.floor(b.minX / step) * step;
  const y0 = Math.floor(b.minY / step) * step;
  const pts = [];
  for (let x = x0; x <= b.maxX; x += step) pts.push(new THREE.Vector3(x, b.minY, 0), new THREE.Vector3(x, b.maxY, 0));
  for (let y = y0; y <= b.maxY; y += step) pts.push(new THREE.Vector3(b.minX, y, 0), new THREE.Vector3(b.maxX, y, 0));
  return new THREE.LineSegments(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: GRID }),
  );
}

function disposeGroup(group) {
  group.traverse((o) => {
    o.geometry?.dispose();
    o.material?.dispose();
  });
  group.clear();
}

export default function Scene({ site, base, footprint, height }) {
  const containerRef = useRef(null);
  const dataRef = useRef({ site, base, footprint, height });
  const apiRef = useRef(null);
  const framedRef = useRef(null);
  const [webglError, setWebglError] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch (err) {
      console.error("Scene: could not create a WebGL context", err);
      setWebglError(true);
      return;
    }
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0xf4f4f6, 1);
    renderer.domElement.style.display = "block";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1_000_000);
    scene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const sun = new THREE.DirectionalLight(0xffffff, 0.55);
    sun.position.set(0.5, 1, 0.8);
    scene.add(sun);

    // Tilt so the authored XY plane is the ground and +Z extrusions point up.
    const group = new THREE.Group();
    group.rotation.x = -Math.PI / 2;
    scene.add(group);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false; // render-on-change (no rAF loop), so no inertia
    controls.addEventListener("change", render);

    function render() {
      renderer.render(scene, camera);
    }

    function resize() {
      const w = container.clientWidth || 1;
      const h = container.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      render();
    }

    // Re-frame the camera only when the site changes, so generating a massing
    // (which changes the footprint, not the plot) doesn't reset the user's orbit.
    function frame(b, h) {
      const sig = `${b.minX},${b.minY},${b.maxX},${b.maxY}`;
      if (framedRef.current === sig) return;
      framedRef.current = sig;
      const cx = (b.minX + b.maxX) / 2;
      const cy = (b.minY + b.maxY) / 2;
      const span = Math.max(b.maxX - b.minX, b.maxY - b.minY, h || 0, 10);
      const d = span * 1.5;
      // Comfortable iso-ish angle: up and to one corner, looking at the plot centre.
      camera.position.set(cx + d * 0.8, d * 0.7, -cy + d * 0.8);
      controls.target.set(cx, Math.min(h || 0, span) * 0.2, -cy);
      controls.update();
    }

    function rebuild() {
      disposeGroup(group);
      const { site, base, footprint, height } = dataRef.current;
      const siteRing = ringOf(site);
      const baseRing = ringOf(base);
      const footRing = ringOf(footprint);
      const b = fitBounds([siteRing, baseRing, footRing].filter(Boolean));
      if (!b) {
        render();
        return;
      }
      group.add(grid(b));
      if (siteRing) group.add(outline(siteRing, SITE, 0.04));
      if (baseRing) {
        group.add(fill(baseRing, BASE, 0.2, 0.02));
        group.add(outline(baseRing, BASE, 0.05));
      }
      if (footRing && height > 0) {
        for (const m of massing(footRing, height)) group.add(m);
      } else if (footRing) {
        group.add(fill(footRing, FOOT, 0.55, 0.06));
        group.add(outline(footRing, FOOT, 0.07));
      }
      frame(b, height);
      render();
    }

    apiRef.current = { rebuild, resize };
    rebuild();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    return () => {
      observer.disconnect();
      controls.dispose();
      disposeGroup(group);
      renderer.dispose();
      container.removeChild(renderer.domElement);
      apiRef.current = null;
    };
  }, []);

  useEffect(() => {
    dataRef.current = { site, base, footprint, height };
    apiRef.current?.rebuild();
  }, [site, base, footprint, height]);

  const swatch = (color) => ({
    width: 12,
    height: 12,
    borderRadius: 2,
    background: `#${color.toString(16).padStart(6, "0")}`,
    flex: "0 0 auto",
  });
  const legendRow = { display: "flex", alignItems: "center", gap: "0.4rem" };
  const empty = !ringOf(site) && !ringOf(base) && !ringOf(footprint);

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%", height: "100%" }}>
      {(webglError || empty) && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            padding: "1rem",
            color: webglError ? colors.infeasible : "#999",
            fontSize: "0.9rem",
            pointerEvents: "none",
          }}
        >
          {webglError
            ? "WebGL isn't available in this browser, so the 3D view can't render. Enable hardware acceleration (or chrome://flags → “Override software rendering list”) and reload."
            : "Select a polygon with a saved site to see it here."}
        </div>
      )}
      <div
        style={{
          position: "absolute",
          top: 10,
          left: 10,
          display: "flex",
          flexDirection: "column",
          gap: "0.3rem",
          fontSize: "0.75rem",
          color: "#555",
          background: "rgba(255,255,255,0.85)",
          padding: "0.4rem 0.55rem",
          borderRadius: 6,
          pointerEvents: "none",
        }}
      >
        <span style={legendRow}>
          <i style={swatch(SITE)} /> Site polygon
        </span>
        <span style={legendRow}>
          <i style={swatch(BASE)} /> Buildable base
        </span>
        <span style={legendRow}>
          <i style={swatch(FOOT)} /> Massing
        </span>
        <span style={{ color: "#999" }}>drag to orbit · scroll to zoom</span>
      </div>
    </div>
  );
}
