// Draw the Lucide icons
lucide.createIcons();

// ---------- Profile dropdown ----------
const profileBtn = document.getElementById("profileBtn");
const profileDropdown = document.getElementById("profileDropdown");

if (profileBtn && profileDropdown) {
  // Open/close when the profile is clicked
  profileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = profileDropdown.classList.toggle("open");
    profileBtn.setAttribute("aria-expanded", open);
  });

  // Close when clicking anywhere else
  document.addEventListener("click", () => {
    profileDropdown.classList.remove("open");
    profileBtn.setAttribute("aria-expanded", false);
  });

  // Close with the Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      profileDropdown.classList.remove("open");
      profileBtn.setAttribute("aria-expanded", false);
    }
  });
}

// Heartbeat: tells the server this page is still open. If every ChronoCare
// tab is closed, the pings stop and a login without "Keep me logged in" ends.
(function () {
  var timer = setInterval(function () {
    fetch("/auth/ping", { credentials: "same-origin", cache: "no-store" })
      .then(function (response) {
        if (response.redirected) {          // the server signed us out
          window.location.href = response.url;
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        if (data && !data.signed_in) clearInterval(timer);  // nobody logged in, stop pinging
      })
      .catch(function () {});               // server down or offline: try again next time
  }, 20000);
})();