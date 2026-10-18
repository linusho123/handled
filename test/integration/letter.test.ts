import { describe, expect, test } from 'vitest'
import { expectContestLetter } from '../steps/letter.ts'

// head-2: the D12 binding ("a one-paragraph letter that mentions the broken
// meter and the two dollars") must hold the app to a letter written from the
// reason, not the reason pasted back. The head reviewer's probe replaced the
// Gemini letter with ' '.join(reason.split()) and D12 stayed green.
const REASON = 'the meter was broken, I put in two dollars and it never started'
const CITATION = '4512087733'
const RECORDED =
  'I am contesting parking citation 4512087733, issued in Los Angeles to license plate 8ABC123, because the meter was broken; I put in two dollars and it never started.'

describe('the D12 contest letter binding', () => {
  test('accepts the letter the cassette recorded', () => {
    expect(() => expectContestLetter(RECORDED, REASON, CITATION)).not.toThrow()
  })

  test.each([
    ['the reason echoed back (the probe)', REASON.split(/\s+/).join(' ')],
    ['the reason with its case and spacing changed', `  The Meter was BROKEN,  I put in two dollars and it never started  `],
    ['a letter in the third person', 'The driver contests parking citation 4512087733 because the meter was broken and two dollars never started it.'],
    ['a letter that names another citation', 'I am contesting parking citation 4512087734 because the meter was broken; I put in two dollars and it never started.'],
    ['a letter that names no citation', 'I am contesting this ticket because the meter was broken; I put in two dollars and it never started.'],
    ['a letter of two paragraphs', 'I am contesting parking citation 4512087733.\n\nThe meter was broken; I put in two dollars and it never started.'],
    ['a letter without the two dollars', 'I am contesting parking citation 4512087733 because the meter was broken.'],
  ])('rejects %s', (_, letter) => {
    expect(() => expectContestLetter(letter, REASON, CITATION)).toThrow()
  })
})
