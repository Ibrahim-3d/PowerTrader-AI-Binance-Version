"""
PowerTrader AI+ Theme Manager
Centralizes theme configuration and dark mode styling
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any


# Dark Theme Color Constants
DARK_BG = "#1e1e1e"          # Main background
DARK_BG2 = "#2d2d30"         # Secondary background
DARK_FG = "#eeeef2"          # Primary text
DARK_PANEL = "#3c3c3c"       # Panel backgrounds
DARK_PANEL2 = "#4c4c4c"      # Lighter panels
DARK_BORDER = "#5a5a5a"      # Borders
DARK_ACCENT = "#02FF58"      # Primary accent (green)
DARK_ACCENT2 = "#00E5FF"     # Secondary accent (cyan)
DARK_MUTED = "#9d9d9d"       # Muted text
DARK_SELECT_BG = "#094771"   # Selection background
DARK_SELECT_FG = "#ffffff"   # Selection foreground


class ThemeConfig:
    """Configuration class for theme colors and styles."""
    
    def __init__(self):
        # Color scheme
        self.colors = {
            'bg': DARK_BG,
            'bg2': DARK_BG2,
            'fg': DARK_FG,
            'panel': DARK_PANEL,
            'panel2': DARK_PANEL2,
            'border': DARK_BORDER,
            'accent': DARK_ACCENT,
            'accent2': DARK_ACCENT2,
            'muted': DARK_MUTED,
            'select_bg': DARK_SELECT_BG,
            'select_fg': DARK_SELECT_FG
        }
        
        # Widget-specific configurations
        self.widget_configs = {
            'button': {
                'padding': (3, 2),
                'focusthickness': 1
            },
            'notebook_tab': {
                'padding': (10, 6)
            },
            'chart_tab': {
                'padding': (10, 6)
            }
        }
    
    def get_color(self, color_key: str) -> str:
        """Get color by key."""
        return self.colors.get(color_key, DARK_FG)
    
    def get_widget_config(self, widget_type: str) -> Dict[str, Any]:
        """Get widget configuration."""
        return self.widget_configs.get(widget_type, {})


class ThemeManager:
    """
    Manages application theming and provides methods to apply themes to widgets.
    """
    
    def __init__(self, root: tk.Tk, theme_config: Optional[ThemeConfig] = None):
        self.root = root
        self.config = theme_config or ThemeConfig()
        self.style = None
        
    def apply_dark_theme(self) -> None:
        """Apply the complete dark theme to the application."""
        self._configure_root_window()
        self._set_widget_defaults()
        self._configure_ttk_styles()
        
    def _configure_root_window(self) -> None:
        """Configure the root window background."""
        try:
            self.root.configure(bg=self.config.get_color('bg'))
        except Exception:
            pass
    
    def _set_widget_defaults(self) -> None:
        """Set defaults for classic Tk widgets."""
        colors = self.config.colors
        
        # Text widgets
        try:
            self.root.option_add("*Text.background", colors['panel'])
            self.root.option_add("*Text.foreground", colors['fg'])
            self.root.option_add("*Text.insertBackground", colors['fg'])
            self.root.option_add("*Text.selectBackground", colors['select_bg'])
            self.root.option_add("*Text.selectForeground", colors['select_fg'])
        except Exception:
            pass
        
        # Listbox widgets
        try:
            self.root.option_add("*Listbox.background", colors['panel'])
            self.root.option_add("*Listbox.foreground", colors['fg'])
            self.root.option_add("*Listbox.selectBackground", colors['select_bg'])
            self.root.option_add("*Listbox.selectForeground", colors['select_fg'])
        except Exception:
            pass
        
        # Menu widgets
        try:
            self.root.option_add("*Menu.background", colors['bg2'])
            self.root.option_add("*Menu.foreground", colors['fg'])
            self.root.option_add("*Menu.activeBackground", colors['select_bg'])
            self.root.option_add("*Menu.activeForeground", colors['select_fg'])
        except Exception:
            pass
    
    def _configure_ttk_styles(self) -> None:
        """Configure ttk widget styles."""
        self.style = ttk.Style(self.root)
        
        # Use a recolorable theme
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        
        self._configure_base_styles()
        self._configure_container_styles()
        self._configure_input_styles()
        self._configure_button_styles()
        self._configure_notebook_styles()
        self._configure_treeview_styles()
        self._configure_scrollbar_styles()
    
    def _configure_base_styles(self) -> None:
        """Configure base widget styles."""
        colors = self.config.colors
        
        # Base defaults
        try:
            self.style.configure(".", background=colors['bg'], foreground=colors['fg'])
        except Exception:
            pass
    
    def _configure_container_styles(self) -> None:
        """Configure container widget styles."""
        colors = self.config.colors
        
        # Basic containers
        for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
            try:
                self.style.configure(name, background=colors['bg'], foreground=colors['fg'])
            except Exception:
                pass
        
        # Label frames
        try:
            self.style.configure(
                "TLabelframe",
                background=colors['bg'],
                foreground=colors['fg'],
                bordercolor="white",
            )
            self.style.configure(
                "TLabelframe.Label", 
                background=colors['bg'], 
                foreground=colors['accent']
            )
        except Exception:
            pass
        
        # Separators
        try:
            self.style.configure("TSeparator", background=colors['border'])
        except Exception:
            pass
        
        # Panedwindows
        try:
            self.style.configure("TPanedwindow", background=colors['bg'])
        except Exception:
            pass
    
    def _configure_input_styles(self) -> None:
        """Configure input widget styles."""
        colors = self.config.colors
        
        # Entry widgets
        try:
            self.style.configure(
                "TEntry",
                fieldbackground=colors['panel'],
                foreground=colors['fg'],
                bordercolor=colors['border'],
                insertcolor=colors['fg'],
            )
        except Exception:
            pass
        
        # Combobox widgets
        try:
            self.style.configure(
                "TCombobox",
                fieldbackground=colors['panel'],
                background=colors['panel'],
                foreground=colors['fg'],
                bordercolor=colors['border'],
                arrowcolor=colors['accent'],
            )
            self.style.map(
                "TCombobox",
                fieldbackground=[
                    ("readonly", colors['panel']),
                    ("focus", colors['panel2']),
                ],
                foreground=[("readonly", colors['fg'])],
                background=[("readonly", colors['panel'])],
            )
        except Exception:
            pass
    
    def _configure_button_styles(self) -> None:
        """Configure button widget styles."""
        colors = self.config.colors
        button_config = self.config.get_widget_config('button')
        
        # Regular buttons
        try:
            self.style.configure(
                "TButton",
                background=colors['bg2'],
                foreground=colors['fg'],
                bordercolor=colors['border'],
                focusthickness=button_config.get('focusthickness', 1),
                focuscolor=colors['accent'],
                padding=button_config.get('padding', (3, 2)),
            )
            self.style.map(
                "TButton",
                background=[
                    ("active", colors['panel2']),
                    ("pressed", colors['panel']),
                    ("disabled", colors['bg2']),
                ],
                foreground=[
                    ("active", colors['accent']),
                    ("disabled", colors['muted']),
                ],
                bordercolor=[
                    ("active", colors['accent2']),
                    ("focus", colors['accent']),
                ],
            )
        except Exception:
            pass
    
    def _configure_notebook_styles(self) -> None:
        """Configure notebook widget styles."""
        colors = self.config.colors
        tab_config = self.config.get_widget_config('notebook_tab')
        chart_tab_config = self.config.get_widget_config('chart_tab')
        
        # Notebook base
        try:
            self.style.configure("TNotebook", background=colors['bg'], bordercolor=colors['border'])
            self.style.configure(
                "TNotebook.Tab",
                background=colors['bg2'],
                foreground=colors['fg'],
                padding=tab_config.get('padding', (10, 6)),
            )
            self.style.map(
                "TNotebook.Tab",
                background=[
                    ("selected", colors['panel']),
                    ("active", colors['panel2']),
                ],
                foreground=[
                    ("selected", colors['accent']),
                    ("active", colors['accent2']),
                ],
            )
        except Exception:
            pass
        
        # Hidden tabs notebook (for custom tab rendering)
        try:
            self.style.configure("HiddenTabs.TNotebook", tabmargins=0)
            self.style.layout(
                "HiddenTabs.TNotebook",
                [
                    (
                        "Notebook.padding",
                        {
                            "sticky": "nswe",
                            "children": [
                                ("Notebook.client", {"sticky": "nswe"}),
                            ],
                        },
                    )
                ],
            )
        except Exception:
            pass
        
        # Chart tab buttons
        try:
            self.style.configure(
                "ChartTab.TButton",
                background=colors['bg2'],
                foreground=colors['fg'],
                bordercolor=colors['border'],
                padding=chart_tab_config.get('padding', (10, 6)),
            )
            self.style.map(
                "ChartTab.TButton",
                background=[("active", colors['panel2']), ("pressed", colors['panel'])],
                foreground=[("active", colors['accent2'])],
                bordercolor=[("active", colors['accent2']), ("focus", colors['accent'])],
            )
        except Exception:
            pass
        
        # Selected chart tab buttons
        try:
            self.style.configure(
                "ChartTabSelected.TButton",
                background=colors['panel'],
                foreground=colors['accent'],
                bordercolor=colors['accent2'],
                padding=chart_tab_config.get('padding', (10, 6)),
            )
        except Exception:
            pass
    
    def _configure_treeview_styles(self) -> None:
        """Configure treeview widget styles."""
        colors = self.config.colors
        
        try:
            self.style.configure(
                "Treeview",
                background=colors['panel'],
                fieldbackground=colors['panel'],
                foreground=colors['fg'],
                bordercolor=colors['border'],
                lightcolor=colors['border'],
                darkcolor=colors['border'],
            )
            self.style.map(
                "Treeview",
                background=[("selected", colors['select_bg'])],
                foreground=[("selected", colors['select_fg'])],
            )
            
            self.style.configure(
                "Treeview.Heading",
                background=colors['bg2'],
                foreground=colors['accent'],
                relief="flat",
            )
            self.style.map(
                "Treeview.Heading",
                background=[("active", colors['panel2'])],
                foreground=[("active", colors['accent2'])],
            )
        except Exception:
            pass
    
    def _configure_scrollbar_styles(self) -> None:
        """Configure scrollbar widget styles."""
        colors = self.config.colors
        
        for sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            try:
                self.style.configure(
                    sb,
                    background=colors['bg2'],
                    troughcolor=colors['bg'],
                    bordercolor=colors['border'],
                    arrowcolor=colors['accent'],
                )
            except Exception:
                pass
    
    def create_themed_menu(self, parent: tk.Widget, tearoff: int = 0) -> tk.Menu:
        """Create a menu with dark theme applied."""
        colors = self.config.colors
        return tk.Menu(
            parent,
            tearoff=tearoff,
            bg=colors['bg2'],
            fg=colors['fg'],
            activebackground=colors['select_bg'],
            activeforeground=colors['select_fg'],
        )
    
    def create_themed_text(self, parent: tk.Widget, **kwargs) -> tk.Text:
        """Create a text widget with dark theme applied."""
        colors = self.config.colors
        defaults = {
            'bg': colors['panel'],
            'fg': colors['fg'],
            'insertbackground': colors['fg'],
            'selectbackground': colors['select_bg'],
            'selectforeground': colors['select_fg'],
            'relief': 'flat',
            'bd': 1
        }
        defaults.update(kwargs)
        return tk.Text(parent, **defaults)
    
    def create_themed_listbox(self, parent: tk.Widget, **kwargs) -> tk.Listbox:
        """Create a listbox widget with dark theme applied."""
        colors = self.config.colors
        defaults = {
            'bg': colors['panel'],
            'fg': colors['fg'],
            'selectbackground': colors['select_bg'],
            'selectforeground': colors['select_fg'],
            'relief': 'flat',
            'bd': 1
        }
        defaults.update(kwargs)
        return tk.Listbox(parent, **defaults)
    
    def get_colors(self) -> Dict[str, str]:
        """Get the current color scheme."""
        return self.config.colors.copy()
    
    def update_color(self, color_key: str, color_value: str) -> None:
        """Update a specific color in the theme."""
        self.config.colors[color_key] = color_value
        # Reapply theme
        self.apply_dark_theme()


# Convenience functions for quick theming
def setup_dark_theme(root: tk.Tk, theme_config: Optional[ThemeConfig] = None) -> ThemeManager:
    """Set up dark theme for the entire application."""
    theme_manager = ThemeManager(root, theme_config)
    theme_manager.apply_dark_theme()
    return theme_manager


def get_default_colors() -> Dict[str, str]:
    """Get the default dark theme colors."""
    return ThemeConfig().colors.copy()


if __name__ == "__main__":
    # Example usage
    root = tk.Tk()
    root.title("Theme Manager Test")
    root.geometry("600x400")
    
    # Apply dark theme
    theme_manager = setup_dark_theme(root)
    
    # Test various widgets
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Buttons
    ttk.Button(frame, text="Test Button").pack(pady=5)
    
    # Entry
    ttk.Entry(frame).pack(pady=5, fill="x")
    
    # Combobox
    combo = ttk.Combobox(frame, values=["Option 1", "Option 2", "Option 3"])
    combo.pack(pady=5, fill="x")
    
    # Notebook
    notebook = ttk.Notebook(frame)
    tab1 = ttk.Frame(notebook)
    tab2 = ttk.Frame(notebook)
    notebook.add(tab1, text="Tab 1")
    notebook.add(tab2, text="Tab 2")
    notebook.pack(pady=5, fill="both", expand=True)
    
    # Themed text widget
    text = theme_manager.create_themed_text(tab1, wrap="word")
    text.pack(fill="both", expand=True)
    text.insert("1.0", "This is a themed text widget with dark colors applied.")
    
    # Label
    ttk.Label(tab2, text="This is a themed label").pack(pady=20)
    
    root.mainloop()
