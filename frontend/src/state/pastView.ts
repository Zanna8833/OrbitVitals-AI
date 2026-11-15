/** Whether a past mission day is shown (kept in step by AppState), for wording outside React state. */
let past = false
export const isPastView = () => past
export const setPastView = (on: boolean) => {
  past = on
}
/** "Today’s" / "That day’s", "today" / "that day" depending on the day shown. */
export const dayPossessive = () => (past ? 'That day’s' : 'Today’s')
export const dayWord = () => (past ? 'that day' : 'today')
