const STEP_ORDER = [
  { key: "download", label: "Descargar", stages: ["nuevo", "descargando", "descargado", "convirtiendo"] },
  { key: "convert", label: "Convertir", stages: ["convertido"] },
  { key: "transcribe", label: "Transcribir", stages: ["extrayendo_audio", "transcribiendo"] },
  { key: "transcript_done", label: "Transcrito", stages: ["transcrito"] },
  { key: "clips", label: "Clips", stages: ["clips_importados"] },
  { key: "cut", label: "Cortar", stages: ["cortando"] },
  { key: "done", label: "Listo", stages: ["completado"] },
];

const STEP_KEY_INDEX = Object.fromEntries(STEP_ORDER.map((s, i) => [s.key, i]));

const STAGE_STEP_INDEX = {
  nuevo: 0, descargando: 0, descargado: 0, convirtiendo: 0,
  convertido: 1,
  extrayendo_audio: 2, transcribiendo: 2,
  transcrito: 3,
  clips_importados: 4,
  cortando: 5,
  completado: 6,
  error: -1,
};

function projectDetail(projectId) {
  return {
    projectId,
    project: null,
    steps: STEP_ORDER,
    toasts: [],
    _toastId: 0,
    ws: null,
    activeJobs: {},
    progress: { download: 0, transcribe: 0, cut: 0 },
    logs: { download: [], transcribe: [], cut: [] },
    detail: {},
    lastActivity: {},
    queued: {},
    now: Date.now(),
    transcribeLang: "es",
    transcribeModel: "medium",
    transcriptPreview: [],
    selectedFormat: "txt",
    clipsJsonText: "",
    vertical916: false,
    finalClips: [],
    _pollTimer: null,
    _autoStartedDownload: false,
    _autoStartedTranscribe: false,

    async init() {
      setInterval(() => { this.now = Date.now(); }, 1000);
      await this.reload();
      this.ws = connectProjectWS(this.projectId, (msg) => this.onWsMessage(msg));
      if (this.project && this.project.stage === "completado") {
        this.loadFinalClips();
      }
    },

    async reload() {
      const res = await fetch(`/api/projects/${this.projectId}`);
      if (!res.ok) { this.toast("No se pudo cargar el proyecto.", "error"); return; }
      this.project = await res.json();
      this.syncJobsFromStage();
      this.maybeAutoStart();
    },

    // Si el servidor dice que algo está corriendo, la página lo refleja aunque
    // no haya sido esta carga la que lo inició (p. ej. al volver desde el dashboard).
    syncJobsFromStage() {
      const running = {
        descargando: "download", convirtiendo: "download",
        extrayendo_audio: "transcribe", transcribiendo: "transcribe",
        cortando: "cut",
      }[this.project.stage];
      for (const job of ["download", "transcribe", "cut"]) {
        this.activeJobs[job] = job === running;
      }
      if (running && !this.lastActivity[running]) this.lastActivity[running] = Date.now();
      if (running && !this._pollTimer) {
        this._pollTimer = setInterval(() => this.reload(), 3000);
      } else if (!running && this._pollTimer) {
        clearInterval(this._pollTimer);
        this._pollTimer = null;
      }
    },

    maybeAutoStart() {
      if (!this.project || this.project.stage === "error") return;
      if (
        this.project.stage === "nuevo" &&
        this.project.source_type === "url" &&
        !this._autoStartedDownload &&
        !this.jobRunning("download")
      ) {
        this._autoStartedDownload = true;
        this.startDownload();
      } else if (
        this.project.stage === "convertido" &&
        !this._autoStartedTranscribe &&
        !this.jobRunning("transcribe")
      ) {
        this._autoStartedTranscribe = true;
        this.startTranscribe();
      }
    },

    stepClass(step) {
      if (!this.project) return "";
      if (this.project.stage === "error") return "";
      const currentIdx = STAGE_STEP_INDEX[this.project.stage] ?? 0;
      const stepIdx = STEP_KEY_INDEX[step.key];
      if (stepIdx < currentIdx) return "done";
      if (stepIdx === currentIdx) return "active";
      return "";
    },

    jobRunning(name) {
      return !!this.activeJobs[name];
    },

    get canDownload() {
      return this.project && this.project.stage === "nuevo" && !this.jobRunning("download");
    },
    get canTranscribe() {
      return this.project && this.project.video_path && !this.jobRunning("transcribe")
        && !["descargando", "convirtiendo"].includes(this.project.stage);
    },
    get canCut() {
      return this.project && this.project.clips && this.project.clips.some((c) => c.selected)
        && !this.jobRunning("cut");
    },

    statusLine(job) {
      const stage = this.project && this.project.stage;
      const labels = {
        download: stage === "convirtiendo" ? "Convirtiendo a H264" : "Descargando",
        transcribe: stage === "extrayendo_audio" ? "Extrayendo audio" : "Transcribiendo",
        cut: "Cortando clips",
      };
      const label = labels[job];
      if (this.queued[job]) return `${label} · en cola, esperando turno…`;
      let line = label;
      const pct = this.progress[job];
      if (pct > 0) line += ` · ${Math.round(pct)}%`;
      let d = this.detail[job] || "";
      if (d.startsWith(label)) d = d.slice(label.length).replace(/^ · /, "");
      if (d) line += ` · ${d}`;
      return line;
    },

    activityText(job) {
      const t = this.lastActivity[job];
      if (!t) return "Iniciando…";
      const secs = Math.max(0, Math.round((this.now - t) / 1000));
      if (secs < 4) return "● activo ahora";
      return secs < 60 ? `Última actividad hace ${secs} s` : `Última actividad hace ${Math.floor(secs / 60)} min`;
    },

    isStalled(job) {
      const t = this.lastActivity[job];
      return !!t && !this.queued[job] && this.now - t > 120000;
    },

    isIndeterminate(job) {
      return this.jobRunning(job) && (this.queued[job] || !(this.progress[job] > 0));
    },

    applySnapshot(snap) {
      for (const [stage, items] of Object.entries(snap.logs || {})) {
        if (!this.logs[stage]) continue;
        this.logs[stage] = items.map((m) => ({ level: m.payload.level || "info", message: m.payload.message }));
        const last = items[items.length - 1];
        if (last) {
          this.lastActivity[stage] = Date.parse(last.timestamp);
          const prog = (snap.progress || {})[stage];
          this.queued[stage] = /esperando turno/.test(last.payload.message || "") &&
            (!prog || Date.parse(prog.timestamp) < Date.parse(last.timestamp));
        }
      }
      for (const [stage, m] of Object.entries(snap.progress || {})) {
        this.progress[stage] = m.payload.percent || 0;
        this.detail[stage] = m.payload.detail || "";
        this.lastActivity[stage] = Date.parse(m.timestamp);
      }
      if ((snap.partials || []).length) this.transcriptPreview = snap.partials;
    },

    onWsMessage(msg) {
      if (msg.type === "snapshot") { this.applySnapshot(msg.payload); return; }
      const stageToJob = {
        download: "download", convert: "download",
        transcribe: "transcribe",
        cut: "cut",
      };
      const jobName = stageToJob[msg.stage] || msg.stage;

      if (msg.type === "log") {
        if (this.logs[jobName]) {
          this.lastActivity[jobName] = Date.now();
          if (/esperando turno/.test(msg.payload.message || "")) this.queued[jobName] = true;
          this.logs[jobName].push({ level: msg.payload.level || "info", message: msg.payload.message });
          this.$nextTick(() => this.scrollConsole(jobName));
        }
      } else if (msg.type === "partial_result") {
        this.transcriptPreview.push(msg.payload.text);
        this.$nextTick(() => {
          const el = this.$refs.transcriptPreviewPanel;
          if (el) el.scrollTop = el.scrollHeight;
        });
      } else if (msg.type === "progress") {
        if (jobName in this.progress) this.progress[jobName] = msg.payload.percent;
        this.detail[jobName] = msg.payload.detail || "";
        this.lastActivity[jobName] = Date.now();
        this.queued[jobName] = false;
        this.activeJobs[jobName] = true;
      } else if (msg.type === "stage_change") {
        this.reload();
      } else if (msg.type === "done") {
        this.activeJobs[jobName] = false;
        this.reload();
        if (jobName === "cut") this.loadFinalClips();
        this.toast(`Listo: ${jobName}`, "success");
      } else if (msg.type === "error") {
        this.activeJobs[jobName] = false;
        this.toast(msg.payload.message || "Ocurrió un error.", "error");
        this.reload();
      }
    },

    scrollConsole(jobName) {
      const refMap = { download: "downloadConsole", transcribe: "transcribeConsole", cut: "cutConsole" };
      const el = this.$refs[refMap[jobName]];
      if (el) el.scrollTop = el.scrollHeight;
    },

    async startDownload() {
      this.activeJobs.download = true;
      this.logs.download = [];
      this.progress.download = 0;
      const res = await fetch(`/api/projects/${this.projectId}/download`, { method: "POST" });
      if (!res.ok) { this.activeJobs.download = false; this.toast("No se pudo iniciar la descarga.", "error"); }
    },

    async startTranscribe() {
      this.activeJobs.transcribe = true;
      this.logs.transcribe = [];
      this.progress.transcribe = 0;
      this.transcriptPreview = [];
      const res = await fetch(`/api/projects/${this.projectId}/transcribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: this.transcribeLang, model: this.transcribeModel }),
      });
      if (!res.ok) { this.activeJobs.transcribe = false; this.toast("No se pudo iniciar la transcripción.", "error"); }
    },

    async copyPrompt() {
      const res = await fetch(`/api/projects/${this.projectId}/clips/prompt`);
      const data = await res.json();
      await navigator.clipboard.writeText(data.prompt);
      this.toast("Prompt copiado al portapapeles.", "success");
    },

    async importClips() {
      let parsed;
      try {
        parsed = JSON.parse(this.clipsJsonText);
      } catch (e) {
        this.toast("El JSON pegado no es válido.", "error");
        return;
      }
      const res = await fetch(`/api/projects/${this.projectId}/clips/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clips: parsed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.toast(err.detail || "No se pudieron importar los clips.", "error");
        return;
      }
      this.clipsJsonText = "";
      this.toast("Clips importados.", "success");
      await this.reload();
    },

    async saveClip(clip) {
      await fetch(`/api/projects/${this.projectId}/clips/${clip.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(clip),
      });
    },

    async deleteClip(clip) {
      await fetch(`/api/projects/${this.projectId}/clips/${clip.id}`, { method: "DELETE" });
      await this.reload();
    },

    async startCut() {
      this.activeJobs.cut = true;
      this.logs.cut = [];
      this.progress.cut = 0;
      const res = await fetch(`/api/projects/${this.projectId}/cut`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vertical_9_16: this.vertical916 }),
      });
      if (!res.ok) { this.activeJobs.cut = false; this.toast("No se pudo iniciar el corte.", "error"); }
    },

    async loadFinalClips() {
      const res = await fetch(`/api/projects/${this.projectId}/clips_finales`);
      if (res.ok) this.finalClips = await res.json();
    },

    async openFolder() {
      await fetch(`/api/projects/${this.projectId}/open-folder`, { method: "POST" });
    },

    async deleteProject() {
      if (!confirm("¿Eliminar este proyecto y todos sus archivos? Esta acción no se puede deshacer.")) return;
      await fetch(`/api/projects/${this.projectId}`, { method: "DELETE" });
      goTo("/");
    },

    toast(message, type = "success") {
      const id = ++this._toastId;
      this.toasts.push({ id, message, type });
      setTimeout(() => { this.toasts = this.toasts.filter((t) => t.id !== id); }, 4000);
    },
  };
}
