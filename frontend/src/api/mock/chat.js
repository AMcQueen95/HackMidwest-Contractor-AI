import { mockAffordability } from './affordability'

export const SUGGESTED_QUESTIONS = [
  'Why did profit drop?',
  'Which jobs lost money?',
  'Who still owes me money?',
  'What costs went up the most?',
]

// One finished exchange, laid out the way POST /api/ask will stream it:
// status events, then text, then card events.
export function sampleConversation(latest) {
  return [
    { role: 'user', text: 'Can I afford a $15,000 purchase?' },
    {
      role: 'assistant',
      statuses: ['Consulted the cash flow analyst'],
      text:
        "Not yet. You have $51,453 available, and after a $15,000 purchase you'd have $36,453. " +
        "That's $16,447 short of the $52,900 you'd want on hand to cover one month of expenses.\n\n" +
        'If Westport Dental and Brookside Property Mgmt pay the $21,000 they owe, you could afford it and still keep that cushion.',
      cards: [{ type: 'affordability', data: mockAffordability(latest, 15000) }],
    },
  ]
}
