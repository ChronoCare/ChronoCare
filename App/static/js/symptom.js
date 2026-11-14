// ---------- Log symptom ----------
// Shared by every page that includes templates/_symptom_modal.html.
// Wrapped in a function so these helpers don't clash with the page's own script
// (diet_plan.js and exercise.js also have functions called esc, api, ...).
(() => {
  const modal = document.getElementById("symptomModal");
  if (!modal) return;

  const form = document.getElementById("symptomForm");
  const result = document.getElementById("symptomResult");
  const errorBox = document.getElementById("symptomError");
  const metricSelect = document.getElementById("symMetric");
  const READING_HINTS = { "Blood sugar": "e.g. 4.2 mmol/L", "Blood pressure": "e.g. 145/95" };

  // Escape text before putting it in HTML (advice comes from the AI)
  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  async function postSymptom(payload) {
    const res = await fetch("/api/symptom", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
      },
      body: JSON.stringify(payload),
    });
    if (res.redirected) { // logged out
      location.reload();
      throw new Error("Please log in again.");
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again.");
    return data;
  }

  // Errors show inside the popup: a toast on the page would be hidden behind it
  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = !message;
  }

  function renderAdvice(advice, savedAs) {
    const section = (title, items) =>
      items?.length ? `<h4>${title}</h4><ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "";

    result.innerHTML = `
      <div class="advice ${advice.urgent ? "urgent" : ""}">
        ${advice.urgent ? `<p class="advice-flag"><i data-lucide="siren"></i> Get help now</p>` : ""}
        <p class="advice-summary">${esc(advice.summary)}</p>
        ${section("Do this now", advice.do_now)}
        ${section("Eat or drink", advice.eat)}
        ${section("Avoid", advice.avoid)}
        ${section("Get medical help if", advice.seek_help_if)}
        ${advice.demo ? `<p class="muted small">Demo answer. Add a Groq API key for personalised advice.</p>` : ""}
      </div>
      ${savedAs ? `<p class="muted small">Also saved to your ${esc(savedAs.toLowerCase())} readings on the Overview.</p>` : ""}
      <button type="button" class="btn btn-outline btn-block" id="symptomAgain">Log another</button>`;
    form.hidden = true;
    result.hidden = false;
    lucide.createIcons();
  }

  function reset() {
    form.reset();
    showError("");
    form.hidden = false;
    result.hidden = true;
  }

  document.getElementById("symptomFab").addEventListener("click", () => modal.showModal());
  document.getElementById("symptomClose").addEventListener("click", () => modal.close());
  modal.addEventListener("close", reset);

  metricSelect.addEventListener("change", () => {
    document.getElementById("symReading").placeholder = READING_HINTS[metricSelect.value] || "Optional";
  });

  result.addEventListener("click", (e) => {
    if (e.target.closest("#symptomAgain")) reset();
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = e.submitter;
    const original = button.innerHTML;
    button.disabled = true;
    button.textContent = "Thinking…";
    showError("");
    try {
      const { advice, savedReading } = await postSymptom({
        metric: metricSelect.value,
        reading: document.getElementById("symReading").value,
        description: document.getElementById("symDesc").value,
        context: modal.dataset.context, // "exercise" on the exercise page
      });
      renderAdvice(advice, savedReading ? metricSelect.value : null);
    } catch (err) {
      showError(err.message);
    } finally {
      button.disabled = false;
      button.innerHTML = original;
    }
  });
})();
