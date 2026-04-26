import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { Button } from '@/components/ui/button'

type Props = {
  code: string
  language?: string
  className?: string
}

export default function CodeBlock({ code, language, className }: Props) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      /* clipboard denied — silent */
    }
  }

  return (
    <div
      className={className}
      style={{
        position: 'relative',
        background: '#0f1117',
        color: '#e5e7eb',
        borderRadius: 8,
        border: '1px solid #1f2937',
        overflow: 'hidden',
        width: '100%',
        minWidth: 0,
        maxWidth: '100%',
        boxSizing: 'border-box',
      }}
    >
      {language && (
        <div
          style={{
            fontSize: 11,
            color: '#9ca3af',
            padding: '6px 12px',
            borderBottom: '1px solid #1f2937',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          {language}
        </div>
      )}
      <Button
        size="sm"
        variant="outline"
        onClick={handleCopy}
        style={{
          position: 'absolute',
          top: language ? 32 : 8,
          right: 8,
          background: '#1f2937',
          borderColor: '#374151',
          color: '#e5e7eb',
        }}
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
        <span style={{ marginLeft: 6 }}>{copied ? 'Copied' : 'Copy'}</span>
      </Button>
      <pre
        style={{
          margin: 0,
          padding: '14px 16px',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          fontSize: 12.5,
          lineHeight: 1.55,
          overflow: 'auto',
          whiteSpace: 'pre',
          // Cap the height so very long snippets (OpenAI/Anthropic tool defs)
          // don't blow out the detail container — they scroll internally.
          maxHeight: 360,
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  )
}
