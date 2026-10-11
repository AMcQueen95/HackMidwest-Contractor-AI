import { CheckIcon, Logo } from './Icons'

export const STEPS = ['Account', 'Company', 'Type of work', 'Add records', 'Review']

export default function OnboardingShell({ step, onBack, backLabel = 'Back', width = 'narrow', account, children }) {
  return (
    <div className="onboarding">
      <header className="onboarding-top">
        <div className="brand">
          <Logo />
          <span className="brand-name">
            Toolbelt <span>CFO</span>
          </span>
        </div>
        {account}
      </header>

      <main className={`onboarding-main is-${width}`}>{children}</main>

      <footer className="stepbar">
        <div className="stepbar-progress" aria-hidden="true">
          <span style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
        </div>
        <div className="stepbar-inner">
          <div className="stepbar-back">
            {onBack && (
              <button type="button" className="button" onClick={onBack}>
                <span aria-hidden="true">←</span> {backLabel}
              </button>
            )}
          </div>
          <ol className="steps" aria-label="Setup progress">
            {STEPS.map((name, index) => {
              const state = index < step ? 'is-done' : index === step ? 'is-current' : ''
              return (
                <li key={name} className={state} aria-current={index === step ? 'step' : undefined}>
                  <span className="step-dot">{index < step ? <CheckIcon /> : index + 1}</span>
                  <span className="step-name">{name}</span>
                </li>
              )
            })}
          </ol>
          <div className="stepbar-count">
            Step {step + 1} of {STEPS.length}<span className="stepbar-current">: {STEPS[step]}</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
