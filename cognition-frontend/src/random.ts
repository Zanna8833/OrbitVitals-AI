// Seeded random numbers: each session (astronaut + mission day) gets its own stimulus set,
// like the 15 alternate versions of the real battery, and the same session can be rebuilt.

export class Random {
  private state: number

  constructor(seed: number) {
    this.state = seed >>> 0
  }

  // mulberry32
  next(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0
    let t = this.state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t = t ^ (t + Math.imul(t ^ (t >>> 7), t | 61))
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }

  // Integer between min and max, both included
  int(min: number, max: number): number {
    return min + Math.floor(this.next() * (max - min + 1))
  }

  pick<T>(items: T[]): T {
    return items[this.int(0, items.length - 1)]
  }

  shuffle<T>(items: T[]): T[] {
    const copy = items.slice()
    for (let i = copy.length - 1; i > 0; i--) {
      const j = this.int(0, i)
      const swap = copy[i]
      copy[i] = copy[j]
      copy[j] = swap
    }
    return copy
  }
}

export function seedFromText(text: string): number {
  let hash = 2166136261
  for (let i = 0; i < text.length; i++) {
    hash = Math.imul(hash ^ text.charCodeAt(i), 16777619)
  }
  return hash >>> 0
}
