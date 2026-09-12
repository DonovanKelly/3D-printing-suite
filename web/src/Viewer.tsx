/** Render the exported material meshes with orbit controls; 2D modes use generated safe SVGs. */
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Box, RotateCcw, Rotate3D, ZoomIn, ZoomOut } from "lucide-react";
import type { Preview, View } from "./types";

function svgUrl(value: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(value)}`;
}

export function Viewer({ preview, view }: { preview: Preview; view: View }) {
  const host = useRef<HTMLDivElement>(null);
  const actions = useRef({
    zoom: (_factor: number) => {},
    reset: () => {},
    rotate: () => {},
    top: () => {},
  });
  const [fallback, setFallback] = useState(false);
  const [rotating, setRotating] = useState(false);

  useEffect(() => {
    if (!host.current || view !== "relief") return;
    const target = host.current;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setFallback(true);
      return;
    }
    setFallback(false);
    setRotating(false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    target.appendChild(renderer.domElement);
    renderer.domElement.setAttribute(
      "aria-label",
      "Interactive 3D relief. Drag to orbit and scroll to zoom.",
    );
    const scene = new THREE.Scene();
    const settings = preview.manifest.settings;
    const width = settings.width_mm,
      height = settings.height_mm;
    const size = Math.max(width, height);
    const camera = new THREE.OrthographicCamera(
      -size,
      size,
      size,
      -size,
      0.1,
      size * 20,
    );
    camera.up.set(-0.24, 0.97, 0);
    const initial = new THREE.Vector3(size * 0.1, -size * 0.85, size * 1.5);
    camera.position.copy(initial);
    camera.lookAt(0, 0, 0);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = true;
    controls.minZoom = 0.35;
    controls.maxZoom = 5;
    controls.autoRotateSpeed = 0.6;
    controls.target.set(0, 0, 0);

    const group = new THREE.Group();
    scene.add(group);
    for (const data of preview.meshes) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(data.vertices, 3),
      );
      geometry.setIndex(data.faces);
      geometry.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({
        color:
          data.material === "background"
            ? settings.background_color
            : settings.artwork_color,
        roughness: 0.84,
        metalness: 0,
        flatShading: true,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(
        data.origin[0] - width / 2,
        data.origin[1] - height / 2,
        0,
      );
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      group.add(mesh);
    }
    scene.add(new THREE.AmbientLight(0xffffff, 1.4));
    const sunlight = new THREE.DirectionalLight(0xffffff, 2.2);
    sunlight.position.set(-size * 0.6, size * 0.8, size * 2);
    sunlight.castShadow = true;
    sunlight.shadow.mapSize.set(2048, 2048);
    Object.assign(sunlight.shadow.camera, {
      left: -size,
      right: size,
      top: size,
      bottom: -size,
      near: 0.1,
      far: size * 5,
    });
    sunlight.shadow.bias = -0.00003;
    sunlight.shadow.normalBias = 0.05;
    scene.add(sunlight);
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(size * 4, size * 4),
      new THREE.ShadowMaterial({ opacity: 0.17 }),
    );
    floor.position.z = -0.15;
    floor.receiveShadow = true;
    scene.add(floor);

    function resize() {
      const w = target.clientWidth,
        h = target.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      const aspect = w / h;
      const halfHeight = Math.max(height * 0.66, (width * 0.66) / aspect);
      camera.left = -halfHeight * aspect;
      camera.right = halfHeight * aspect;
      camera.top = halfHeight;
      camera.bottom = -halfHeight;
      camera.updateProjectionMatrix();
    }
    const observer = new ResizeObserver(resize);
    observer.observe(target);
    resize();
    actions.current = {
      zoom: (factor) => {
        camera.zoom = Math.min(5, Math.max(0.35, camera.zoom * factor));
        camera.updateProjectionMatrix();
      },
      reset: () => {
        camera.position.copy(initial);
        camera.zoom = 1;
        camera.up.set(-0.24, 0.97, 0);
        controls.target.set(0, 0, 0);
        controls.autoRotate = false;
        camera.updateProjectionMatrix();
        controls.update();
        setRotating(false);
      },
      rotate: () => {
        controls.autoRotate = !controls.autoRotate;
        setRotating(controls.autoRotate);
      },
      top: () => {
        camera.position.set(0, 0, size * 1.5);
        camera.up.set(0, 1, 0);
        controls.target.set(0, 0, 0);
        controls.autoRotate = false;
        controls.update();
        setRotating(false);
      },
    };
    let frame: number;
    const render = () => {
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(render);
    };
    render();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material)
            ? object.material
            : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [preview, view]);

  return (
    <>
      {view === "relief" && <div className="webgl-host" ref={host} />}
      {(view !== "relief" || fallback) && (
        <div className="flat-preview">
          <img
            src={svgUrl(
              view === "vector" ? preview.vector_svg : preview.assembly_svg,
            )}
            alt={
              view === "vector"
                ? "Traced black-and-white vector artwork"
                : "Front-view assembly map with piece labels"
            }
          />
          {fallback && view === "relief" && (
            <p className="hint">
              3D rendering is unavailable in this browser. Showing your assembly
              map.
            </p>
          )}
        </div>
      )}
      {view === "relief" && !fallback && (
        <div className="canvas-tools">
          <div className="tool-strip">
            <button
              aria-label="Auto rotate"
              aria-pressed={rotating}
              onClick={() => actions.current.rotate()}
            >
              <Rotate3D />
            </button>
            <span />
            <button
              aria-label="View from top"
              onClick={() => actions.current.top()}
            >
              <Box />
            </button>
            <span />
            <button
              aria-label="Zoom out"
              onClick={() => actions.current.zoom(0.85)}
            >
              <ZoomOut />
            </button>
            <button
              aria-label="Zoom in"
              onClick={() => actions.current.zoom(1.15)}
            >
              <ZoomIn />
            </button>
            <span />
            <button
              aria-label="Reset view"
              onClick={() => actions.current.reset()}
            >
              <RotateCcw />
            </button>
          </div>
          <p>Drag to orbit · Scroll to zoom</p>
        </div>
      )}
      {view !== "relief" && (
        <div className="flat-caption">
          {view === "assembly"
            ? "Front view · Row 01 is the top"
            : "Black areas become raised artwork · Image proportions are preserved"}
        </div>
      )}
    </>
  );
}
