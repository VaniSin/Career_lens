// ============================================================
// Career Lens — Main JavaScript
// Handles: auth, resume upload, ATS, career tools,
//          portfolio, mock interviews, chatbot, dashboard
// ============================================================

"use strict";

// ──────────────────────────────────────────────────────────────
// STATE
// ──────────────────────────────────────────────────────────────
const State = {
    user: null,         // current auth user object or null
    resumeReady: false, // whether a resume has been uploaded
    activeDashSection: "overview",
    activeInterview: null,  // { id, questions, currentIndex }
    dashRefreshTimer: null, // setInterval handle for auto-refresh
};

// ──────────────────────────────────────────────────────────────
// UTILITIES
// ──────────────────────────────────────────────────────────────

function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, c =>
        ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])
    );
}

function el(id) { return document.getElementById(id); }

function showEl(id)  { const e = el(id); if (e) e.classList.remove("hidden"); }
function hideEl(id)  { const e = el(id); if (e) e.classList.add("hidden"); }
function toggleEl(id){ const e = el(id); if (e) e.classList.toggle("hidden"); }

function setHtml(id, html) { const e = el(id); if (e) e.innerHTML = html; }
function setText(id, text) { const e = el(id); if (e) e.textContent = text; }

function showAlert(id, msg) {
    const e = el(id);
    if (!e) return;
    e.textContent = msg;
    e.classList.remove("hidden");
}

function hideAlert(id) { hideEl(id); }

function fmtDate(str) {
    if (!str) return "";
    return new Date(str).toLocaleDateString("en-IN", { day:"2-digit", month:"short", year:"numeric" });
}

function fmtSize(bytes) {
    if (!bytes) return "";
    return bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

function getInitials(name) {
    return (name || "U").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
}

async function api(path, opts = {}) {
    const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...opts
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
}

// ──────────────────────────────────────────────────────────────
// PAGE SWITCHING
// ──────────────────────────────────────────────────────────────

// ──────────────────────────────────────────────────────────────
// DASHBOARD AUTO-REFRESH
// ──────────────────────────────────────────────────────────────

const DASH_REFRESH_INTERVAL_MS = 30_000; // refresh every 30 s

function startDashboardAutoRefresh() {
    stopDashboardAutoRefresh(); // clear any existing timer
    State.dashRefreshTimer = setInterval(() => {
        if (!document.hidden && State.user) {
            loadDashboardSummary(false); // silent refresh (no spinner)
        }
    }, DASH_REFRESH_INTERVAL_MS);
}

function stopDashboardAutoRefresh() {
    if (State.dashRefreshTimer) {
        clearInterval(State.dashRefreshTimer);
        State.dashRefreshTimer = null;
    }
}

// Pause / resume auto-refresh based on tab visibility
document.addEventListener("visibilitychange", () => {
    if (!State.user) return;
    const dashVisible = el("dashboardPage") && !el("dashboardPage").classList.contains("hidden");
    if (!dashVisible) return;
    if (document.hidden) {
        stopDashboardAutoRefresh();
    } else {
        loadDashboardSummary(false); // immediate refresh on tab focus
        startDashboardAutoRefresh();
    }
});

// ──────────────────────────────────────────────────────────────
// PAGE SWITCHING
// ──────────────────────────────────────────────────────────────

function showHomePage() {
    stopDashboardAutoRefresh();
    showEl("homePage");
    hideEl("dashboardPage");
    showEl("mainFooter");
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function showDashboardPage(section = "overview") {
    if (!State.user) { openAuthModal(); return; }
    hideEl("homePage");
    showEl("dashboardPage");
    hideEl("mainFooter");
    hideEl("userDropdown");
    showDashboardSection(section || State.activeDashSection);
    loadDashboardSummary(true); // initial load with spinner
    startDashboardAutoRefresh();
}

// ──────────────────────────────────────────────────────────────
// AUTH — State rendering
// ──────────────────────────────────────────────────────────────

function renderAuthState() {
    if (State.user) {
        hideEl("headerGuest");
        showEl("headerUser");
        const init = getInitials(State.user.name);
        const avatarEls = [el("userAvatarBtn"), el("sidebarAvatar")];
        avatarEls.forEach(e => { if (e) e.textContent = init; });
        setText("ddName", State.user.name);
        setText("ddEmail", State.user.email);
        setText("sidebarName", State.user.name);
        setText("sidebarEmail", State.user.email);

        // Greeting
        const h = new Date().getHours();
        const greet = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
        setText("greetingTitle", `${greet}, ${State.user.name.split(" ")[0]} 👋`);
    } else {
        showEl("headerGuest");
        hideEl("headerUser");
    }
}

async function checkAuth() {
    const { ok, data } = await api("/auth/me");
    if (ok && data.authenticated) {
        State.user = data.user;
    } else {
        State.user = null;
    }
    renderAuthState();
}

// ──────────────────────────────────────────────────────────────
// WELCOME MODAL
// ──────────────────────────────────────────────────────────────

const welcomeModal = el("welcomeModal");

function closeWelcome() {
    if (welcomeModal) welcomeModal.classList.add("hidden");
    sessionStorage.setItem("cl_welcomed", "1");
}

if (welcomeModal) {
    if (sessionStorage.getItem("cl_welcomed") === "1") {
        welcomeModal.classList.add("hidden");
    }
    el("welcomeStart")?.addEventListener("click", () => {
        closeWelcome();
        el("resume")?.scrollIntoView({ behavior: "smooth" });
    });
    el("welcomeSkip")?.addEventListener("click", closeWelcome);
}

// ──────────────────────────────────────────────────────────────
// AUTH MODAL
// ──────────────────────────────────────────────────────────────

function openAuthModal(pane = "login") {
    showEl("authModal");
    if (pane === "login") {
        showEl("loginPane");
        hideEl("registerPane");
    } else {
        hideEl("loginPane");
        showEl("registerPane");
    }
}

function closeAuthModal() { hideEl("authModal"); }

el("headerLoginBtn")?.addEventListener("click", () => openAuthModal("login"));
el("headerRegisterBtn")?.addEventListener("click", () => openAuthModal("register"));
el("closeAuthModal")?.addEventListener("click", closeAuthModal);
el("closeAuthModal2")?.addEventListener("click", closeAuthModal);
el("showRegister")?.addEventListener("click", (e) => { e.preventDefault(); openAuthModal("register"); });
el("showLogin")?.addEventListener("click", (e) => { e.preventDefault(); openAuthModal("login"); });

// Click outside to close
el("authModal")?.addEventListener("click", (e) => {
    if (e.target === el("authModal")) closeAuthModal();
});

function isGmail(email) {
    return /^[a-zA-Z0-9._%+-]+@gmail\.com$/i.test((email || "").trim());
}

// Login
el("loginBtn")?.addEventListener("click", async () => {
    hideAlert("loginError");
    const email = el("loginEmail").value.trim();
    const password = el("loginPassword").value;
    if (!email || !password) { showAlert("loginError", "Please enter email and password."); return; }

    if (!isGmail(email)) {
        showAlert("loginError", "Invalid Gmail: Email must end with @gmail.com (e.g. yourname@gmail.com)");
        return;
    }

    el("loginBtn").textContent = "Signing in...";
    el("loginBtn").disabled = true;

    const { ok, data } = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
    });

    el("loginBtn").textContent = "Sign in";
    el("loginBtn").disabled = false;

    if (ok) {
        State.user = data.user;
        renderAuthState();
        closeAuthModal();
        el("loginEmail").value = "";
        el("loginPassword").value = "";
    } else {
        showAlert("loginError", data.error || "Login failed.");
    }
});

// Register
el("registerBtn")?.addEventListener("click", async () => {
    hideAlert("registerError");
    const name = el("regName").value.trim();
    const email = el("regEmail").value.trim();
    const password = el("regPassword").value;

    if (!name || !email || !password) { showAlert("registerError", "Please fill in all fields."); return; }

    if (!isGmail(email)) {
        showAlert("registerError", "Invalid Gmail: Email must end with @gmail.com (e.g. yourname@gmail.com)");
        return;
    }

    el("registerBtn").textContent = "Creating account...";
    el("registerBtn").disabled = true;

    const { ok, data } = await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({ name, email, password })
    });

    el("registerBtn").textContent = "Create account →";
    el("registerBtn").disabled = false;

    if (ok) {
        State.user = data.user;
        renderAuthState();
        closeAuthModal();
    } else {
        showAlert("registerError", data.error || "Registration failed.");
    }
});

// Logout
async function doLogout() {
    stopDashboardAutoRefresh();
    await api("/auth/logout", { method: "POST" });
    State.user = null;
    State.resumeReady = false;
    renderAuthState();
    showHomePage();
    hideEl("dashboard");
    hideEl("readyBanner");
}

el("logoutBtn")?.addEventListener("click", doLogout);
el("sideLogout")?.addEventListener("click", doLogout);

// ──────────────────────────────────────────────────────────────
// HEADER — Mobile nav & user dropdown
// ──────────────────────────────────────────────────────────────

el("hambBtn")?.addEventListener("click", () => {
    toggleEl("mainNav");
});

el("userAvatarBtn")?.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleEl("userDropdown");
});

document.addEventListener("click", () => hideEl("userDropdown"));
el("userDropdown")?.addEventListener("click", (e) => e.stopPropagation());

// ──────────────────────────────────────────────────────────────
// RESUME UPLOAD (original functionality preserved)
// ──────────────────────────────────────────────────────────────

const fileInput = el("fileInput");
const fileNameDisplay = el("fileNameDisplay");
const uploadForm = el("uploadForm");
const uploadMessage = el("uploadMessage");

fileInput?.addEventListener("change", () => {
    fileNameDisplay.textContent = fileInput.files[0]?.name || "No file selected";
});

uploadForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    uploadMessage.className = "upload-message";
    uploadMessage.textContent = "";

    if (!fileInput.files[0]) {
        uploadMessage.className = "upload-message error";
        uploadMessage.textContent = "Please choose your PDF resume first.";
        return;
    }

    const data = new FormData();
    data.append("resume", fileInput.files[0]);

    const btn = el("uploadBtn");
    btn.disabled = true;
    btn.textContent = "Uploading...";

    try {
        const res = await fetch("/upload", { method: "POST", body: data });
        const d = await res.json();
        if (!res.ok) throw new Error(d.error || "Upload failed.");

        uploadMessage.textContent = "Resume uploaded successfully.";
        el("readyFileName").textContent = d.filename;
        el("readyStats").textContent = `${d.words.toLocaleString()} words · ${d.characters.toLocaleString()} characters extracted`;

        showEl("readyBanner");
        el("dashboard").removeAttribute("hidden");
        State.resumeReady = true;

        el("dashboard").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
        uploadMessage.className = "upload-message error";
        uploadMessage.textContent = err.message;
    } finally {
        btn.disabled = false;
        btn.textContent = "Upload resume →";
    }
});

// ──────────────────────────────────────────────────────────────
// CAREER TOOLS (ATS, Jobs, Roadmap) — Original logic preserved
// ──────────────────────────────────────────────────────────────

function list(items, emptyText) {
    return items?.length
        ? `<ul>${items.map(i => `<li>${esc(i)}</li>`).join("")}</ul>`
        : `<p>${esc(emptyText)}</p>`;
}

function showResults(title, kicker, html) {
    setText("resultTitle", title);
    setText("resultKicker", kicker);
    setHtml("resultsContent", html);
    showEl("resultsPanel");
    el("resultsPanel").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function runFeature(which) {
    document.querySelectorAll(".tool-card").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.feature === which);
    });

    if (which === "roadmap" && !sessionStorage.getItem("selectedCareer")) {
        showResults("Choose a career first", "CAREER PLANNING",
            `<div class="result-box"><p>Explore a recommended career first to generate your personalized learning roadmap. Click <strong>Matching Jobs</strong> and select a career to continue.</p></div>`);
        return;
    }

    const titles = { ats: "ATS-readiness analysis", jobs: "Career recommendations", roadmap: "Your personalized roadmap" };
    const kickers = { ats: "RESUME ANALYSIS", jobs: "CAREER MATCHING", roadmap: "CAREER PLANNING" };

    showResults(titles[which], kickers[which], `<p>Preparing your insights… <span class="spinner"></span></p>`);

    try {
        let opts = { method: "POST" };
        if (which === "roadmap") {
            opts.headers = { "Content-Type": "application/json" };
            opts.body = JSON.stringify({ role: sessionStorage.getItem("selectedCareer") });
        }

        const res = await fetch(`/analyze/${which}`, opts);
        const d = await res.json();
        if (!res.ok) throw new Error(d.error || "Analysis failed.");

        if (which === "jobs") { renderJobs(d); return; }
        if (which === "ats")  { renderATS(d);  return; }
        if (which === "roadmap") { renderRoadmap(d); return; }
    } catch (err) {
        showResults("Analysis unavailable", "PLEASE REVIEW",
            `<div class="result-box"><p>${esc(err.message)}</p></div>`);
    }
}

function renderATS(d) {
    const breakdown = d.breakdown || {};
    const checks = d.checks || Object.entries(breakdown).map(([name, item]) => ({
        name, status: item.score >= item.max * 0.7 ? "pass" : "review",
        detail: `Score: ${item.score}/${item.max}`
    }));
    const sections = d.detected_sections || d.found_sections || [];
    const label = d.label || d.rating || "Resume analysis";
    const score = Math.min(100, Math.max(0, Number(d.score) || 0));

    const checkHtml = checks.map(c => {
        const icon = c.status === "pass"
            ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`
            : `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
        return `
        <div class="result-box">
          <h4 style="display:flex;align-items:center;gap:6px">${icon} ${esc(c.name)}</h4>
          <p>${esc(c.detail)}</p>
        </div>`;
    }).join("");

    showResults("ATS-readiness analysis", "RESUME ANALYSIS", `
        <div class="flex-center gap-8">
          <span class="score-value">${score}</span>
          <span class="score-denom"> / 100</span>
        </div>
        <p style="margin:6px 0 0;font-size:15px;color:var(--text-muted)">${esc(label)}</p>
        <div class="score-bar"><span style="width:${score}%"></span></div>

        <div class="result-box mb-16">
          <h4>Detected sections</h4>
          <p>${esc(sections.join(" · ") || "No common sections detected.")}</p>
        </div>

        <h4 style="margin-bottom:10px">Detailed checks</h4>
        <div class="result-grid">${checkHtml}</div>

        <h4 style="margin:16px 0 8px">Suggested improvements</h4>
        ${list(d.suggestions || [], "Keep tailoring your resume to relevant roles.")}

        <p style="font-size:12px;color:var(--text-light);margin-top:16px">
          Prototype heuristic — not a guarantee of passing an employer's ATS.
        </p>`);
}

function renderJobs(d) {
    const recs = d.recommendations || [];
    if (!recs.length) {
        showResults("Career recommendations", "TARGET ROLE ALIGNMENT",
            `<div class="result-box"><h4>More information needed</h4><p>We could not identify enough skills in your resume. Add your technical skills and project details, then upload again.</p></div>`);
        return;
    }

    const cards = recs.map((job, i) => {
        const companies = (job.recommended_companies || []).map(c =>
            `<span class="company-tag"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 21h18M3 7v14M21 7v14M6 11h.01M6 15h.01M10 11h.01M10 15h.01M14 11h.01M14 15h.01M18 11h.01M18 15h.01M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4"/></svg>${esc(c)}</span>`
        ).join("");

        return `
        <div class="career-card" style="background:#ffffff;border:1.5px solid var(--border);border-radius:var(--radius-lg);padding:22px;margin-bottom:18px;box-shadow:var(--shadow-xs);">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
            <h4 style="font-size:18px;font-weight:700;color:var(--text);margin:0;">${i + 1}. ${esc(job.role)}</h4>
            <div style="display:flex;align-items:baseline;gap:4px">
              <span class="score-value" style="font-size:28px">${Number(job.score) || 0}</span>
              <span class="score-denom" style="font-size:13px">/ 100 Match</span>
            </div>
          </div>
          <div class="score-bar" style="margin:10px 0 14px"><span style="width:${Math.min(100, Number(job.score) || 0)}%"></span></div>
          <p style="font-size:13.5px;color:var(--text-secondary);line-height:1.55;margin-bottom:12px">${esc(job.description)}</p>

          ${companies ? `
          <div style="margin:12px 0;">
            <div style="font-size:11px;font-weight:700;color:var(--text-muted);letter-spacing:0.5px;text-transform:uppercase;margin-bottom:6px">Recommended Hiring Companies:</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;">${companies}</div>
          </div>` : ""}

          <div class="result-box" style="margin:12px 0;background:#f8fafc;border-left:3.5px solid var(--accent);border-radius:var(--radius-sm);padding:12px 14px;">
            <strong style="font-size:12.5px;color:var(--primary);display:block;margin-bottom:4px;">🎯 Evidence-Based Alignment:</strong>
            <p style="font-size:13px;color:var(--text);line-height:1.5;margin:0;">${esc(job.reason)}</p>
          </div>

          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:10px;margin-top:12px">
            <div class="result-box" style="margin:0;padding:12px">
              <h4 style="font-size:12.5px;margin-bottom:6px;color:#059669">✓ Verified Resume Skills</h4>
              ${list(job.matched_skills, "None verified.")}
            </div>
            <div class="result-box" style="margin:0;padding:12px">
              <h4 style="font-size:12.5px;margin-bottom:6px;color:#d97706">⚡ Missing Skills &amp; Gaps</h4>
              ${list(job.missing_skills, "None detected.")}
            </div>
          </div>

          <button class="btn btn-primary btn-sm" style="margin-top:16px"
            data-role="${esc(job.role)}" onclick="selectCareer('${esc(job.role)}')">
            Explore this career &amp; bridge gaps →
          </button>
        </div>`;
    }).join("");

    showResults("Target Role Alignment", "REAL-WORLD CAREER BENCHMARK", `
        <p style="margin-bottom:16px;color:var(--text-muted)">Evaluated against real-world employer hiring bars using Groq AI. Select any career pathway to analyze specific skill gaps and generate a prioritized learning roadmap.</p>
        ${cards}
        <p style="font-size:12px;color:var(--text-light);margin-top:16px">Grounding based on verified skills, degree, and projects extracted from your resume.</p>`);
}

function renderRoadmap(d) {
    const matchedPills = (d.matched_skills || []).map(s =>
        `<span class="badge badge-green" style="margin:2px 3px;">✓ ${esc(s)}</span>`
    ).join("");

    const missingPills = (d.missing_skills || []).map(s =>
        `<span class="badge badge-orange" style="margin:2px 3px;">⚡ ${esc(s)}</span>`
    ).join("");

    const steps = (d.steps || []).map((s, idx) => `
        <div class="roadmap-milestone-card">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;flex-wrap:wrap;gap:6px">
            <span class="step-num" style="margin:0">${esc(s.week || `Milestone ${idx + 1}`)}</span>
            <span style="font-size:11px;font-weight:700;color:var(--accent);letter-spacing:0.5px">ACTIONABLE MILESTONE</span>
          </div>
          <h4 style="font-size:16px;font-weight:700;color:var(--primary);margin-bottom:8px">${esc(s.title)}</h4>
          <p style="font-size:13.5px;line-height:1.6;color:var(--text);margin-bottom:10px">${esc(s.detail)}</p>
          ${s.practical_project ? `
          <div class="milestone-project-box">
            <strong style="color:#0f766e;display:flex;align-items:center;gap:6px;font-size:12.5px;margin-bottom:4px">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              Practical Milestone Artifact:
            </strong>
            <span style="font-size:13px;color:#134e4a;line-height:1.5;display:block">${esc(s.practical_project)}</span>
          </div>` : ""}
        </div>`).join("");

    showResults(`Your ${esc(d.role || "career")} roadmap`, "ACTIONABLE LEARNING ROADMAP", `
        <p style="margin-bottom:16px;color:var(--text-muted)">Prioritized, week-by-week learning plan calibrated to bridge your actual resume gaps for <strong>${esc(d.role)}</strong>.</p>
        <div class="result-box mb-16">
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:12px">
            <div>
              <strong style="font-size:11.5px;color:var(--text-muted);display:block;margin-bottom:6px;letter-spacing:0.5px;text-transform:uppercase">Strengths Found on Your Resume</strong>
              <div>${matchedPills || "<span class='text-muted text-small'>No baseline skills recorded</span>"}</div>
            </div>
            <div>
              <strong style="font-size:11.5px;color:var(--text-muted);display:block;margin-bottom:6px;letter-spacing:0.5px;text-transform:uppercase">Critical Skills Targeted</strong>
              <div>${missingPills || "<span class='text-muted text-small'>Role mastery sequence</span>"}</div>
            </div>
          </div>
        </div>
        <h4 style="margin:20px 0 12px;font-size:16px">Prioritized Learning &amp; Project Sequence</h4>
        <div style="display:grid;gap:14px">${steps || "<div class='result-box'><p>No roadmap steps generated.</p></div>"}</div>
        <p style="font-size:12px;color:var(--text-light);margin-top:20px">Grounding based on corporate hiring bars. Adjust pace to your weekly schedule.</p>`);
}

async function selectCareer(role) {
    sessionStorage.setItem("selectedCareer", role);
    showResults("Skill gap analysis", "YOUR LEARNING PRIORITIES",
        `<p>Analyzing your skills for <strong>${esc(role)}</strong>… <span class="spinner"></span></p>`);

    try {
        const res = await fetch("/analyze/skills", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role })
        });
        const d = await res.json();
        if (!res.ok) throw new Error(d.error || "Skill analysis failed.");

        const priorityCards = (d.prioritized_skills || []).map(item => `
            <div class="result-box">
              <h4>${esc(item.skill)}
                <span class="priority-${esc(String(item.priority || "medium").toLowerCase())}">
                  · ${esc(item.priority || "Review")} Priority
                </span>
              </h4>
              <p>${esc(item.reason)}</p>
            </div>`).join("");

        const gapContent = priorityCards || `<div class="result-box"><p>No missing skills detected. Focus on projects and interview preparation.</p></div>`;

        showResults(`Your skill gaps for ${esc(role)}`, "SKILL GAP ANALYSIS", `
            <p style="margin-bottom:16px">${esc(d.description)}</p>
            <div class="result-box mb-16">
              <h4>Skills already in your resume</h4>
              ${list(d.matched_skills, "No matching skills detected yet.")}
            </div>
            <h4 style="margin-bottom:10px">What to learn next</h4>
            <div class="result-grid">${gapContent}</div>
            <button class="btn btn-primary mt-16" id="buildRoadmapBtn">Build my personalized roadmap →</button>`);

        el("buildRoadmapBtn")?.addEventListener("click", () => runFeature("roadmap"));
    } catch (err) {
        showResults("Skill analysis unavailable", "PLEASE REVIEW",
            `<div class="result-box"><p>${esc(err.message)}</p></div>`);
    }
}

// Wire tool cards
document.querySelectorAll(".tool-card").forEach(btn => {
    btn.addEventListener("click", () => runFeature(btn.dataset.feature));
});

el("closeResults")?.addEventListener("click", () => {
    hideEl("resultsPanel");
    document.querySelectorAll(".tool-card").forEach(b => b.classList.remove("active"));
});

// ──────────────────────────────────────────────────────────────
// DASHBOARD — Sections
// ──────────────────────────────────────────────────────────────

function showDashboardSection(section) {
    const sections = ["overview", "portfolio", "interviews", "chatHistory", "profile", "security"];
    sections.forEach(s => {
        const id = "section" + s.charAt(0).toUpperCase() + s.slice(1);
        const el2 = el(id);
        if (el2) el2.classList.toggle("hidden", s !== section);

        const sideId = "side" + s.charAt(0).toUpperCase() + s.slice(1);
        el(sideId)?.classList.toggle("active", s === section);
    });
    State.activeDashSection = section;

    if (section === "portfolio")    loadPortfolio();
    if (section === "interviews")   loadInterviewSessions();
    if (section === "chatHistory")  loadChatHistory();
    if (section === "profile")      loadProfile();
}

async function loadDashboardSummary(showSpinner = false) {
    // Show loading indicators on the stat counters the first time
    if (showSpinner) {
        ["statDocs", "statInterviews", "statCompleted"].forEach(id => setText(id, "…"));
    }

    // Animate the manual refresh button (if present)
    const refreshBtn = el("dashRefreshBtn");
    if (refreshBtn) refreshBtn.classList.add("spinning");

    const { ok, data } = await api("/dashboard/summary");

    if (refreshBtn) refreshBtn.classList.remove("spinning");

    if (!ok) return;
    setText("statDocs", data.documents ?? 0);
    setText("statInterviews", data.interviews ?? 0);
    setText("statCompleted", data.completed_interviews ?? 0);

    // Update last-refreshed timestamp
    const ts = el("dashLastRefreshed");
    if (ts) {
        const now = new Date();
        ts.textContent = `Updated ${now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}`;
    }

    // Recent docs
    const docsArea = el("recentDocsArea");
    if (docsArea) {
        if (data.recent_documents?.length) {
            docsArea.innerHTML = data.recent_documents.map(d => `
                <div class="flex-center gap-8" style="padding:8px 0;border-bottom:1px solid var(--border)">
                  <span style="font-size:18px">${docIcon(d.category)}</span>
                  <div style="flex:1;min-width:0">
                    <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(d.name)}</div>
                    <div style="font-size:11px;color:var(--text-muted)">${fmtDate(d.uploaded_at)}</div>
                  </div>
                </div>`).join("");
        } else {
            docsArea.innerHTML = `<p class="text-muted text-small">No documents yet. <a href="#" onclick="showDashboardSection('portfolio')">Upload one →</a></p>`;
        }
    }

    // Recent interviews
    const intArea = el("recentInterviewsArea");
    if (intArea) {
        if (data.recent_interviews?.length) {
            intArea.innerHTML = data.recent_interviews.map(i => `
                <div class="flex-center gap-8" style="padding:8px 0;border-bottom:1px solid var(--border)">
                  <span style="display:inline-grid;place-items:center;width:18px;height:18px;background:var(--teal-soft);border-radius:4px;color:#0d9488">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
                  </span>
                  <div style="flex:1;min-width:0">
                    <div style="font-size:13px;font-weight:600">${esc(i.company)} · ${esc(i.role)}</div>
                    <div style="font-size:11px;color:var(--text-muted)">${fmtDate(i.created_at)} · ${i.status}</div>
                  </div>
                </div>`).join("");
        } else {
            intArea.innerHTML = `<p class="text-muted text-small">No sessions yet. <a href="#" onclick="showDashboardSection('interviews')">Start one →</a></p>`;
        }
    }
}

// Wire manual refresh button
el("dashRefreshBtn")?.addEventListener("click", () => loadDashboardSummary(false));

// ──────────────────────────────────────────────────────────────
// PORTFOLIO
// ──────────────────────────────────────────────────────────────

let activeCatFilter = "All";

function docIcon(cat) {
    const svgFile = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
    const svgCert = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>`;
    const svgFolder = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>`;
    
    if (cat === "Certificate" || cat === "Degree/Marksheet") return svgCert;
    if (cat === "Project") return svgFolder;
    return svgFile;
}

async function loadPortfolio(cat = activeCatFilter) {
    activeCatFilter = cat;
    const grid = el("docGrid");
    if (!grid) return;
    grid.innerHTML = `<p class="text-muted text-small">Loading documents…</p>`;

    const url = cat && cat !== "All" ? `/portfolio/documents?category=${encodeURIComponent(cat)}` : "/portfolio/documents";
    const { ok, data } = await api(url);

    if (!ok) { grid.innerHTML = `<p class="text-muted text-small">Failed to load documents.</p>`; return; }

    if (!data.documents?.length) {
        grid.innerHTML = `<div id="docEmptyMsg" style="grid-column:1/-1">
            <p class="text-muted text-small">No documents found. Click <strong>Upload Document</strong> to add one.</p></div>`;
        return;
    }

    grid.innerHTML = data.documents.map(doc => `
        <div class="doc-card" id="doc-${doc.id}">
          <div class="doc-icon">${docIcon(doc.category)}</div>
          <div>
            <div class="doc-name">${esc(doc.name)}</div>
            <div class="doc-category"><span class="badge badge-blue">${esc(doc.category)}</span></div>
            <div class="doc-date">${fmtDate(doc.uploaded_at)} · ${fmtSize(doc.file_size)}</div>
          </div>
          <div class="doc-actions">
            <a href="/portfolio/documents/${doc.id}/download" class="btn btn-ghost btn-sm" download>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Download
            </a>
            <button class="btn btn-danger btn-sm" onclick="deleteDoc(${doc.id})">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              Delete
            </button>
          </div>
        </div>`).join("");
}

// Category filter tabs
el("docFilterTabs")?.addEventListener("click", (e) => {
    const tab = e.target.closest(".category-tab");
    if (!tab) return;
    document.querySelectorAll(".category-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    loadPortfolio(tab.dataset.cat);
});

// Open upload panel
el("openUploadDocBtn")?.addEventListener("click", () => {
    toggleEl("uploadDocPanel");
});

el("closeUploadDocPanel")?.addEventListener("click", () => hideEl("uploadDocPanel"));

// Upload document form
el("docUploadForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert("docUploadError");

    const file = el("docFile").files[0];
    if (!file) { showAlert("docUploadError", "Please select a file."); return; }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", el("docName").value.trim());
    formData.append("category", el("docCategory").value);
    formData.append("description", el("docDescription").value.trim());

    const btn = el("docUploadBtn");
    btn.disabled = true;
    btn.textContent = "Uploading…";

    const res = await fetch("/portfolio/documents", { method: "POST", body: formData });
    const data = await res.json();

    btn.disabled = false;
    btn.textContent = "Upload document";

    if (res.ok) {
        hideEl("uploadDocPanel");
        el("docUploadForm").reset();
        loadPortfolio();
        loadDashboardSummary();
    } else {
        showAlert("docUploadError", data.error || "Upload failed.");
    }
});

async function deleteDoc(docId) {
    if (!confirm("Delete this document? This cannot be undone.")) return;
    const { ok, data } = await api(`/portfolio/documents/${docId}`, { method: "DELETE" });
    if (ok) {
        el(`doc-${docId}`)?.remove();
        loadDashboardSummary();
    } else {
        alert(data.error || "Delete failed.");
    }
}

// ──────────────────────────────────────────────────────────────
// MOCK INTERVIEWS
// ──────────────────────────────────────────────────────────────

el("newInterviewBtn")?.addEventListener("click", () => {
    toggleEl("interviewSetupPanel");
    hideEl("interviewActivePanel");
});

el("cancelInterviewSetup")?.addEventListener("click", () => hideEl("interviewSetupPanel"));

el("interviewSetupForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert("interviewSetupError");

    const company = el("interviewCompany").value.trim();
    const role = el("interviewRole").value;
    const count = Number(el("interviewCount").value);

    if (!company) { showAlert("interviewSetupError", "Please enter a company name."); return; }
    if (!role) { showAlert("interviewSetupError", "Please select a job role."); return; }

    const btn = e.target.querySelector("[type=submit]");
    btn.disabled = true;
    btn.textContent = "Generating questions…";

    const { ok, data } = await api("/interview/sessions", {
        method: "POST",
        body: JSON.stringify({ company, role, count })
    });

    btn.disabled = false;
    btn.textContent = "Generate Questions →";

    if (ok) {
        hideEl("interviewSetupPanel");
        startActiveInterview(data.session, data.questions);
        loadDashboardSummary();
    } else {
        showAlert("interviewSetupError", data.error || "Failed to create session.");
    }
});

function startActiveInterview(session, questions) {
    State.activeInterview = {
        id: session.id,
        company: session.company,
        role: session.role,
        questions,
        currentIndex: 0,
        answers: {},
        summary: session.summary || null
    };
    showEl("interviewActivePanel");
    hideEl("interviewSessionsList");
    renderQuestion();
}

function renderFeedbackDetail(detail, rawFeedback) {
    const box = el("feedbackBox");
    if (!box) return;
    if (detail && detail.score !== undefined) {
        const mistakes = (detail.mistakes || []).map(m => `<li>${esc(m)}</li>`).join("");
        const missing = (detail.missing_points || []).map(m => `<li>${esc(m)}</li>`).join("");
        const score = detail.score;
        const verdict = detail.verdict || (score >= 8 ? "Strong Answer" : score >= 6 ? "Good Attempt" : "Needs Review");
        const verdictColor = score >= 8 ? "#059669" : score >= 6 ? "#0284c7" : "#d97706";

        box.innerHTML = `
            <div class="feedback-score-header">
              <div>
                <span class="feedback-score-num">${score}</span><span style="font-size:13px;color:var(--text-muted);font-weight:600"> / 10 Score</span>
              </div>
              <span class="badge" style="background:${verdictColor}18;color:${verdictColor};border:1px solid ${verdictColor}40;font-weight:700">
                ${esc(verdict)}
              </span>
            </div>

            ${mistakes ? `
            <div class="feedback-section-title mistakes">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
              Mistakes &amp; Inaccuracies Identified:
            </div>
            <ul style="margin:0 0 12px 18px;font-size:13px;color:#991b1b;line-height:1.5">${mistakes}</ul>` : ""}

            ${missing ? `
            <div class="feedback-section-title missing">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              Missing Points &amp; Critical Nuances:
            </div>
            <ul style="margin:0 0 12px 18px;font-size:13px;color:#92400e;line-height:1.5">${missing}</ul>` : ""}

            ${detail.improved_answer ? `
            <div class="feedback-section-title improved">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
              Correct / Improved Model Answer:
            </div>
            <div class="feedback-improved-content">${formatMarkdown(detail.improved_answer)}</div>` : ""}

            ${detail.explanation ? `
            <div class="feedback-section-title explanation" style="margin-top:12px">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
              Key Concept &amp; Architectural Explanation:
            </div>
            <p style="font-size:13px;color:var(--text);margin:0;line-height:1.55">${esc(detail.explanation)}</p>` : ""}
        `;
    } else {
        box.innerHTML = formatMarkdown(rawFeedback || "Answer evaluated.");
    }
}

function renderInterviewSummary(summary, company, role) {
    const card = el("interviewActivePanel");
    if (!card) return;

    const score = summary?.overall_score ?? 75;
    const verdict = summary?.verdict ?? (score >= 80 ? "Hire" : "Needs More Preparation");
    const strengths = (summary?.strengths || []).map(s =>
        `<div class="report-list-item strength">
           <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
           <span>${esc(s)}</span>
         </div>`
    ).join("");

    const weaknesses = (summary?.weaknesses || []).map(w =>
        `<div class="report-list-item weakness">
           <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
           <span>${esc(w)}</span>
         </div>`
    ).join("");

    const tips = (summary?.personalized_tips || []).map(t =>
        `<div class="report-list-item tip">
           <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
           <span>${esc(t)}</span>
         </div>`
    ).join("");

    card.innerHTML = `
        <div class="interview-report-card">
          <div class="report-hero">
            <div class="report-score-box">
              <div class="report-score-value">${score}</div>
              <div class="report-score-label">Overall Score</div>
            </div>
            <div style="flex:1">
              <div style="font-size:11.5px;font-weight:700;color:var(--accent);letter-spacing:0.5px;text-transform:uppercase;margin-bottom:4px">
                GROQ AI INTERVIEW REPORT &middot; ${esc(company).toUpperCase()}
              </div>
              <h3 style="font-size:22px;color:var(--text);margin-bottom:6px">${esc(role)} Interview Debrief</h3>
              <p style="font-size:13.5px;color:var(--text-secondary);line-height:1.55;margin-bottom:12px">${esc(summary?.summary_text || "Interview questions completed. Review your strengths, weaknesses, and personalized tips below.")}</p>
              <span class="badge ${score >= 80 ? 'badge-green' : 'badge-orange'}" style="font-size:12px;padding:4px 10px;font-weight:700">
                Evaluation Verdict: ${esc(verdict)}
              </span>
            </div>
          </div>

          <div class="report-grid">
            <div class="result-box" style="margin:0;padding:16px;background:#f0fdf4;border-color:#bbf7d0">
              <h4 style="color:#15803d;font-size:14px;margin-bottom:12px;display:flex;align-items:center;gap:6px">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                Key Strengths Demonstrated
              </h4>
              ${strengths || "<p class='text-muted text-small'>Strengths evaluated.</p>"}
            </div>

            <div class="result-box" style="margin:0;padding:16px;background:#fef2f2;border-color:#fecaca">
              <h4 style="color:#b91c1c;font-size:14px;margin-bottom:12px;display:flex;align-items:center;gap:6px">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Mistakes, Gaps &amp; Weaknesses
              </h4>
              ${weaknesses || "<p class='text-muted text-small'>Review missing points.</p>"}
            </div>
          </div>

          <div class="result-box" style="margin:20px 0 24px;padding:18px;background:#fdf4ff;border-color:#f5d0fe;border-left:4px solid #9333ea">
            <h4 style="color:#7e22ce;font-size:15px;margin-bottom:12px;display:flex;align-items:center;gap:6px">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              Personalized Improvement Tips for ${esc(company)}
            </h4>
            <div style="display:grid;gap:6px">${tips || "<p class='text-muted text-small'>Focus on core system architecture and STAR behavioral examples.</p>"}</div>
          </div>

          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <button class="btn btn-primary" onclick="exitInterview()">Back to interview sessions &rarr;</button>
          </div>
        </div>`;
    loadDashboardSummary();
}

function renderQuestion() {
    const { questions, currentIndex, company, role } = State.activeInterview;
    const q = questions[currentIndex];
    const total = questions.length;

    setText("progressLabel", `Question ${currentIndex + 1} of ${total}`);
    setText("questionCategoryBadge", q.category || "Technical");
    setText("activeCategoryLabel", (q.category || "TECHNICAL").toUpperCase());
    setText("activeQuestionText", q.question);
    setText("interviewCompanyRole", `${company} · ${role}`);

    // Source badge
    const sourceEl = el("questionSourceBadge");
    if (sourceEl) {
        const isPyq = q.is_pyq || (q.source_label && q.source_label.toLowerCase().includes("pyq"));
        sourceEl.className = isPyq ? "badge-pyq" : "badge-practice";
        sourceEl.textContent = isPyq ? "✓ Real Reported Question (PYQ)" : (q.source_label || "AI-Generated Practice");
        sourceEl.title = isPyq ? "Reported by candidates in real company interview debriefs" : "Targeted company & role practice question";
    }

    // Source note
    const noteEl = el("questionSourceNote");
    if (noteEl) {
        if (q.source_note) {
            noteEl.innerHTML = `<span>📌 <strong>Context:</strong> ${esc(q.source_note)}</span>`;
            noteEl.classList.remove("hidden");
        } else {
            noteEl.classList.add("hidden");
        }
    }

    const pct = Math.round(((currentIndex + 1) / total) * 100);
    el("progressFill").style.width = `${pct}%`;

    const savedAns = State.activeInterview.answers[q.id || currentIndex] || q.answer || "";
    el("answerTextarea").value = savedAns;

    const nextBtn = el("nextQuestionBtn");
    el("prevQuestionBtn").disabled = currentIndex === 0;

    // Has feedback?
    if (q.feedback_detail || (q.feedback && q.feedback.trim())) {
        renderFeedbackDetail(q.feedback_detail, q.feedback);
        showEl("feedbackBox");
        if (nextBtn) {
            nextBtn.textContent = currentIndex === total - 1 ? "Complete Interview & View Results →" : "Next Question →";
            nextBtn.dataset.mode = currentIndex === total - 1 ? "finish" : "next";
            nextBtn.disabled = false;
        }
    } else {
        hideEl("feedbackBox");
        if (nextBtn) {
            nextBtn.textContent = "Evaluate & Submit Answer →";
            nextBtn.dataset.mode = "submit";
            nextBtn.disabled = false;
        }
    }
}

el("nextQuestionBtn")?.addEventListener("click", async () => {
    const { questions, currentIndex, id: sessionId, company, role } = State.activeInterview;
    const q = questions[currentIndex];
    const nextBtn = el("nextQuestionBtn");
    const mode = nextBtn?.dataset.mode || "submit";

    if (mode === "submit") {
        const answer = el("answerTextarea").value.trim();
        if (!answer) {
            alert("Please type your response before submitting for AI evaluation.");
            return;
        }

        State.activeInterview.answers[q.id || currentIndex] = answer;
        nextBtn.disabled = true;
        nextBtn.innerHTML = `<span class="spinner"></span> Evaluating with Groq AI…`;

        const { ok, data } = await api(`/interview/sessions/${sessionId}/answer`, {
            method: "POST",
            body: JSON.stringify({ question_id: q.id, answer })
        });

        nextBtn.disabled = false;

        if (ok) {
            q.answer = answer;
            q.feedback = data.feedback;
            q.feedback_detail = data.feedback_detail;
            if (data.summary) State.activeInterview.summary = data.summary;

            renderFeedbackDetail(data.feedback_detail, data.feedback);
            showEl("feedbackBox");
            el("feedbackBox")?.scrollIntoView({ behavior: "smooth", block: "nearest" });

            if (currentIndex === questions.length - 1 || data.completed) {
                nextBtn.textContent = "Finish & View Performance Report →";
                nextBtn.dataset.mode = "finish";
            } else {
                nextBtn.textContent = "Next Question →";
                nextBtn.dataset.mode = "next";
            }
        } else {
            alert(data.error || "Evaluation failed. Please try again.");
            nextBtn.textContent = "Evaluate & Submit Answer →";
        }
    } else if (mode === "next") {
        if (currentIndex < questions.length - 1) {
            State.activeInterview.currentIndex++;
            renderQuestion();
        }
    } else if (mode === "finish") {
        if (State.activeInterview.summary) {
            renderInterviewSummary(State.activeInterview.summary, company, role);
        } else {
            // Fetch summary
            const { ok, data } = await api(`/interview/sessions/${sessionId}/summary`);
            if (ok && data.summary) {
                renderInterviewSummary(data.summary, company, role);
            } else {
                exitInterview();
            }
        }
    }
});

el("prevQuestionBtn")?.addEventListener("click", () => {
    if (State.activeInterview.currentIndex > 0) {
        State.activeInterview.currentIndex--;
        renderQuestion();
    }
});

el("exitInterviewBtn")?.addEventListener("click", exitInterview);

function exitInterview() {
    State.activeInterview = null;
    hideEl("interviewActivePanel");
    showEl("interviewSessionsList");
    loadInterviewSessions();
}

async function loadInterviewSessions() {
    const list2 = el("interviewSessionsList");
    if (!list2) return;
    list2.innerHTML = `<p class="text-muted text-small">Loading sessions…</p>`;

    const { ok, data } = await api("/interview/sessions");
    if (!ok) { list2.innerHTML = `<p class="text-muted text-small">Failed to load sessions.</p>`; return; }

    if (!data.sessions?.length) {
        list2.innerHTML = `<p class="text-muted text-small">No interview sessions yet. Click <strong>New Interview</strong> to start practicing!</p>`;
        return;
    }

    list2.innerHTML = `
        <div style="display:grid;gap:14px">
          ${data.sessions.map(s => `
            <div class="card" style="padding:0">
              <div class="card-header">
                <div>
                  <div style="font-size:15px;font-weight:700">${esc(s.company)} &nbsp;·&nbsp; ${esc(s.role)}</div>
                  <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${fmtDate(s.created_at)} · ${s.answered_count}/${s.question_count} answered</div>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                  <span class="badge ${s.status === 'completed' ? 'badge-green' : 'badge-orange'}">${s.status}</span>
                  <button class="btn btn-ghost btn-sm" onclick="resumeInterview(${s.id})">Resume</button>
                  <button class="btn btn-danger btn-sm" onclick="deleteSession(${s.id})">Delete</button>
                </div>
              </div>
            </div>`).join("")}
        </div>`;
}

async function resumeInterview(sessionId) {
    const { ok, data } = await api(`/interview/sessions/${sessionId}`);
    if (!ok) { alert("Failed to load session."); return; }
    startActiveInterview(data.session, data.questions);
}

async function deleteSession(sessionId) {
    if (!confirm("Delete this interview session?")) return;
    const { ok } = await api(`/interview/sessions/${sessionId}`, { method: "DELETE" });
    if (ok) loadInterviewSessions();
}

// ──────────────────────────────────────────────────────────────
// PROFILE
// ──────────────────────────────────────────────────────────────

async function loadProfile() {
    const { ok, data } = await api("/auth/me");
    if (!ok || !data.user) return;
    const u = data.user;
    const set = (id, val) => { const e = el(id); if (e) e.value = val ?? ""; };
    set("profileName", u.name);
    set("profileJobTitle", u.job_title);
    set("profilePhone", u.phone);
    set("profileLocation", u.location);
    set("profileExpYears", u.experience_years);
    set("profileLinkedIn", u.linkedin_url);
    set("profileGitHub", u.github_url);
    set("profileBio", u.bio);
}

el("profileForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert("profileSuccess");
    hideAlert("profileError");

    const payload = {
        name: el("profileName").value.trim(),
        job_title: el("profileJobTitle").value.trim(),
        phone: el("profilePhone").value.trim(),
        location: el("profileLocation").value.trim(),
        experience_years: Number(el("profileExpYears").value) || 0,
        linkedin_url: el("profileLinkedIn").value.trim(),
        github_url: el("profileGitHub").value.trim(),
        bio: el("profileBio").value.trim()
    };

    const { ok, data } = await api("/auth/profile", { method: "PUT", body: JSON.stringify(payload) });
    if (ok) {
        State.user = { ...State.user, ...data.user };
        renderAuthState();
        showAlert("profileSuccess", "Profile updated successfully!");
    } else {
        showAlert("profileError", data.error || "Update failed.");
    }
});

// ──────────────────────────────────────────────────────────────
// SECURITY / PASSWORD
// ──────────────────────────────────────────────────────────────

el("passwordForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert("passwordSuccess");
    hideAlert("passwordError");

    const current = el("currentPassword").value;
    const newPw = el("newPassword").value;
    const confirm = el("confirmPassword").value;

    if (newPw !== confirm) { showAlert("passwordError", "Passwords do not match."); return; }

    const { ok, data } = await api("/auth/password", {
        method: "PUT",
        body: JSON.stringify({ current_password: current, new_password: newPw })
    });

    if (ok) {
        el("passwordForm").reset();
        showAlert("passwordSuccess", "Password changed successfully!");
    } else {
        showAlert("passwordError", data.error || "Failed to change password.");
    }
});

// ──────────────────────────────────────────────────────────────
// CHAT HISTORY
// ──────────────────────────────────────────────────────────────

async function loadChatHistory() {
    const area = el("chatHistoryList");
    if (!area) return;
    area.innerHTML = `<p class="text-muted text-small">Loading history…</p>`;

    const { ok, data } = await api("/chat/history");
    if (!ok) { area.innerHTML = `<p class="text-muted text-small">Failed to load chat history.</p>`; return; }

    if (!data.history?.length) {
        area.innerHTML = `<p class="text-muted text-small">No chat history yet. Start a conversation with CareerBot!</p>`;
        return;
    }

    area.innerHTML = data.history.map(m => `
        <div class="flex-center gap-12" style="padding:12px 0;border-bottom:1px solid var(--border);align-items:flex-start;">
          <div style="width:28px;height:28px;border-radius:6px;display:grid;place-items:center;background:${m.role === "user" ? "var(--accent-soft);color:var(--accent)" : "var(--surface);color:var(--text-secondary)"};flex-shrink:0;">
            ${m.role === "user" 
              ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
              : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`}
          </div>
          <div style="flex:1">
            <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:3px">${m.role === "user" ? "You" : "Career Lens Assistant"} &middot; <span style="font-weight:400;color:var(--text-muted)">${fmtDate(m.created_at)}</span></div>
            <div style="font-size:14px;line-height:1.6;color:var(--text-secondary)">${esc(m.content)}</div>
          </div>
        </div>`).join("");
}

el("clearChatHistoryBtn")?.addEventListener("click", async () => {
    if (!confirm("Clear all chat history?")) return;
    const { ok } = await api("/chat/history", { method: "DELETE" });
    if (ok) loadChatHistory();
});

// ──────────────────────────────────────────────────────────────
// CHATBOT
// ──────────────────────────────────────────────────────────────

let chatOpen = false;

el("chatbotToggle")?.addEventListener("click", () => {
    chatOpen = !chatOpen;
    el("chatbotWindow").classList.toggle("hidden", !chatOpen);
    if (chatOpen) el("chatInput")?.focus();
});

el("chatbotClose")?.addEventListener("click", () => {
    chatOpen = false;
    hideEl("chatbotWindow");
});

async function sendChatMessage() {
    const input = el("chatInput");
    const msg = input.value.trim();
    if (!msg) return;

    input.value = "";
    appendChatMsg("user", msg);
    appendChatMsg("bot", "…", "typing");

    try {
        const { ok, data } = await api("/chat/message", {
            method: "POST",
            body: JSON.stringify({ message: msg })
        });

        // Remove typing indicator
        const typingEl = document.querySelector(".chat-msg.typing");
        if (typingEl) typingEl.remove();

        if (ok) {
            appendChatMsg("bot", data.message);
        } else {
            appendChatMsg("bot", data.error || "Sorry, I couldn't respond right now.");
        }
    } catch {
        const typingEl = document.querySelector(".chat-msg.typing");
        if (typingEl) typingEl.remove();
        appendChatMsg("bot", "Sorry, I couldn't connect right now. Please try again.");
    }
}

function formatMarkdown(text) {
    if (!text) return "";
    let html = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Code blocks ```...```
    html = html.replace(/```([\w]*)\n([\s\S]*?)```/g, (m, lang, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
    });

    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Headings
    html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
    html = html.replace(/^## (.*$)/gim, "<h3>$1</h3>");

    // Bold & Italic
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");

    // Lists (•, -, *)
    html = html.replace(/^[•\-\*]\s+(.*$)/gim, "<li>$1</li>");
    html = html.replace(/(<li>[\s\S]*?<\/li>)/gi, (match) => `<ul>${match}</ul>`);
    html = html.replace(/<\/ul>\s*<ul>/g, "");

    // Line breaks
    html = html.replace(/\n\n/g, "</p><p>");
    html = html.replace(/\n/g, "<br>");

    return `<p>${html}</p>`.replace(/<p>\s*<\/p>/g, "");
}

function appendChatMsg(role, content, extraClass = "") {
    const messages = el("chatMessages");
    const div = document.createElement("div");
    div.className = `chat-msg ${role} ${extraClass}`.trim();

    if (extraClass === "typing") {
        div.textContent = content;
    } else {
        div.innerHTML = formatMarkdown(content);
    }

    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

el("chatSendBtn")?.addEventListener("click", sendChatMessage);

el("chatInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
    }
});

// ──────────────────────────────────────────────────────────────
// INIT
// ──────────────────────────────────────────────────────────────

(async function init() {
    await checkAuth();
})();