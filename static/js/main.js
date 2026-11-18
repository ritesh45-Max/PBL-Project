/* TruthGuard AI - frontend behaviour */
document.addEventListener("DOMContentLoaded", () => {
  setupDropzones();
  setupCharCounters();
  setupAnalyzeForms();
  setupConfirmDialogs();
});

/* ---------- Drag & drop upload with preview and validation ---------- */
function setupDropzones() {
  document.querySelectorAll("[data-dropzone]").forEach((zone) => {
    const input = zone.querySelector("[data-file-input]");
    const previewBox = zone.querySelector("[data-preview-box]");
    const prompt = zone.querySelector(".dz-prompt");
    const form = zone.closest("form");
    const errorBox = form ? form.querySelector("[data-error]") : null;
    const allowed = (zone.dataset.exts || "").split(",");
    const maxBytes = Number(zone.dataset.maxMb || 5) * 1024 * 1024;

    const showError = (msg) => {
      if (!errorBox) return;
      errorBox.textContent = msg;
      errorBox.classList.remove("d-none");
    };
    const clearError = () => errorBox && errorBox.classList.add("d-none");

    const handleFile = (file) => {
      clearError();
      if (!file) return;
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      if (!allowed.includes(ext)) {
        showError(`Unsupported file type. Allowed: ${allowed.join(", ").toUpperCase()}.`);
        input.value = "";
        return;
      }
      if (file.size === 0) {
        showError("The selected file is empty.");
        input.value = "";
        return;
      }
      if (file.size > maxBytes) {
        showError(`File is too large. Maximum size is ${zone.dataset.maxMb} MB.`);
        input.value = "";
        return;
      }
      showPreview(file);
    };

    const showPreview = (file) => {
      previewBox.innerHTML = "";
      const url = URL.createObjectURL(file);
      const isVideo = file.type.startsWith("video") || /(mp4|webm|mov|avi)$/i.test(file.name);
      const media = document.createElement(isVideo ? "video" : "img");
      media.src = url;
      if (isVideo) {
        media.controls = true;
        media.muted = true;
        media.preload = "metadata";
      } else {
        media.alt = "Selected image preview";
      }
      const name = document.createElement("div");
      name.className = "preview-name";
      name.textContent = `${file.name} · ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
      previewBox.append(media, name);
      previewBox.classList.remove("d-none");
      prompt.classList.add("d-none");
    };

    zone.addEventListener("click", (event) => {
      if (event.target.closest("video")) return; // let video controls work
      input.click();
    });
    input.addEventListener("change", () => handleFile(input.files[0]));

    ["dragenter", "dragover"].forEach((evt) =>
      zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
    ["dragleave", "drop"].forEach((evt) =>
      zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
    zone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files[0];
      if (!file) return;
      input.files = e.dataTransfer.files; // hand the dropped file to the form input
      handleFile(file);
    });
  });
}

/* ---------- Character counter for the text box ---------- */
function setupCharCounters() {
  document.querySelectorAll("textarea[data-counter]").forEach((area) => {
    const form = area.closest("form");
    const target = form.querySelector("[data-counter-target]");
    const update = () => {
      const max = area.maxLength > 0 ? area.maxLength : 5000;
      target.textContent = `${area.value.length} / ${max}`;
    };
    area.addEventListener("input", update);
    update();
  });
}

/* ---------- Loading overlay on analysis submit ---------- */
function setupAnalyzeForms() {
  document.querySelectorAll("form.analyze-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const fileInput = form.querySelector("[data-file-input]");
      if (fileInput && !fileInput.files.length) {
        event.preventDefault();
        const errorBox = form.querySelector("[data-error]");
        if (errorBox) {
          errorBox.textContent = "Please choose a file before analyzing.";
          errorBox.classList.remove("d-none");
        }
        return;
      }
      if (!form.checkValidity()) {
        event.preventDefault();
        form.reportValidity();
        return;
      }
      const button = form.querySelector("button[type='submit']");
      if (button) button.disabled = true;
      document.getElementById("loadingOverlay").classList.remove("d-none");
    });
  });
}

/* ---------- Confirm dialogs (e.g. deleting history) ---------- */
function setupConfirmDialogs() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
}
