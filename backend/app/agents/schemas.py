"""Shapes the API returns. This is the contract with the UI."""

from pydantic import BaseModel, Field


class Issue(BaseModel):
    title: str = Field(description="Short headline, e.g. 'Software up 176%'")
    detail: str = Field(description="One sentence with the numbers behind it")
    agent: str = Field(description="Which specialist found it: expense, jobs or cash_flow")


class Recommendation(BaseModel):
    action: str = Field(description="What the owner should do, starting with a verb")
    impact: str = Field(description="Why it helps, with a dollar figure from the tools if there is one")


class ReportNarrative(BaseModel):
    """What the CFO agent writes. Headline numbers are filled in from code, not the model."""

    summary: str = Field(description="Two or three plain sentences on how the month went and why")
    issues: list[Issue] = Field(description="Three to five problems, biggest dollar impact first")
    recommendations: list[Recommendation] = Field(description="Three to five actions, most valuable first")


class FinancialHealthReport(ReportNarrative):
    """GET /api/report response."""

    business: str
    month: str
    revenue: float
    expenses: float
    profit: float
    margin_pct: float | None


class AskResponse(BaseModel):
    """POST /api/ask response."""

    answer: str
    session_id: str
