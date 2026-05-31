import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from organizer import MovieOrganizer
import json
from datetime import datetime

__version__ = "1.1.0"
CONFIG_FILE = os.path.expanduser("~/.movie_organizer_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except Exception:
        pass

# Constants for macOS-inspired dark theme
COLOR_MAC_BG = "#1E1E1E"          # Main dark background
COLOR_MAC_SIDEBAR = "#161617"     # Darker sidebar background
COLOR_MAC_CARD = "#2C2C2E"        # Active card background
COLOR_MAC_CARD_BORDER = "#3A3A3C" # Subtle border line
COLOR_MAC_INPUT = "#1C1C1E"       # Text field background
COLOR_MAC_ACCENT = "#0A84FF"      # System Blue accent
COLOR_MAC_ACCENT_HOVER = "#007AFF"# Slightly darker hover blue
COLOR_MAC_MUTED = "#8E8E93"       # Secondary text
COLOR_MAC_GREEN = "#34C759"       # Subtitle success badge
COLOR_MAC_RED = "#FF453A"         # Warning/Undo red
COLOR_MAC_RED_BG = "#2D1214"      # Soft red background for hover

# Shell Context Menu integration functions
def register_context_menu():
    try:
        import winreg
        import shutil
        
        persistent_icon = os.path.abspath(os.path.expanduser("~/.movie_organizer_icon.ico"))
        
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            exe_path = os.path.abspath(sys.executable)
            cmd = f'"{exe_path}" "%1"'
            bg_cmd = f'"{exe_path}" "%v"'
            
            # First priority: copy from sys._MEIPASS if available
            ico_source = None
            if hasattr(sys, '_MEIPASS'):
                ico_source = os.path.join(sys._MEIPASS, "app_icon.ico")
            
            if not ico_source or not os.path.exists(ico_source):
                exe_dir = os.path.dirname(exe_path)
                parent_dir = os.path.dirname(exe_dir)
                potential_ico1 = os.path.join(exe_dir, "app_icon.ico")
                potential_ico2 = os.path.join(parent_dir, "app_icon.ico")
                if os.path.exists(potential_ico1):
                    ico_source = potential_ico1
                elif os.path.exists(potential_ico2):
                    ico_source = potential_ico2
        else:
            # Running as script
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            cmd = f'"{python_exe}" "{script_path}" "%1"'
            bg_cmd = f'"{python_exe}" "{script_path}" "%v"'
            script_dir = os.path.dirname(script_path)
            ico_source = os.path.join(script_dir, "app_icon.ico")

        # Copy the icon to the persistent home directory location
        if ico_source and os.path.exists(ico_source):
            try:
                shutil.copy(ico_source, persistent_icon)
            except Exception:
                pass

        # Select the best icon path for registry
        if os.path.exists(persistent_icon):
            icon_path = persistent_icon
        elif ico_source and os.path.exists(ico_source):
            icon_path = ico_source
        else:
            icon_path = exe_path if getattr(sys, 'frozen', False) else None

        # Format icon path for registry (quotes if there are spaces)
        if icon_path:
            icon_path_reg = f'"{icon_path}"' if ' ' in icon_path else icon_path
        else:
            icon_path_reg = None

        # 1. Directory Shell context menu (right-clicking a folder)
        key_path = r"Software\Classes\directory\shell\MovieOrganizer"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "Organize Movies here")
            if icon_path_reg:
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_path_reg)
            
            with winreg.CreateKeyEx(key, "command", 0, winreg.KEY_SET_VALUE) as subkey:
                winreg.SetValue(subkey, "", winreg.REG_SZ, cmd)

        # 2. Directory Background Shell context menu (right-clicking inside folder background)
        bg_key_path = r"Software\Classes\Directory\Background\shell\MovieOrganizer"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, bg_key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "Organize Movies here")
            if icon_path_reg:
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_path_reg)
                
            with winreg.CreateKeyEx(key, "command", 0, winreg.KEY_SET_VALUE) as subkey:
                winreg.SetValue(subkey, "", winreg.REG_SZ, bg_cmd)
        return True, "Successfully registered context menu!"
    except Exception as e:
        return False, f"Failed to register: {e}"

def unregister_context_menu():
    try:
        import winreg
        def delete_key_recursive(root, path):
            try:
                key = winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS)
            except OSError:
                return # key doesn't exist
            
            subkeys = []
            try:
                i = 0
                while True:
                    subkeys.append(winreg.EnumKey(key, i))
                    i += 1
            except OSError:
                pass
            
            for subkey in subkeys:
                delete_key_recursive(root, f"{path}\\{subkey}")
                
            winreg.CloseKey(key)
            winreg.DeleteKey(root, path)

        delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\directory\shell\MovieOrganizer")
        delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\Background\shell\MovieOrganizer")
        return True, "Successfully unregistered context menu!"
    except Exception as e:
        return False, f"Failed to unregister: {e}"


class MovieOrganizerApp(ctk.CTk):
    def __init__(self, start_dir=None):
        super().__init__()
        
        # Configure window
        self.title(f"Movie Organizer v{__version__}")
        self.geometry("980x640")
        self.minsize(900, 520)
        
        # Set themes
        ctk.set_appearance_mode("dark")
        
        # Determine persistent icon and copy it to home directory
        self.persistent_ico = os.path.abspath(os.path.expanduser("~/.movie_organizer_icon.ico"))
        ico_source = None
        if getattr(sys, 'frozen', False):
            # Compiled exe
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
            ico_source = os.path.join(base_path, "app_icon.ico")
        else:
            # Running as script
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv else __file__))
            ico_source = os.path.join(script_dir, "app_icon.ico")
            
        if ico_source and os.path.exists(ico_source):
            try:
                import shutil
                if not os.path.exists(self.persistent_ico) or os.path.getmtime(ico_source) > os.path.getmtime(self.persistent_ico):
                    shutil.copy(ico_source, self.persistent_ico)
            except Exception:
                pass
                
        # Set Taskbar App ID for Windows to display custom icon on taskbar
        if sys.platform.startswith("win"):
            try:
                import ctypes
                myappid = f"PastiShow.MovieOrganizer.App.{__version__}"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        # Set Tkinter window icon
        if os.path.exists(self.persistent_ico):
            try:
                self.iconbitmap(self.persistent_ico)
            except Exception:
                pass
        elif ico_source and os.path.exists(ico_source):
            try:
                self.iconbitmap(ico_source)
            except Exception:
                pass
        
        # Set start directory
        if start_dir and os.path.isdir(start_dir):
            self.current_dir = os.path.abspath(start_dir)
        else:
            self.current_dir = os.path.abspath(os.getcwd())
            
        self.movies_data = []
        self.row_widgets = []
        self.scan_running = False
        
        # Load Config
        self.config = load_config()
        self.omdb_key = self.config.get("omdb_key", "")
        self.proxy_url = self.config.get("proxy_url", "")
        self.min_size_mb = int(self.config.get("min_size_mb", 50))
        self.scan_subfolders_val = bool(self.config.get("scan_subfolders", False))
        self.undo_timeout_seconds = int(self.config.get("undo_timeout_seconds", 15))
        self.enable_debug_log = bool(self.config.get("enable_debug_log", True))
        
        self.organizer = MovieOrganizer(self.current_dir, enable_debug_log=self.enable_debug_log)
        
        # Build UI
        self.create_widgets()
        
        # Initial scan on startup
        self.scan_folder()
        
        # Hook window close event
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # Configure overall grid: Column 0 (Sidebar), Column 1 (Main Content Area)
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==================== SIDEBAR ====================
        sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=COLOR_MAC_SIDEBAR, border_width=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)

        # Branding
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(25, 25))
        
        brand_logo = ctk.CTkLabel(
            brand_frame, 
            text="🎥", 
            font=ctk.CTkFont(size=36)
        )
        brand_logo.pack(side="left", padx=(0, 10))
        
        brand_text_frame = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_text_frame.pack(side="left", fill="y")
        
        brand_title = ctk.CTkLabel(
            brand_text_frame,
            text="PastiShow",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#FFFFFF"
        )
        brand_title.pack(anchor="w")
        
        brand_sub = ctk.CTkLabel(
            brand_text_frame,
            text="MOVIE ORGANIZER",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=COLOR_MAC_MUTED
        )
        brand_sub.pack(anchor="w", pady=(0, 2))

        # Target Folder Selection Group
        section_folder = ctk.CTkLabel(
            sidebar,
            text="TARGET DIRECTORY",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLOR_MAC_MUTED
        )
        section_folder.pack(anchor="w", padx=20, pady=(10, 5))

        self.path_label = ctk.CTkLabel(
            sidebar,
            text=self.shorten_path(self.current_dir),
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#FFFFFF",
            anchor="w",
            height=28,
            fg_color=COLOR_MAC_INPUT,
            corner_radius=6,
            padx=10
        )
        self.path_label.pack(fill="x", padx=20, pady=(0, 8))

        browse_btn = ctk.CTkButton(
            sidebar,
            text="Choose Folder...",
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLOR_MAC_CARD,
            hover_color="#3A3A3C",
            text_color="#FFFFFF",
            corner_radius=6,
            command=self.browse_folder
        )
        browse_btn.pack(fill="x", padx=20, pady=(0, 25))

        # Settings & Help Options
        section_options = ctk.CTkLabel(
            sidebar,
            text="OPTIONS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLOR_MAC_MUTED
        )
        section_options.pack(anchor="w", padx=20, pady=(10, 5))
        
        pref_btn = ctk.CTkButton(
            sidebar,
            text="⚙️  Preferences...",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLOR_MAC_CARD,
            hover_color="#3A3A3C",
            text_color="#FFFFFF",
            corner_radius=6,
            anchor="w",
            command=self.open_preferences
        )
        pref_btn.pack(fill="x", padx=20, pady=5)
        
        help_btn = ctk.CTkButton(
            sidebar,
            text="❓  Help Guide...",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLOR_MAC_CARD,
            hover_color="#3A3A3C",
            text_color="#FFFFFF",
            corner_radius=6,
            anchor="w",
            command=self.open_help
        )
        help_btn.pack(fill="x", padx=20, pady=5)

        # Primary Sidebar Action: Scan Directory
        self.scan_btn = ctk.CTkButton(
            sidebar,
            text="Scan Directory",
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            command=self.scan_folder
        )
        self.scan_btn.pack(fill="x", side="bottom", padx=20, pady=25)

        # Warning Card (hidden by default)
        self.warning_card = ctk.CTkFrame(
            sidebar, 
            fg_color="#3a1c1c", 
            border_width=1,
            border_color="#f87171",
            corner_radius=8
        )
        warning_title = ctk.CTkLabel(
            self.warning_card,
            text="⚠️ Connection Issue",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#f87171",
            anchor="w"
        )
        warning_title.pack(fill="x", padx=12, pady=(10, 4))
        
        warning_msg = ctk.CTkLabel(
            self.warning_card,
            text="No internet connection found or cannot connect to OMDb.\n\nNo rating, images, html file, and genre will be added.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#fca5a5",
            justify="left",
            wraplength=210,
            anchor="w"
        )
        warning_msg.pack(fill="x", padx=12, pady=(0, 10))

        self.retry_conn_btn = ctk.CTkButton(
            self.warning_card,
            text="Retry Connection",
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#f87171",
            hover_color="#ef4444",
            text_color="#1e1e1e",
            corner_radius=6,
            command=self.retry_connection
        )
        self.retry_conn_btn.pack(fill="x", padx=12, pady=(0, 12))


        # ==================== MAIN PANEL ====================
        main_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=COLOR_MAC_BG, border_width=0)
        main_panel.grid(row=0, column=1, sticky="nsew")
        main_panel.grid_columnconfigure(0, weight=1)
        main_panel.grid_rowconfigure(1, weight=1) # Scroll area stretches

        # Main Header
        header_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=25, pady=(25, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        
        main_title = ctk.CTkLabel(
            header_frame,
            text="Detected Movies",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#FFFFFF"
        )
        main_title.grid(row=0, column=0, sticky="w")

        self.stats_label = ctk.CTkLabel(
            header_frame,
            text="Scanning folder...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_MAC_MUTED
        )
        self.stats_label.grid(row=0, column=1, sticky="e")

        # Select All / Deselect All controls
        controls_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        controls_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        
        self.select_all_btn = ctk.CTkButton(
            controls_frame,
            text="☑ Select All",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            text_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_CARD,
            width=80,
            height=22,
            command=self.select_all_movies
        )
        self.select_all_btn.pack(side="left", padx=(0, 10))
        
        self.deselect_all_btn = ctk.CTkButton(
            controls_frame,
            text="☒ Deselect All",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            text_color=COLOR_MAC_MUTED,
            hover_color=COLOR_MAC_CARD,
            width=90,
            height=22,
            command=self.deselect_all_movies
        )
        self.deselect_all_btn.pack(side="left")

        # Scrollable list of movies
        self.scroll_frame = ctk.CTkScrollableFrame(
            main_panel,
            fg_color="transparent",
            scrollbar_button_color=COLOR_MAC_CARD_BORDER,
            scrollbar_button_hover_color=COLOR_MAC_MUTED
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=25, pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Welcome/Empty state label (inside scroll frame)
        self.empty_label = ctk.CTkLabel(
            self.scroll_frame,
            text="No movies detected. Adjust your size threshold or choose another folder.",
            font=ctk.CTkFont(family="Segoe UI", size=14, slant="italic"),
            text_color=COLOR_MAC_MUTED
        )
        self.empty_label.pack(expand=True, pady=100)

        # ==================== BOTTOM STATUS & ACTION BAR ====================
        bottom_frame = ctk.CTkFrame(main_panel, height=75, corner_radius=0, fg_color=COLOR_MAC_SIDEBAR, border_width=1, border_color=COLOR_MAC_CARD_BORDER)
        bottom_frame.grid(row=2, column=0, sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_propagate(False)

        # Status messages & Progress bar
        status_container = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        status_container.pack(side="left", fill="y", padx=20, pady=15)
        
        self.status_msg = ctk.CTkLabel(
            status_container, 
            text="Ready.", 
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#FFFFFF"
        )
        self.status_msg.pack(anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(
            status_container, 
            width=200, 
            progress_color=COLOR_MAC_ACCENT,
            fg_color=COLOR_MAC_CARD_BORDER,
            height=6
        )
        # Hidden initially
        self.progress_bar.set(0)

        # Action Buttons container (Right aligned)
        actions_container = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        actions_container.pack(side="right", fill="y", padx=20, pady=15)

        self.undo_btn = ctk.CTkButton(
            actions_container, 
            text="Undo Last Action", 
            width=120,
            height=34,
            fg_color="transparent",
            border_color=COLOR_MAC_RED,
            border_width=1,
            text_color=COLOR_MAC_RED,
            hover_color=COLOR_MAC_RED_BG,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8,
            command=self.undo_organization
        )
        self.undo_btn.pack(side="left", padx=(0, 10))
        self.check_undo_status()

        self.organize_btn = ctk.CTkButton(
            actions_container, 
            text="Organize Selected", 
            height=34,
            width=180,
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8,
            command=self.run_organization
        )
        self.organize_btn.pack(side="left")

    # ==================== CONTROLLER FUNCTIONS ====================

    def shorten_path(self, path):
        """Truncates path for UI presentation if too long."""
        if len(path) <= 30:
            return path
        return "..." + path[-27:]

    def browse_folder(self):
        selected = filedialog.askdirectory(initialdir=self.current_dir)
        if selected:
            self.current_dir = os.path.abspath(selected)
            self.path_label.configure(text=self.shorten_path(self.current_dir))
            self.organizer = MovieOrganizer(self.current_dir, enable_debug_log=self.enable_debug_log)
            self.scan_folder()

    def scan_folder(self):
        self.check_undo_status()
        self.organizer.connection_failed = False
        self.update_connection_warning()
        self.status_msg.configure(text="Scanning folder for movies...", text_color="#FFFFFF")
        self.progress_bar.pack(anchor="w", pady=(4, 0))
        self.progress_bar.configure(mode="indefinite")
        self.progress_bar.start()
        
        # Clear existing card rows
        for row in self.row_widgets:
            for w in row.values():
                if isinstance(w, (tk.Widget, ctk.CTkBaseClass)):
                    try:
                        w.destroy()
                    except Exception:
                        pass
        self.row_widgets = []
        self.movies_data = []
        self.empty_label.pack_forget()
        
        # Setup pause toggle state and scan button
        self.scan_running = True
        self.scan_paused = False
        self.scan_btn.configure(
            text="⏸ Pause Scan", 
            fg_color=COLOR_MAC_CARD, 
            hover_color="#3A3A3C",
            state="normal",
            command=self.toggle_scan_pause
        )
        self.organize_btn.configure(state="disabled")
        
        min_size = self.min_size_mb
        scan_sub = self.scan_subfolders_val
        omdb_key = self.omdb_key
        proxy_url = self.proxy_url
        
        def on_movie_scanned(movie):
            self.after(0, lambda: self.add_scanned_movie_to_ui(movie))
            
        def is_paused_fn():
            return getattr(self, "scan_paused", False)
            
        # Run scanning in thread
        def _bg_scan():
            try:
                movies, ignored_count = self.organizer.scan_movies(
                    min_size_mb=min_size, 
                    scan_subfolders=scan_sub, 
                    api_key=omdb_key,
                    proxy_url=proxy_url,
                    on_movie_scanned=on_movie_scanned,
                    is_paused_fn=is_paused_fn
                )
                self.after(0, lambda: self.finish_scan(movies, ignored_count, min_size))
            except Exception as e:
                self.after(0, lambda: self.scan_failed(str(e)))
                
        threading.Thread(target=_bg_scan, daemon=True).start()

    def toggle_scan_pause(self):
        self.scan_paused = not getattr(self, "scan_paused", False)
        if self.scan_paused:
            self.scan_btn.configure(
                text="▶ Resume Scan", 
                fg_color=COLOR_MAC_ACCENT, 
                hover_color=COLOR_MAC_ACCENT_HOVER
            )
            self.status_msg.configure(text="Scan paused.", text_color=COLOR_MAC_MUTED)
        else:
            self.scan_btn.configure(
                text="⏸ Pause Scan", 
                fg_color=COLOR_MAC_CARD, 
                hover_color="#3A3A3C"
            )
            self.status_msg.configure(text="Scanning folder for movies...", text_color="#FFFFFF")

    def add_scanned_movie_to_ui(self, movie):
        self.movies_data.append(movie)
        idx = len(self.movies_data) - 1
        self.render_movie_card(movie, idx)
        
        display_title = movie.get('parsed_title', '')
        self.status_msg.configure(text=f"Scanned: {display_title}", text_color="#FFFFFF")
        self.update_selection_stats()

    def render_movie_card(self, movie, idx):
        card = ctk.CTkFrame(
            self.scroll_frame, 
            fg_color=COLOR_MAC_CARD, 
            border_width=1, 
            border_color=COLOR_MAC_CARD_BORDER,
            height=56,
            corner_radius=10
        )
        card.pack(fill="x", pady=6, padx=4)
        card.pack_propagate(False)
        
        # Grid columns for card layout: Checkbox, Original Filename, Arrow icon, Editable Title, Editable Year, Badge area
        card.grid_columnconfigure(0, weight=0, minsize=40)  # Checkbox
        card.grid_columnconfigure(1, weight=3)              # Original Filename
        card.grid_columnconfigure(2, weight=0, minsize=30)  # Arrow pointer
        card.grid_columnconfigure(3, weight=3)              # Editable Title
        card.grid_columnconfigure(4, weight=0, minsize=80)  # Editable Year
        card.grid_columnconfigure(5, weight=0, minsize=240) # Badges
        
        # 1. Checkbox
        chk_var = tk.BooleanVar(value=True)
        cb = ctk.CTkCheckBox(
            card, 
            text="", 
            variable=chk_var, 
            width=18,
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            border_color=COLOR_MAC_CARD_BORDER,
            corner_radius=4,
            command=self.update_selection_stats
        )
        cb.grid(row=0, column=0, padx=(15, 0), pady=14, sticky="w")
        
        # 2. Original Filename (Truncated nicely for macOS aesthetic)
        orig_name = movie['original_filename']
        display_name = orig_name if len(orig_name) <= 28 else orig_name[:25] + "..."
        orig_lbl = ctk.CTkLabel(
            card, 
            text=display_name, 
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLOR_MAC_MUTED,
            anchor="w"
        )
        orig_lbl.grid(row=0, column=1, padx=(10, 5), pady=14, sticky="ew")
        
        # 3. Arrow Indicator
        arrow_lbl = ctk.CTkLabel(
            card, 
            text="→", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_MAC_MUTED
        )
        arrow_lbl.grid(row=0, column=2, pady=14)
        
        # 4. Editable Title Entry (Sleek text input)
        title_var = tk.StringVar(value=movie['parsed_title'])
        title_entry = ctk.CTkEntry(
            card, 
            textvariable=title_var, 
            height=28,
            fg_color=COLOR_MAC_INPUT,
            border_color=COLOR_MAC_CARD_BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FFFFFF",
            corner_radius=6
        )
        title_entry.grid(row=0, column=3, padx=10, pady=14, sticky="ew")
        
        # 5. Editable Year Entry
        year_var = tk.StringVar(value=movie['parsed_year'] or "")
        year_entry = ctk.CTkEntry(
            card, 
            textvariable=year_var, 
            height=28, 
            width=60, 
            fg_color=COLOR_MAC_INPUT,
            border_color=COLOR_MAC_CARD_BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#FFFFFF",
            justify="center",
            corner_radius=6
        )
        year_entry.grid(row=0, column=4, padx=5, pady=14)
        
        # 6. Details Badges
        badges_frame = ctk.CTkFrame(card, fg_color="transparent")
        badges_frame.grid(row=0, column=5, padx=15, pady=14, sticky="e")
        
        # TV Show badge (Orange)
        if movie.get('is_tv_show'):
            tv_badge = ctk.CTkLabel(
                badges_frame, 
                text="SERIES", 
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color="#FF9500", # macOS orange
                text_color="#FFFFFF",
                corner_radius=4,
                width=48,
                height=18
            )
            tv_badge.pack(side="left", padx=2)
        
        # IMDb Rating badge
        rating_val = movie.get('imdb_rating')
        if rating_val:
            rating_badge = ctk.CTkLabel(
                badges_frame, 
                text=f"⭐ {rating_val}", 
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color="#F5C518",
                text_color="#000000",
                corner_radius=4,
                width=48,
                height=18
            )
            rating_badge.pack(side="left", padx=2)
            
        # Genre badge (Purple)
        genre_val = movie.get('genre')
        if genre_val:
            first_genre = genre_val.split(',')[0].strip().upper()
            genre_badge = ctk.CTkLabel(
                badges_frame, 
                text=first_genre, 
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color="#5856D6", # macOS purple
                text_color="#FFFFFF",
                corner_radius=4,
                width=55,
                height=18
            )
            genre_badge.pack(side="left", padx=2)
        
        # Size badge
        size_val = movie['size_mb']
        size_txt = f"{size_val / 1024:.1f} GB" if size_val >= 1000 else f"{int(size_val)} MB"
        size_badge = ctk.CTkLabel(
            badges_frame, 
            text=size_txt, 
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color="#3A3A3C",
            text_color="#FFFFFF",
            corner_radius=4,
            width=55,
            height=18
        )
        size_badge.pack(side="left", padx=2)
        
        # Subtitle badge (Green)
        associated_files = movie.get('associated_files', [])
        subtitle_exts = {'.srt', '.ass', '.sub', '.idx', '.vtt', '.ssa'}
        sub_count = len([f for f in associated_files if os.path.splitext(f)[1].lower() in subtitle_exts])
        if sub_count > 0:
            sub_badge = ctk.CTkLabel(
                badges_frame, 
                text=f"SUB x{sub_count}" if sub_count > 1 else "SUB", 
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color=COLOR_MAC_GREEN,
                text_color="#FFFFFF",
                corner_radius=4,
                width=42,
                height=18
            )
            sub_badge.pack(side="left", padx=2)
            
        # Info badge (Blue)
        info_count = len(associated_files) - sub_count
        if info_count > 0:
            info_badge = ctk.CTkLabel(
                badges_frame, 
                text=f"INF x{info_count}" if info_count > 1 else "INF", 
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color=COLOR_MAC_ACCENT,
                text_color="#FFFFFF",
                corner_radius=4,
                width=42,
                height=18
            )
            info_badge.pack(side="left", padx=2)
        
        # Store references
        self.row_widgets.append({
            'frame': card,
            'chk_var': chk_var,
            'title_var': title_var,
            'year_var': year_var,
            'movie_idx': idx
        })

    def finish_scan(self, movies, ignored_count, min_size):
        self.scan_running = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        # Restore scan button
        self.scan_btn.configure(
            text="Scan Directory",
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            command=self.scan_folder,
            state="normal"
        )
        
        # Sync final list of movies in case there are any modifications
        self.movies_data = movies
        
        if not movies:
            self.empty_label.pack(expand=True, pady=100)
            self.stats_label.configure(text="No movies detected.")
            if ignored_count > 0:
                self.status_msg.configure(
                    text=f"Scan complete. 0 movies found (ignored {ignored_count} files < {min_size}MB).", 
                    text_color=COLOR_MAC_MUTED
                )
            else:
                self.status_msg.configure(text="Scan completed. No movie files found.", text_color=COLOR_MAC_MUTED)
            self.organize_btn.configure(state="disabled")
            self.check_undo_status()
            return
            
        self.empty_label.pack_forget()
        self.update_selection_stats()
        
        status_txt = f"Scan complete. Found {len(movies)} movie(s)."
        if ignored_count > 0:
            status_txt += f" (ignored {ignored_count} files < {min_size}MB)."
            
        self.status_msg.configure(text=status_txt, text_color=COLOR_MAC_GREEN)
        self.organize_btn.configure(state="normal")
        self.check_undo_status()
        self.update_connection_warning()

    def scan_failed(self, err_msg):
        self.scan_running = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        # Restore scan button
        self.scan_btn.configure(
            text="Scan Directory",
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            command=self.scan_folder,
            state="normal"
        )
        self.stats_label.configure(text="Scan failed.")
        self.status_msg.configure(text=f"Error scanning: {err_msg}", text_color=COLOR_MAC_RED)
        self.organize_btn.configure(state="disabled")

    def update_selection_stats(self):
        total = len(self.movies_data)
        selected = sum(1 for row in self.row_widgets if row['chk_var'].get())
        self.stats_label.configure(text=f"Total: {total} | Selected: {selected}")
        
        # ACTIVATE OR DISABLE BUTTON ACCORDING TO SELECTION AND SCAN STATE
        if getattr(self, "scan_running", False):
            self.organize_btn.configure(state="disabled")
        elif selected == 0:
            self.organize_btn.configure(state="disabled")
        else:
            self.organize_btn.configure(state="normal")

    def select_all_movies(self):
        for row in self.row_widgets:
            row['chk_var'].set(True)
        self.update_selection_stats()

    def deselect_all_movies(self):
        for row in self.row_widgets:
            row['chk_var'].set(False)
        self.update_selection_stats()

    def run_organization(self):
        selected_items = []
        for row in self.row_widgets:
            if row['chk_var'].get():
                idx = row['movie_idx']
                # Create a modified copy of the movie object with edited entries
                movie = self.movies_data[idx].copy()
                movie['parsed_title'] = row['title_var'].get().strip()
                movie['parsed_year'] = row['year_var'].get().strip()
                selected_items.append(movie)
                
        if not selected_items:
            return
            
        self.status_msg.configure(text="Organizing selected movies...", text_color="#FFFFFF")
        self.progress_bar.pack(anchor="w", pady=(4, 0))
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.organize_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        
        omdb_key = self.omdb_key
        proxy_url = self.proxy_url
        
        def _bg_organize():
            try:
                count = self.organizer.organize_movies(
                    selected_items, 
                    api_key=omdb_key,
                    proxy_url=proxy_url
                )
                self.after(0, lambda: self.finish_organization(count))
            except Exception as e:
                self.after(0, lambda: self.organize_failed(str(e)))
                
        threading.Thread(target=_bg_organize, daemon=True).start()

    def finish_organization(self, count):
        self.progress_bar.pack_forget()
        self.scan_btn.configure(state="normal")
        self.status_msg.configure(text=f"Successfully organized {count} movie(s)!", text_color=COLOR_MAC_GREEN)
        
        # Clear the movie cards from UI since they are organized
        for row in self.row_widgets:
            for w in row.values():
                if isinstance(w, (tk.Widget, ctk.CTkBaseClass)):
                    try:
                        w.destroy()
                    except Exception:
                        pass
        self.row_widgets = []
        self.movies_data = []
        self.update_selection_stats()
        self.empty_label.pack(expand=True, pady=100)
        
        # Check and update undo status immediately (shows the undo button)
        self.check_undo_status()
        
        # Start a user-configured timer to clean up undo history
        self.after(self.undo_timeout_seconds * 1000, self.cleanup_undo_history)

    def organize_failed(self, err_msg):
        self.progress_bar.pack_forget()
        self.scan_btn.configure(state="normal")
        self.status_msg.configure(text=f"Error organizing: {err_msg}", text_color=COLOR_MAC_RED)
        self.organize_btn.configure(state="normal")

    def check_undo_status(self):
        history_file = os.path.join(self.current_dir, '.organizer_history.json')
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_list = json.load(f)
                    if history_list and isinstance(history_list, list):
                        last_action = history_list[-1]
                        timestamp_str = last_action.get('timestamp')
                        if timestamp_str:
                            dt = datetime.fromisoformat(timestamp_str)
                            diff = (datetime.now() - dt).total_seconds()
                            if diff > self.undo_timeout_seconds:
                                # Over limit! Delete it.
                                try:
                                    os.remove(history_file)
                                except Exception:
                                    pass
                                self.undo_btn.pack_forget()
                                return
            except Exception:
                pass
            self.undo_btn.pack(side="left", padx=(0, 10), before=self.organize_btn)
            self.undo_btn.configure(state="normal", border_color=COLOR_MAC_RED, text_color=COLOR_MAC_RED)
        else:
            self.undo_btn.pack_forget()

    def update_connection_warning(self):
        if getattr(self.organizer, "connection_failed", False):
            self.warning_card.pack(fill="x", side="bottom", padx=20, pady=(0, 15))
        else:
            self.warning_card.pack_forget()

    def retry_connection(self):
        self.retry_conn_btn.configure(state="disabled", text="Checking...")
        self.status_msg.configure(text="Checking connection to OMDb...", text_color="#FFFFFF")
        
        omdb_key = self.omdb_key
        proxy_url = self.proxy_url
        
        def _bg_check():
            try:
                success = self.organizer.check_connection(api_key=omdb_key, proxy_url=proxy_url)
                if success:
                    self.organizer.connection_failed = False
                    self.after(0, self.connection_restored)
                else:
                    self.after(0, self.connection_retry_failed)
            except Exception:
                self.after(0, self.connection_retry_failed)
                
        threading.Thread(target=_bg_check, daemon=True).start()

    def connection_restored(self):
        self.retry_conn_btn.configure(state="normal", text="Retry Connection")
        self.update_connection_warning()
        self.status_msg.configure(text="Connection to OMDb restored successfully!", text_color=COLOR_MAC_GREEN)

    def connection_retry_failed(self):
        self.retry_conn_btn.configure(state="normal", text="Retry Connection")
        self.status_msg.configure(text="Connection check failed. OMDb is still unreachable.", text_color=COLOR_MAC_RED)

    def on_close(self):
        # 1. Clean up history log
        history_file = os.path.join(self.current_dir, '.organizer_history.json')
        if os.path.exists(history_file):
            try:
                os.remove(history_file)
            except Exception:
                pass
                
        self.destroy()

    def undo_organization(self):
        self.status_msg.configure(text="Reversing last action...", text_color="#FFFFFF")
        self.progress_bar.pack(anchor="w", pady=(4, 0))
        self.progress_bar.configure(mode="indefinite")
        self.progress_bar.start()
        self.undo_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        
        def _bg_undo():
            try:
                result = self.organizer.undo_last_action()
                self.after(0, lambda: self.finish_undo(result))
            except Exception as e:
                self.after(0, lambda: self.undo_failed(str(e)))
                
        threading.Thread(target=_bg_undo, daemon=True).start()

    def finish_undo(self, result):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scan_btn.configure(state="normal")
        
        if result is None:
            self.status_msg.configure(text="No organization history found.", text_color=COLOR_MAC_RED)
        else:
            success, failed = result
            if failed > 0:
                self.status_msg.configure(text=f"Restored {success} files. {failed} failed.", text_color=COLOR_MAC_MUTED)
            else:
                self.status_msg.configure(text=f"Restored {success} files back to their original places!", text_color=COLOR_MAC_GREEN)
                
        self.scan_folder()

    def undo_failed(self, err_msg):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scan_btn.configure(state="normal")
        self.status_msg.configure(text=f"Error reversing changes: {err_msg}", text_color=COLOR_MAC_RED)
        self.check_undo_status()

    # Registry context menu management
    def add_registry(self):
        success, msg = register_context_menu()
        if success:
            self.status_msg.configure(text=msg, text_color=COLOR_MAC_GREEN)
        else:
            self.status_msg.configure(text=msg, text_color=COLOR_MAC_RED)

    def remove_registry(self):
        success, msg = unregister_context_menu()
        if success:
            self.status_msg.configure(text=msg, text_color=COLOR_MAC_GREEN)
        else:
            self.status_msg.configure(text=msg, text_color=COLOR_MAC_RED)

    def cleanup_undo_history(self):
        history_file = os.path.join(self.current_dir, '.organizer_history.json')
        if os.path.exists(history_file):
            try:
                os.remove(history_file)
            except OSError:
                pass
        self.check_undo_status()

    def save_settings(self):
        self.config["omdb_key"] = self.omdb_key
        self.config["proxy_url"] = self.proxy_url
        self.config["min_size_mb"] = self.min_size_mb
        self.config["scan_subfolders"] = self.scan_subfolders_val
        self.config["undo_timeout_seconds"] = self.undo_timeout_seconds
        self.config["enable_debug_log"] = self.enable_debug_log
        save_config(self.config)

    def open_preferences(self):
        pref_win = PreferencesWindow(self)
        pref_win.focus()

    def open_help(self):
        help_win = HelpWindow(self)
        help_win.focus()


class PreferencesWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Preferences")
        self.geometry("460x430")
        self.resizable(False, False)
        
        # Make modal-like
        self.transient(parent)
        self.grab_set()
        
        # Configure layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Tabview for macOS style tabs
        tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=COLOR_MAC_ACCENT,
            segmented_button_selected_hover_color=COLOR_MAC_ACCENT_HOVER,
            segmented_button_unselected_color=COLOR_MAC_CARD,
            text_color="#FFFFFF"
        )
        tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        tab_general = tabview.add("General")
        tab_api = tabview.add("API & Connection")
        tab_system = tabview.add("System Menu")
        
        # --- GENERAL TAB ---
        tab_general.grid_columnconfigure(0, weight=1)
        
        lbl_gen = ctk.CTkLabel(tab_general, text="General Scan & Match Options", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_gen.pack(anchor="w", padx=10, pady=(10, 15))
        
        size_frame = ctk.CTkFrame(tab_general, fg_color="transparent")
        size_frame.pack(fill="x", padx=10, pady=10)
        
        size_lbl = ctk.CTkLabel(size_frame, text="Minimum File Size:", font=ctk.CTkFont(size=12))
        size_lbl.pack(side="left")
        
        self.size_entry = ctk.CTkEntry(size_frame, width=80, height=26, justify="center")
        self.size_entry.insert(0, str(self.parent.min_size_mb))
        self.size_entry.pack(side="left", padx=(15, 5))
        
        size_unit = ctk.CTkLabel(size_frame, text="MB", text_color=COLOR_MAC_MUTED)
        size_unit.pack(side="left")
        
        self.subfolder_var = tk.BooleanVar(value=self.parent.scan_subfolders_val)
        subfolder_cb = ctk.CTkCheckBox(
            tab_general,
            text="Scan subfolders recursively",
            variable=self.subfolder_var,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_MAC_ACCENT,
            border_color=COLOR_MAC_CARD_BORDER,
            corner_radius=4
        )
        subfolder_cb.pack(anchor="w", padx=10, pady=15)
        
        # Undo Timeout frame
        undo_frame = ctk.CTkFrame(tab_general, fg_color="transparent")
        undo_frame.pack(fill="x", padx=10, pady=10)
        
        undo_lbl = ctk.CTkLabel(undo_frame, text="Undo Timeout:", font=ctk.CTkFont(size=12))
        undo_lbl.pack(side="left")
        
        self.undo_entry = ctk.CTkEntry(undo_frame, width=80, height=26, justify="center")
        self.undo_entry.insert(0, str(self.parent.undo_timeout_seconds))
        self.undo_entry.pack(side="left", padx=(15, 5))
        
        undo_unit = ctk.CTkLabel(undo_frame, text="seconds", text_color=COLOR_MAC_MUTED)
        undo_unit.pack(side="left")
        
        # Debug Log check
        self.debug_log_var = tk.BooleanVar(value=self.parent.enable_debug_log)
        debug_log_cb = ctk.CTkCheckBox(
            tab_general,
            text="Enable debug logging (.organizer_debug.log)",
            variable=self.debug_log_var,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_MAC_ACCENT,
            border_color=COLOR_MAC_CARD_BORDER,
            corner_radius=4
        )
        debug_log_cb.pack(anchor="w", padx=10, pady=10)
        
        # --- API & CONNECTION TAB ---
        tab_api.grid_columnconfigure(0, weight=1)
        
        lbl_api = ctk.CTkLabel(tab_api, text="OMDb API & Proxy Configuration", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_api.pack(anchor="w", padx=10, pady=(10, 15))
        
        key_frame = ctk.CTkFrame(tab_api, fg_color="transparent")
        key_frame.pack(fill="x", padx=10, pady=8)
        key_lbl = ctk.CTkLabel(key_frame, text="OMDb API Key:", width=100, anchor="w")
        key_lbl.pack(side="left")
        self.key_entry = ctk.CTkEntry(key_frame, width=220, height=26)
        self.key_entry.insert(0, self.parent.omdb_key)
        self.key_entry.pack(side="left")
        
        proxy_frame = ctk.CTkFrame(tab_api, fg_color="transparent")
        proxy_frame.pack(fill="x", padx=10, pady=8)
        proxy_lbl = ctk.CTkLabel(proxy_frame, text="Proxy (optional):", width=100, anchor="w")
        proxy_lbl.pack(side="left")
        self.proxy_entry = ctk.CTkEntry(proxy_frame, width=220, height=26, placeholder_text="e.g. http://127.0.0.1:7890 or none")
        self.proxy_entry.insert(0, self.parent.proxy_url)
        self.proxy_entry.pack(side="left")
        
        api_note = ctk.CTkLabel(
            tab_api,
            text="Note: Enter 'none' to explicitly bypass system proxy overrides.",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=COLOR_MAC_MUTED
        )
        api_note.pack(anchor="w", padx=115, pady=(2, 10))
        
        # --- SYSTEM TAB ---
        tab_system.grid_columnconfigure(0, weight=1)
        
        lbl_sys = ctk.CTkLabel(tab_system, text="Explorer Context Menu Integration", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_sys.pack(anchor="w", padx=10, pady=(10, 15))
        
        lbl_sys_desc = ctk.CTkLabel(
            tab_system,
            text="Integrate Movie Organizer directly into Windows Explorer.\nRight-click any folder to organize movies in that directory.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_MAC_MUTED,
            justify="left"
        )
        lbl_sys_desc.pack(anchor="w", padx=10, pady=(0, 15))
        
        reg_add = ctk.CTkButton(
            tab_system,
            text="Register Context Menu Icon & Integration",
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            font=ctk.CTkFont(weight="bold"),
            command=self.parent.add_registry
        )
        reg_add.pack(fill="x", padx=10, pady=8)
        
        reg_remove = ctk.CTkButton(
            tab_system,
            text="Unregister Context Menu Integration",
            fg_color="transparent",
            text_color=COLOR_MAC_RED,
            border_color=COLOR_MAC_RED,
            border_width=1,
            hover_color=COLOR_MAC_RED_BG,
            command=self.parent.remove_registry
        )
        reg_remove.pack(fill="x", padx=10, pady=8)
        
        # --- BOTTOM ACTION BAR ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="e")
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=80,
            fg_color="transparent",
            border_color=COLOR_MAC_CARD_BORDER,
            border_width=1,
            text_color="#FFFFFF",
            hover_color=COLOR_MAC_CARD,
            command=self.destroy
        )
        cancel_btn.pack(side="left", padx=(0, 10))
        
        save_btn = ctk.CTkButton(
            btn_frame,
            text="Apply Settings",
            width=110,
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            font=ctk.CTkFont(weight="bold"),
            command=self.save_and_close
        )
        save_btn.pack(side="left")
        
        # Enable clipboard copy-paste shortcuts on entry fields
        self.enable_clipboard_shortcuts(self.size_entry)
        self.enable_clipboard_shortcuts(self.undo_entry)
        self.enable_clipboard_shortcuts(self.key_entry)
        self.enable_clipboard_shortcuts(self.proxy_entry)
        
    def enable_clipboard_shortcuts(self, entry_widget):
        try:
            entry = entry_widget._entry
        except AttributeError:
            entry = entry_widget
            
        def select_all(event):
            entry.select_range(0, tk.END)
            entry.icursor(tk.END)
            return "break"
            
        def copy(event):
            try:
                selected_text = entry.selection_get()
                self.clipboard_clear()
                self.clipboard_append(selected_text)
            except tk.TclError:
                pass
            return "break"
            
        def cut(event):
            try:
                selected_text = entry.selection_get()
                self.clipboard_clear()
                self.clipboard_append(selected_text)
                entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass
            return "break"
            
        def paste(event):
            try:
                text = self.clipboard_get()
                try:
                    entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except tk.TclError:
                    pass
                entry.insert(tk.INSERT, text)
            except tk.TclError:
                pass
            return "break"
            
        entry.bind("<Control-a>", select_all)
        entry.bind("<Control-c>", copy)
        entry.bind("<Control-v>", paste)
        entry.bind("<Control-x>", cut)
        entry.bind("<Control-A>", select_all)
        entry.bind("<Control-C>", copy)
        entry.bind("<Control-V>", paste)
        entry.bind("<Control-X>", cut)
        
    def save_and_close(self):
        try:
            self.parent.min_size_mb = int(self.size_entry.get())
        except ValueError:
            self.parent.min_size_mb = 50
            
        try:
            self.parent.undo_timeout_seconds = int(self.undo_entry.get())
        except ValueError:
            self.parent.undo_timeout_seconds = 15
            
        self.parent.scan_subfolders_val = self.subfolder_var.get()
        self.parent.enable_debug_log = self.debug_log_var.get()
        self.parent.omdb_key = self.key_entry.get().strip()
        self.parent.proxy_url = self.proxy_entry.get().strip()
        
        if hasattr(self.parent, 'organizer'):
            self.parent.organizer.enable_debug_log = self.parent.enable_debug_log
            
        self.parent.save_settings()
        self.destroy()


class HelpWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Help Guide & Documentation")
        self.geometry("560x460")
        self.resizable(False, False)
        
        # Make modal-like
        self.transient(parent)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Tabview for Help sections
        tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=COLOR_MAC_ACCENT,
            segmented_button_unselected_color=COLOR_MAC_CARD,
            text_color="#FFFFFF"
        )
        tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        tab_usage = tabview.add("How to Use")
        tab_api = tabview.add("OMDb API Key")
        tab_proxy = tabview.add("Proxy Config")
        tab_tv = tabview.add("TV Shows & Subfolders")
        
        # --- HOW TO USE TAB ---
        txt_usage = (
            "🎥  Welcome to PastiShow Movie Organizer!\n\n"
            "This utility automates cleaning and sorting loose film files.\n\n"
            "Steps to Use:\n"
            "1. Target Directory: Choose the folder containing loose movies via the 'Choose Folder' button.\n"
            "2. Scan: Click 'Scan Directory'. The app lists matches and groups matching subtitles/info files.\n"
            "3. Inline Editing: If needed, double-click/edit the Title or Year textboxes directly in the list.\n"
            "4. Selection: Check or uncheck movies you wish to organize.\n"
            "5. Run: Click 'Organize Selected'. Directories are made for each movie with rating and genre tags.\n"
            "6. Undo: Made a mistake? A red 'Undo Last Action' button is active for 15 seconds to rollback moves."
        )
        self.create_text_box(tab_usage, txt_usage)
        
        # --- OMDB API KEY TAB ---
        txt_api = (
            "🔑  How to Get a Free OMDb API Key:\n\n"
            "To automatically fetch ratings, posters, and genres from IMDb, the app uses the OMDb API. You can get a free key in seconds:\n\n"
            "1. Visit the OMDb API Key registration page:\n"
            "   https://www.omdbapi.com/apikey.aspx\n\n"
            "2. Choose the 'FREE' tier (1,000 daily requests limit, which is plenty for personal usage).\n\n"
            "3. Submit your email. You will receive a verification link.\n\n"
            "4. Click the link in the email to activate the key.\n\n"
            "5. Open Preferences in this app, paste the 8-character key, and click 'Apply Settings'. App will fetch details automatically on scan."
        )
        self.create_text_box(tab_api, txt_api)
        
        # --- PROXY CONFIG TAB ---
        txt_proxy = (
            "🌐  Proxy Configuration:\n\n"
            "If your network is behind a firewall, has restricted internet access, or blocks requests to OMDb, you can configure a custom proxy:\n\n"
            "Format Options:\n"
            "• HTTP Proxy:   http://127.0.0.1:7890\n"
            "• SOCKS Proxy:  socks5://127.0.0.1:10808\n\n"
            "Bypassing System Proxies:\n"
            "If your Windows system-wide internet settings contain broken proxy configurations (which is common when using local VPNs/proxies that are turned off), connection attempts will fail with 'connection refused' error.\n\n"
            "To fix this, type 'none' into the Proxy settings field to force requests to bypass system overrides and go direct."
        )
        self.create_text_box(tab_proxy, txt_proxy)
        
        # --- TV SHOWS & SUBFOLDERS TAB ---
        txt_tv = (
            "📺  TV Show Detection:\n"
            "The app automatically counts files sharing a parsed title. If a title is detected more than once (e.g. Friends S01E01, Friends S01E02), it is classified as a TV Series. The OMDb search parameter switches to 'type=series' to fetch the correct series metadata and poster.\n\n"
            "📁  In-Place Subfolder Renaming:\n"
            "When 'Scan subfolders recursively' is active:\n"
            "• If a movie file is found at the target root, a new folder is created and files are moved in.\n"
            "• If a movie file is already nested inside a subdirectory (e.g. 'Inception/Inception.mp4'), the app will rename the containing folder in-place ('Inception' -> 'Inception (2010) [8.8] [Sci-Fi]'), maintaining any subdirectory structure you already established.\n"
            "• Restorations (Undo) will correctly rename directories back to their old names."
        )
        self.create_text_box(tab_tv, txt_tv)
        
        # --- CLOSE BUTTON ---
        ok_btn = ctk.CTkButton(
            self,
            text="Close Guide",
            width=100,
            fg_color=COLOR_MAC_ACCENT,
            hover_color=COLOR_MAC_ACCENT_HOVER,
            font=ctk.CTkFont(weight="bold"),
            command=self.destroy
        )
        ok_btn.pack(side="bottom", pady=15)
        
    def create_text_box(self, parent, text):
        box = ctk.CTkTextbox(
            parent,
            fg_color="transparent",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#FFFFFF",
            wrap="word"
        )
        box.pack(fill="both", expand=True, padx=5, pady=5)
        box.insert("0.0", text)
        box.configure(state="disabled")


if __name__ == "__main__":
    start_path = None
    if len(sys.argv) > 1:
        potential_path = sys.argv[1]
        if os.path.isdir(potential_path):
            start_path = potential_path
            
    app = MovieOrganizerApp(start_path)
    app.mainloop()
