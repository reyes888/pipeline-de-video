const STAGE_LABELS = {
  nuevo: "Nuevo",
  descargando: "Descargando…",
  descargado: "Descargado",
  convirtiendo: "Convirtiendo…",
  convertido: "Convertido",
  extrayendo_audio: "Extrayendo audio…",
  transcribiendo: "Transcribiendo…",
  transcrito: "Transcrito",
  clips_importados: "Clips importados",
  cortando: "Cortando clips…",
  completado: "Completado",
  error: "Error",
};

const IN_PROGRESS_STAGES = new Set([
  "descargando", "convirtiendo", "extrayendo_audio", "transcribiendo", "cortando",
]);

const STAGE_HINTS = {
  nuevo: "Haz clic para empezar o reanudar",
  descargando: "Preparando el video…",
  descargado: "Preparando el video…",
  convirtiendo: "Preparando el video…",
  convertido: "Haz clic para transcribir",
  extrayendo_audio: "Transcribiendo…",
  transcribiendo: "Transcribiendo…",
  transcrito: "Haz clic para encontrar los mejores momentos",
  clips_importados: "Haz clic para cortar los clips",
  cortando: "Cortando clips…",
  completado: "Listo — haz clic para ver los clips",
  error: "Hubo un error — haz clic para revisar",
};

function dashboard() {
  return {
    projects: [],
    loading: true,
    showNew: false,
    newTab: "link",
    urlsText: "",
    creating: false,
    dragOver: false,
    selectedFiles: [],
    uploading: false,
    uploadPercent: 0,
    toasts: [],
    _toastId: 0,
    _pollTimer: null,

    async init() {
      await this.load();
      this._pollTimer = setInterval(() => this.load(), 4000);
    },

    async load() {
      try {
        const res = await fetch("/api/projects");
        this.projects = await res.json();
      } catch (e) {
        // silencioso: red local, reintenta en el próximo poll
      } finally {
        this.loading = false;
      }
    },

    async createProjects() {
      const urls = this.urlsText.split("\n").map((u) => u.trim()).filter(Boolean);
      if (urls.length === 0) {
        this.toast("Pega al menos un link.", "error");
        return;
      }
      this.creating = true;
      try {
        const res = await fetch("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ urls }),
        });
        if (!res.ok) throw new Error("No se pudo crear el proyecto.");
        const created = await res.json();
        this.urlsText = "";
        this.showNew = false;
        if (created.length === 1) {
          goTo(`/projects/${created[0].id}`);
          return;
        }
        this.toast(`${created.length} proyectos creados — haz clic en cada uno para empezar.`, "success");
        await this.load();
      } catch (e) {
        this.toast(e.message, "error");
      } finally {
        this.creating = false;
      }
    },

    handleFileSelect(event) {
      this.addFiles(event.target.files);
      event.target.value = "";
    },

    handleDrop(event) {
      this.addFiles(event.dataTransfer.files);
    },

    addFiles(fileList) {
      const videos = Array.from(fileList).filter((f) => f.type.startsWith("video/") || !f.type);
      this.selectedFiles.push(...videos);
    },

    formatBytes(bytes) {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`;
      if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
      return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
    },

    uploadFiles() {
      if (!this.selectedFiles.length) return;
      const formData = new FormData();
      for (const f of this.selectedFiles) formData.append("files", f);

      this.uploading = true;
      this.uploadPercent = 0;

      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/projects/upload");
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) this.uploadPercent = Math.round((e.loaded / e.total) * 100);
      };
      xhr.onload = () => {
        this.uploading = false;
        if (xhr.status >= 200 && xhr.status < 300) {
          const created = JSON.parse(xhr.responseText);
          this.selectedFiles = [];
          this.showNew = false;
          if (created.length === 1) {
            goTo(`/projects/${created[0].id}`);
            return;
          }
          this.toast(`${created.length} video(s) subido(s), procesando…`, "success");
          this.load();
        } else {
          this.toast("No se pudo subir el/los archivo(s).", "error");
        }
      };
      xhr.onerror = () => {
        this.uploading = false;
        this.toast("Error de red al subir el archivo.", "error");
      };
      xhr.send(formData);
    },

    isRunning(stage) {
      return IN_PROGRESS_STAGES.has(stage);
    },

    stageLabel(stage) {
      return STAGE_LABELS[stage] || stage;
    },

    stageHint(stage) {
      return STAGE_HINTS[stage] || "";
    },

    badgeClass(stage) {
      if (stage === "error") return "badge-error";
      if (stage === "completado") return "badge-success";
      if (IN_PROGRESS_STAGES.has(stage)) return "badge-progress";
      return "badge-neutral";
    },

    timeAgo(iso) {
      const diffMs = Date.now() - new Date(iso).getTime();
      const mins = Math.floor(diffMs / 60000);
      if (mins < 1) return "hace un momento";
      if (mins < 60) return `hace ${mins} min`;
      const hours = Math.floor(mins / 60);
      if (hours < 24) return `hace ${hours} h`;
      return `hace ${Math.floor(hours / 24)} d`;
    },

    toast(message, type = "success") {
      const id = ++this._toastId;
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id);
      }, 4000);
    },
  };
}
