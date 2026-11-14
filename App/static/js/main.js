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
