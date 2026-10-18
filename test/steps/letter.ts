// The D12 contest letter as the card shows it (head-2): one paragraph that
// mentions the broken meter and the two dollars, written from the spoken
// reason, never the reason pasted back. It reads as the driver's own contest
// statement: first person, naming the citation the card shows, as the recorded
// letter does ("I am contesting parking citation 4512087733 ...").
import { expect } from 'vitest'

const normalise = (text: string) => text.toLowerCase().split(/\s+/).filter(Boolean).join(' ')

export function expectContestLetter(letter: string | null | undefined, reason: string, citation: string): void {
  expect(letter, 'the card shows no letter').toBeTruthy()
  const text = letter!
  expect(text, 'one paragraph').not.toMatch(/\n/)
  expect(text).toMatch(/\bmeter\b/i)
  expect(text).toMatch(/\bbroken\b/i)
  expect(text).toMatch(/\btwo dollars\b|\$2(\.00)?\b/i)
  // Written from the reason, not the reason itself.
  expect(normalise(text), 'the letter is the spoken reason echoed back').not.toBe(normalise(reason))
  // The driver's statement: first person, contesting the citation on the card and no other.
  expect(text, 'the letter is not in the first person').toMatch(/\b(I|I'm|I am|my)\b/)
  expect(text, 'the letter does not say it contests anything').toMatch(/\bcontest(ing|s)?\b/i)
  expect(text, `the letter does not name citation ${citation}`).toMatch(new RegExp(`(^|\\D)${citation}(\\D|$)`))
  for (const other of text.match(/\d{8,}/g) ?? []) expect(other, 'the letter names another citation').toBe(citation)
}
