// Visual feedback only; the browser still submits the form to FastAPI.
const form = document.querySelector("#career-form");
const button = form.querySelector('button[type="submit"]');
const thinking = document.querySelector("#thinking");

form.addEventListener("submit", () => {
  thinking.hidden = false;
  form.setAttribute("aria-busy", "true");
  button.disabled = true;
});

// Restore the form when navigating back to a cached page.
window.addEventListener("pageshow", () => {
  thinking.hidden = true;
  form.removeAttribute("aria-busy");
  button.disabled = false;
});
