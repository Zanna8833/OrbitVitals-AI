import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

/** Small, polite confirmation after an action ("Check-in saved"). Never used for alerts. */
const Ctx = createContext<(text: string) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ id: number; text: string } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const show = useCallback((text: string) => {
    clearTimeout(timer.current)
    setToast({ id: Date.now(), text })
    timer.current = setTimeout(() => setToast(null), 2600)
  }, [])
  return (
    <Ctx.Provider value={show}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {toast && (
          <div key={toast.id} className="toast">
            <span className="toast-check" aria-hidden="true">
              ✓
            </span>
            {toast.text}
          </div>
        )}
      </div>
    </Ctx.Provider>
  )
}

// The hook belongs with its provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  return useContext(Ctx)
}
