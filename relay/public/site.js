/**
 * Wires each [data-copy] button to copy the text of the element its
 * selector names, and shows "Copied" briefly as confirmation.
 */
function initCopyButtons() {
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const source = document.querySelector(button.dataset.copy);
      if (!source) return;
      try {
        await navigator.clipboard.writeText(source.textContent.trim());
        button.textContent = "Copied";
        button.dataset.state = "done";
      } catch {
        button.textContent = "Press Ctrl+C";
      }
      setTimeout(() => {
        button.textContent = "Copy";
        delete button.dataset.state;
      }, 1800);
    });
  });
}

document.addEventListener("DOMContentLoaded", initCopyButtons);
