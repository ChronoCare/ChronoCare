// ---------- Exercise page ----------
// Same structure as diet_plan.js: sessions instead of meals, minutes instead of calories.
const pageData = JSON.parse(document.getElementById("exercise-data").textContent);

const state = {
  plan: pageData.plan,
  checklist: pageData.checklist,
  view: "day",
  dayIndex: pageData.todayIndex,
  swap: null, // { session: index } while the user is choosing a replacement
};

const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const INTENSITY_COLORS = { Low: "#a8d8c4", Moderate: "#4fa483", High: "#e5885f" };
const WEEKLY_TARGET = 150; // minutes of moderate activity a week (common health guideline)

Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.color = "#6b7a74";
let chart = null;

// ---------- Helpers ----------

// Escape text before putting it in HTML (plan text comes from the AI)
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// CSS-friendly name, e.g. "Yoga & mobility" -> "yoga-mobility"
const slug = (text) => String(text).toLowerCase().replace(/[^a-z]+/g, "-").replace(/(^-|-$)/g, "");

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

// Disable a button and show a loading label while fn runs
async function withBusy(button, label, fn) {
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = label;
  try {
    await fn();
  } catch (err) {
    showToast(err.message);
  } finally {
    button.disabled = false;
    button.innerHTML = original;
    lucide.createIcons();
  }
}

// Minutes per intensity for a list of sessions, e.g. { Low: 10, Moderate: 30, High: 0 }
function minutesByIntensity(sessions) {
  const totals = { Low: 0, Moderate: 0, High: 0 };
  sessions.forEach((s) => (totals[s.intensity] = (totals[s.intensity] || 0) + (s.duration_min || 0)));
  return totals;
}

const sum = (list, key) => list.reduce((total, item) => total + (item[key] || 0), 0);

function drawChart(canvasId, config) {
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById(canvasId), config);
}

function openModal(id) {
  document.getElementById(id).showModal();
}

// ---------- Schedule ----------

function renderSchedule() {
  const body = document.getElementById("scheduleBody");
  document.getElementById("planSummary").textContent = state.plan?.summary || "";

  if (!state.plan) {
    if (chart) chart.destroy();
    chart = null;
    body.innerHTML = `
      <div class="empty">
        <i data-lucide="dumbbell"></i>
        <p><strong>No workout plan yet</strong></p>
        <p class="muted small">Generate a 7-day plan based on your details, goal and fitness level.</p>
        <button type="button" class="btn" data-open="regenModal">Generate my plan</button>
      </div>`;
  } else if (state.view === "day") {
    renderDay(body);
  } else {
    renderWeek(body);
  }
  lucide.createIcons();
}

function sessionRow(session, i) {
  const swapping = state.swap?.session === i;
  const steps = session.steps?.length
    ? `<ul class="steps">${session.steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ul>`
    : "";
  return `
    <li class="meal-row session-row ${swapping ? "swapping" : ""}">
      <span class="slot-tag cat-${slug(session.category)}">${esc(session.category)}</span>
      <div class="meal-main">
        <a href="${esc(session.video_url)}" target="_blank" rel="noopener" class="meal-name">
          ${esc(session.name)} <i data-lucide="external-link"></i>
        </a>
        <small>${esc(session.description)}</small>
        ${steps}
      </div>
      <div class="session-meta">
        <span class="kcal">${esc(session.duration_min)} min</span>
        <span class="intensity int-${slug(session.intensity)}">${esc(session.intensity)}</span>
      </div>
      <button type="button" class="swap-btn" data-swap="${i}" title="Swap with an alternative"
              aria-label="Swap ${esc(session.name)}"><i data-lucide="repeat"></i></button>
    </li>`;
}

function renderDay(body) {
  const day = state.plan.days[state.dayIndex];
  const minutes = minutesByIntensity(day.sessions);
  const totalMinutes = sum(day.sessions, "duration_min");
  const chips = DAY_SHORT.map((d, i) => `
    <button type="button" class="chip ${i === state.dayIndex ? "active" : ""} ${i === pageData.todayIndex ? "today" : ""}"
            data-day="${i}">${d}</button>`).join("");
  const legend = Object.entries(INTENSITY_COLORS).map(([name, color]) => `
    <li><span class="key" style="background:${color}"></span>${name} <strong>${minutes[name]} min</strong></li>`).join("");

  body.innerHTML = `
    <div class="day-chips">${chips}</div>
    ${day.focus ? `<p class="day-focus">${esc(day.focus)}</p>` : ""}
    <div class="day-layout">
      <ul class="meal-list">${day.sessions.map(sessionRow).join("")}</ul>
      <div class="macros">
        <div class="donut">
          <canvas id="intensityChart"></canvas>
          <div class="donut-center"><strong>${totalMinutes}</strong><span>min</span></div>
        </div>
        <ul class="macro-legend">
          ${legend}
          <li class="legend-total">About <strong>${sum(day.sessions, "calories")} kcal</strong></li>
        </ul>
      </div>
    </div>`;

  drawChart("intensityChart", {
    type: "doughnut",
    data: {
      labels: Object.keys(INTENSITY_COLORS),
      datasets: [{
        data: Object.keys(INTENSITY_COLORS).map((k) => minutes[k]),
        backgroundColor: Object.values(INTENSITY_COLORS),
        borderWidth: 0,
      }],
    },
    options: {
      cutout: "72%",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.parsed} min` } } },
    },
  });
}

function renderWeek(body) {
  const weekMinutes = state.plan.days.reduce((total, d) => total + sum(d.sessions, "duration_min"), 0);
  const activeMinutes = state.plan.days.reduce(
    (total, d) => total + sum(d.sessions.filter((s) => s.intensity !== "Low"), "duration_min"), 0);

  body.innerHTML = `
    <p class="muted small">
      <strong>${weekMinutes} min</strong> this week, ${activeMinutes} of them moderate or high intensity
      (a common target is ${WEEKLY_TARGET}). Click a day to see its workouts.
    </p>
    <div class="week-chart"><canvas id="weekChart"></canvas></div>`;

  drawChart("weekChart", {
    type: "bar",
    data: {
      labels: DAY_SHORT,
      datasets: Object.entries(INTENSITY_COLORS).map(([intensity, color]) => ({
        label: intensity,
        data: state.plan.days.map((d) => minutesByIntensity(d.sessions)[intensity]),
        backgroundColor: color,
        borderRadius: 6,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, title: { display: true, text: "minutes" }, grid: { color: "#e6ece9" } },
      },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: {
          callbacks: {
            footer: (items) => {
              const day = state.plan.days[items[0].dataIndex];
              return `Total: ${items.reduce((s, i) => s + i.parsed.y, 0)} min${day.focus ? ` · ${day.focus}` : ""}`;
            },
          },
        },
      },
      onClick: (_event, elements) => {
        if (elements.length) {
          state.dayIndex = elements[0].index;
          setView("day");
        }
      },
    },
  });
}

function setView(view) {
  state.view = view;
  state.swap = null;
  document.querySelectorAll(".seg").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  renderSchedule();
  renderAlternatives();
}

// ---------- Alternatives ----------

function renderAlternatives() {
  const body = document.getElementById("altsBody");
  const banner = document.getElementById("swapBanner");

  if (!state.plan) {
    banner.hidden = true;
    body.innerHTML = `<p class="muted small">Alternatives appear here once you have a plan.</p>`;
    return;
  }

  if (state.swap) {
    const session = state.plan.days[state.dayIndex].sessions[state.swap.session];
    banner.hidden = false;
    banner.innerHTML = `
      <span>Pick a workout to replace <strong>${esc(session.name)}</strong> on ${DAY_SHORT[state.dayIndex]}.</span>
      <button type="button" class="btn-link" data-action="cancel-swap">Cancel</button>`;
  } else {
    banner.hidden = true;
  }

  const alts = state.plan.alternatives;
  body.innerHTML = alts.length
    ? alts.map((alt, i) => `
        <article class="alt-card ${state.swap ? "match" : ""}">
          <span class="slot-tag cat-${slug(alt.category)}">${esc(alt.category)}</span>
          <a href="${esc(alt.video_url)}" target="_blank" rel="noopener" class="alt-name">${esc(alt.name)}</a>
          <small class="muted">${esc(alt.description)}</small>
          <div class="alt-foot">
            <span class="kcal">${esc(alt.duration_min)} min · <span class="intensity int-${slug(alt.intensity)}">${esc(alt.intensity)}</span></span>
            ${state.swap ? `<button type="button" class="btn btn-sm" data-use-alt="${i}">Use this</button>` : ""}
          </div>
        </article>`).join("")
    : `<p class="muted small">No alternatives in this plan.</p>`;
}

// ---------- Checklist (shares /api/checklist with the diet page) ----------

function renderChecklist() {
  document.getElementById("checklist").innerHTML = state.checklist.map((item, i) => `
    <li>
      <label class="check-item">
        <input type="checkbox" data-check="${i}" ${item.done ? "checked" : ""}>
        <span>${esc(item.label)}</span>
      </label>
    </li>`).join("");
  updateProgress();
}

function updateProgress() {
  const done = state.checklist.filter((i) => i.done).length;
  const total = state.checklist.length;
  document.getElementById("checkProgress").style.width = total ? `${(done / total) * 100}%` : "0%";
  document.getElementById("checkCount").textContent = `${done} of ${total} done`;
}

document.getElementById("checklist").addEventListener("change", async (e) => {
  const item = state.checklist[e.target.dataset.check];
  if (!item) return;
  item.done = e.target.checked;
  updateProgress();
  try {
    await api("/api/checklist", { label: item.label, done: item.done });
  } catch (err) {
    item.done = !item.done; // undo if saving failed
    e.target.checked = item.done;
    updateProgress();
    showToast(err.message);
  }
});

// ---------- New plan ----------

document.getElementById("regenForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = Object.fromEntries(new FormData(e.target));
  withBusy(e.submitter, "Generating…", async () => {
    await api("/api/exercise/generate", form);
    location.reload();
  });
});

// ---------- Goal (shared with the diet page) ----------

const goalForm = document.getElementById("goalForm");
const goalView = document.getElementById("goalView");

document.getElementById("editGoalBtn")?.addEventListener("click", () => {
  goalView.hidden = true;
  goalForm.hidden = false;
  document.getElementById("goalText").focus();
});

document.getElementById("cancelGoalBtn")?.addEventListener("click", () => {
  goalForm.hidden = true;
  goalView.hidden = false;
});

goalForm.addEventListener("submit", (e) => {
  e.preventDefault();
  withBusy(e.submitter, "Saving…", async () => {
    await api("/api/goal", { text: document.getElementById("goalText").value });
    if (state.plan && confirm("Goal saved! Make a new workout plan that matches it?")) {
      try {
        await api("/api/exercise/generate", state.plan.prefs || {});
      } catch (err) {
        alert(`Your goal was saved, but the new plan failed: ${err.message}`);
      }
    }
    location.reload();
  });
});

// ---------- Clicks ----------

document.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-view], [data-day], [data-swap], [data-use-alt], [data-action], [data-open], [data-close]");
  if (!el) return;

  if (el.dataset.view) return setView(el.dataset.view);
  if (el.dataset.open) return openModal(el.dataset.open);
  if (el.hasAttribute("data-close")) return el.closest("dialog").close();

  if (el.dataset.day) {
    state.dayIndex = Number(el.dataset.day);
    state.swap = null;
    renderSchedule();
    renderAlternatives();
    return;
  }

  if (el.dataset.swap) {
    const i = Number(el.dataset.swap);
    state.swap = state.swap?.session === i ? null : { session: i };
    renderSchedule();
    renderAlternatives();
    if (state.swap) document.querySelector(".alts-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  if (el.dataset.useAlt) {
    await withBusy(el, "Swapping…", async () => {
      const res = await api("/api/exercise/swap", { day: state.dayIndex, session: state.swap.session, alt: Number(el.dataset.useAlt) });
      state.plan = res.plan;
      state.checklist = res.checklist;
      state.swap = null;
      renderSchedule();
      renderAlternatives();
      renderChecklist();
      showToast("Workout swapped.");
    });
    return;
  }

  if (el.dataset.action === "cancel-swap") {
    state.swap = null;
    renderSchedule();
    renderAlternatives();
  }
});

// Esc cancels swap mode (dialogs close themselves on Esc)
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.swap && !document.querySelector("dialog[open]")) {
    state.swap = null;
    renderSchedule();
    renderAlternatives();
  }
});

// ---------- First render ----------
renderSchedule();
renderAlternatives();
renderChecklist();
