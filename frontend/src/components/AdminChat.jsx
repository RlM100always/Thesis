/**
 * Global admin↔business chat bubble — mounts once in AppFrame so it floats
 * over every business panel. Features:
 *   • File / image attachments (uploaded to /api/app/messages/upload)
 *   • Seen receipts (✓ sent, ✓✓ read, shown only on sender's own messages)
 *   • 30-second unread poll so badge updates without a page reload
 *   • Drag-to-resize chat window height
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

// ── helpers ────────────────────────────────────────────────────────────────
function fmt(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("bn-BD", { hour: "2-digit", minute: "2-digit" });
}

function isImage(name = "") {
  return /\.(png|jpe?g|gif|webp|svg)$/i.test(name);
}

function fileSizeLabel(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── sub-components ─────────────────────────────────────────────────────────
function SeenTick({ msg, myType }) {
  if (msg.sender_type !== myType) return null;
  const seen = !!msg.read_at;
  return (
    <span title={seen ? `পড়া হয়েছে ${fmt(msg.read_at)}` : "পাঠানো হয়েছে"}
      style={{ fontSize: 11, marginLeft: 4, color: seen ? "#4caf50" : "rgba(255,255,255,0.6)" }}>
      {seen ? "✓✓" : "✓"}
    </span>
  );
}

function AttachmentPreview({ url, name }) {
  if (!url) return null;
  if (isImage(name)) {
    return (
      <a href={url} target="_blank" rel="noreferrer" style={{ display: "block", marginTop: 6 }}>
        <img src={url} alt={name} style={{ maxWidth: 200, maxHeight: 160, borderRadius: 8, display: "block" }} />
      </a>
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer"
      style={{ display: "inline-flex", alignItems: "center", gap: 6, marginTop: 6,
        background: "rgba(0,0,0,0.12)", borderRadius: 8, padding: "5px 10px", fontSize: 12, color: "inherit", textDecoration: "none" }}>
      📎 {name}
    </a>
  );
}

function Bubble({ m, myType }) {
  const mine = m.sender_type === myType;
  return (
    <div style={{ alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "78%", display: "flex", flexDirection: "column" }}>
      <div style={{
        background: mine ? "var(--green, #0a8754)" : "var(--bg-subtle, #f1f5f9)",
        color: mine ? "#fff" : "inherit",
        borderRadius: mine ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
        padding: "8px 13px", fontSize: 13, lineHeight: 1.55,
        boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
      }}>
        {m.content && <span>{m.content}</span>}
        <AttachmentPreview url={m.attachment_url} name={m.attachment_name} />
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", marginTop: 2 }}>
          <span style={{ fontSize: 10, opacity: 0.75 }}>{fmt(m.created_at)}</span>
          <SeenTick msg={m} myType={myType} />
        </div>
      </div>
      {!mine && (
        <span style={{ fontSize: 11, color: "var(--muted)", marginTop: 2, marginLeft: 2 }}>{m.sender_name}</span>
      )}
    </div>
  );
}

// ── main component ─────────────────────────────────────────────────────────
export default function AdminChatBubble() {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [thread, setThread] = useState(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [height, setHeight] = useState(460);
  const bottomRef = useRef(null);
  const fileRef = useRef(null);
  const dragRef = useRef(null);

  // ── poll unread ──────────────────────────────────────────────────────────
  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const d = await api.getAdminMessagesUnread();
        if (alive) setUnread(d.unread || 0);
      } catch (_) {}
    }
    poll();
    const t = setInterval(poll, 30000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  // ── open / refresh thread ────────────────────────────────────────────────
  const openChat = useCallback(async () => {
    setOpen(true);
    try {
      const d = await api.getAdminMessages();
      setThread(d);
      setUnread(0);
    } catch (_) {}
  }, []);

  // Poll for new messages while chat is open (every 15s)
  useEffect(() => {
    if (!open) return;
    const t = setInterval(async () => {
      try {
        const d = await api.getAdminMessages();
        setThread(d);
        setUnread(0);
      } catch (_) {}
    }, 15000);
    return () => clearInterval(t);
  }, [open]);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [open, thread?.messages?.length]);

  // ── send text ────────────────────────────────────────────────────────────
  async function send() {
    const content = text.trim();
    if (!content || sending) return;
    setSending(true);
    try {
      const msg = await api.replyToAdmin(content);
      setThread(prev => prev ? { ...prev, messages: [...(prev.messages || []), msg] } : prev);
      setText("");
    } catch (_) {}
    setSending(false);
  }

  // ── file upload ──────────────────────────────────────────────────────────
  async function uploadFile(file) {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const result = await api.uploadChatFile(fd);
      // Send as a message with attachment
      const msg = await api.replyToAdmin("", result.url, result.filename);
      setThread(prev => prev ? { ...prev, messages: [...(prev.messages || []), msg] } : prev);
    } catch (e) {
      alert(`ফাইল আপলোড ব্যর্থ: ${e.message}`);
    }
    setUploading(false);
  }

  // ── drag-to-resize ───────────────────────────────────────────────────────
  function onDragStart(e) {
    const startY = e.clientY;
    const startH = height;
    function onMove(ev) {
      const delta = startY - ev.clientY;
      setHeight(Math.max(300, Math.min(700, startH + delta)));
    }
    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  // ── paste image ──────────────────────────────────────────────────────────
  function onPaste(e) {
    const item = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith("image/"));
    if (item) { e.preventDefault(); uploadFile(item.getAsFile()); }
  }

  // ── drag-drop file onto chat ─────────────────────────────────────────────
  function onDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file) uploadFile(file);
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={open ? () => setOpen(false) : openChat}
        style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 9000,
          background: "var(--green, #0a8754)", color: "#fff",
          border: "none", borderRadius: "50%", width: 54, height: 54,
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: "pointer", boxShadow: "0 4px 20px rgba(0,0,0,0.22)",
          fontSize: 22, transition: "transform 0.15s",
        }}
        title="Admin বার্তা"
      >
        {open ? "✕" : "💬"}
        {!open && unread > 0 && (
          <span style={{
            position: "absolute", top: 2, right: 2,
            background: "#e63946", borderRadius: 99,
            minWidth: 19, height: 19, fontSize: 11,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 700, padding: "0 4px",
          }}>{unread > 99 ? "99+" : unread}</span>
        )}
      </button>

      {/* Chat window */}
      {open && (
        <div
          onDrop={onDrop} onDragOver={e => e.preventDefault()}
          style={{
            position: "fixed", bottom: 90, right: 24, zIndex: 8999,
            width: "min(380px, calc(100vw - 32px))",
            height: height,
            background: "var(--bg-card, #fff)",
            borderRadius: 16, boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
            display: "flex", flexDirection: "column",
            border: "1px solid var(--border, #e2e8f0)",
            overflow: "hidden",
          }}
        >
          {/* Drag handle */}
          <div
            ref={dragRef}
            onMouseDown={onDragStart}
            style={{
              height: 6, cursor: "ns-resize",
              background: "linear-gradient(to bottom, var(--border,#e2e8f0), transparent)",
              flexShrink: 0,
            }}
          />

          {/* Header */}
          <div style={{
            padding: "8px 14px", borderBottom: "1px solid var(--border,#e2e8f0)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
            flexShrink: 0,
          }}>
            <div>
              <span style={{ fontWeight: 700, fontSize: 14 }}>Platform Admin</span>
              <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: 8 }}>
                {thread?.messages?.length
                  ? `${thread.messages.length}টি বার্তা`
                  : "কোনো বার্তা নেই"}
              </span>
            </div>
            <button onClick={() => setOpen(false)}
              style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "var(--muted)", lineHeight: 1 }}>×</button>
          </div>

          {/* Messages */}
          <div style={{
            flex: 1, overflowY: "auto", padding: "12px 14px",
            display: "flex", flexDirection: "column", gap: 10,
          }}>
            {!thread ? (
              <div style={{ textAlign: "center", color: "var(--muted)", fontSize: 13, padding: 20 }}>লোড হচ্ছে…</div>
            ) : thread.messages?.length === 0 ? (
              <div style={{ textAlign: "center", color: "var(--muted)", fontSize: 13, padding: 20 }}>
                <div style={{ fontSize: 28 }}>💬</div>
                <div style={{ marginTop: 8 }}>Admin কোনো বার্তা পাঠালে এখানে দেখাবে।<br />আপনিও প্রথম বার্তা পাঠাতে পারেন।</div>
              </div>
            ) : thread.messages.map(m => (
              <Bubble key={m.id} m={m} myType="business" />
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Upload progress */}
          {uploading && (
            <div style={{ padding: "4px 14px", fontSize: 12, color: "var(--muted)", background: "var(--bg-subtle,#f8fafc)", flexShrink: 0 }}>
              ফাইল আপলোড হচ্ছে…
            </div>
          )}

          {/* Input */}
          <div style={{
            padding: "8px 10px", borderTop: "1px solid var(--border,#e2e8f0)",
            display: "flex", gap: 6, alignItems: "flex-end", flexShrink: 0,
          }}>
            {/* File attach */}
            <input ref={fileRef} type="file" style={{ display: "none" }}
              accept="image/*,.pdf,.xlsx,.xls,.csv,.docx,.doc,.txt,.zip"
              onChange={e => { uploadFile(e.target.files?.[0]); e.target.value = ""; }} />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              title="ফাইল সংযুক্ত করুন"
              style={{
                background: "none", border: "1px solid var(--border,#e2e8f0)",
                borderRadius: 8, padding: "0 8px", height: 36, cursor: "pointer",
                color: "var(--muted)", fontSize: 16, flexShrink: 0,
              }}>📎</button>

            <textarea
              style={{
                flex: 1, resize: "none", border: "1px solid var(--border,#e2e8f0)",
                borderRadius: 10, padding: "7px 10px", fontSize: 13,
                fontFamily: "inherit", lineHeight: 1.4, maxHeight: 100, overflowY: "auto",
              }}
              rows={1}
              value={text}
              onChange={e => {
                setText(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px";
              }}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              onPaste={onPaste}
              placeholder="বার্তা লিখুন… (Shift+Enter নতুন লাইন)"
            />

            <button
              onClick={send}
              disabled={sending || !text.trim()}
              style={{
                background: text.trim() ? "var(--green, #0a8754)" : "var(--border,#e2e8f0)",
                color: text.trim() ? "#fff" : "var(--muted)",
                border: "none", borderRadius: 10, padding: "0 14px",
                height: 36, cursor: text.trim() ? "pointer" : "default",
                fontSize: 13, transition: "background 0.15s", flexShrink: 0,
              }}>
              {sending ? "…" : "পাঠান"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
