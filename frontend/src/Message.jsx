import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

function CopyButton({ getText, label = "Copy", className = "" }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    const text = getText();
    if (!text) return;
    navigator.clipboard?.writeText(text).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1400);
      },
      () => {},
    );
  }
  return (
    <button type="button" className={className} onClick={copy}>
      {copied ? "Copied" : label}
    </button>
  );
}

function PreBlock({ children }) {
  const ref = useRef(null);
  const codeEl = Array.isArray(children) ? children[0] : children;
  const className = codeEl?.props?.className || "";
  const lang = className.replace(/^language-/, "") || "text";

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-lang">{lang}</span>
        <CopyButton
          className="code-copy"
          getText={() => ref.current?.innerText ?? ""}
        />
      </div>
      <pre ref={ref}>{children}</pre>
    </div>
  );
}

const MD_COMPONENTS = {
  pre: PreBlock,
};

function Avatar({ role }) {
  if (role === "user") {
    return (
      <div className="avatar avatar-user" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c0-4 4-7 8-7s8 3 8 7" />
        </svg>
      </div>
    );
  }
  return (
    <div className="avatar avatar-bot" aria-hidden="true">🇵🇰</div>
  );
}

export default function Message({ role, text, variant, pending }) {
  const bodyRef = useRef(null);
  const isUser = role === "user";
  const isError = variant === "error";

  return (
    <article
      className={`msg msg-${role}${variant ? " " + variant : ""}${pending ? " pending" : ""}`}
    >
      <Avatar role={role} />
      <div className="msg-content">
        <div className="msg-name">{isUser ? "You" : "PakEconBot"}</div>
        <div ref={bodyRef} className={`msg-body${isError ? " msg-body-error" : ""}`}>
          {pending ? (
            <span className="typing">
              <span></span><span></span><span></span>
            </span>
          ) : isUser || isError ? (
            text
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={MD_COMPONENTS}
            >
              {text}
            </ReactMarkdown>
          )}
        </div>
        {!pending && !isUser && !isError && text && (
          <div className="msg-actions">
            <CopyButton
              className="msg-copy"
              getText={() => bodyRef.current?.innerText ?? ""}
            />
          </div>
        )}
      </div>
    </article>
  );
}
