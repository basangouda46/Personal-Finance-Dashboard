from customtkinter import *
import tkinter
from pandastable import Table

# --- THE MONKEY PATCH FIX ---
# This re-routes pandastable's internal event binder directly to the base application window
_original_init = Table.__init__
def patched_init(self, parent, *args, **kwargs):
    _original_init(self, parent, *args, **kwargs)
    # Safely find the absolute root window across widget layers
    app_root = parent.winfo_toplevel()
    
    # Override the library's restricted bindings onto the actual root window
    app_root.bind_all("<KP_8>", self.handle_arrow_keys)
    app_root.bind_all("<Return>", self.handle_arrow_keys)
    app_root.bind_all("<Tab>", self.handle_arrow_keys)
    app_root.bind_all("<Up>", self.handle_arrow_keys)
    app_root.bind_all("<Down>", self.handle_arrow_keys)
Table.__init__ = patched_init
# -----------------------------

root = CTk()

root.geometry("2500 x 2500")


tabview = CTkTabview(master=root)
tabview.pack(padx=20, pady=20, fill="both", expand=True)

tabview.add("Dashboard")
tabview.add("Balance Sheet")

window_income = CTkFrame(master=tabview.tab("Dashboard"), width=500, height=500)
# window_income.pack(fill="both", expand=True)
# window_income.grid(row=0, column = 0, padx=10, pady=5)
window_income.pack(fill="both", expand=True, padx=10, pady=5)

# pt = Table(window_income)
pt = Table(parent=window_income, showstatusbar=True, showtoolbar=True)
pt.show()



root.mainloop()

