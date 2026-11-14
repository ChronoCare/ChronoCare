// ---------- Sleep page ----------
// Same structure as diet_plan.js and exercise.js, plus logging sleep.
const pageData = JSON.parse(document.getElementById("sleep-data").textContent);

const state = {
  plan: pageData.plan,
  routine: pageData.routine,
  nights: pageData.nights, // last 7 nights, oldest first; hours = null if not logged
  stats: pageData.stats,
  goal: pageData.goal,
  view: "day",
  nightIndex: pageData.nights.length - 1, // last night
  swap: null, // { item: index } while choosing a replacement
};

const COLORS = { met: "#1f7a5c", close: "#f2b84b", short: "#e5885f", empty: "#eef6f2" };

Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.color = "#6b7a74";
let chart = null;

// ---------- Helpers ----------

// Escape text before putting it in HTML (routine text comes from the AI)
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const slug = (text) => String(text).toLowerCase().replace(/[^a-z]+/g, "-").replace(/(^-|-$)/g, "");

// "23:15" -> "11:15 pm"
function clock(hhmm) {
  if (!hhmm) return "";
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
}

// 7.5 -> "7 h 30 m"
function duration(hours) {
  const total = Math.round(hours * 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h} h ${m} m` : `${h} h`;
}

// "23:00" + 8 hours -> "07:00"
function addHours(hhmm, hours) {
  const [h, m] = hhmm.split(":").map(Number);
  const total = (h * 60 + m + Math.round(hours * 60)) % (24 * 60);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function hoursBetween(bed, wake) {
  const toMin = (t) => t.split(":").map(Number).reduce((h, m) => h * 60 + m);
  return (((toMin(wake) - toMin(bed)) % 1440) + 1440) % 1440 / 60;
}

function nightName(night, i) {
  const isLast = i === state.nights.length - 1;
  return isLast ? `Last night (${night.label})` : `${night.label} night`;
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

// Disable a button and show a loading label while fn runs
async function withBusy(button, label, fn, onError = showToast) {
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = label;
  try {
    await fn();
  } catch (err) {
    onError(err.message);
  } finally {
    button.disabled = false;
    button.innerHTML = original;
    lucide.createIcons();
  }
}

function drawChart(canvasId, config) {
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById(canvasId), config);
}

function barColor(hours) {
  if (hours >= state.goal.hours) return COLORS.met;
  if (hours >= state.goal.hours - 1) return COLORS.close;
  return COLORS.short;
}

// ---------- Sleep card: one night ----------

function renderSleep() {
  const body = document.getElementById("sleepBody");
  document.getElementById("planSummary").textContent = state.plan?.summary || "";
  state.view === "day" ? renderNight(body) : renderWeek(body);
  lucide.createIcons();
}

function renderNight(body) {
  const night = state.nights[state.nightIndex];
  const chips = state.nights.map((n, i) => `
    <button type="button" class="chip ${i === state.nightIndex ? "active" : ""} ${n.hours === null ? "" : "logged"}"
            data-night="${i}">${n.label}</button>`).join("");

  if (night.hours === null) {
    if (chart) chart.destroy();
    chart = null;
    body.innerHTML = `
      <div class="day-chips">${chips}</div>
      <div class="empty">
        <i data-lucide="moon"></i>
        <p><strong>No sleep logged for ${esc(nightName(night, state.nightIndex).toLowerCase())}</strong></p>
        <p class="muted small">Log when you went to bed and woke up to see how you did.</p>
        <button type="button" class="btn" data-log-night="${night.date}">Log this night</button>
      </div>`;
    return;
  }

  const goal = state.goal.hours;
  const diff = night.hours - goal;
  const verdict = Math.abs(diff) < 0.25
    ? `Right on your ${goal} h goal`
    : diff > 0 ? `${duration(diff)} more than your ${goal} h goal` : `${duration(-diff)} short of your ${goal} h goal`;
  const quality = night.quality ? pageData.quality[night.quality] : null;

  body.innerHTML = `
    <div class="day-chips">${chips}</div>
    <div class="day-layout">
      <div class="night-detail">
        <p class="night-title">${esc(nightName(night, state.nightIndex))}</p>
        <p class="night-hours">${duration(night.hours)}</p>
        <p class="night-verdict ${diff >= -0.25 ? "good" : "short"}">${verdict}</p>
        <dl class="night-facts">
          <div><dt>Went to bed</dt><dd>${clock(night.bedtime)}</dd></div>
          <div><dt>Woke up</dt><dd>${clock(night.wake)}</dd></div>
          ${quality ? `<div><dt>Quality</dt><dd>${"★".repeat(night.quality)}${"☆".repeat(5 - night.quality)} ${quality}</dd></div>` : ""}
        </dl>
        ${night.note ? `<p class="muted small">"${esc(night.note)}"</p>` : ""}
        <button type="button" class="btn-link" data-log-night="${night.date}">Edit this night</button>
      </div>
      <div class="macros">
        <div class="donut">
          <canvas id="nightChart"></canvas>
          <div class="donut-center"><strong>${Math.round((night.hours / goal) * 100)}%</strong><span>of goal</span></div>
        </div>
      </div>
    </div>`;

  drawChart("nightChart", {
    type: "doughnut",
    data: {
      labels: ["Slept", "Short of goal"],
      datasets: [{
        data: [night.hours, Math.max(goal - night.hours, 0)],
        backgroundColor: [barColor(night.hours), COLORS.empty],
        borderWidth: 0,
      }],
    },
    options: {
      cutout: "72%",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.label}: ${duration(c.parsed)}` } } },
    },
  });
}

// ---------- Sleep card: week ----------

function renderWeek(body) {
  const s = state.stats;
  const tiles = s.logged
    ? `
      <div class="stat"><span>Average</span><strong>${duration(s.average)}</strong></div>
      <div class="stat"><span>Best night</span><strong>${duration(s.best)}</strong><small>${esc(s.bestLabel)}</small></div>
      <div class="stat"><span>Usual bedtime</span><strong>${esc(s.avgBedtime)}</strong></div>
      <div class="stat"><span>Nights logged</span><strong>${s.logged} / ${s.nights}</strong></div>`
    : `<p class="muted small">Log a few nights to see your weekly average.</p>`;

  body.innerHTML = `
    <div class="stats">${tiles}</div>
    <div class="week-chart"><canvas id="weekChart"></canvas></div>`;

  drawChart("weekChart", {
    data: {
      labels: state.nights.map((n) => n.label),
      datasets: [
        {
          type: "bar",
          label: "Slept",
          data: state.nights.map((n) => n.hours),
          backgroundColor: state.nights.map((n) => (n.hours === null ? COLORS.empty : barColor(n.hours))),
          borderRadius: 6,
        },
        {
          type: "line",
          label: `Goal (${state.goal.hours} h)`,
          data: state.nights.map(() => state.goal.hours),
          borderColor: "#6b7a74",
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, suggestedMax: Math.max(10, state.goal.hours + 1), title: { display: true, text: "hours" }, grid: { color: "#e6ece9" } },
      },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: {
          callbacks: {
            label: (c) => (c.dataset.type === "line" ? ` Goal: ${state.goal.hours} h`
              : c.parsed.y === null ? " Not logged" : ` Slept: ${duration(c.parsed.y)}`),
          },
        },
      },
      onClick: (_event, elements) => {
        if (elements.length) {
          state.nightIndex = elements[0].index;
          setView("day");
        }
      },
    },
  });
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".seg").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  renderSleep();
}

// ---------- Tonight's routine (checklist) ----------

function renderRoutine() {
  const list = document.getElementById("routine");
  if (!state.plan) {
    list.innerHTML = `
      <li class="empty">
        <i data-lucide="bed-double"></i>
        <p class="muted small">Get a bedtime routine built around your sleep goal.</p>
        <button type="button" class="btn btn-sm" data-open="regenModal">Make my routine</button>
      </li>`;
  } else {
    list.innerHTML = state.routine.map((item, i) => `
      <li class="routine-row ${state.swap?.item === i ? "swapping" : ""}">
        <label class="check-item">
          <input type="checkbox" data-check="${i}" ${item.done ? "checked" : ""}>
          <span>
            <span class="routine-time">${esc(item.time)}</span>
            ${esc(item.name)}
            <small class="routine-desc">${esc(item.description)}</small>
          </span>
        </label>
        <button type="button" class="swap-btn" data-swap="${i}" title="Swap with an alternative"
                aria-label="Swap ${esc(item.name)}"><i data-lucide="repeat"></i></button>
      </li>`).join("");
  }
  updateProgress();
  lucide.createIcons();
}

function updateProgress() {
  const done = state.routine.filter((i) => i.done).length;
  const total = state.routine.length;
  document.getElementById("checkProgress").style.width = total ? `${(done / total) * 100}%` : "0%";
  document.getElementById("checkCount").textContent = total ? `${done} of ${total} done` : "";
}

document.getElementById("routine").addEventListener("change", async (e) => {
  const item = state.routine[e.target.dataset.check];
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

function renderTips() {
  const tips = state.plan?.tips || [];
  document.getElementById("tipsBox").hidden = !tips.length;
  document.getElementById("tipsList").innerHTML = tips.map((t) => `<li>${esc(t)}</li>`).join("");
}

// ---------- Alternatives ----------

function renderAlternatives() {
  const body = document.getElementById("altsBody");
  const banner = document.getElementById("swapBanner");

  if (!state.plan) {
    banner.hidden = true;
    body.innerHTML = `<p class="muted small">Alternatives appear here once you have a routine.</p>`;
    return;
  }

  if (state.swap) {
    const item = state.routine[state.swap.item];
    banner.hidden = false;
    banner.innerHTML = `
      <span>Pick something to do at <strong>${esc(item.time || "this step")}</strong> instead of <strong>${esc(item.name)}</strong>.</span>
      <button type="button" class="btn-link" data-action="cancel-swap">Cancel</button>`;
  } else {
    banner.hidden = true;
  }

  const alts = state.plan.alternatives;
  body.innerHTML = alts.length
    ? alts.map((alt, i) => `
        <article class="alt-card ${state.swap ? "match" : ""}">
          <span class="slot-tag rcat-${slug(alt.category)}">${esc(alt.category)}</span>
          <a href="${esc(alt.link)}" target="_blank" rel="noopener" class="alt-name">${esc(alt.name)}</a>
          <small class="muted">${esc(alt.description)}</small>
          <div class="alt-foot">
            <span class="kcal">${alt.minutes ? `${esc(alt.minutes)} min` : ""}</span>
            ${state.swap ? `<button type="button" class="btn btn-sm" data-use-alt="${i}">Use this</button>` : ""}
          </div>
        </article>`).join("")
    : `<p class="muted small">No alternatives in this routine.</p>`;
}

// ---------- Log sleep ----------

const logModal = document.getElementById("logModal");
const logForm = document.getElementById("logForm");
const logError = document.getElementById("logError");

function updatePreview() {
  const bed = document.getElementById("logBedtime").value;
  const wake = document.getElementById("logWake").value;
  document.getElementById("hoursPreview").textContent =
    bed && wake ? `That's ${duration(hoursBetween(bed, wake))} of sleep.` : "";
}

// Open the popup for a night (or last night), filled in with what's already logged
function openLogModal(nightDate) {
  const index = nightDate ? state.nights.findIndex((n) => n.date === nightDate) : state.nights.length - 1;
  const night = state.nights[index];
  document.getElementById("logNight").innerHTML = state.nights
    .map((n, i) => `<option value="${n.date}" ${i === index ? "selected" : ""}>${esc(nightName(n, i))}${n.hours === null ? "" : " ✓"}</option>`)
    .reverse().join("");
  document.getElementById("logBedtime").value = night.bedtime || state.goal.bedtime;
  document.getElementById("logWake").value = night.wake || addHours(state.goal.bedtime, state.goal.hours);
  document.getElementById("logQuality").value = night.quality || "";
  document.getElementById("logNote").value = night.note || "";
  logError.hidden = true;
  updatePreview();
  logModal.showModal();
}

document.getElementById("logNight").addEventListener("change", (e) => openLogModal(e.target.value));
document.getElementById("logBedtime").addEventListener("input", updatePreview);
document.getElementById("logWake").addEventListener("input", updatePreview);

logForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const form = Object.fromEntries(new FormData(logForm));
  withBusy(e.submitter, "Saving…", async () => {
    const res = await api("/api/sleep/log", form);
    state.nights = res.nights;
    state.stats = res.stats;
    state.nightIndex = state.nights.findIndex((n) => n.date === form.night);
    logModal.close();
    renderSleep();
    showToast("Sleep saved.");
  }, (message) => {
    // Errors show inside the popup: a toast on the page would be hidden behind it
    logError.textContent = message;
    logError.hidden = false;
  });
});

// ---------- Sleep goal ----------

const goalForm = document.getElementById("goalForm");
const goalView = document.getElementById("goalView");

document.getElementById("editGoalBtn")?.addEventListener("click", () => {
  goalView.hidden = true;
  goalForm.hidden = false;
});

document.getElementById("cancelGoalBtn")?.addEventListener("click", () => {
  goalForm.hidden = true;
  goalView.hidden = false;
});

goalForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const form = Object.fromEntries(new FormData(goalForm));
  withBusy(e.submitter, "Saving…", async () => {
    await api("/api/sleep/goal", form);
    if (state.plan && confirm("Goal saved! Make a new bedtime routine that matches it?")) {
      try {
        await api("/api/sleep/generate");
      } catch (err) {
        alert(`Your goal was saved, but the new routine failed: ${err.message}`);
      }
    }
    location.reload();
  });
});

// ---------- New routine ----------

document.getElementById("regenForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = Object.fromEntries(new FormData(e.target));
  withBusy(e.submitter, "Generating…", async () => {
    await api("/api/sleep/generate", form);
    location.reload();
  });
});

// ---------- Clicks ----------

document.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-view], [data-night], [data-log-night], [data-swap], [data-use-alt], [data-action], [data-open], [data-close]");
  if (!el) return;

  if (el.dataset.view) return setView(el.dataset.view);
  if (el.dataset.open) return document.getElementById(el.dataset.open).showModal();
  if (el.hasAttribute("data-close")) return el.closest("dialog").close();
  if (el.hasAttribute("data-log-night")) return openLogModal(el.dataset.logNight);

  if (el.dataset.night) {
    state.nightIndex = Number(el.dataset.night);
    renderSleep();
    return;
  }

  if (el.dataset.swap) {
    const i = Number(el.dataset.swap);
    state.swap = state.swap?.item === i ? null : { item: i };
    renderRoutine();
    renderAlternatives();
    if (state.swap) document.querySelector(".alts-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  if (el.dataset.useAlt) {
    await withBusy(el, "Swapping…", async () => {
      const res = await api("/api/sleep/swap", { item: state.swap.item, alt: Number(el.dataset.useAlt) });
      state.plan = res.plan;
      state.routine = res.routine;
      state.swap = null;
      renderRoutine();
      renderAlternatives();
      showToast("Routine updated.");
    });
    return;
  }

  if (el.dataset.action === "cancel-swap") {
    state.swap = null;
    renderRoutine();
    renderAlternatives();
  }
});

// Esc cancels swap mode (dialogs close themselves on Esc)
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.swap && !document.querySelector("dialog[open]")) {
    state.swap = null;
    renderRoutine();
    renderAlternatives();
  }
});

// ---------- First render ----------
renderSleep();
renderRoutine();
renderAlternatives();
renderTips();
