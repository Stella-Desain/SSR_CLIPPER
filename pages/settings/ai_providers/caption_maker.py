"""
Caption Maker Settings Page — Dual Mode: Local Whisper + API Whisper
"""

import os
import glob
import customtkinter as ctk
from tkinter import messagebox

from pages.settings.ai_providers.base_provider import BaseProviderSettingsPage


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _detect_cached_whisper_models() -> list[str]:
    """Return list of faster-whisper model sizes already downloaded to HF cache."""
    cached = []
    size_names = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]

    # HuggingFace hub cache locations
    hf_home = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
    hub_dir = os.path.join(hf_home, "hub")

    for size in size_names:
        # faster-whisper saves under models--Systran--faster-whisper-<size>
        pattern = os.path.join(hub_dir, f"models--Systran--faster-whisper-{size}", "**", "model.bin")
        if glob.glob(pattern, recursive=True):
            cached.append(size)

    # Also check ctranslate2 / local paths the user might have
    return cached


# ──────────────────────────────────────────────────────────────────────────────
# Page
# ──────────────────────────────────────────────────────────────────────────────

class CaptionMakerSettingsPage(BaseProviderSettingsPage):
    """Settings page for Caption Maker AI provider with Local/API dual mode"""

    # Caption Maker uses a manual text field for the Whisper model name
    USE_MANUAL_INPUT = True
    DEFAULT_MODEL = "whisper-1"

    def __init__(self, parent, config, on_save_callback, on_back_callback):
        super().__init__(
            parent=parent,
            title="Caption Maker",
            provider_key="caption_maker",
            config=config,
            on_save_callback=on_save_callback,
            on_back_callback=on_back_callback,
        )

    # ──────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────

    def create_provider_content(self):
        """Create provider settings content with Local Whisper toggle"""

        # ─── Mode Toggle ───────────────────────────────────
        mode_section = self.create_section("Transcription Mode")

        mode_frame = ctk.CTkFrame(mode_section, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=(0, 12))

        toggle_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        toggle_frame.pack(fill="x")
        toggle_frame.grid_columnconfigure((0, 1), weight=1, uniform="mode")

        self.mode_var = ctk.StringVar(value="api")

        self.local_btn = ctk.CTkButton(
            toggle_frame, text="🖥️ Local Whisper (Gratis)",
            height=40, corner_radius=8,
            fg_color=("gray85", "gray25"), text_color=("gray30", "gray70"),
            hover_color=("gray75", "gray30"),
            command=lambda: self._set_mode("local"),
        )
        self.local_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.api_btn = ctk.CTkButton(
            toggle_frame, text="☁️ Whisper API",
            height=40, corner_radius=8,
            fg_color=("#1F6AA5", "#1F6AA5"), text_color="white",
            hover_color=("#36719F", "#144870"),
            command=lambda: self._set_mode("api"),
        )
        self.api_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # ─── Gemini warning (hidden by default) ────────────
        self.gemini_warning = ctk.CTkFrame(
            self.content, fg_color=("#7f1a1a", "#5a0000"), corner_radius=8
        )
        ctk.CTkLabel(
            self.gemini_warning,
            text="⚠️  Gemini tidak support Whisper Audio API",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffcccc",
        ).pack(anchor="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            self.gemini_warning,
            text=(
                "Endpoint /audio/transcriptions tidak ada di Google Gemini,\n"
                "sehingga akan selalu dapat HTTP 404.\n\n"
                "Solusi:\n"
                "  • Pakai mode 🖥️ Local Whisper (gratis, offline)\n"
                "  • Atau ganti provider ke 🤖 Open AI / ⚙️ Custom\n"
                "    yang memang support audio transcription"
            ),
            font=ctk.CTkFont(size=10),
            text_color="#ffcccc",
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # ─── Local Whisper Settings ─────────────────────────
        self.local_frame = ctk.CTkFrame(self.content, fg_color="transparent")

        local_info = ctk.CTkFrame(self.local_frame, fg_color=("gray85", "gray20"), corner_radius=8)
        local_info.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            local_info, text="🖥️ Local Whisper (faster-whisper)",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            local_info,
            text=(
                "Jalankan Whisper langsung di PC kamu.\n"
                "• Gratis — tidak butuh API key atau kredit\n"
                "• Akurasi tinggi (setara Whisper API)\n"
                "• Model di-download otomatis saat pertama kali (~1.5GB)"
            ),
            font=ctk.CTkFont(size=10), text_color="gray", justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # Model Size
        model_section = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        model_section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(model_section, text="Model Size",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")

        self.local_model_var = ctk.StringVar(value="large-v3-turbo")
        self.local_model_dropdown = ctk.CTkOptionMenu(
            model_section,
            values=["large-v3-turbo", "large-v3", "medium", "small", "base", "tiny"],
            variable=self.local_model_var,
            height=36,
            command=self._on_local_model_changed,
        )
        self.local_model_dropdown.pack(fill="x", pady=(5, 0))

        # Model info label (size + cache status)
        self.model_info_label = ctk.CTkLabel(
            model_section, text="", font=ctk.CTkFont(size=9),
            text_color="gray", justify="left",
        )
        self.model_info_label.pack(anchor="w", pady=(5, 0))

        # Detect already-cached models and update dropdown labels
        self._refresh_local_model_labels()

        # Device
        device_section = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        device_section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(device_section, text="Device",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")

        self.device_var = ctk.StringVar(value="auto")
        self.device_dropdown = ctk.CTkOptionMenu(
            device_section, values=["auto", "cpu", "cuda"],
            variable=self.device_var, height=36,
        )
        self.device_dropdown.pack(fill="x", pady=(5, 0))
        ctk.CTkLabel(
            device_section,
            text="Auto = pakai GPU (CUDA) kalau tersedia, kalau tidak pakai CPU",
            font=ctk.CTkFont(size=9), text_color="gray",
        ).pack(anchor="w", pady=(3, 0))

        # Compute Type
        compute_section = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        compute_section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(compute_section, text="Compute Type",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")

        self.compute_var = ctk.StringVar(value="auto")
        self.compute_dropdown = ctk.CTkOptionMenu(
            compute_section, values=["auto", "float16", "int8", "float32"],
            variable=self.compute_var, height=36,
        )
        self.compute_dropdown.pack(fill="x", pady=(5, 0))
        ctk.CTkLabel(
            compute_section,
            text="Auto = float16 (GPU) atau int8 (CPU). int8 paling hemat memori.",
            font=ctk.CTkFont(size=9), text_color="gray",
        ).pack(anchor="w", pady=(3, 0))

        # Save button (local mode)
        local_save_frame = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        local_save_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            local_save_frame, text="💾 Save Local Whisper Settings", height=40,
            fg_color=("#27ae60", "#27ae60"), hover_color=("#219a52", "#219a52"),
            command=self.save_local_settings,
        ).pack(fill="x")

        # ─── API Info box (shown by default) ───────────────
        self.api_info = ctk.CTkFrame(self.content, fg_color=("gray85", "gray20"), corner_radius=8)

        ctk.CTkLabel(
            self.api_info, text="📝 About Caption Maker (API)",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(10, 5))
        ctk.CTkLabel(
            self.api_info,
            text=(
                "Uses Whisper-compatible API to transcribe audio and generate\n"
                "word-by-word captions with precise timing.\n\n"
                "Compatible providers: OpenAI, Groq (whisper-large-v3),\n"
                "and any Custom endpoint with /audio/transcriptions support."
            ),
            font=ctk.CTkFont(size=10), text_color="gray", justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        self.api_info.pack(fill="x", pady=(0, 10))

        # Snapshot children before calling super (to track which are API-specific)
        _before = set(self.content.winfo_children())

        # Call parent to create standard API fields (URL, Key, Model)
        super().create_provider_content()

        _after = set(self.content.winfo_children())
        self._api_section_widgets = [
            w for w in self.content.winfo_children()
            if w in (_after - _before)
        ]

        # Load local whisper settings and set correct mode
        self._load_local_settings()

    # ──────────────────────────────────────────────────────
    # Mode switching
    # ──────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        """Switch between local and API mode."""
        self.mode_var.set(mode)

        if mode == "local":
            self.local_btn.configure(fg_color=("#1F6AA5", "#1F6AA5"), text_color="white")
            self.api_btn.configure(fg_color=("gray85", "gray25"), text_color=("gray30", "gray70"))
            self.api_info.pack_forget()
            self.gemini_warning.pack_forget()
            self._hide_api_sections()
            self.local_frame.pack(fill="x", pady=(0, 10))
        else:
            self.api_btn.configure(fg_color=("#1F6AA5", "#1F6AA5"), text_color="white")
            self.local_btn.configure(fg_color=("gray85", "gray25"), text_color=("gray30", "gray70"))
            self.local_frame.pack_forget()
            # Show/hide Gemini warning based on current provider selection
            self._update_gemini_warning()
            self.api_info.pack(fill="x", pady=(0, 10))
            self._show_api_sections()

    def _hide_api_sections(self):
        for widget in self._api_section_widgets:
            widget.pack_forget()

    def _show_api_sections(self):
        for widget in self._api_section_widgets:
            widget.pack(fill="x", pady=(0, 10))

    # ──────────────────────────────────────────────────────
    # Gemini warning
    # ──────────────────────────────────────────────────────

    def _on_provider_type_changed(self, value):
        """Override: also update Gemini warning when provider changes."""
        super()._on_provider_type_changed(value)
        # Only show warning in API mode
        if hasattr(self, "mode_var") and self.mode_var.get() == "api":
            self._update_gemini_warning()

    def _update_gemini_warning(self):
        """Show or hide the Gemini incompatibility warning."""
        if not hasattr(self, "gemini_warning"):
            return
        ptype = self._get_provider_type_key()
        if ptype == "gemini":
            # Insert warning before api_info
            self.gemini_warning.pack(fill="x", pady=(0, 6))
        else:
            self.gemini_warning.pack_forget()

    # ──────────────────────────────────────────────────────
    # Local model helpers
    # ──────────────────────────────────────────────────────

    def _refresh_local_model_labels(self):
        """Detect cached faster-whisper models and update dropdown values."""
        cached = _detect_cached_whisper_models()
        sizes = ["large-v3-turbo", "large-v3", "medium", "small", "base", "tiny"]

        labelled = []
        for s in sizes:
            label = f"✓ {s} (downloaded)" if s in cached else s
            labelled.append(label)

        self.local_model_dropdown.configure(values=labelled)

        # Keep raw size as the stored value (strip label prefix)
        current_raw = self.local_model_var.get().replace("✓ ", "").replace(" (downloaded)", "")
        for label in labelled:
            raw = label.replace("✓ ", "").replace(" (downloaded)", "")
            if raw == current_raw:
                self.local_model_var.set(label)
                self._on_local_model_changed(label)
                break

    def _get_raw_model_size(self) -> str:
        """Strip UI label decoration from selected local model."""
        v = self.local_model_var.get()
        return v.replace("✓ ", "").replace(" (downloaded)", "").strip()

    def _on_local_model_changed(self, model_label: str):
        """Update info text below the local model dropdown."""
        size = model_label.replace("✓ ", "").replace(" (downloaded)", "").strip()
        info_map = {
            "large-v3-turbo": "~1.5GB download | 4x faster | Akurasi tinggi (REKOMENDASI)",
            "large-v3": "~3GB download | Akurasi tertinggi | Butuh ~4GB VRAM untuk GPU",
            "medium": "~800MB download | Cepat di CPU | Akurasi bagus",
            "small": "~500MB download | Sangat cepat | Akurasi cukup",
            "base": "~150MB download | Ultra cepat | Akurasi dasar",
            "tiny": "~75MB download | Instant | Akurasi rendah (testing only)",
        }
        self.model_info_label.configure(text=info_map.get(size, ""))

    # ──────────────────────────────────────────────────────
    # Config load
    # ──────────────────────────────────────────────────────

    def _load_local_settings(self):
        """Load local whisper settings from config."""
        if hasattr(self.config, "config"):
            config_dict = self.config.config
        else:
            config_dict = self.config

        local_settings = config_dict.get("local_whisper", {})

        if local_settings.get("enabled", False):
            self._set_mode("local")
        else:
            self._set_mode("api")

        raw_size = local_settings.get("model_size", "large-v3-turbo")
        # Try to match with potentially-labelled dropdown value
        for val in self.local_model_dropdown.cget("values"):
            if raw_size in val:
                self.local_model_var.set(val)
                self._on_local_model_changed(val)
                break

        self.device_var.set(local_settings.get("device", "auto"))
        self.compute_var.set(local_settings.get("compute_type", "auto"))

    # ──────────────────────────────────────────────────────
    # Save
    # ──────────────────────────────────────────────────────

    def save_local_settings(self):
        """Save local whisper settings."""
        if hasattr(self.config, "config"):
            config_dict = self.config.config
        else:
            config_dict = self.config

        raw_size = self._get_raw_model_size()
        local_settings = {
            "enabled": True,
            "model_size": raw_size,
            "device": self.device_var.get(),
            "compute_type": self.compute_var.get(),
        }

        config_dict["local_whisper"] = local_settings

        if self.on_save_callback:
            self.on_save_callback(config_dict)

        messagebox.showinfo(
            "Success",
            f"Local Whisper settings saved!\n\n"
            f"Model: {raw_size}\n"
            f"Device: {local_settings['device']}\n"
            f"Compute: {local_settings['compute_type']}\n\n"
            f"Model akan di-download otomatis saat pertama kali digunakan.",
        )
        self.on_back()

    def save_settings(self):
        """Override save to handle dual mode."""
        mode = self.mode_var.get()

        if mode == "local":
            self.save_local_settings()
        else:
            # Disable local whisper when saving API mode
            if hasattr(self.config, "config"):
                config_dict = self.config.config
            else:
                config_dict = self.config

            config_dict["local_whisper"] = {
                "enabled": False,
                "model_size": self._get_raw_model_size(),
                "device": self.device_var.get(),
                "compute_type": self.compute_var.get(),
            }

            # Parent handles API settings save
            super().save_settings()
