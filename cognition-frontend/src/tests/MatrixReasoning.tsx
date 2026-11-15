import { useEffect, useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import { COLOURS, SHAPES, ShapeGlyph } from '../stimuli'
import type { ShapeKind } from '../stimuli'
import type { CorrectTrial, TestProps } from '../types'

// 12 grid patterns of increasing difficulty, one cell missing; the test stops after 3 errors in a row
// (Basner et al. 2015/2021). Time limit per item: not given in the sources read, our choice.
const ITEM_COUNT = 12
const STOP_AFTER_ERRORS = 3
const ITEM_TIME_LIMIT_MS = 30000
const OPTION_COUNT = 5 // five options (NASA TM-2020-5008023)

type Cell = { shape: ShapeKind; count: number; colour: string; rotation: number }
type Item = { grid: Cell[]; options: Cell[]; answer: number }

function sameCell(a: Cell, b: Cell): boolean {
  return a.shape === b.shape && a.count === b.count && a.colour === b.colour && a.rotation === b.rotation
}

function makeItem(random: Random, level: number): Item {
  const shapes = random.shuffle(SHAPES).slice(0, 3)
  const colours = random.shuffle(COLOURS).slice(0, 3)
  const counts = random.shuffle([1, 2, 3])
  const rotations = [0, 30, 60]
  const baseColour = colours[0]
  const grid: Cell[] = []
  for (let row = 0; row < 3; row++) {
    for (let column = 0; column < 3; column++) {
      // More rules at each level: shape by row, count by column, colour on the diagonals, rotation by column
      let shape = shapes[row]
      if (level >= 4) {
        shape = shapes[(row + column) % 3]
      }
      let count = 1
      if (level >= 2) {
        count = counts[column]
      }
      let colour = baseColour
      if (level >= 3) {
        colour = colours[(row + 2 * column) % 3]
      }
      let rotation = 0
      if (level >= 4) {
        rotation = rotations[(column + row) % 3]
      }
      grid.push({ shape: shape, count: count, colour: colour, rotation: rotation })
    }
  }
  const correct = grid[8]
  // Distractors change one feature of the right answer
  const options: Cell[] = [correct]
  let guard = 0
  while (options.length < OPTION_COUNT && guard < 200) {
    guard = guard + 1
    const option = { ...correct }
    const change = random.int(0, 3)
    if (change === 0) option.shape = random.pick(SHAPES)
    if (change === 1) option.count = random.int(1, 3)
    if (change === 2) option.colour = random.pick(COLOURS)
    if (change === 3) option.rotation = random.pick(rotations)
    let duplicate = false
    for (const existing of options) {
      if (sameCell(existing, option)) duplicate = true
    }
    if (!duplicate) options.push(option)
  }
  const shuffled = random.shuffle(options)
  let answer = 0
  for (let i = 0; i < shuffled.length; i++) {
    if (sameCell(shuffled[i], correct)) answer = i
  }
  return { grid: grid, options: shuffled, answer: answer }
}

function CellPicture(props: { cell: Cell; size: number }) {
  const glyphs = []
  for (let i = 0; i < props.cell.count; i++) {
    const x = (i - (props.cell.count - 1) / 2) * 30
    glyphs.push(<ShapeGlyph key={i} shape={props.cell.shape} colour={props.cell.colour} filled={true} x={x} y={0} r={11} rotate={props.cell.rotation} />)
  }
  return <svg width={props.size} height={props.size} viewBox="-50 -50 100 100">{glyphs}</svg>
}

export default function MatrixReasoning(props: TestProps) {
  const items = useMemo(function () {
    const random = new Random(props.seed)
    const list: Item[] = []
    for (let i = 0; i < ITEM_COUNT; i++) {
      list.push(makeItem(random, 1 + Math.floor(i / 3)))
    }
    return list
  }, [props.seed])
  const [index, setIndex] = useState(0)
  const trials = useRef<CorrectTrial[]>([])
  const errorsInRow = useRef(0)
  const shownAt = useRef(performance.now())

  function record(correct: boolean, reactionTime: number | null) {
    trials.current.push({ rt_ms: reactionTime, correct: correct })
    if (correct) {
      errorsInRow.current = 0
    } else {
      errorsInRow.current = errorsInRow.current + 1
    }
    if (index + 1 === ITEM_COUNT || errorsInRow.current === STOP_AFTER_ERRORS) {
      // Items not reached count as wrong
      while (trials.current.length < ITEM_COUNT) {
        trials.current.push({ rt_ms: null, correct: false })
      }
      props.onFinish({ trials: trials.current })
      return
    }
    shownAt.current = performance.now()
    setIndex(index + 1)
  }

  useEffect(function () {
    const timer = window.setTimeout(function () {
      record(false, null)
    }, ITEM_TIME_LIMIT_MS)
    return function () {
      window.clearTimeout(timer)
    }
  }, [index])

  const item = items[index]
  const cells = []
  for (let i = 0; i < 9; i++) {
    if (i === 8) {
      cells.push(<div key={i} className="mrt-cell missing">?</div>)
    } else {
      cells.push(<div key={i} className="mrt-cell"><CellPicture cell={item.grid[i]} size={96} /></div>)
    }
  }
  const options = []
  for (let i = 0; i < item.options.length; i++) {
    options.push(
      <button key={i} className="mrt-option" onClick={function () { record(i === item.answer, Math.round(performance.now() - shownAt.current)) }}>
        <CellPicture cell={item.options[i]} size={80} />
      </button>,
    )
  }
  return (
    <div className="stage">
      <div className="mrt-grid">{cells}</div>
      <div className="mrt-options">{options}</div>
      <div className="trial-counter">{index + 1} / {ITEM_COUNT}</div>
    </div>
  )
}
