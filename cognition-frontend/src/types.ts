// Session file written for the ground (read by cognition.py). Field names match the Python scorer.

export type TestCode = 'MPT' | 'VOLT' | 'F2B' | 'AM' | 'LOT' | 'ERT' | 'MRT' | 'DSST' | 'BART' | 'PVT'

export type CorrectTrial = { rt_ms: number | null; correct: boolean }
export type MotorTrial = { rt_ms: number; distance_px: number }
export type FractalTrial = { is_match: boolean; responded: boolean; rt_ms: number | null }
export type LineTrial = { rt_ms: number; clicks_off: number }
export type Balloon = { pumps: number; pop_point: number; popped: boolean; pump_rts_ms: number[] }

export type TestResult =
  | { trials: CorrectTrial[] }
  | { trials: MotorTrial[] }
  | { trials: FractalTrial[] }
  | { trials: LineTrial[] }
  | { balloons: Balloon[] }
  | { stimuli: { rt_ms: number | null }[]; false_starts: number }

export type Session = {
  astronaut_id: string
  mission_day: number
  started_at: string
  survey: Record<string, number>
  tests: Partial<Record<TestCode, TestResult>>
}

export type TestProps = {
  seed: number
  onFinish: (result: TestResult) => void
}

// Standard order of administration (Basner et al. 2015, Fig. 1)
export const TEST_ORDER: TestCode[] = ['MPT', 'VOLT', 'F2B', 'AM', 'LOT', 'ERT', 'MRT', 'DSST', 'BART', 'PVT']

export const TEST_NAMES: Record<TestCode, string> = {
  MPT: 'Motor Praxis',
  VOLT: 'Visual Object Learning',
  F2B: 'Fractal 2-Back',
  AM: 'Abstract Matching',
  LOT: 'Line Orientation',
  ERT: 'Emotion Recognition',
  MRT: 'Matrix Reasoning',
  DSST: 'Digit Symbol Substitution',
  BART: 'Balloon Analog Risk',
  PVT: 'Psychomotor Vigilance',
}


// Our wording, following the instructions described in NASA TM-2020-5008023 (Appendix C)
export const TEST_INSTRUCTIONS: Record<TestCode, string[]> = {
  MPT: ['Squares will appear one at a time, each smaller than the one before.', 'Click each square as fast as you can.'],
  VOLT: ['You will see 10 objects, one at a time. Memorise them.',
    'Then you will see 20 objects: say whether each one was in the set, and how sure you are.'],
  F2B: ['Fractal pictures will appear one at a time.',
    'Press SPACE when the picture is the same as the one two pictures before. The test is continuous.'],
  AM: ['This is a test of your ability to learn abstract rules.',
    'Choose the set at the bottom that best fits the object at the top. Feedback tells you if you were right.',
    'The rules may seem illogical at first. Feedback is always shown over the left-hand set.'],
  LOT: ['Rotate the blue line with the arrows until it is parallel to the black line, then press Done.'],
  ERT: ['You will see faces. Decide if the person looks happy, sad, angry, fearful or shows no emotion.',
    // Attribution required by the CC BY 4.0 licence of the photos
    'Photos: 100 Peers face set (osf.io/nwjbf), CC BY 4.0.'],
  MRT: ['Each matrix has a missing cell. Choose the option that best fills it.'],
  DSST: ['A symbol appears at the top. Find it in the key at the bottom and press its number.',
    'The first three answers show feedback. The test lasts about 90 seconds.'],
  BART: ['Inflate each balloon as much as you can without popping it. Each inflation adds $1 to the reward.',
    'Collect moves the reward to your total winnings. If the balloon pops, its reward is lost. There are 30 balloons.'],
  PVT: ['When numbers start counting up in the box, press SPACE (or tap the box) as fast as you can.',
    'Do not press before the numbers appear. The test lasts 3 minutes.'],
}
