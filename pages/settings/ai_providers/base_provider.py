"""
Base class for AI Provider settings pages
"""

import threading
import customtkinter as ctk
from tkinter import messagebox

from pages.settings.base_dialog import BaseSettingsSubPage

# Provider presets
PROVIDER_PRESETS = {
    "🤖 Open AI": {
        "key": "openai",
        "base_url": "https://api.openai.com/v1",
    },
    "✨ Gemini": {
        "key": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    "⚙️ Custom Provider 1": {
        "key": "custom1",
        "base_url": "",
    },
    "⚙️ Custom Provider 2": {
        "key": "custom2",
        "base_url": "",
    },
}

PROVIDER_DISPLAY_NAMES = list(PROVIDER_PRESETS.keys())


def _url_to_provider_display(base_url: str, custom_url_1: str = "", custom_url_2: str = "") -> str:
    """Guess provider display name from a saved base_url."""
    if not base_url:
        return "🤖 Open AI"
    if "openai.com" in base_url:
        return "🤖 Open AI"
    if "googleapis.com" in base_url or "gemini" in base_url.lower():
        return "✨ Gemini"
    if custom_url_2 and base_url.rstrip("/") == custom_url_2.rstrip("/"):
        return "⚙️ Custom Provider 2"
    # Default unknown URLs to Custom Provider 1
    return "⚙️ Custom Provider 1"


class BaseProviderSettingsPage(BaseSettingsSubPage):
    """Base class for AI provider settings pages"""

    # Override in child class for fixed model list (None = load from API)
    FIXED_MODELS = None
    # Override in child class to use manual input instead of dropdown
    USE_MANUAL_INPUT = False
    # Default model value when using manual input
    DEFAULT_MODEL = ""

    def __init__(self, parent, title, provider_key, config, on_save_callback, on_back_callback):
        self.config = config
        self.provider_key = provider_key
        self.on_save_callback = on_save_callback
        self.models_list = []

        super().__init__(parent, title, on_back_callback)

        self.create_provider_content()
        self.load_config()

    # ──────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────

    def create_provider_content(self):
        """Create provider settings content"""
        # Provider Type Section
        type_section = self.create_section("Provider Type")

        type_frame = ctk.CTkFrame(type_section, fg_color="transparent")
        type_frame.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(type_frame, text="Select API Provider",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")

        self.provider_type_var = ctk.StringVar(value="🤖 Open AI")
        self.provider_dropdown = ctk.CTkOptionMenu(
            type_frame,
            values=PROVIDER_DISPLAY_NAMES,
            variable=self.provider_type_var,
            height=36,
            command=self._on_provider_type_changed,
        )
        self.provider_dropdown.pack(fill="x", pady=(5, 0))

        self.system_message_textbox = None

        # URL Section for Custom Provider 1
        self.url_section = self.create_section("Base URL (Custom Provider 1)")
        self.url_section.pack_forget()

        url_frame = ctk.CTkFrame(self.url_section, fg_color="transparent")
        url_frame.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(url_frame, text="API Base URL",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="https://your-provider.com/v1", height=36
        )
        self.url_entry.pack(fill="x", pady=(5, 0))

        # URL Section for Custom Provider 2
        self.url_section_2 = self.create_section("Base URL (Custom Provider 2)")
        self.url_section_2.pack_forget()

        url_frame_2 = ctk.CTkFrame(self.url_section_2, fg_color="transparent")
        url_frame_2.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(url_frame_2, text="API Base URL",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.url_entry_2 = ctk.CTkEntry(
            url_frame_2, placeholder_text="https://your-second-provider.com/v1", height=36
        )
        self.url_entry_2.pack(fill="x", pady=(5, 0))

        # API Key Section
        key_section = self.create_section("API Key")

        key_frame = ctk.CTkFrame(key_section, fg_color="transparent")
        key_frame.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(key_frame, text="API Key",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.key_entry = ctk.CTkEntry(
            key_frame, placeholder_text="sk-...", show="•", height=36
        )
        self.key_entry.pack(fill="x", pady=(5, 0))

        # Model Section
        self.model_section = self.create_section("Model")

        model_frame = ctk.CTkFrame(self.model_section, fg_color="transparent")
        model_frame.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(model_frame, text="Model Name",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")

        model_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        model_row.pack(fill="x", pady=(5, 0))

        if self.USE_MANUAL_INPUT:
            self.model_entry = ctk.CTkEntry(
                model_row, placeholder_text=f"e.g., {self.DEFAULT_MODEL}", height=36
            )
            self.model_entry.pack(fill="x")
            self.model_dropdown = None
            self.model_var = None
            self.load_btn = None
            self.merge_btn = None
        else:
            self.model_var = ctk.StringVar(value="")
            self.model_entry = None

            if self.FIXED_MODELS:
                self.model_dropdown = ctk.CTkOptionMenu(
                    model_row,
                    values=self.FIXED_MODELS,
                    variable=self.model_var,
                    height=36,
                )
                self.model_dropdown.pack(fill="x")
                self.load_btn = None
                self.merge_btn = None
            else:
                # Dynamic dropdown + Load + Load & Merge buttons
                self.model_dropdown = ctk.CTkOptionMenu(
                    model_row,
                    values=["-- Click Load to fetch models --"],
                    variable=self.model_var,
                    height=36,
                    width=200,
                )
                self.model_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 4))

                self.load_btn = ctk.CTkButton(
                    model_row, text="🔄 Load", width=70, height=36,
                    command=lambda: self.load_models(append=False),
                )
                self.load_btn.pack(side="left", padx=(0, 3))

                self.merge_btn = ctk.CTkButton(
                    model_row, text="⊕ Merge", width=72, height=36,
                    fg_color=("gray70", "gray30"),
                    hover_color=("gray60", "gray40"),
                    command=lambda: self.load_models(append=True),
                    tooltip_text="Append models from current provider to existing list",
                )
                self.merge_btn.pack(side="left")

        # Model count label
        self.model_count_label = ctk.CTkLabel(
            model_frame, text="", font=ctk.CTkFont(size=9), text_color="gray"
        )
        self.model_count_label.pack(anchor="w", pady=(4, 0))

        # Actions
        actions_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            actions_frame, text="🔍 Validate Configuration", height=40,
            fg_color=("3B8ED0", "#1F6AA5"), hover_color=("#36719F", "#144870"),
            command=self.validate_config,
        ).pack(fill="x", pady=(0, 10))

        self.create_save_button(self.save_settings)

    # ──────────────────────────────────────────────────────
    # Provider type helpers
    # ──────────────────────────────────────────────────────

    def _on_provider_type_changed(self, value):
        """Handle provider type dropdown change."""
        preset = PROVIDER_PRESETS.get(value, {})
        ptype = preset.get("key", "custom1")

        # Hide both custom URL sections first
        self.url_section.pack_forget()
        self.url_section_2.pack_forget()

        if ptype == "custom1":
            try:
                self.url_section.pack(
                    fill="x", pady=(0, 10),
                    after=self.content.winfo_children()[1],
                )
            except Exception:
                self.url_section.pack(fill="x", pady=(0, 10))
        elif ptype == "custom2":
            try:
                self.url_section_2.pack(
                    fill="x", pady=(0, 10),
                    after=self.content.winfo_children()[1],
                )
            except Exception:
                self.url_section_2.pack(fill="x", pady=(0, 10))
        else:
            # Preset provider — auto-fill URL entry for reference
            preset_url = preset.get("base_url", "")
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, preset_url)

    def _get_provider_type_key(self) -> str:
        """Return 'openai', 'gemini', 'custom1', or 'custom2'."""
        value = self.provider_type_var.get()
        return PROVIDER_PRESETS.get(value, {}).get("key", "custom1")

    def get_base_url(self) -> str:
        """Return the effective base URL for the selected provider."""
        ptype = self._get_provider_type_key()
        if ptype == "openai":
            return "https://api.openai.com/v1"
        elif ptype == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        elif ptype == "custom2":
            return self.url_entry_2.get().strip() or "https://api.openai.com/v1"
        else:  # custom1
            return self.url_entry.get().strip() or "https://api.openai.com/v1"

    @staticmethod
    def _looks_custom(url: str) -> bool:
        """Return True if the URL is not from a known preset provider."""
        if not url:
            return False
        known = ("openai.com", "googleapis.com")
        return not any(k in url for k in known)

    # ──────────────────────────────────────────────────────
    # Model loading
    # ──────────────────────────────────────────────────────

    def load_models(self, append: bool = False):
        """Load available models from the currently selected API.

        Args:
            append: If True, merge fetched models into the existing list
                    instead of replacing it. Use this to combine models from
                    multiple providers.
        """
        if self.FIXED_MODELS:
            return

        api_key = self.key_entry.get().strip()
        if not api_key:
            messagebox.showerror("Error", "Please enter API Key first")
            return

        url = self.get_base_url()
        provider_name = self.provider_type_var.get()

        self.load_btn.configure(state="disabled", text="Loading...")
        if self.merge_btn:
            self.merge_btn.configure(state="disabled")

        existing = list(self.model_dropdown.cget("values")) if append else []
        # Strip placeholder
        existing = [m for m in existing if not m.startswith("--")]

        def do_load():
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=url)
                models_response = client.models.list()
                models = sorted(m.id for m in models_response.data)
                self.after(0, lambda: self._on_models_loaded(models, existing, provider_name))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: self._on_models_error(msg))

        threading.Thread(target=do_load, daemon=True).start()

    def _on_models_loaded(self, new_models: list, existing: list, provider_name: str):
        """Merge & update model dropdown."""
        self.load_btn.configure(state="normal", text="🔄 Load")
        if self.merge_btn:
            self.merge_btn.configure(state="normal")

        if not new_models:
            messagebox.showwarning("Warning", "No models found from this provider")
            return

        # Merge: existing first, then new (deduplicated)
        combined = list(existing)
        for m in new_models:
            if m not in combined:
                combined.append(m)

        self.models_list = combined
        self.model_dropdown.configure(values=combined)

        current = self.model_var.get()
        if current not in combined:
            self.model_var.set(combined[0])

        added = len(new_models)
        total = len(combined)
        mode = "merged" if existing else "loaded"
        self.model_count_label.configure(
            text=f"✓ {mode} {added} models from {provider_name} — {total} total in list"
        )

    def _on_models_error(self, error: str):
        self.load_btn.configure(state="normal", text="🔄 Load")
        if self.merge_btn:
            self.merge_btn.configure(state="normal")
        messagebox.showerror("Error", f"Failed to load models:\n{error}")

    # ──────────────────────────────────────────────────────
    # Validate
    # ──────────────────────────────────────────────────────

    def validate_config(self):
        """Validate provider configuration."""
        api_key = self.key_entry.get().strip()
        model = self.model_var.get().strip() if self.model_var else (
            self.model_entry.get().strip() if self.model_entry else ""
        )
        url = self.get_base_url()

        if not api_key:
            messagebox.showerror("Error", "API Key is required")
            return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=url)
            client.models.list()
            messagebox.showinfo(
                "Success",
                f"✓ Configuration valid!\n\nModel: {model}\nURL: {url}",
            )
        except Exception as e:
            messagebox.showerror("Error", f"Validation failed:\n{str(e)}")

    # ──────────────────────────────────────────────────────
    # Load / Save config
    # ──────────────────────────────────────────────────────

    def load_config(self):
        """Load config into UI."""
        if hasattr(self.config, "config"):
            config_dict = self.config.config
        else:
            config_dict = self.config

        ai_providers = config_dict.get("ai_providers", {})
        provider = ai_providers.get(self.provider_key, {})

        base_url = provider.get("base_url", "")
        custom_url_1 = provider.get("custom_url_1", "")
        custom_url_2 = provider.get("custom_url_2", "")

        # Populate both custom URL entries
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, custom_url_1 or (base_url if self._looks_custom(base_url) else ""))

        self.url_entry_2.delete(0, "end")
        self.url_entry_2.insert(0, custom_url_2)

        # Detect provider type from saved URL
        display_name = _url_to_provider_display(base_url, custom_url_1, custom_url_2)
        self.provider_type_var.set(display_name)
        self._on_provider_type_changed(display_name)

        # API key
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, provider.get("api_key", ""))

        saved_model = provider.get("model", "")

        if self.USE_MANUAL_INPUT:
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, saved_model or self.DEFAULT_MODEL)
        else:
            if saved_model:
                if self.FIXED_MODELS:
                    if saved_model in self.FIXED_MODELS:
                        self.model_var.set(saved_model)
                    else:
                        self.model_var.set(self.FIXED_MODELS[0])
                else:
                    self.model_var.set(saved_model)
                    current_values = list(self.model_dropdown.cget("values"))
                    if saved_model not in current_values:
                        self.model_dropdown.configure(values=[saved_model] + current_values)

        # System message
        if self.system_message_textbox:
            system_message = provider.get("system_message", "")
            if not system_message:
                system_message = config_dict.get("system_prompt", "")
            self.system_message_textbox.delete("1.0", "end")
            self.system_message_textbox.insert("1.0", system_message)

    def save_settings(self):
        """Save settings."""
        api_key = self.key_entry.get().strip()

        if self.USE_MANUAL_INPUT:
            model = self.model_entry.get().strip() or self.DEFAULT_MODEL
        else:
            model = self.model_var.get().strip() if self.model_var else ""

        url = self.get_base_url()

        if not api_key:
            messagebox.showerror("Error", "API Key is required")
            return

        if not model or model.startswith("--"):
            messagebox.showerror("Error", "Please select or enter a model")
            return

        if hasattr(self.config, "config"):
            config_dict = self.config.config
        else:
            config_dict = self.config

        if "ai_providers" not in config_dict:
            config_dict["ai_providers"] = {}

        # Persist both custom URLs so switching between them doesn't lose data
        existing = config_dict["ai_providers"].get(self.provider_key, {})
        provider_config = {
            "base_url": url,
            "api_key": api_key,
            "model": model,
            "custom_url_1": self.url_entry.get().strip() or existing.get("custom_url_1", ""),
            "custom_url_2": self.url_entry_2.get().strip() or existing.get("custom_url_2", ""),
        }

        if self.system_message_textbox:
            system_message = self.system_message_textbox.get("1.0", "end").strip()
            if system_message:
                provider_config["system_message"] = system_message

        config_dict["ai_providers"][self.provider_key] = provider_config

        if self.on_save_callback:
            self.on_save_callback(config_dict)

        messagebox.showinfo("Success", f"{self.title} settings saved!")
        self.on_back()
