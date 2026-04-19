(function () {
  const STORAGE_KEY = "pakeconbot_conversation_id";

  const chatEl = document.getElementById("chat");
  const form = document.getElementById("form");
  const input = document.getElementById("input");
  const btnSend = document.getElementById("btn-send");
  const btnClear = document.getElementById("btn-clear");

  function getConversationId() {
    return sessionStorage.getItem(STORAGE_KEY);
  }

  function setConversationId(id) {
    if (id) sessionStorage.setItem(STORAGE_KEY, id);
    else sessionStorage.removeItem(STORAGE_KEY);
  }

  function appendMessage(role, text, className) {
    const div = document.createElement("div");
    div.className = "msg " + role + (className ? " " + className : "");
    div.textContent = text;
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
    return div;
  }

  function showWelcome() {
    appendMessage(
      "bot meta",
      "Ask a question about Pakistan’s economy. Your thread is saved for follow-ups until you clear it."
    );
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || d).join("; ")
            : res.statusText;
      throw new Error(msg || "Request failed");
    }
    return data;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", message);
    input.value = "";
    input.style.height = "";

    btnSend.disabled = true;
    const pending = appendMessage("bot", "");
    pending.innerHTML =
      '<span class="typing">Thinking <span>.</span><span>.</span><span>.</span></span>';

    try {
      const cid = getConversationId();
      const payload = { message };
      if (cid) payload.conversation_id = cid;

      const data = await postJson("/api/chat", payload);
      if (data.conversation_id) setConversationId(data.conversation_id);
      pending.className = "msg bot";
      pending.textContent = data.answer || "";
    } catch (err) {
      pending.className = "msg error";
      pending.textContent = err instanceof Error ? err.message : String(err);
    } finally {
      btnSend.disabled = false;
      chatEl.scrollTop = chatEl.scrollHeight;
      input.focus();
    }
  });

  btnClear.addEventListener("click", async () => {
    const cid = getConversationId();
    btnClear.disabled = true;
    try {
      if (cid) {
        await postJson("/api/clear", { conversation_id: cid });
      }
      setConversationId(null);
      chatEl.innerHTML = "";
      showWelcome();
    } catch (err) {
      appendMessage("bot", err instanceof Error ? err.message : String(err), "error");
    } finally {
      btnClear.disabled = false;
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  showWelcome();
  input.focus();
})();
