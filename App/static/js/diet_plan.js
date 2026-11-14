// ---------- Diet plan page ----------
const pageData = JSON.parse(document.getElementById("diet-data").textContent);

const state = {
  plan: pageData.plan,
  checklist: pageData.checklist,
  view: "day",
  dayIndex: pageData.todayIndex,
  swap: null, // { meal: index, slot: "Lunch" } while the user is choosing a replacement
};

const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack"];
const SLOT_COLORS = { Breakfast: "#f2b84b", Lunch: "#4fa483", Dinner: "#1f7a5c", Snack: "#a8d8c4" };
const MACRO_COLORS = { Protein: "#1f7a5c", Carbs: "#f2b84b", Fat: "#e5885f" };
const READING_HINTS = { "Blood sugar": "e.g. 4.2 mmol/L", "Blood pressure": "e.g. 145/95" };

Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.color = "#6b7a74";
let chart = null;

// ---------- Helpers ----------

// Escape text before putting it in HTML (plan text comes from the AI)
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

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

function sumMeals(meals) {
  const total = (key) => meals.reduce((sum, m) => sum + (m[key] || 0), 0);
  return { calories: total("calories"), protein: total("protein_g"), carbs: total("carbs_g"), fat: total("fat_g") };
}

function drawChart(canvasId, config) {
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById(canvasId), config);
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
        <i data-lucide="utensils"></i>
        <p><strong>No meal plan yet</strong></p>
        <p class="muted small">Generate a 7-day plan based on your details and goal.</p>
        <button type="button" class="btn" data-action="start">Generate my plan</button>
      </div>`;
  } else if (state.view === "day") {
    renderDay(body);
  } else {
    renderWeek(body);
  }
  lucide.createIcons();
}

function mealRow(meal, i) {
  const swapping = state.swap?.meal === i;
  return `
    <li class="meal-row ${swapping ? "swapping" : ""}">
      <span class="slot-tag">${esc(meal.slot)}</span>
      <div class="meal-main">
        <a href="${esc(meal.recipe_url)}" target="_blank" rel="noopener" class="meal-name">
          ${esc(meal.name)} <i data-lucide="external-link"></i>
        </a>
        <small>${esc(meal.description)}</small>
      </div>
      <span class="kcal">${esc(meal.calories)} kcal</span>
      <button type="button" class="swap-btn" data-swap="${i}" title="Swap with an alternative"
              aria-label="Swap ${esc(meal.name)}"><i data-lucide="repeat"></i></button>
    </li>`;
}

function renderDay(body) {
  const day = state.plan.days[state.dayIndex];
  const totals = sumMeals(day.meals);
  const chips = DAY_SHORT.map((d, i) => `
    <button type="button" class="chip ${i === state.dayIndex ? "active" : ""} ${i === pageData.todayIndex ? "today" : ""}"
            data-day="${i}">${d}</button>`).join("");
  const legend = Object.entries(MACRO_COLORS).map(([name, color]) => `
    <li><span class="key" style="background:${color}"></span>${name} <strong>${totals[name.toLowerCase()]} g</strong></li>`).join("");

  body.innerHTML = `
    <div class="day-chips">${chips}</div>
    <div class="day-layout">
      <ul class="meal-list">${day.meals.map(mealRow).join("")}</ul>
      <div class="macros">
        <div class="donut">
          <canvas id="macroChart"></canvas>
          <div class="donut-center"><strong>${totals.calories}</strong><span>kcal</span></div>
        </div>
        <ul class="macro-legend">${legend}</ul>
      </div>
    </div>`;

  drawChart("macroChart", {
    type: "doughnut",
    data: {
      labels: Object.keys(MACRO_COLORS),
      datasets: [{
        data: [totals.protein, totals.carbs, totals.fat],
        backgroundColor: Object.values(MACRO_COLORS),
        borderWidth: 0,
      }],
    },
    options: {
      cutout: "72%",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.parsed} g` } } },
    },
  });
}

function renderWeek(body) {
  body.innerHTML = `
    <p class="muted small">Calories per day. Click a day to see its meals.</p>
    <div class="week-chart"><canvas id="weekChart"></canvas></div>`;

  drawChart("weekChart", {
    type: "bar",
    data: {
      labels: DAY_SHORT,
      datasets: SLOTS.map((slot) => ({
        label: slot,
        data: state.plan.days.map((d) => sumMeals(d.meals.filter((m) => m.slot === slot)).calories),
        backgroundColor: SLOT_COLORS[slot],
        borderRadius: 6,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, title: { display: true, text: "kcal" }, grid: { color: "#e6ece9" } },
      },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: { callbacks: { footer: (items) => `Total: ${items.reduce((s, i) => s + i.parsed.y, 0)} kcal` } },
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

  const alts = state.plan.alternatives;
  if (state.swap) {
    const meal = state.plan.days[state.dayIndex].meals[state.swap.meal];
    const hasMatch = alts.some((a) => a.slot === state.swap.slot);
    banner.hidden = false;
    banner.innerHTML = `
      <span>${hasMatch
        ? `Pick a <strong>${esc(meal.slot.toLowerCase())}</strong> to replace <strong>${esc(meal.name)}</strong> on ${DAY_SHORT[state.dayIndex]}.`
        : `No ${esc(meal.slot.toLowerCase())} alternatives in this plan. Try making a new plan.`}</span>
      <button type="button" class="btn-link" data-action="cancel-swap">Cancel</button>`;
  } else {
    banner.hidden = true;
  }

  body.innerHTML = alts.length
    ? alts.map((alt, i) => {
        const match = state.swap && alt.slot === state.swap.slot;
        const dim = state.swap && !match;
        return `
          <article class="alt-card ${match ? "match" : ""} ${dim ? "dim" : ""}">
            <span class="slot-tag">${esc(alt.slot)}</span>
            <a href="${esc(alt.recipe_url)}" target="_blank" rel="noopener" class="alt-name">${esc(alt.name)}</a>
            <small class="muted">${esc(alt.description)}</small>
            <div class="alt-foot">
              <span class="kcal">${esc(alt.calories)} kcal</span>
              ${match ? `<button type="button" class="btn btn-sm" data-use-alt="${i}">Use this</button>` : ""}
            </div>
          </article>`;
      }).join("")
    : `<p class="muted small">No alternatives in this plan.</p>`;
}

// ---------- Checklist ----------

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

// ---------- Plan generation ----------

function openModal(id) {
  document.getElementById(id).showModal();
}

async function generatePlan(button, note = "") {
  await withBusy(button, "Generating…", async () => {
    await api("/api/diet/generate", { note });
    location.reload();
  });
}

document.getElementById("regenBtn").addEventListener("click", () => openModal("regenModal"));

document.getElementById("regenForm").addEventListener("submit", (e) => {
  e.preventDefault();
  generatePlan(e.submitter, document.getElementById("regenNote").value.trim());
});

// ---------- Goal ----------

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
    if (state.plan && confirm("Goal saved! Make a new meal plan that matches it?")) {
      try {
        await api("/api/diet/generate");
      } catch (err) {
        alert(`Your goal was saved, but the new plan failed: ${err.message}`);
      }
    }
    location.reload();
  });
});

// ---------- Log symptom ----------

const symptomForm = document.getElementById("symptomForm");
const symptomResult = document.getElementById("symptomResult");
const metricSelect = document.getElementById("symMetric");

metricSelect.addEventListener("change", () => {
  document.getElementById("symReading").placeholder = READING_HINTS[metricSelect.value] || "Optional";
});

function renderAdvice(advice) {
  const section = (title, items) =>
    items?.length ? `<h4>${title}</h4><ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "";

  symptomResult.innerHTML = `
    <div class="advice ${advice.urgent ? "urgent" : ""}">
      ${advice.urgent ? `<p class="advice-flag"><i data-lucide="siren"></i> Get help now</p>` : ""}
      <p class="advice-summary">${esc(advice.summary)}</p>
      ${section("Do this now", advice.do_now)}
      ${section("Eat or drink", advice.eat)}
      ${section("Avoid", advice.avoid)}
      ${section("Get medical help if", advice.seek_help_if)}
      ${advice.demo ? `<p class="muted small">Demo answer. Add a Groq API key for personalised advice.</p>` : ""}
    </div>
    <button type="button" class="btn btn-outline btn-block" data-action="new-symptom">Log another</button>`;
  symptomForm.hidden = true;
  symptomResult.hidden = false;
  lucide.createIcons();
}

symptomForm.addEventListener("submit", (e) => {
  e.preventDefault();
  withBusy(e.submitter, "Thinking…", async () => {
    const { advice } = await api("/api/symptom", {
      metric: metricSelect.value,
      reading: document.getElementById("symReading").value,
      description: document.getElementById("symDesc").value,
    });
    renderAdvice(advice);
  });
});

function resetSymptomForm() {
  symptomForm.reset();
  symptomForm.hidden = false;
  symptomResult.hidden = true;
}

document.getElementById("symptomModal").addEventListener("close", resetSymptomForm);

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
    const meal = state.plan.days[state.dayIndex].meals[i];
    state.swap = state.swap?.meal === i ? null : { meal: i, slot: meal.slot };
    renderSchedule();
    renderAlternatives();
    if (state.swap) document.querySelector(".alts-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  if (el.dataset.useAlt) {
    await withBusy(el, "Swapping…", async () => {
      const res = await api("/api/diet/swap", { day: state.dayIndex, meal: state.swap.meal, alt: Number(el.dataset.useAlt) });
      state.plan = res.plan;
      state.checklist = res.checklist;
      state.swap = null;
      renderSchedule();
      renderAlternatives();
      renderChecklist();
      showToast("Meal swapped.");
    });
    return;
  }

  const action = el.dataset.action;
  if (action === "start") {
    generatePlan(el);
  } else if (action === "cancel-swap") {
    state.swap = null;
    renderSchedule();
    renderAlternatives();
  } else if (action === "new-symptom") {
    resetSymptomForm();
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
