import { ExternalLink, Copy } from 'lucide-react'
import Modal from '@/components/common/Modal'
import { useEscalationBriefing } from '@/hooks/useEscalationBriefing'
import { useUiStore } from '@/store/ui'

interface EscalationModalProps {
  accountId: string
  accountName: string
  onClose: () => void
}

export default function EscalationModal({ accountId, accountName, onClose }: EscalationModalProps) {
  const addToast = useUiStore((s) => s.addToast)
  const { data: briefing, isLoading } = useEscalationBriefing(accountId)

  function buildText(): string {
    if (!briefing) return ''
    const bullets = briefing.evidence_bullets.map((b) => `• ${b}`).join('\n')
    const owners = briefing.suggested_owners.map((o) => `→ ${o.name}: ${o.action}`).join('\n')
    return `🚨 Account Escalation: ${accountName}\n\n${briefing.health_summary}\n\nEvidence:\n${bullets}\n\nSuggested owners:\n${owners}`
  }

  function handleCopy() {
    navigator.clipboard.writeText(buildText()).catch(() => {})
    addToast('Copied to clipboard', 'copied')
    onClose()
  }

  function handleOpenSlack() {
    window.open('https://app.slack.com/client', '_blank', 'noopener,noreferrer')
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Escalate — ${accountName}`}
      footer={
        <>
          <button className="btn-cta-secondary" onClick={handleOpenSlack}>
            <ExternalLink size={12} /> Open Slack
          </button>
          <span style={{ flex: 1 }} />
          <button className="btn-cta-primary" onClick={handleCopy} disabled={isLoading}>
            <Copy size={12} /> Copy to clipboard
          </button>
        </>
      }
    >
      {isLoading ? (
        <div className="modal-loading">Building briefing…</div>
      ) : briefing ? (
        <>
          <div className="escalation-summary">{briefing.health_summary}</div>
          <div style={{ marginBottom: 14 }}>
            <div className="email-label" style={{ marginBottom: 8 }}>Evidence</div>
            {briefing.evidence_bullets.map((bullet, i) => (
              <div key={i} className="escalation-bullet">{bullet}</div>
            ))}
          </div>
          <div>
            <div className="email-label" style={{ marginBottom: 8 }}>Suggested owners</div>
            {briefing.suggested_owners.map((owner, i) => (
              <div key={i} className="escalation-owner">
                <span className="escalation-owner-name">{owner.name}</span>
                <span className="escalation-owner-action">{owner.action}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </Modal>
  )
}
