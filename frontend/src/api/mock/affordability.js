// Mock only: mirrors backend/app/finance/cashflow.py::affordability with the
// default one-month reserve. Delete when GET /api/affordability exists.
const round2 = (n) => Math.round(n * 100) / 100

export function mockAffordability(latest, amount) {
  const { balance, tax_reserve, available_cash, cash_in, cash_out } = latest.cash_balance
  const reserve = latest.monthly_summary.expenses
  const collections = latest.receivables.total_outstanding
  const rate = latest.business.tax_reserve_rate
  const projectedTax = round2(Math.max(0, cash_in - cash_out + collections) * rate)
  const availableAfter = round2(available_cash - amount)
  const projectedAvailable = round2(balance + collections - projectedTax - amount)
  return {
    as_of_date: latest.business.as_of_date,
    currency: 'USD',
    purchase_amount: amount,
    reserve_month: latest.monthly_summary.month,
    reserve_months: 1,
    reserve_required: reserve,
    cash_balance: balance,
    tax_reserve,
    available_cash,
    cash_after_purchase: round2(balance - amount),
    available_after_purchase: availableAfter,
    can_afford_now: availableAfter >= reserve,
    shortfall: round2(Math.max(0, reserve - availableAfter)),
    status: 'evaluated',
    collection_scenario: {
      assumption:
        'All outstanding invoices are collected in full; no additional expenses occur. This is a scenario, not a forecast.',
      collections,
      tax_reserve: projectedTax,
      available_after_purchase: projectedAvailable,
      can_afford: projectedAvailable >= reserve,
    },
  }
}
