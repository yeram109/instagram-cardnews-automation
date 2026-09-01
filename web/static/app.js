const $ = (id) => document.getElementById(id);

const state = {
  files: [],      // 업로드 순서 = 슬라이드 순서 (1번이 커버)
  jobId: null,
  polling: null,
  mode: null,     // "generate" | "export"
};

// ────────────────────────────────────────── 이미지 선택
const dropzone = $("dropzone");
const fileInput = $("file-input");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  addFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => {
  addFiles(fileInput.files);
  fileInput.value = "";
});

const ALLOWED = ["image/jpeg", "image/png", "image/webp"];

function addFiles(fileList) {
  for (const file of fileList) {
    if (!ALLOWED.includes(file.type)) continue;
    state.files.push(file);
  }
  renderThumbs();
}

function renderThumbs() {
  const list = $("thumbs");
  list.innerHTML = "";
  state.files.forEach((file, i) => {
    const li = document.createElement("li");
    li.className = "thumb";

    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    img.alt = file.name;
    img.onload = () => URL.revokeObjectURL(img.src);

    const slot = document.createElement("span");
    slot.className = "thumb-slot";
    slot.textContent = i === 0 ? "커버" : String(i + 1);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "thumb-remove";
    remove.textContent = "×";
    remove.title = "제거";
    remove.onclick = () => {
      state.files.splice(i, 1);
      renderThumbs();
    };

    const move = document.createElement("div");
    move.className = "thumb-move";
    const left = document.createElement("button");
    left.type = "button";
    left.textContent = "←";
    left.disabled = i === 0;
    left.onclick = () => swap(i, i - 1);
    const right = document.createElement("button");
    right.type = "button";
    right.textContent = "→";
    right.disabled = i === state.files.length - 1;
    right.onclick = () => swap(i, i + 1);
    move.append(left, right);

    li.append(img, slot, remove, move);
    list.append(li);
  });
}

function swap(a, b) {
  [state.files[a], state.files[b]] = [state.files[b], state.files[a]];
  renderThumbs();
}

// ────────────────────────────────────────── 생성 요청
$("job-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const topic = $("topic").value.trim();
  const text = $("text").value.trim();
  if (!topic || !text) return;

  const form = new FormData();
  form.append("theme", document.querySelector('input[name="theme"]:checked').value);
  form.append("topic", topic);
  form.append("text", text);
  form.append("use_unsplash", $("use-unsplash").checked ? "true" : "false");
  state.files.forEach((file) => form.append("images", file, file.name));

  showError("form-error", null);
  setBusy(true);
  showPanel("progress");
  $("progress-step").textContent = "업로드 중...";

  try {
    const res = await fetch("/api/jobs", { method: "POST", body: form });
    const data = await parse(res);
    state.jobId = data.job_id;
    state.mode = "generate";
    startPolling();
  } catch (err) {
    setBusy(false);
    showPanel("idle");
    showError("form-error", err.message);
  }
});

// ────────────────────────────────────────── 폴링
function startPolling() {
  stopPolling();
  state.polling = setInterval(poll, 1000);
  poll();
}

function stopPolling() {
  if (state.polling) clearInterval(state.polling);
  state.polling = null;
}

async function poll() {
  try {
    const res = await fetch(`/api/jobs/${state.jobId}`);
    const job = await parse(res);

    if (job.status === "running" || job.status === "exporting") {
      const suffix = job.progress ? ` (${job.progress})` : "";
      $("progress-step").textContent = job.step + suffix;
      if (state.mode === "export") $("export-btn").textContent = "캡처 중" + suffix;
      return;
    }

    stopPolling();
    setBusy(false);

    if (job.status === "error") {
      if (state.mode === "export") {
        showPanel("result");
        showError("result-error", job.error);
        $("export-btn").textContent = "저장 (PNG 다운로드)";
      } else {
        showPanel("idle");
        showError("form-error", job.error);
      }
      return;
    }

    if (job.status === "ready") {
      showPanel("result");
      if (state.mode === "export" && job.zip_url) {
        showDownloads(job);
      } else {
        renderCards(job);
      }
    }
  } catch (err) {
    stopPolling();
    setBusy(false);
    showPanel("idle");
    showError("form-error", err.message);
  }
}

// ────────────────────────────────────────── 미리보기
function renderCards(job) {
  const cards = $("cards");
  cards.innerHTML = "";
  // 재생성 시 브라우저가 이전 HTML을 재사용하지 않도록 캐시 무효화
  const bust = Date.now();

  job.slides.forEach((slide, i) => {
    const card = document.createElement("div");
    card.className = "card";

    const frame = document.createElement("iframe");
    frame.src = `${slide.html_url}?t=${bust}`;
    frame.setAttribute("scrolling", "no");
    frame.title = slide.name;

    const label = document.createElement("span");
    label.className = "card-label";
    label.textContent = i === 0 ? "01 커버" : slide.name.replace("slide_", "");

    card.append(frame, label);
    card.onclick = () => openModal(`${slide.html_url}?t=${bust}`);
    cards.append(card);
  });

  $("slide-count").textContent = `${job.slides.length}장`;
  $("downloads").hidden = true;
  $("export-btn").textContent = "저장 (PNG 다운로드)";
  showError("result-error", null);
}

function showDownloads(job) {
  $("downloads").hidden = false;
  $("zip-link").href = encodeURI(job.zip_url);  // 한글 제목이 파일명에 들어간다

  const list = $("png-list");
  list.innerHTML = "";
  job.slides.forEach((slide) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `/runs/${job.id}/png/${slide.name}.png`;
    a.download = `${slide.name}.png`;
    a.textContent = `${slide.name}.png`;
    li.append(a);
    list.append(li);
  });

  $("export-btn").textContent = "다시 저장";
  $("zip-link").click();  // ZIP 자동 다운로드
}

// ────────────────────────────────────────── 저장 / 피드백
$("export-btn").addEventListener("click", async () => {
  setBusy(true);
  showError("result-error", null);
  $("export-btn").textContent = "캡처 중";
  try {
    const res = await fetch(`/api/jobs/${state.jobId}/export`, { method: "POST" });
    await parse(res);
    state.mode = "export";
    startPolling();
  } catch (err) {
    setBusy(false);
    $("export-btn").textContent = "저장 (PNG 다운로드)";
    showError("result-error", err.message);
  }
});

$("feedback-btn").addEventListener("click", async () => {
  const feedback = $("feedback").value.trim();
  if (!feedback) return;

  const form = new FormData();
  form.append("feedback", feedback);

  setBusy(true);
  showError("result-error", null);
  showPanel("progress");
  $("progress-step").textContent = "피드백 반영해 다시 생성 중...";

  try {
    const res = await fetch(`/api/jobs/${state.jobId}/feedback`, { method: "POST", body: form });
    await parse(res);
    state.mode = "generate";
    $("feedback").value = "";
    startPolling();
  } catch (err) {
    setBusy(false);
    showPanel("result");
    showError("result-error", err.message);
  }
});

// ────────────────────────────────────────── 확대 보기
function openModal(url) {
  $("modal-frame").src = url;
  $("modal").hidden = false;
}

function closeModal() {
  $("modal").hidden = true;
  $("modal-frame").src = "about:blank";
}

$("modal-close").addEventListener("click", closeModal);
$("modal").addEventListener("click", (e) => {
  if (e.target === $("modal")) closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("modal").hidden) closeModal();
});

// ────────────────────────────────────────── 유틸
function showPanel(name) {
  $("idle").hidden = name !== "idle";
  $("progress").hidden = name !== "progress";
  $("result").hidden = name !== "result";
}

function setBusy(busy) {
  $("generate-btn").disabled = busy;
  $("export-btn").disabled = busy;
  $("feedback-btn").disabled = busy;
  $("generate-btn").textContent = busy ? "생성 중..." : "카드뉴스 생성";
}

function showError(id, message) {
  const el = $(id);
  el.textContent = message || "";
  el.hidden = !message;
}

async function parse(res) {
  const data = await res.json().catch(() => ({}));
  if (res.ok) return data;
  // FastAPI 검증 실패는 detail 이 배열로 온다
  const detail = Array.isArray(data.detail)
    ? data.detail.map((d) => d.msg).join(", ")
    : data.detail;
  throw new Error(detail || `요청 실패 (${res.status})`);
}
