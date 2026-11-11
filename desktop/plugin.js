// ascii-launchscreen — desktop half: full-window ASCII launchscreen overlay.
//
// Loads at app start, fetches the generated launchscreen from the plugin
// backend (GET /api/plugins/ascii-launchscreen/launchscreen), and shows it
// full-window for its configured duration (still: 5 s, animation: 8 s by
// default — both tweakable in Settings -> Plugins). Falls back to an embedded
// HERMES banner when no launchscreen has been generated yet. Click to skip.

import { TITLEBAR_AREAS } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'
import { useEffect, useState } from 'react'

const FALLBACK = {
  kind: 'still',
  color_mode: 'mono',
  mono_color_hex: '#3b82f6',
  duration_ms: 5000,
  frame_delay_ms: 80,
  frames: [
    {
      text:
        '██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗\n' +
        '██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝\n' +
        '███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗\n' +
        '██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║\n' +
        '██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║\n' +
        '╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝'
    }
  ]
}

function esc(ch) {
  if (ch === '<') return '&lt;'
  if (ch === '>') return '&gt;'
  if (ch === '&') return '&amp;'
  return ch
}

// Build a colored HTML string from a frame's text + per-cell foreground colors.
function colorHtml(frame) {
  const rows = String(frame.text || '').split('\n')
  const fg = frame.fg
  let html = ''
  for (let y = 0; y < rows.length; y++) {
    const line = rows[y]
    for (let x = 0; x < line.length; x++) {
      const c = fg && fg[y] && fg[y][x]
      const ch = esc(line[x])
      if (c && Array.isArray(c)) {
        html += '<span style="color:rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')">' + ch + '</span>'
      } else {
        html += ch
      }
    }
    if (y < rows.length - 1) html += '\n'
  }
  return html
}

function Launchscreen({ ctx }) {
  const [spec, setSpec] = useState(null)
  const [idx, setIdx] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    let live = true
    const finish = (s) => { if (live) setSpec(s) }
    ctx.rest('/launchscreen').then(
      (s) => finish(s && s.available ? s : FALLBACK),
      () => finish(FALLBACK)
    )
    return () => { live = false }
  }, [])

  useEffect(() => {
    if (!spec || done) return
    const frames = Array.isArray(spec.frames) ? spec.frames : []
    let stopAnim = function () {}
    if (frames.length > 1) {
      const delay = spec.frame_delay_ms || 80
      stopAnim = ctx.setInterval(() => setIdx((i) => (i + 1) % frames.length), delay)
    }
    const dur = spec.duration_ms || (spec.kind === 'still' ? 5000 : 8000)
    const stopTimer = ctx.setTimeout(() => setDone(true), dur)
    return () => { stopAnim(); stopTimer() }
  }, [spec, done])

  if (done || !spec) return null

  const frames = Array.isArray(spec.frames) ? spec.frames : []
  const frame = frames[idx] || { text: '' }
  const mono = spec.color_mode !== 'color' || !frame.fg
  const hex = spec.mono_color_hex || '#3b82f6'
  const width = spec.width || 80
  const fontSize = Math.max(0.5, Math.min(1.6, 92 / width))

  return jsx('div', {
    onClick: () => setDone(true),
    style: {
      position: 'fixed',
      inset: '0',
      zIndex: 2147483000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--background, var(--ui-background))',
      cursor: 'pointer',
      overflow: 'hidden'
    },
    children: mono
      ? jsx('pre', {
          style: {
            color: hex,
            fontFamily: 'var(--font-mono, ui-monospace, monospace)',
            fontSize: fontSize + 'vw',
            lineHeight: 1,
            margin: 0,
            whiteSpace: 'pre',
            overflow: 'hidden'
          },
          children: String(frame.text || '')
        })
      : jsx('pre', {
          style: {
            fontFamily: 'var(--font-mono, ui-monospace, monospace)',
            fontSize: fontSize + 'vw',
            lineHeight: 1,
            margin: 0,
            whiteSpace: 'pre',
            overflow: 'hidden'
          },
          dangerouslySetInnerHTML: { __html: colorHtml(frame) }
        })
  })
}

export default {
  id: 'ascii-launchscreen',
  name: 'ASCII Launchscreen',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'launchscreen',
      area: TITLEBAR_AREAS.center,
      render: () => jsx(Launchscreen, { ctx })
    })
  }
}
