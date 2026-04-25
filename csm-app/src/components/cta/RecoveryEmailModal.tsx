import { useState } from 'react'
import { RefreshCw, Send, Edit3 } from 'lucide-react'
import Modal from '@/components/common/Modal'
import { useRecoveryEmail } from '@/hooks/useRecoveryEmail'
import { useUiStore } from '@/store/ui'

interface RecoveryEmailModalProps {
  accountId: string
  onClose: () => void
}

export default function RecoveryEmailModal({ accountId, onClose }: RecoveryEmailModalProps) {
  const [variation, setVariation] = useState(0)
  const [editMode, setEditMode] = useState(false)
  const [editedBody, setEditedBody] = useState('')
  const addToast = useUiStore((s) => s.addToast)

  const { data: draft, isLoading } = useRecoveryEmail(accountId, variation)

  function handleSend() {
    addToast(`Email sent to ${draft?.to ?? 'contact'}`, 'success')
    onClose()
  }

  function handleRegenerate() {
    setVariation((v) => (v + 1) % 2)
    setEditMode(false)
    setEditedBody('')
  }

  function handleEditStart() {
    setEditMode(true)
    setEditedBody(draft?.body ?? '')
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Send Recovery Email"
      footer={
        <>
          <button className="btn-cta-secondary" onClick={handleRegenerate}>
            <RefreshCw size={12} /> Regenerate
          </button>
          {!editMode && (
            <button className="btn-cta-secondary" onClick={handleEditStart}>
              <Edit3 size={12} /> Edit before sending
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button className="btn-cta-primary" onClick={handleSend} disabled={isLoading}>
            <Send size={12} /> Send
          </button>
        </>
      }
    >
      {isLoading ? (
        <div className="modal-loading">Generating email…</div>
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
                rows={10}
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
