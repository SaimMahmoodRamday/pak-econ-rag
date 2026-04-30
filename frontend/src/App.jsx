import { useEffect, useRef, useState } from "react";
import Message from "./Message.jsx";
import { sendMessage, clearConversation } from "./api.js";

const SUGGESTED = [
  "What are the major sectors of Pakistan’s economy?"
];

function EmptyState({ onPick, disabled }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon" aria-hidden="true">🇵🇰</div>
      <h2 className="empty-state-title">Ask about Pakistan’s economy</h2>
      <p className="empty-state-subtitle">
        GDP, trade, inflation, sectors, fiscal policy — answers cite the local
        knowledge base.
      </p>
      <div className="suggestions">
        {SUGGESTED.map((q) => (
          <button
            key={q}
            type="button"
            className="suggestion"
            onClick={() => onPick(q)}
            disabled={disabled}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const chatRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, pending]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function autoResize(ta) {
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }

  async function send(text) {
    const message = (text ?? "").trim();
    if (!message || pending) return;
    setMessages((m) => [...m, { role: "user", text: message }]);
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "";
    setPending(true);
    try {
      const data = await sendMessage(message);
      setMessages((m) => [...m, { role: "bot", text: data.answer || "" }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((m) => [...m, { role: "bot", variant: "error", text: msg }]);
    } finally {
      setPending(false);
      inputRef.current?.focus();
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    send(input);
  }

  async function onClear() {
    try {
      await clearConversation();
      setMessages([]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages([{ role: "bot", variant: "error", text: msg }]);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  function onInputChange(e) {
    setInput(e.target.value);
    autoResize(e.target);
  }

  const empty = messages.length === 0 && !pending;

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">🇵🇰</span>
          <div>
            <h1>PakEconBot</h1>
            <p className="tagline">Pakistan economy · agentic RAG</p>
          </div>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn ghost"
            onClick={onClear}
            disabled={pending || messages.length === 0}
          >
            Clear thread
          </button>
        </div>
      </header>

      <main className="chat" ref={chatRef} aria-live="polite">
        {empty && <EmptyState onPick={send} disabled={pending} />}
        {messages.map((m, i) => (
          <Message key={i} role={m.role} text={m.text} variant={m.variant} />
        ))}
        {pending && <Message role="bot" pending />}
      </main>

      <form className="composer" onSubmit={onSubmit} autoComplete="off">
        <label className="sr-only" htmlFor="input">Your question</label>
        <textarea
          id="input"
          ref={inputRef}
          rows={1}
          placeholder="Message PakEconBot…"
          value={input}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          required
        />
        <button
          type="submit"
          className="btn primary"
          disabled={pending || !input.trim()}
        >
          Send
        </button>
      </form>
      <p className="hint">
        Press <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
      </p>
    </div>
  );
}
