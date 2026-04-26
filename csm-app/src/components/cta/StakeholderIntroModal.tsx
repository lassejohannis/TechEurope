import { useState } from 'react'
import { Send, Edit3 } from 'lucide-react'
import Modal from '@/components/common/Modal'
import { useStakeholderIntroEmail } from '@/hooks/useStakeholderIntroEmail'
import { useUiStore } from '@/store/ui'

interface StakeholderIntroModalProps {
  accountId: string
  contactId: string
  contactName: string
  onClose: () => void
}

export default function StakeholderIntroModal({ accountId, contactId, contactName, onClose }: StakeholderIntroModalProps) {
  const [editMode, setEditMode] = useState(false)
  const [editedBody, setEditedBody] = useState('')
  const addToast = useUiStore((s) => s.addToast)

  const { data: draft, isLoading } = useStakeholderIntroEmail(accountId, contactId)

  function handleSend() {
    addToast(`Intro email sent to ${contactName}`, 'success')
    onClose()
  }

  function handleEditStart() {
    setEditMode(true)
    setEditedBody(draft?.body ?? '')
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Intro Email — ${contactName}`}
      footer={
        <>
          {!editMode && (
            <button className="btn-cta-secondary" onClick={handleEditStart}>
              <Edit3 size={12} /> Edit before sending
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button className="btn-cta-primary" onClick={handleSend} disabled={isLoading}>
            <Send size={12} /> Send Email
          </button>
        </>
      }
    >
      {isLoading ? (
        <div className="modal-loading">Generating intro email…</div>
      ) : draft ? (
        <>
          <div className="email-field">
            <div className="email-label">To</div>
            <div className="email-to">{draft.to}</div>
          </div>
          <div className="email-field">
            <div className="email-label">Subject</div>
            <div className="email-subject">{draft.subject}</div>
          </div>
          <div className="email-field">
            <div className="email-label">Body</div>
            {editMode ? (
              <textarea
                className="email-body-edit"
                value={editedBody}
                onChange={(e) => setEditedBody(e.target.value)}
                rows={12}
              />
            ) : (
              <div className="email-body">{draft.body}</div>
            )}
          </div>
        </>
      ) : null}
    </Modal>
  )
}
