"""
Caption Maker Settings Page — Dual Mode: Local Whisper + API Whisper
"""

import customtkinter as ctk
from tkinter import messagebox

from pages.settings.ai_providers.base_provider import BaseProviderSettingsPage


class CaptionMakerSettingsPage(BaseProviderSettingsPage):
    """Settings page for Caption Maker AI provider with Local/API dual mode"""
    
    # Use manual input instead of dropdown
    USE_MANUAL_INPUT = True
    DEFAULT_MODEL = "whisper-1"
    
    def __init__(self, parent, config, on_save_callback, on_back_callback):
        super().__init__(
            parent=parent,
            title="Caption Maker",
            provider_key="caption_maker",
            config=config,
            on_save_callback=on_save_callback,
            on_back_callback=on_back_callback
        )
    
    def create_provider_content(self):
        """Create provider settings content with Local Whisper toggle"""
        # ─── Mode Toggle Section ───
        mode_section = self.create_section("Transcription Mode")
        
        mode_frame = ctk.CTkFrame(mode_section, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=(0, 12))
        
        # Toggle buttons frame
        toggle_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        toggle_frame.pack(fill="x")
        toggle_frame.grid_columnconfigure((0, 1), weight=1, uniform="mode")
        
        self.mode_var = ctk.StringVar(value="api")
        
        self.local_btn = ctk.CTkButton(toggle_frame, text="🖥️ Local Whisper (Gratis)",
            height=40, corner_radius=8, fg_color=("gray85", "gray25"),
            text_color=("gray30", "gray70"), hover_color=("gray75", "gray30"),
            command=lambda: self._set_mode("local"))
        self.local_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.api_btn = ctk.CTkButton(toggle_frame, text="☁️ Whisper API",
            height=40, corner_radius=8, fg_color=("#1F6AA5", "#1F6AA5"),
            text_color="white", hover_color=("#36719F", "#144870"),
            command=lambda: self._set_mode("api"))
        self.api_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        
        # ─── Local Whisper Settings (hidden by default) ───
        self.local_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        
        # Info box
        local_info = ctk.CTkFrame(self.local_frame, fg_color=("gray85", "gray20"), corner_radius=8)
        local_info.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(local_info, text="🖥️ Local Whisper (faster-whisper)",
            font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(10, 5))
        ctk.CTkLabel(local_info,
            text="Jalankan Whisper Large V3 Turbo langsung di PC kamu.\n"
                 "• Gratis — tidak butuh API key atau kredit\n"
                 "• Akurasi tinggi (setara Whisper API)\n"
                 "• Model di-download otomatis saat pertama kali (~1.5GB)",
            font=ctk.CTkFont(size=10), text_color="gray", justify="left").pack(anchor="w", padx=12, pady=(0, 10))
        
        # Model Size
        model_section = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        model_section.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(model_section, text="Model Size",
            font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        
        self.local_model_var = ctk.StringVar(value="large-v3-turbo")
        self.local_model_dropdown = ctk.CTkOptionMenu(model_section,
            values=["large-v3-turbo", "large-v3", "medium", "small", "base", "tiny"],
            variable=self.local_model_var, height=36,
            command=self._on_model_size_changed)
        self.local_model_dropdown.pack(fill="x", pady=(5, 0))
        
        # Model info label
        self.model_info_label = ctk.CTkLabel(model_section, text="",
            font=ctk.CTkFont(size=9), text_color="gray", justify="left")
        self.model_info_label.pack(anchor="w", pady=(5, 0))
        self._on_model_size_changed("large-v3-turbo")
        
        # Device
        device_section = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        device_section.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(device_section, text="Device",
            font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        
        self.device_var = ctk.StringVar(value="auto")
        self.device_dropdown = ctk.CTkOptionMenu(device_section,
            values=["auto", "cpu", "cuda"],
            variable=self.device_var, height=36)
        self.device_dropdown.pack(fill="x", pady=(5, 0))
        
        ctk.CTkLabel(device_section,
            text="Auto = pakai GPU (CUDA) kalau tersedia, kalau tidak pakai CPU",
            font=ctk.CTkFont(size=9), text_color="gray").pack(anchor="w", pady=(3, 0))
        
        # Compute Type
        compute_section = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        compute_section.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(compute_section, text="Compute Type",
            font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        
        self.compute_var = ctk.StringVar(value="auto")
        self.compute_dropdown = ctk.CTkOptionMenu(compute_section,
            values=["auto", "float16", "int8", "float32"],
            variable=self.compute_var, height=36)
        self.compute_dropdown.pack(fill="x", pady=(5, 0))
        
        ctk.CTkLabel(compute_section,
            text="Auto = float16 (GPU) atau int8 (CPU). int8 paling hemat memori.",
            font=ctk.CTkFont(size=9), text_color="gray").pack(anchor="w", pady=(3, 0))
        
        # Save button for local mode
        local_save_frame = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        local_save_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkButton(local_save_frame, text="💾 Save Local Whisper Settings", height=40,
            fg_color=("#27ae60", "#27ae60"), hover_color=("#219a52", "#219a52"),
            command=self.save_local_settings).pack(fill="x")
        
        # ─── API Info Box (shown by default) ───
        self.api_info = ctk.CTkFrame(self.content, fg_color=("gray85", "gray20"), corner_radius=8)
        
        ctk.CTkLabel(self.api_info, text="📝 About Caption Maker (API)",
            font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(10, 5))
        ctk.CTkLabel(self.api_info,
            text="Uses Whisper API to transcribe audio and generate\nword-by-word captions with precise timing.",
            font=ctk.CTkFont(size=10), text_color="gray", justify="left").pack(anchor="w", padx=12, pady=(0, 10))
        
        self.api_info.pack(fill="x", pady=(0, 10))
        
        # Snapshot widgets before calling super (to know which ones are API-specific)
        _before = set(self.content.winfo_children())
        
        # Call parent to create standard API fields (URL, Key, Model)
        super().create_provider_content()
        
        # Track API-specific widgets (those added by parent)
        _after = set(self.content.winfo_children())
        self._api_section_widgets = [w for w in self.content.winfo_children() if w in (_after - _before)]
        
        # Load local whisper settings and set correct mode
        self._load_local_settings()
    
    def _set_mode(self, mode: str):
        """Switch between local and API mode"""
        self.mode_var.set(mode)
        
        if mode == "local":
            # Highlight local button
            self.local_btn.configure(fg_color=("#1F6AA5", "#1F6AA5"), text_color="white")
            self.api_btn.configure(fg_color=("gray85", "gray25"), text_color=("gray30", "gray70"))
            # Hide API info + API fields, show local settings
            self.api_info.pack_forget()
            self._hide_api_sections()
            self.local_frame.pack(fill="x", pady=(0, 10))
        else:
            # Highlight API button
            self.api_btn.configure(fg_color=("#1F6AA5", "#1F6AA5"), text_color="white")
            self.local_btn.configure(fg_color=("gray85", "gray25"), text_color=("gray30", "gray70"))
            # Hide local settings, show API info + API fields
            self.local_frame.pack_forget()
            self.api_info.pack(fill="x", pady=(0, 10))
            self._show_api_sections()
    
    def _hide_api_sections(self):
        """Hide API-specific UI sections when in local mode"""
        for widget in self._api_section_widgets:
            widget.pack_forget()
    
    def _show_api_sections(self):
        """Show API-specific UI sections when in API mode"""
        for widget in self._api_section_widgets:
            widget.pack(fill="x", pady=(0, 10))
    
    def _on_model_size_changed(self, model_name: str):
        """Update model info label based on selected model"""
        info_map = {
            "large-v3-turbo": "~1.5GB download | 4x faster | Akurasi tinggi (REKOMENDASI)",
            "large-v3": "~3GB download | Akurasi tertinggi | Butuh ~4GB VRAM untuk GPU",
            "medium": "~800MB download | Cepat di CPU | Akurasi bagus",
            "small": "~500MB download | Sangat cepat | Akurasi cukup",
            "base": "~150MB download | Ultra cepat | Akurasi dasar",
            "tiny": "~75MB download | Instant | Akurasi rendah (testing only)",
        }
        self.model_info_label.configure(text=info_map.get(model_name, ""))
    
    def _load_local_settings(self):
        """Load local whisper settings from config"""
        if hasattr(self.config, 'config'):
            config_dict = self.config.config
        else:
            config_dict = self.config
        
        local_settings = config_dict.get("local_whisper", {})
        
        if local_settings.get("enabled", False):
            self._set_mode("local")
        else:
            self._set_mode("api")
        
        self.local_model_var.set(local_settings.get("model_size", "large-v3-turbo"))
        self.device_var.set(local_settings.get("device", "auto"))
        self.compute_var.set(local_settings.get("compute_type", "auto"))
        
        # Update info label
        self._on_model_size_changed(self.local_model_var.get())
    
    def save_local_settings(self):
        """Save local whisper settings"""
        if hasattr(self.config, 'config'):
            config_dict = self.config.config
        else:
            config_dict = self.config
        
        local_settings = {
            "enabled": True,
            "model_size": self.local_model_var.get(),
            "device": self.device_var.get(),
            "compute_type": self.compute_var.get()
        }
        
        config_dict["local_whisper"] = local_settings
        
        if self.on_save_callback:
            self.on_save_callback(config_dict)
        
        messagebox.showinfo("Success",
            f"Local Whisper settings saved!\n\n"
            f"Model: {local_settings['model_size']}\n"
            f"Device: {local_settings['device']}\n"
            f"Compute: {local_settings['compute_type']}\n\n"
            f"Model akan di-download otomatis saat pertama kali digunakan.")
        self.on_back()
    
    def save_settings(self):
        """Override save to handle dual mode"""
        mode = self.mode_var.get()
        
        if mode == "local":
            self.save_local_settings()
        else:
            # Disable local whisper when saving API mode
            if hasattr(self.config, 'config'):
                config_dict = self.config.config
            else:
                config_dict = self.config
            
            config_dict["local_whisper"] = {
                "enabled": False,
                "model_size": self.local_model_var.get(),
                "device": self.device_var.get(),
                "compute_type": self.compute_var.get()
            }
            
            # Call parent save for API settings
            super().save_settings()
