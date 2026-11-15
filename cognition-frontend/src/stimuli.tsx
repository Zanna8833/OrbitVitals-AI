// Procedural stimuli. The real battery uses licensed pictures (3D figures, fractals, actor photos):
// here every stimulus is drawn from a seed, so each session gets a new set and nothing is copied.

import type { JSX } from 'react'
import { Random } from './random'

// ---------- VOLT: wireframe 3D objects with one blue facet (NASA TM-2020-5008023) ----------

export type WireObject = { base: [number, number][]; pyramid: boolean; depth: number; rx: number; ry: number; blueFace: number }

export function makeWireObject(random: Random): WireObject {
  // An irregular convex base polygon, extruded into a prism or raised into a pyramid
  const corners = random.int(3, 7)
  const angles: number[] = []
  for (let i = 0; i < corners; i++) {
    angles.push(random.next() * Math.PI * 2)
  }
  angles.sort(function (a, b) { return a - b })
  const base: [number, number][] = []
  for (const angle of angles) {
    const radius = 55 + random.next() * 30
    base.push([Math.cos(angle) * radius, Math.sin(angle) * radius])
  }
  return {
    base: base,
    pyramid: random.next() < 0.4,
    depth: 40 + random.next() * 60,
    rx: 20 + random.next() * 50,
    ry: random.next() * 360,
    blueFace: random.int(0, corners),
  }
}

export function wireObjectKey(object: WireObject): string {
  const parts: string[] = [String(object.pyramid), String(object.base.length)]
  for (const corner of object.base) {
    parts.push(Math.round(corner[0] / 8) + ',' + Math.round(corner[1] / 8))
  }
  return parts.join(';')
}

export function WireObjectPicture(props: { object: WireObject; size: number }): JSX.Element {
  const object = props.object
  const rx = (object.rx * Math.PI) / 180
  const ry = (object.ry * Math.PI) / 180
  // Rotate around the vertical axis, then tilt, then project orthographically
  function project(x: number, y: number, z: number): [number, number] {
    const x1 = x * Math.cos(ry) - y * Math.sin(ry)
    const y1 = x * Math.sin(ry) + y * Math.cos(ry)
    const y2 = y1 * Math.cos(rx) - z * Math.sin(rx)
    return [x1, y2]
  }
  const half = object.depth / 2
  const bottom: [number, number][] = []
  const top: [number, number][] = []
  for (const corner of object.base) {
    bottom.push(project(corner[0], corner[1], -half))
    if (!object.pyramid) {
      top.push(project(corner[0], corner[1], half))
    }
  }
  const apex = project(0, 0, half)
  // Faces: one per side, plus the base; the blue one is filled
  const faces: [number, number][][] = []
  for (let i = 0; i < object.base.length; i++) {
    const next = (i + 1) % object.base.length
    if (object.pyramid) {
      faces.push([bottom[i], bottom[next], apex])
    } else {
      faces.push([bottom[i], bottom[next], top[next], top[i]])
    }
  }
  faces.push(bottom)
  const lines: JSX.Element[] = []
  for (let i = 0; i < faces.length; i++) {
    lines.push(
      <polygon key={i} points={pointsText(faces[i])} fill={i === object.blueFace ? '#2f6fe0' : 'none'}
        fillOpacity={0.85} stroke="#111" strokeWidth={1.6} strokeLinejoin="round" />,
    )
  }
  return (
    <svg width={props.size} height={props.size} viewBox="-110 -110 220 220">
      {lines}
    </svg>
  )
}

function pointsText(points: [number, number][]): string {
  const parts: string[] = []
  for (const point of points) {
    parts.push(point[0].toFixed(1) + ',' + point[1].toFixed(1))
  }
  return parts.join(' ')
}

// ---------- F2B: fractal pictures ----------

export type FractalSpec = { sides: number; depth: number; ratio: number; twist: number; hue: number; hue2: number }

export function makeFractal(random: Random): FractalSpec {
  return {
    sides: random.int(3, 7),
    depth: random.int(2, 3),
    ratio: 0.32 + random.next() * 0.16,
    twist: random.next() * 60,
    hue: random.int(0, 359),
    hue2: random.int(0, 359),
  }
}

export function Fractal(props: { spec: FractalSpec; size: number }): JSX.Element {
  const spec = props.spec
  const shapes: JSX.Element[] = []
  // Each level draws a polygon and smaller copies at its corners
  function draw(cx: number, cy: number, radius: number, angle: number, level: number): void {
    const corners: [number, number][] = []
    for (let i = 0; i < spec.sides; i++) {
      const a = (angle + (360 * i) / spec.sides) * (Math.PI / 180)
      corners.push([cx + radius * Math.cos(a), cy + radius * Math.sin(a)])
    }
    const lightness = 30 + level * 15
    let hue = spec.hue
    if (level % 2 === 1) {
      hue = spec.hue2
    }
    shapes.push(
      <polygon key={shapes.length} points={pointsText(corners)} fill={'hsl(' + hue + ',70%,' + lightness + '%)'}
        stroke="#0b0f17" strokeWidth={0.8} opacity={0.9} />,
    )
    if (level >= spec.depth) {
      return
    }
    for (const corner of corners) {
      draw(corner[0], corner[1], radius * spec.ratio * 1.4, angle + spec.twist, level + 1)
    }
  }
  draw(0, 0, 55, -90, 0)
  return (
    <svg width={props.size} height={props.size} viewBox="-110 -110 220 220">
      <rect x={-110} y={-110} width={220} height={220} fill="#05070c" />
      {shapes}
    </svg>
  )
}

// ---------- ERT: faces ----------

export type Emotion = 'happy' | 'sad' | 'angry' | 'fearful' | 'no emotion'
export const EMOTIONS: Emotion[] = ['happy', 'sad', 'angry', 'fearful', 'no emotion']

export type FaceSpec = { emotion: Emotion; intensity: number; skin: string; hair: string; width: number; hairStyle: number }

const SKIN_TONES = ['#f1d0b5', '#e0b08f', '#c68c62', '#9b6a45', '#6f4a31']
const HAIR_COLOURS = ['#1f1a17', '#4a3426', '#8a6a3d', '#b9b2a6', '#6b2f1f']

export function makeFace(random: Random, emotion: Emotion): FaceSpec {
  return {
    emotion: emotion,
    // Mostly low intensities, as in the real test
    intensity: 0.35 + random.next() * 0.5,
    skin: random.pick(SKIN_TONES),
    hair: random.pick(HAIR_COLOURS),
    width: 0.86 + random.next() * 0.16,
    hairStyle: random.int(0, 2),
  }
}

export function Face(props: { spec: FaceSpec; size: number }): JSX.Element {
  const spec = props.spec
  const k = spec.intensity
  let mouthCurve = 0
  let mouthOpen = 0
  let browTilt = 0 // positive = inner ends down (angry), negative = inner ends up (sad, fear)
  let browRaise = 0
  let eyeOpen = 1
  if (spec.emotion === 'happy') {
    mouthCurve = 14 * k
    eyeOpen = 1 - 0.3 * k
  } else if (spec.emotion === 'sad') {
    mouthCurve = -9 * k
    browTilt = -9 * k
    eyeOpen = 1 - 0.2 * k
  } else if (spec.emotion === 'angry') {
    mouthCurve = -3 * k
    browTilt = 11 * k
    browRaise = -4 * k
    eyeOpen = 1 - 0.35 * k
  } else if (spec.emotion === 'fearful') {
    mouthOpen = 9 * k
    browTilt = -6 * k
    browRaise = 7 * k
    eyeOpen = 1 + 0.5 * k
  }
  const faceWidth = 62 * spec.width
  const eyeHeight = 6 * eyeOpen
  const browY = -26 - browRaise
  let hair = <path d={'M ' + -faceWidth + ' -20 Q 0 -110 ' + faceWidth + ' -20 Q 30 -62 ' + -faceWidth + ' -20'} fill={spec.hair} />
  if (spec.hairStyle === 1) {
    hair = <path d={'M ' + -faceWidth + ' 0 Q -70 -95 0 -88 Q 70 -95 ' + faceWidth + ' 0 L ' + (faceWidth - 8) + ' -40 Q 0 -70 ' + (-faceWidth + 8) + ' -40 Z'} fill={spec.hair} />
  } else if (spec.hairStyle === 2) {
    hair = <path d={'M ' + -faceWidth + ' 40 Q -80 -100 0 -86 Q 80 -100 ' + faceWidth + ' 40 L ' + (faceWidth - 6) + ' -30 Q 0 -66 ' + (-faceWidth + 6) + ' -30 Z'} fill={spec.hair} />
  }
  return (
    <svg width={props.size} height={props.size} viewBox="-100 -100 200 200">
      <rect x={-100} y={-100} width={200} height={200} fill="#cfd5dd" />
      <rect x={-34} y={50} width={68} height={60} fill={spec.skin} />
      <ellipse cx={0} cy={0} rx={faceWidth} ry={78} fill={spec.skin} stroke="#5a463a" strokeWidth={1} />
      {hair}
      {/* eyes */}
      <ellipse cx={-24} cy={-8} rx={9} ry={eyeHeight} fill="#fff" stroke="#3a2c24" strokeWidth={1} />
      <ellipse cx={24} cy={-8} rx={9} ry={eyeHeight} fill="#fff" stroke="#3a2c24" strokeWidth={1} />
      <circle cx={-24} cy={-8} r={Math.min(4, eyeHeight)} fill="#2b2420" />
      <circle cx={24} cy={-8} r={Math.min(4, eyeHeight)} fill="#2b2420" />
      {/* brows: the inner end moves with browTilt */}
      <line x1={-38} y1={browY} x2={-12} y2={browY + browTilt} stroke="#2b2420" strokeWidth={4} strokeLinecap="round" />
      <line x1={38} y1={browY} x2={12} y2={browY + browTilt} stroke="#2b2420" strokeWidth={4} strokeLinecap="round" />
      {/* nose */}
      <path d="M 0 0 L -6 20 L 4 22" fill="none" stroke="#7a5c48" strokeWidth={2} />
      {/* mouth */}
      <path d={'M -22 42 Q 0 ' + (42 + mouthCurve) + ' 22 42 Q 0 ' + (42 + mouthCurve + mouthOpen) + ' -22 42'}
        fill={mouthOpen > 1 ? '#5a2a2a' : 'none'} stroke="#7a3b3b" strokeWidth={3} strokeLinecap="round" />
    </svg>
  )
}

// ---------- AM: figures in three shades (NASA TM-2020-5008023: circles, triangles, hexagons, crosses, stars;
// light blue, dark blue or unfilled) ----------

export type FigureShape = 'circle' | 'triangle' | 'hexagon' | 'cross' | 'star'
export type Shade = 'light' | 'dark' | 'unfilled'
export type Figure = { shape: FigureShape; shade: Shade }

export const FIGURE_SHAPES: FigureShape[] = ['circle', 'triangle', 'hexagon', 'cross', 'star']
export const SHADES: Shade[] = ['light', 'dark', 'unfilled']

function regularPolygon(sides: number, radius: number, startAngle: number): [number, number][] {
  const points: [number, number][] = []
  for (let i = 0; i < sides; i++) {
    const angle = startAngle + (2 * Math.PI * i) / sides
    points.push([radius * Math.cos(angle), radius * Math.sin(angle)])
  }
  return points
}

export function FigurePicture(props: { figure: Figure }): JSX.Element {
  let fill = 'none'
  if (props.figure.shade === 'light') fill = '#8fb8f5'
  if (props.figure.shade === 'dark') fill = '#1f4fb8'
  const style = { fill: fill, stroke: '#1f4fb8', strokeWidth: 3, strokeLinejoin: 'round' as const }
  let element: JSX.Element
  const shape = props.figure.shape
  if (shape === 'circle') {
    element = <circle cx={0} cy={0} r={30} {...style} />
  } else if (shape === 'triangle') {
    element = <polygon points={pointsText(regularPolygon(3, 34, -Math.PI / 2))} {...style} />
  } else if (shape === 'hexagon') {
    element = <polygon points={pointsText(regularPolygon(6, 32, 0))} {...style} />
  } else if (shape === 'cross') {
    element = <polygon points="-10,-32 10,-32 10,-10 32,-10 32,10 10,10 10,32 -10,32 -10,10 -32,10 -32,-10 -10,-10" {...style} />
  } else {
    const points: [number, number][] = []
    for (let i = 0; i < 10; i++) {
      const angle = -Math.PI / 2 + (Math.PI * i) / 5
      let radius = 34
      if (i % 2 === 1) radius = 14
      points.push([radius * Math.cos(angle), radius * Math.sin(angle)])
    }
    element = <polygon points={pointsText(points)} {...style} />
  }
  return <svg viewBox="-40 -40 80 80">{element}</svg>
}

// ---------- MRT: simple shapes on a grid ----------

export type ShapeKind = 'circle' | 'square' | 'triangle' | 'diamond'

export const SHAPES: ShapeKind[] = ['circle', 'square', 'triangle', 'diamond']
export const COLOURS = ['#e5484d', '#2f6fe0', '#d9a520', '#2e9e62']

export function ShapeGlyph(props: { shape: ShapeKind; colour: string; filled: boolean; x: number; y: number; r: number; rotate?: number }): JSX.Element {
  const fill = props.filled ? props.colour : 'none'
  const common = { fill: fill, stroke: props.colour, strokeWidth: 3 }
  let element: JSX.Element
  const r = props.r
  if (props.shape === 'circle') {
    element = <circle cx={0} cy={0} r={r} {...common} />
  } else if (props.shape === 'square') {
    element = <rect x={-r} y={-r} width={2 * r} height={2 * r} {...common} />
  } else if (props.shape === 'triangle') {
    element = <polygon points={'0,' + -r + ' ' + r + ',' + r * 0.8 + ' ' + -r + ',' + r * 0.8} {...common} />
  } else {
    element = <polygon points={'0,' + -r + ' ' + r + ',0 0,' + r + ' ' + -r + ',0'} {...common} />
  }
  let rotation = 0
  if (props.rotate !== undefined) {
    rotation = props.rotate
  }
  return <g transform={'translate(' + props.x + ',' + props.y + ') rotate(' + rotation + ')'}>{element}</g>
}

// ---------- DSST: symbols ----------

export const SYMBOL_PATHS = [
  'M -14 -14 L 14 14 M 14 -14 L -14 14',
  'M -14 0 L 14 0 M 0 -14 L 0 14 M -14 -14 L 14 -14',
  'M -14 14 L 0 -14 L 14 14',
  'M -14 -14 L 14 -14 L 14 14',
  'M -14 0 Q 0 -24 14 0 Q 0 24 -14 0',
  'M -14 -14 L -14 14 L 14 14 M 0 -14 L 0 4',
  'M -12 -14 L 12 -14 L -12 14 L 12 14',
  'M 0 -14 A 14 14 0 1 1 -0.1 -14 M 0 -6 L 0 6',
  'M -14 6 L -4 -14 L 6 6 L 14 -8',
  'M -14 -4 L 14 -4 M -14 6 L 14 6 M -6 -14 L -6 14',
  'M -14 14 L -14 -14 L 14 -14 L 14 2 L -2 2',
  'M -14 0 L 0 -14 L 14 0 L 0 14 Z M -4 0 L 4 0',
]

export function SymbolGlyph(props: { index: number; size: number }): JSX.Element {
  return (
    <svg width={props.size} height={props.size} viewBox="-20 -20 40 40">
      <path d={SYMBOL_PATHS[props.index]} fill="none" stroke="currentColor" strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
