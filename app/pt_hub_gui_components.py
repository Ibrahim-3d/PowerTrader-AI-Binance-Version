"""
PowerTrader AI+ GUI Components Module
Extracted GUI components and widgets from main pt_hub.py for better modularity
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Any, Dict, List, Optional


class ToolTip:
    """Simple tooltip helper for widgets."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)

    def on_enter(self, event=None):
        """Show tooltip on mouse enter."""
        if self.tooltip_window is not None:
            return

        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 5
        y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            background="#FFFFDD",
            foreground="#000000",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 8),
            padx=5,
            pady=2,
        )
        label.pack()

    def on_leave(self, event=None):
        """Hide tooltip on mouse leave."""
        if self.tooltip_window is not None:
            self.tooltip_window.destroy()
            self.tooltip_window = None


class _WrapItem:
    """Internal wrapper for items in WrapFrame."""

    def __init__(self, widget, min_width=0):
        self.widget = widget
        self.min_width = min_width


class WrapFrame(ttk.Frame):
    """
    Frame that automatically wraps its children to multiple rows
    when they exceed the available width.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._children_list: List[_WrapItem] = []
        self.bind("<Configure>", self._on_configure)

    def add_child(self, widget, min_width=0):
        """Add a widget to the wrap frame."""
        item = _WrapItem(widget, min_width)
        self._children_list.append(item)
        self._relayout()

    def remove_child(self, widget):
        """Remove a widget from the wrap frame."""
        self._children_list = [
            item for item in self._children_list if item.widget != widget
        ]
        widget.pack_forget()
        self._relayout()

    def _on_configure(self, event):
        """Handle frame resize events."""
        if event.widget == self:
            self._relayout()

    def _relayout(self):
        """Relayout all children with wrapping."""
        if not self._children_list:
            return

        # Forget all current packing
        for item in self._children_list:
            item.widget.pack_forget()

        # Get available width
        available_width = self.winfo_width()
        if available_width <= 1:  # Not yet realized
            available_width = 400  # Default width

        current_row_width = 0
        need_new_row = False

        for item in self._children_list:
            # Get widget's requested width
            item.widget.update_idletasks()
            widget_width = max(item.widget.winfo_reqwidth(), item.min_width)

            # Check if we need to start a new row
            if (
                current_row_width + widget_width > available_width
                and current_row_width > 0
            ):
                need_new_row = True
                current_row_width = 0

            # Pack the widget
            if need_new_row:
                item.widget.pack(side=tk.LEFT, padx=2, pady=2)
                need_new_row = False
            else:
                item.widget.pack(side=tk.LEFT, padx=2, pady=2)

            current_row_width += widget_width


class NeuralSignalTile(ttk.Frame):
    """
    Enhanced neural signal tile with improved visual design and functionality.
    """

    def __init__(self, parent, coin: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.coin = coin
        self.signal_value = 0.0
        self.confidence = 0.0
        self.trend = "neutral"

        self._setup_ui()

    def _setup_ui(self):
        """Setup the neural signal tile UI."""
        # Main container
        self.configure(relief="raised", borderwidth=2, padding=10)

        # Coin label
        self.coin_label = ttk.Label(
            self, text=self.coin, font=("TkDefaultFont", 12, "bold")
        )
        self.coin_label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        # Signal strength bar
        self.signal_frame = ttk.Frame(self)
        self.signal_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        self.signal_label = ttk.Label(self.signal_frame, text="Signal:")
        self.signal_label.pack(side=tk.LEFT)

        self.signal_bar = ttk.Progressbar(
            self.signal_frame, length=100, mode="determinate", value=0
        )
        self.signal_bar.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)

        # Confidence indicator
        self.confidence_frame = ttk.Frame(self)
        self.confidence_frame.grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5)
        )

        self.confidence_label = ttk.Label(self.confidence_frame, text="Confidence:")
        self.confidence_label.pack(side=tk.LEFT)

        self.confidence_value = ttk.Label(self.confidence_frame, text="0%")
        self.confidence_value.pack(side=tk.RIGHT)

        # Trend indicator
        self.trend_label = ttk.Label(
            self, text="●", font=("TkDefaultFont", 16), foreground="gray"
        )
        self.trend_label.grid(row=3, column=0, columnspan=2, pady=(5, 0))

        # Configure grid weights
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def update_signal(
        self, signal_value: float, confidence: float, trend: str = "neutral"
    ):
        """Update the neural signal display."""
        self.signal_value = max(-1.0, min(1.0, signal_value))
        self.confidence = max(0.0, min(1.0, confidence))
        self.trend = trend

        # Update signal bar
        bar_value = (self.signal_value + 1.0) * 50  # Convert -1,1 to 0,100
        self.signal_bar["value"] = bar_value

        # Color code the signal bar
        if self.signal_value > 0.3:
            style = "Green.Horizontal.TProgressbar"
        elif self.signal_value < -0.3:
            style = "Red.Horizontal.TProgressbar"
        else:
            style = "TProgressbar"

        try:
            self.signal_bar.configure(style=style)
        except:
            pass  # Style might not exist

        # Update confidence
        self.confidence_value.configure(text=f"{self.confidence*100:.0f}%")

        # Update trend indicator
        if trend == "bullish":
            self.trend_label.configure(foreground="green", text="▲")
        elif trend == "bearish":
            self.trend_label.configure(foreground="red", text="▼")
        else:
            self.trend_label.configure(foreground="gray", text="●")

    def get_signal_data(self) -> Dict[str, Any]:
        """Get current signal data."""
        return {
            "coin": self.coin,
            "signal_value": self.signal_value,
            "confidence": self.confidence,
            "trend": self.trend,
        }


class StatusBar(ttk.Frame):
    """Enhanced status bar with multiple status indicators."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the status bar UI."""
        # Left side - main status
        self.main_status = ttk.Label(self, text="Ready", relief="sunken")
        self.main_status.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # Right side - additional status indicators
        self.right_frame = ttk.Frame(self)
        self.right_frame.pack(side=tk.RIGHT, padx=2)

        # Exchange status
        self.exchange_status = ttk.Label(
            self.right_frame, text="Exchange: Disconnected", relief="sunken", width=20
        )
        self.exchange_status.pack(side=tk.LEFT, padx=1)

        # Training status
        self.training_status = ttk.Label(
            self.right_frame, text="Training: Idle", relief="sunken", width=15
        )
        self.training_status.pack(side=tk.LEFT, padx=1)

        # System status
        self.system_status = ttk.Label(
            self.right_frame, text="System: OK", relief="sunken", width=12
        )
        self.system_status.pack(side=tk.LEFT, padx=1)

    def update_main_status(self, text: str):
        """Update the main status text."""
        self.main_status.configure(text=text)

    def update_exchange_status(self, text: str, connected: bool = False):
        """Update exchange connection status."""
        color = "lightgreen" if connected else "lightcoral"
        self.exchange_status.configure(text=f"Exchange: {text}", background=color)

    def update_training_status(self, text: str, active: bool = False):
        """Update training status."""
        color = "lightyellow" if active else "white"
        self.training_status.configure(text=f"Training: {text}", background=color)

    def update_system_status(self, text: str, healthy: bool = True):
        """Update system health status."""
        color = "lightgreen" if healthy else "lightcoral"
        self.system_status.configure(text=f"System: {text}", background=color)


class ProgressDialog(tk.Toplevel):
    """Modal progress dialog for long-running operations."""

    def __init__(self, parent, title: str, message: str, **kwargs):
        super().__init__(parent, **kwargs)

        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.geometry("400x150")
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        x = parent_x + (parent_width // 2) - 200
        y = parent_y + (parent_height // 2) - 75
        self.geometry(f"400x150+{x}+{y}")

        self._setup_ui(message)

    def _setup_ui(self, message: str):
        """Setup the progress dialog UI."""
        # Message label
        self.message_label = ttk.Label(
            self, text=message, wraplength=350, justify=tk.CENTER
        )
        self.message_label.pack(pady=20, padx=20)

        # Progress bar
        self.progress_bar = ttk.Progressbar(self, length=300, mode="indeterminate")
        self.progress_bar.pack(pady=10)
        self.progress_bar.start()

        # Status label
        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(pady=5)

    def update_message(self, message: str):
        """Update the progress message."""
        self.message_label.configure(text=message)

    def update_status(self, status: str):
        """Update the status text."""
        self.status_label.configure(text=status)

    def set_progress(self, value: int):
        """Set progress bar to determinate mode with value."""
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", value=value)

    def close(self):
        """Close the progress dialog."""
        self.progress_bar.stop()
        self.destroy()


class LogViewer(tk.Toplevel):
    """Enhanced log viewer window with filtering and search."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.title("PowerTrader AI+ Log Viewer")
        self.geometry("800x600")
        self.transient(parent)

        self._setup_ui()
        self.log_lines = []

    def _setup_ui(self):
        """Setup the log viewer UI."""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Clear button
        clear_btn = ttk.Button(toolbar, text="Clear", command=self.clear_logs)
        clear_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Search frame
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var, width=20
        )
        self.search_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.search_entry.bind("<Return>", self.search_logs)

        search_btn = ttk.Button(search_frame, text="Find", command=self.search_logs)
        search_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Filter checkboxes
        filter_frame = ttk.Frame(toolbar)
        filter_frame.pack(side=tk.RIGHT)

        self.show_info = tk.BooleanVar(value=True)
        self.show_warning = tk.BooleanVar(value=True)
        self.show_error = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            filter_frame, text="Info", variable=self.show_info, command=self.filter_logs
        ).pack(side=tk.RIGHT, padx=2)
        ttk.Checkbutton(
            filter_frame,
            text="Warning",
            variable=self.show_warning,
            command=self.filter_logs,
        ).pack(side=tk.RIGHT, padx=2)
        ttk.Checkbutton(
            filter_frame,
            text="Error",
            variable=self.show_error,
            command=self.filter_logs,
        ).pack(side=tk.RIGHT, padx=2)

        # Text widget with scrollbar
        text_frame = ttk.Frame(self)
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = tk.Text(
            text_frame, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED
        )

        scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure text tags for different log levels
        self.log_text.tag_configure("info", foreground="black")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("success", foreground="green")

    def add_log_line(self, message: str, level: str = "info"):
        """Add a log line to the viewer."""
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level.upper()}: {message}\n"

        self.log_lines.append((formatted_message, level))

        # Update display if filters allow
        if self._should_show_level(level):
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, formatted_message, level)
            self.log_text.configure(state=tk.DISABLED)
            self.log_text.see(tk.END)

    def clear_logs(self):
        """Clear all log lines."""
        self.log_lines.clear()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def search_logs(self, event=None):
        """Search for text in log lines."""
        search_term = self.search_var.get().lower()
        if not search_term:
            return

        # Find and highlight matching text
        self.log_text.tag_remove("search", 1.0, tk.END)

        start = 1.0
        while True:
            pos = self.log_text.search(search_term, start, tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(search_term)}c"
            self.log_text.tag_add("search", pos, end)
            start = end

        self.log_text.tag_configure("search", background="yellow")

        # Jump to first match
        first_match = self.log_text.search(search_term, 1.0, tk.END, nocase=True)
        if first_match:
            self.log_text.see(first_match)

    def filter_logs(self):
        """Filter logs based on level checkboxes."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)

        for message, level in self.log_lines:
            if self._should_show_level(level):
                self.log_text.insert(tk.END, message, level)

        self.log_text.configure(state=tk.DISABLED)

    def _should_show_level(self, level: str) -> bool:
        """Check if a log level should be shown based on filters."""
        level = level.lower()
        if level == "info":
            return self.show_info.get()
        elif level == "warning":
            return self.show_warning.get()
        elif level == "error":
            return self.show_error.get()
        return True
