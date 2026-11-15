import { useEffect, useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import { EMOTIONS, Face, makeFace } from '../stimuli'
import type { Emotion, FaceSpec } from '../stimuli'
import type { CorrectTrial, TestProps } from '../types'

// 40 faces, 8 for each of the 5 categories (Basner et al. 2021). Photos come from public/faces/manifest.json
// ([{ "file": "faces/...jpg", "emotion": "happy" }, ...]); without it the test falls back to drawn faces.
const FACES_PER_EMOTION = 8

type Photo = { file: string; emotion: Emotion }
type Stimulus = { emotion: Emotion; photo: string | null; drawn: FaceSpec | null }

function chooseStimuli(seed: number, photos: Photo[] | null): Stimulus[] {
  const random = new Random(seed)
  const list: Stimulus[] = []
  for (const emotion of EMOTIONS) {
    const available: Photo[] = []
    if (photos !== null) {
      for (const photo of photos) {
        if (photo.emotion === emotion) available.push(photo)
      }
    }
    if (available.length >= FACES_PER_EMOTION) {
      for (const photo of random.shuffle(available).slice(0, FACES_PER_EMOTION)) {
        list.push({ emotion: emotion, photo: photo.file, drawn: null })
      }
    } else {
      for (let i = 0; i < FACES_PER_EMOTION; i++) {
        list.push({ emotion: emotion, photo: null, drawn: makeFace(random, emotion) })
      }
    }
  }
  return random.shuffle(list)
}

export default function EmotionRecognition(props: TestProps) {
  const [photos, setPhotos] = useState<Photo[] | null | undefined>(undefined)
  const [index, setIndex] = useState(0)
  const trials = useRef<CorrectTrial[]>([])
  const shownAt = useRef(performance.now())

  useEffect(function () {
    fetch('faces/manifest.json')
      .then(function (response) {
        if (!response.ok) throw new Error('no manifest')
        return response.json()
      })
      .then(function (list: Photo[]) { setPhotos(list) })
      .catch(function () { setPhotos(null) })
  }, [])

  const faces = useMemo(function () {
    if (photos === undefined) return []
    return chooseStimuli(props.seed, photos)
  }, [props.seed, photos])

  useEffect(function () {
    shownAt.current = performance.now()
  }, [faces])

  // Preload the photos so that response times do not include loading
  useEffect(function () {
    for (const face of faces) {
      if (face.photo !== null) {
        const image = new Image()
        image.src = face.photo
      }
    }
  }, [faces])

  if (faces.length === 0) {
    return <div className="stage" />
  }

  function answer(label: string) {
    trials.current.push({ rt_ms: Math.round(performance.now() - shownAt.current), correct: label === faces[index].emotion })
    if (index + 1 === faces.length) {
      props.onFinish({ trials: trials.current })
      return
    }
    shownAt.current = performance.now()
    setIndex(index + 1)
  }

  const buttons = []
  for (const emotion of EMOTIONS) {
    buttons.push(<button key={emotion} className="answer" onClick={function () { answer(emotion) }}>{emotion}</button>)
  }
  const face = faces[index]
  let picture = <img src={face.photo === null ? '' : face.photo} alt="" />
  if (face.drawn !== null) {
    picture = <Face spec={face.drawn} size={280} />
  }
  return (
    <div className="stage">
      <div className="stimulus-box">{picture}</div>
      <div className="answer-row">{buttons}</div>
      <div className="trial-counter">{index + 1} / {faces.length}</div>
    </div>
  )
}
