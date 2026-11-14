// ---------- Overview page ----------
const pageData = JSON.parse(document.getElementById("overview-data").textContent);

const state = {
  items: pageData.items,          // today's plan, in time order
  cards: pageData.cards,          // latest blood sugar, blood pressure, sleep
  weeks: pageData.weeks,          // 4 weeks, oldest first
  weekIndex: pageData.weeks.length - 1,
  selectedDay: null,              // index of a clicked day in the shown week
};

const KIND_ICONS = {
  meal: "utensils", workout: "activity", rest: "bed-double", sleep: "moon", check: "stethoscope",
};
const TONE_ICONS = { good: "check", warn: "circle-alert", bad: "triangle-alert" };
const TONE_COLORS = { good: "#1f7a5c", warn: "#d99a1e", bad: "#e5533d" };

// ---------- Helpers ----------

// Escape text before putting it in HTML (plan names come from the AI)
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// "17:30" -> "5:30 PM"
function clock(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

const toMinutes = (hhmm) => hhmm.split(":").map(Number).reduce((h, m) => h * 60 + m);

// When a reading was logged, in the viewer's own time zone
function whenLogged(iso) {
  if (!iso) return "";
  const at = new Date(iso);
  const time = at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const days = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(at).setHours(0, 0, 0, 0)) / 86400000);
  if (days === 0) return `Today, ${time}`;
  if (days === 1) return `Yesterday, ${time}`;
  return at.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

// A ring drawn with CSS (see .ov-ring); `percent` from 0 to 100
function ring(percent, color, label = `${percent}%`) {
  return `<span class="ov-ring" style="--p:${percent};--c:${color}"><span>${label}</span></span>`;
}

async function api(url, body = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Flask-WTF's CSRFProtect rejects POSTs without this token (it comes from base.html)
      "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
    },
    body: JSON.stringify(body),
  });
  // Logged out (e.g. session expired): Flask redirects to the login page
  if (res.redirected) {
    location.reload();
    throw new Error("Please log in again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again.");
  return data;
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => (toast.hidden = true), 4000);
}

// ---------- Greeting ----------

function renderGreeting() {
  const hour = new Date().getHours();
  document.getElementById("greeting").textContent =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  document.getElementById("todayDate").textContent =
    new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
}

// ---------- Reading cards ----------

function renderCards() {
  const empty = {
    sugar: `<p class="ov-empty">No readings yet</p><button type="button" class="btn btn-sm btn-outline" data-log="blood_sugar">Log your first</button>`,
    pressure: `<p class="ov-empty">No readings yet</p><button type="button" class="btn btn-sm btn-outline" data-log="blood_pressure">Log your first</button>`,
    sleep: `<p class="ov-empty">No sleep logged yet</p><a class="btn btn-sm btn-outline" href="/sleep">Log last night</a>`,
  };
  for (const [key, card] of Object.entries(state.cards)) {
    const body = document.querySelector(`[data-card="${key}"] .ov-stat-body`);
    if (!card) {
      body.innerHTML = empty[key];
      continue;
    }
    body.innerHTML = `
      <div class="ov-stat-main">
        <div>
          <p class="ov-value">${esc(card.value)} <span>${esc(card.unit)}</span></p>
          <p class="ov-status tone-${card.tone}"><i data-lucide="${TONE_ICONS[card.tone]}"></i> ${esc(card.status)}</p>
        </div>
        ${ring(card.score, TONE_COLORS[card.tone])}
      </div>
      <p class="muted small">${esc(card.detail)}${card.at ? ` · ${whenLogged(card.at)}` : ""}</p>`;
  }
  lucide.createIcons();
}

// ---------- Today's plan ----------

function renderPlan() {
  const list = document.getElementById("planItems");
  if (!state.items.length) {
    list.innerHTML = `
      <li class="ov-empty-plan">
        <p><strong>Nothing planned yet</strong></p>
        <p class="muted small">Make a plan on any page and it shows up here.</p>
        <p class="ov-links">
          <a class="btn btn-sm btn-outline" href="/diet_plan">Meal plan</a>
          <a class="btn btn-sm btn-outline" href="/exercise">Workouts</a>
          <a class="btn btn-sm btn-outline" href="/sleep">Sleep routine</a>
        </p>
      </li>`;
  } else {
    list.innerHTML = state.items.map((item, i) => `
      <li class="ov-item ${item.done ? "done" : ""}">
        <span class="ov-icon ov-kind-${item.kind}"><i data-lucide="${KIND_ICONS[item.kind]}"></i></span>
        <span class="ov-time">${clock(item.time)}</span>
        <div class="ov-item-text">
          <p class="ov-item-title">${esc(item.title)}</p>
          <p class="muted small">${esc(item.detail)}</p>
        </div>
        <label class="ov-check" title="Mark as done">
          <input type="checkbox" data-item="${i}" ${item.done ? "checked" : ""}>
          <span><i data-lucide="check"></i></span>
          <span class="sr-only">Done: ${esc(item.title)}</span>
        </label>
      </li>`).join("");
  }
  const done = state.items.filter((i) => i.done).length;
  document.getElementById("planCount").textContent = state.items.length ? `${done} of ${state.items.length} done` : "";
  document.getElementById("planProgress").style.width = state.items.length ? `${(done / state.items.length) * 100}%` : "0%";
  lucide.createIcons();
}

document.getElementById("planItems").addEventListener("change", async (e) => {
  const item = state.items[e.target.dataset.item];
  if (!item) return;
  await setDone(item, e.target.checked);
});

// Tick or untick an item, keep the week and "Up next" in sync, undo if saving fails
async function setDone(item, done) {
  const change = done ? 1 : -1;
  const today = state.weeks[state.weeks.length - 1].days.find((d) => d.isToday);
  item.done = done;
  today.done += change;
  state.weeks[state.weeks.length - 1].done += change;
  rerenderPlanParts();
  try {
    await api("/api/checklist", { label: item.label, done });
  } catch (err) {
    item.done = !done;
    today.done -= change;
    state.weeks[state.weeks.length - 1].done -= change;
    rerenderPlanParts();
    showToast(err.message);
  }
}

function rerenderPlanParts() {
  renderPlan();
  renderWeek();
  renderUpNext();
}

// ---------- Consistency ----------

function dayStatus(day) {
  if (day.status === "future") return "future";
  if (day.done === 0) return "none";
  return day.done >= day.total ? "all" : "some";
}

function renderWeek() {
  const week = state.weeks[state.weekIndex];
  const isThisWeek = state.weekIndex === state.weeks.length - 1;
  document.getElementById("weekTitle").textContent = isThisWeek ? "This week" : week.label;
  document.querySelector('[data-week="-1"]').disabled = state.weekIndex === 0;
  document.querySelector('[data-week="1"]').disabled = isThisWeek;

  document.getElementById("weekDays").innerHTML = week.days.map((day, i) => `
    <button type="button" class="ov-day ${day.isToday ? "today" : ""} ${state.selectedDay === i ? "selected" : ""}"
            data-day="${i}" ${day.status === "future" ? "disabled" : ""}>
      <span>${day.dow}</span>
      <strong>${day.num}</strong>
      <i class="ov-dot dot-${dayStatus(day)}"></i>
    </button>`).join("");

  const day = state.selectedDay !== null ? week.days[state.selectedDay] : null;
  const done = day ? day.done : week.done;
  const total = day ? day.total : week.total;
  const percent = total ? Math.round((done / total) * 100) : 0;
  document.getElementById("weekPercent").textContent = total ? `${percent}%` : "–";
  document.getElementById("weekText").textContent = !total
    ? "No plans to track yet"
    : day ? `of the plan done on ${new Date(day.date + "T00:00").toLocaleDateString([], { weekday: "long" })} (${done} of ${total})`
    : `of your plan completed ${isThisWeek ? "this week" : "that week"}`;
  const weekRing = document.getElementById("weekRing");
  weekRing.style.setProperty("--p", percent);
  weekRing.style.setProperty("--c", "#1f7a5c");
}

// ---------- Up next ----------

function renderUpNext() {
  const box = document.getElementById("upNext");
  if (!state.items.length) {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  const now = new Date().getHours() * 60 + new Date().getMinutes();
  const next = state.items.find((i) => !i.done && toMinutes(i.time) >= now);
  const missed = state.items.find((i) => !i.done);
  const item = next || missed;

  if (!item) {
    box.innerHTML = `
      <span class="ov-icon ov-next-icon"><i data-lucide="party-popper"></i></span>
      <div><p class="eyebrow">All done</p><h3>You've finished today's plan</h3><p class="muted small">Nice work. See you tomorrow.</p></div>`;
  } else {
    const button = item.link
      ? `<a class="btn btn-outline" href="${esc(item.link)}" ${item.link.startsWith("http") ? 'target="_blank" rel="noopener"' : ""}>${esc(item.linkLabel)} <i data-lucide="chevron-right"></i></a>`
      : item.action
        ? `<button type="button" class="btn btn-outline" data-log="${item.action === "log-sugar" ? "blood_sugar" : "blood_pressure"}">${esc(item.actionLabel)} <i data-lucide="chevron-right"></i></button>`
        : "";
    box.innerHTML = `
      <span class="ov-icon ov-next-icon ov-kind-${item.kind}"><i data-lucide="${KIND_ICONS[item.kind]}"></i></span>
      <div class="ov-next-text">
        <p class="eyebrow">${next ? "Up next" : "Still to do"} · ${clock(item.time)}</p>
        <h3>${esc(item.title)}</h3>
        <p class="muted small">${esc(item.detail)}</p>
      </div>
      ${button}`;
  }
  lucide.createIcons();
}

// ---------- Log health data ----------

const modal = document.getElementById("readingModal");
const form = document.getElementById("readingForm");
const metric = document.getElementById("metric");
const errorBox = document.getElementById("readingError");
const result = document.getElementById("readingResult");

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = !message;
}

function updateFields() {
  const sugar = metric.value === "blood_sugar";
  document.querySelectorAll("[data-sugar-only]").forEach((el) => (el.hidden = !sugar));
  const input = document.getElementById("readingValue");
  input.placeholder = sugar ? (document.getElementById("unit").value === "mmol/L" ? "e.g. 5.6" : "e.g. 100") : "e.g. 120/80";
  input.inputMode = sugar ? "decimal" : "text";
}

function openReadingModal(kind) {
  form.reset();
  try { // remember the unit they used last time (only in this browser)
    const unit = localStorage.getItem("sugarUnit");
    if (unit) document.getElementById("unit").value = unit;
  } catch {}
  metric.value = kind;
  form.hidden = false;
  result.hidden = true;
  showError("");
  updateFields();
  modal.showModal();
  document.getElementById("readingValue").focus();
}

metric.addEventListener("change", updateFields);
document.getElementById("unit").addEventListener("change", updateFields);

function showUrgent(advice) {
  result.innerHTML = `
    <div class="advice urgent">
      <p class="advice-flag"><i data-lucide="siren"></i> Get help now</p>
      <p class="advice-summary">${esc(advice.summary)}</p>
      <h4>Do this now</h4>
      <ul>${advice.do_now.map((step) => `<li>${esc(step)}</li>`).join("")}</ul>
    </div>
    <p class="muted small">Your reading was saved.</p>
    <button type="button" class="btn btn-outline btn-block" data-close>Close</button>`;
  form.hidden = true;
  result.hidden = false;
  lucide.createIcons();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  const button = e.submitter;
  button.disabled = true;
  showError("");
  try {
    const res = await api("/api/readings", data);
    if (data.kind === "blood_sugar") {
      try { localStorage.setItem("sugarUnit", data.unit); } catch {}
    }
    state.cards = res.cards;
    renderCards();
    // Logging a reading also ticks off the matching "Check ..." item in today's plan
    const check = state.items.find((i) => i.action === (data.kind === "blood_sugar" ? "log-sugar" : "log-pressure"));
    if (check && !check.done) await setDone(check, true);
    if (res.urgent) {
      showUrgent(res.urgent);
    } else {
      modal.close();
      showToast("Reading saved.");
    }
  } catch (err) {
    showError(err.message); // inside the popup: a toast would be hidden behind it
  } finally {
    button.disabled = false;
  }
});

// ---------- Clicks ----------

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-log], [data-week], [data-day], [data-close]");
  if (!el) return;

  if (el.dataset.log) return openReadingModal(el.dataset.log);
  if (el.hasAttribute("data-close")) return el.closest("dialog").close();

  if (el.dataset.week) {
    state.weekIndex = Math.min(state.weeks.length - 1, Math.max(0, state.weekIndex + Number(el.dataset.week)));
    state.selectedDay = null;
    renderWeek();
    return;
  }

  if (el.dataset.day) {
    const i = Number(el.dataset.day);
    state.selectedDay = state.selectedDay === i ? null : i; // click again to go back to the week
    renderWeek();
  }
});

// ---------- First render ----------
renderGreeting();
renderCards();
renderPlan();
renderWeek();
renderUpNext();
setInterval(renderUpNext, 60 * 1000); // keep "Up next" current as time passes
