// Canned text in the shape cfo_agent.ask() returns: a short answer, then
// "Issues", then "Recommendations". Every figure comes from books.json.
export const NARRATIVES = {
  '2026-08': `August was a strong month. $60,000 came in and $45,000 went out, leaving $15,000 in profit, and all three finished jobs made money.

Issues
- Payroll was the largest cost at $24,000, a little over half of everything spent.
- These books start in August, so there is no earlier month to compare costs against.
- Software included a one-time Workspace charge of $36.43 on top of Housecall Pro.

Recommendations
- Keep pricing commercial HVAC the way you did: both jobs cleared a 52% margin.
- Residential HVAC was the best earner at 67.5% margin. Take more of that work if it's available.
- Check back after September closes to see which costs are moving.`,
  '2026-09': `September lost $7,830: $45,070 came in and $52,900 went out. Two customers haven't paid $21,000 in invoices, and materials, fuel, insurance, and software all cost more than in August.

Issues
- Westport Dental owes $12,000 (10 days overdue) and Brookside Property Mgmt owes $9,000 (5 days overdue).
- The Westport Dental job (SEP-001) lost $1,232: it cost $13,232 against a $12,000 quote.
- Software spending rose 176%. ServiceTitan ($398 a month) was added while Housecall Pro ($169 a month) is still being paid.
- Materials rose 40%, fuel 35%, insurance 26%, and marketing 50%.

Recommendations
- Call Westport Dental and Brookside this week. Collecting the $21,000 more than covers the month's loss.
- Pick one dispatch app. Dropping the other saves $169 to $398 a month.
- Add a materials price clause to fixed bids so a supplier increase doesn't come out of your margin.
- Hold off on large purchases until those two invoices are paid.`,
}

// Splits the agent's plain text into its three parts. Works on partial text
// too, so it can be called on every streamed chunk.
export function parseNarrative(text) {
  const [head, afterIssues = ''] = text.split(/^Issues\s*$/m)
  const [issuesText, recsText = ''] = afterIssues.split(/^Recommendations\s*$/m)
  const bullets = (block) =>
    block
      .split('\n')
      .map((line) => line.replace(/^[-•]\s*/, '').trim())
      .filter(Boolean)
  return {
    summary: head.trim(),
    issues: bullets(issuesText),
    recommendations: bullets(recsText),
  }
}
