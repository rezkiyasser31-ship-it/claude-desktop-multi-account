import os
import sys

# Ensure pythonw has valid stdout/stderr to avoid NoneType write crashes
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
import customtkinter as ctk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import native_switcher
import launcher

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CLAUDE_CORAL = "#D97757"
CLAUDE_CORAL_HOVER = "#C06243"
CARD_BG = "#232326"
BORDER_COLOR = "#38383D"
SUCCESS_GREEN = "#10B981"
TEXT_MUTED = "#9CA3AF"
ACTIVE_BLUE = "#3B82F6"
PURPLE_ACCENT = "#8B5CF6"

HANDOFF_PROMPT_TEMPLATE = """Please create a concise, high-density handoff summary of our conversation so far so I can seamlessly transfer it to a fresh account.
Include:
- Goal & Objectives:
- Key Decisions & Technical Context:
- Current Code / Implementation State:
- Immediate Next Steps:
Format it as a clean block ready to paste into a new session."""

class ClaudeNativeMultiApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Claude Desktop Multi-Account & Continuity Hub")
        self.geometry("780x820")
        self.minsize(700, 680)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.config_data = launcher.load_config()
        self.account_frames = {}
        self.status_labels = {}
        self.action_buttons = {}

        self.create_ui()

        # Safely poll status on the main GUI thread using self.after
        self.stop_polling = False
        self.after(1000, self._poll_status)

    def create_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=25, pady=(18, 8))

        top_row = ctk.CTkFrame(header, fg_color="transparent")
        top_row.pack(fill="x")

        title_label = ctk.CTkLabel(
            top_row,
            text="Claude Multi-Account & Continuity Hub",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#FFFFFF"
        )
        title_label.pack(side="left")

        native_badge = ctk.CTkLabel(
            top_row,
            text="  Native Windows App  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FFFFFF",
            fg_color=CLAUDE_CORAL,
            corner_radius=6
        )
        native_badge.pack(side="right")

        subtitle = ctk.CTkLabel(
            header,
            text="Context-preserving handoff and 1-click account switching for Claude Desktop.",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_MUTED
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        # Main Scrollable Body
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Section 1: 80% TOKEN LIMIT / CONTEXT HANDOFF ASSISTANT (Hero Feature)
        handoff_card = ctk.CTkFrame(self.scroll_frame, fg_color="#1E232B", corner_radius=10, border_width=1, border_color="#3B82F6")
        handoff_card.pack(fill="x", pady=(0, 14), ipady=8)

        handoff_top = ctk.CTkFrame(handoff_card, fg_color="transparent")
        handoff_top.pack(fill="x", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            handoff_top,
            text="🔄 80% TOKEN LIMIT HANDOFF & RESUME",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#60A5FA"
        ).pack(side="left")

        handoff_desc = (
            "When your chat reaches ~80% token capacity or nears the message limit:\n"
            "1. Click '1. Copy Handoff Prompt' and send it to Claude in your current account.\n"
            "2. Copy Claude's summary, then click '2. Switch & Prepare Account 2' below.\n"
            "The app automatically swaps to Account 2 and formats the resume prompt on your clipboard!"
        )
        ctk.CTkLabel(
            handoff_card,
            text=handoff_desc,
            font=ctk.CTkFont(size=12),
            text_color="#CBD5E1",
            wraplength=670,
            justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # Handoff Action Row
        handoff_btn_row = ctk.CTkFrame(handoff_card, fg_color="transparent")
        handoff_btn_row.pack(fill="x", padx=16, pady=(0, 6))

        step1_btn = ctk.CTkButton(
            handoff_btn_row,
            text="📋 1. Copy Handoff Prompt",
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self.copy_handoff_template
        )
        step1_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.step2_btn = ctk.CTkButton(
            handoff_btn_row,
            text="⚡ 2. Switch & Resume in Account 2",
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.switch_and_resume_target
        )
        self.step2_btn.pack(side="right", fill="x", expand=True)

        self.handoff_status_lbl = ctk.CTkLabel(
            handoff_card,
            text="Ready. Click Step 1 to copy the handoff request.",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        )
        self.handoff_status_lbl.pack(anchor="w", padx=16, pady=(2, 4))

        # Section 2: Status & Quick Action Card
        status_card = ctk.CTkFrame(self.scroll_frame, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        status_card.pack(fill="x", pady=(0, 14), ipady=4)

        st_top = ctk.CTkFrame(status_card, fg_color="transparent")
        st_top.pack(fill="x", padx=16, pady=(8, 4))

        self.native_status_lbl = ctk.CTkLabel(
            st_top,
            text="Native Claude Desktop: Checking...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF"
        )
        self.native_status_lbl.pack(side="left")

        save_active_btn = ctk.CTkButton(
            st_top,
            text="Snapshot Current Login",
            width=160,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self.snapshot_current_account
        )
        save_active_btn.pack(side="right")

        # Section 3: Managed Accounts List
        acc_sec_header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        acc_sec_header.pack(fill="x", pady=(4, 8))

        ctk.CTkLabel(
            acc_sec_header,
            text="MANAGED CLAUDE ACCOUNTS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=CLAUDE_CORAL
        ).pack(side="left")

        add_btn = ctk.CTkButton(
            acc_sec_header,
            text="+ Add Account",
            width=110,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#333338",
            hover_color="#44444A",
            command=self.add_new_account
        )
        add_btn.pack(side="right")

        self.accounts_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.accounts_container.pack(fill="x", pady=(0, 14))
        self.render_account_cards()

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=25, pady=(4, 10))

        self.status_bottom = ctk.CTkLabel(
            footer,
            text="Ready. Select an account or use the 80% Token Limit Assistant.",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        )
        self.status_bottom.pack(side="left")

    def render_account_cards(self):
        for widget in self.accounts_container.winfo_children():
            widget.destroy()

        self.account_frames.clear()
        self.status_labels.clear()
        self.action_buttons.clear()

        active_id = self.config_data.get("active_account", "account_1")
        accounts = self.config_data.get("accounts", [])
        
        # Pick the other account for the Step 2 handoff button (preferring saved profiles)
        saved_alts = [a for a in accounts if a["id"] != active_id and native_switcher.has_saved_session(a["id"])]
        if saved_alts:
            target = saved_alts[0]
        else:
            other_alts = [a for a in accounts if a["id"] != active_id]
            target = other_alts[0] if other_alts else (accounts[0] if accounts else None)

        if target and hasattr(self, "step2_btn"):
            self.step2_btn.configure(text=f"⚡ 2. Switch & Resume in {target['name']}")

        for acc in self.config_data["accounts"]:
            acc_id = acc["id"]
            name = acc["name"]
            color = acc.get("color", CLAUDE_CORAL)
            is_active = (acc_id == active_id)
            has_saved = native_switcher.has_saved_session(acc_id)

            card = ctk.CTkFrame(
                self.accounts_container,
                fg_color=CARD_BG,
                corner_radius=10,
                border_width=2 if is_active else 1,
                border_color=ACTIVE_BLUE if is_active else BORDER_COLOR
            )
            card.pack(fill="x", pady=(0, 8), ipady=6)
            self.account_frames[acc_id] = card

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=6)

            # Left side
            info_col = ctk.CTkFrame(inner, fg_color="transparent")
            info_col.pack(side="left", fill="y")

            name_row = ctk.CTkFrame(info_col, fg_color="transparent")
            name_row.pack(anchor="w")

            dot = ctk.CTkLabel(name_row, text="●", font=ctk.CTkFont(size=16), text_color=color)
            dot.pack(side="left", padx=(0, 6))

            name_lbl = ctk.CTkLabel(name_row, text=name, font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF")
            name_lbl.pack(side="left")

            email = acc.get("email", "")
            if email:
                email_lbl = ctk.CTkLabel(name_row, text=f"({email})", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED)
                email_lbl.pack(side="left", padx=(6, 0))

            rename_btn = ctk.CTkButton(
                name_row,
                text="Rename",
                width=55,
                height=22,
                font=ctk.CTkFont(size=11),
                fg_color="#333338",
                hover_color="#44444A",
                command=lambda aid=acc_id: self.rename_account(aid)
            )
            rename_btn.pack(side="left", padx=(10, 0))

            if has_saved:
                relogin_btn = ctk.CTkButton(
                    name_row,
                    text="Re-login",
                    width=60,
                    height=22,
                    font=ctk.CTkFont(size=11),
                    fg_color="#333338",
                    hover_color="#44444A",
                    command=lambda aid=acc_id: self.relink_account(aid)
                )
                relogin_btn.pack(side="left", padx=(6, 0))

            # Status row
            sub_row = ctk.CTkFrame(info_col, fg_color="transparent")
            sub_row.pack(anchor="w", padx=(16, 0), pady=(2, 0))

            saved_uuid = native_switcher.get_saved_account_uuid(acc_id)
            uuid_hint = f" [UUID: {saved_uuid[:8]}...]" if saved_uuid else ""
            st_text = f"● Active in Native App{uuid_hint}" if is_active else (f"● Saved Profile{uuid_hint}" if has_saved else "○ Not Saved Yet")
            st_color = ACTIVE_BLUE if is_active else (SUCCESS_GREEN if has_saved else "#FBBF24")
            st_lbl = ctk.CTkLabel(sub_row, text=st_text, font=ctk.CTkFont(size=11, weight="bold"), text_color=st_color)
            st_lbl.pack(side="left")
            self.status_labels[acc_id] = st_lbl

            # Right side: Switch / Set up button
            btn_col = ctk.CTkFrame(inner, fg_color="transparent")
            btn_col.pack(side="right")

            if is_active:
                btn_text = "Open Native App"
                btn_color = "#334155"
                btn_hover = "#475569"
            elif has_saved:
                btn_text = f"Switch to {name}"
                btn_color = CLAUDE_CORAL
                btn_hover = CLAUDE_CORAL_HOVER
            else:
                btn_text = "Set Up / Log In"
                btn_color = "#2563EB"
                btn_hover = "#1D4ED8"

            action_btn = ctk.CTkButton(
                btn_col,
                text=btn_text,
                width=150,
                height=32,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=btn_color,
                hover_color=btn_hover,
                command=lambda aid=acc_id: self.switch_account(aid)
            )
            action_btn.pack(side="right")
            self.action_buttons[acc_id] = action_btn

    def _poll_status(self):
        if self.stop_polling:
            return
        try:
            running = native_switcher.is_native_claude_running()
            live_uuid = native_switcher.get_live_account_uuid()
            live_id = native_switcher.get_account_for_uuid(live_uuid) if live_uuid else None

            # Auto-detect when account changes in Claude Desktop (e.g. manual log-in/switch)
            if live_id and live_id != self.config_data.get("active_account"):
                self.config_data["active_account"] = live_id
                launcher.save_config(self.config_data)
                self.render_account_cards()

            current_active = self.config_data.get("active_account", "account_1")
            acc = next((a for a in self.config_data.get("accounts", []) if a["id"] == current_active), None)
            active_name = acc["name"] if acc else current_active

            if running:
                if live_id:
                    self.native_status_lbl.configure(
                        text=f"Native Claude Desktop: ● RUNNING ({active_name})", 
                        text_color=SUCCESS_GREEN
                    )
                elif live_uuid:
                    self.native_status_lbl.configure(
                        text=f"Native Claude Desktop: ● RUNNING (Unsaved Profile)", 
                        text_color="#F59E0B"
                    )
                else:
                    self.native_status_lbl.configure(
                        text=f"Native Claude Desktop: ● RUNNING ({active_name})", 
                        text_color=SUCCESS_GREEN
                    )
            else:
                self.native_status_lbl.configure(
                    text=f"Native Claude Desktop: ○ CLOSED (Active: {active_name})", 
                    text_color=TEXT_MUTED
                )
        except Exception:
            pass

        if not self.stop_polling:
            self.after(1500, self._poll_status)

    def copy_handoff_template(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(HANDOFF_PROMPT_TEMPLATE)
            self.handoff_status_lbl.configure(
                text="✓ Handoff prompt copied! Paste it into your current Claude chat.",
                text_color="#34D399"
            )
        except Exception as e:
            self.handoff_status_lbl.configure(text=f"Error copying: {e}", text_color="#EF4444")

    def switch_and_resume_target(self):
        # Refresh current active from live detection
        live_id = native_switcher.get_live_account_id()
        if live_id:
            self.config_data["active_account"] = live_id
            
        active_id = self.config_data.get("active_account", "account_1")
        accounts = self.config_data.get("accounts", [])
        
        # Pick the other account (preferring saved profiles)
        saved_alts = [a for a in accounts if a["id"] != active_id and native_switcher.has_saved_session(a["id"])]
        if saved_alts:
            target = saved_alts[0]
        else:
            other_alts = [a for a in accounts if a["id"] != active_id]
            target = other_alts[0] if other_alts else accounts[0]
            
        target_id = target["id"]
        target_name = target["name"]

        # Read clipboard summary
        try:
            summary = self.clipboard_get().strip()
        except Exception:
            summary = ""

        if not summary or summary == HANDOFF_PROMPT_TEMPLATE:
            # Prompt user to copy the summary first
            summary = simpledialog.askstring(
                "Conversation Context",
                "Paste the summary or latest context from your previous chat:",
                parent=self
            )
            if not summary or not summary.strip():
                return

        # Prepare continuing prompt on clipboard
        continuing_prompt = (
            f"We are continuing our project from a previous conversation that reached its token limit.\n\n"
            f"Here is the handoff summary of where we left off:\n"
            f"----------------------------------------\n"
            f"{summary}\n"
            f"----------------------------------------\n\n"
            f"Please confirm you have absorbed this context and let's continue with the immediate next steps."
        )

        try:
            self.clipboard_clear()
            self.clipboard_append(continuing_prompt)
        except Exception:
            pass

        self.handoff_status_lbl.configure(
            text=f"Swapping Native App to {target_name} & context ready on clipboard!",
            text_color="#60A5FA"
        )
        self.status_bottom.configure(text=f"Switched to {target_name}. Hit Ctrl+V in Claude Desktop!")

        def run_switch():
            native_switcher.switch_to_native_account(target_id, current_active_id=active_id)
            self.config_data["active_account"] = target_id
            launcher.save_config(self.config_data)
            self.after(300, self.render_account_cards)

        threading.Thread(target=run_switch, daemon=True).start()

    def snapshot_current_account(self):
        live_uuid = native_switcher.get_live_account_uuid()
        if not live_uuid:
            messagebox.showwarning(
                "No Session Detected",
                "Claude Desktop does not appear to have an active session.\n"
                "Please open Claude Desktop and make sure you are logged in."
            )
            return

        # Check if this live UUID belongs to an existing account
        matched_id = native_switcher.get_account_for_uuid(live_uuid)
        active_id = self.config_data.get("active_account", "account_1")
        
        if matched_id:
            target_save_id = matched_id
        elif not native_switcher.has_saved_session(active_id):
            target_save_id = active_id
        else:
            unsaved = [a for a in self.config_data.get("accounts", []) if not native_switcher.has_saved_session(a["id"])]
            if unsaved:
                target_save_id = unsaved[0]["id"]
            else:
                target_save_id = active_id
        
        acc = next((a for a in self.config_data["accounts"] if a["id"] == target_save_id), None)
        name = acc["name"] if acc else target_save_id

        confirm = messagebox.askyesno(
            "Snapshot Current Session",
            f"Save the current login in Claude Desktop to profile '{name}'?\n\n"
            f"Profile: {name} ({target_save_id})\n"
            f"Detected Session UUID: {live_uuid[:8]}...\n\n"
            "This will briefly pause Claude Desktop to snapshot the session files safely."
        )
        if not confirm:
            return

        self.status_bottom.configure(text=f"Saving current session to {name}...")
        
        def run_save():
            native_switcher.save_current_native_session(target_save_id)
            native_switcher.launch_native_claude()
            self.config_data["active_account"] = target_save_id
            launcher.save_config(self.config_data)
            self.after(500, self.render_account_cards)
            self.status_bottom.configure(text=f"Successfully saved session for {name}!")

        threading.Thread(target=run_save, daemon=True).start()

    def switch_account(self, target_id: str):
        # Refresh active account from live session
        live_id = native_switcher.get_live_account_id()
        if live_id:
            active_id = live_id
            self.config_data["active_account"] = live_id
        else:
            active_id = self.config_data.get("active_account", "account_1")

        target_acc = next((a for a in self.config_data["accounts"] if a["id"] == target_id), None)
        target_name = target_acc["name"] if target_acc else target_id

        if active_id == target_id and native_switcher.is_native_claude_running():
            self.status_bottom.configure(text=f"{target_name} is already open and running.")
            return

        if active_id == target_id and native_switcher.has_saved_session(target_id):
            self.status_bottom.configure(text=f"Opening Claude Desktop for {target_name}...")
            native_switcher.launch_native_claude()
            return

        has_saved = native_switcher.has_saved_session(target_id)
        if not has_saved:
            msg = (
                f"You are setting up '{target_name}'.\n\n"
                "1. Claude Desktop will open in a clean state.\n"
                "2. Sign in to your account.\n"
                "3. Once logged in, click 'Snapshot Current Login' in this Hub to save it."
            )
            messagebox.showinfo("First Time Account Setup", msg)

        self.status_bottom.configure(text=f"Switching native app to {target_name}...")

        def run_switch():
            native_switcher.switch_to_native_account(target_id, current_active_id=active_id)
            self.config_data["active_account"] = target_id
            launcher.save_config(self.config_data)

            self.after(500, self.render_account_cards)
            self.status_bottom.configure(text=f"Now active in Claude Desktop: {target_name}")

        threading.Thread(target=run_switch, daemon=True).start()

    def rename_account(self, account_id: str):
        acc = next((a for a in self.config_data["accounts"] if a["id"] == account_id), None)
        if not acc:
            return
        new_name = simpledialog.askstring("Rename Account", f"Enter label or email for {acc['name']}:", initialvalue=acc["name"], parent=self)
        if new_name and new_name.strip():
            acc["name"] = new_name.strip()
            launcher.save_config(self.config_data)
            self.render_account_cards()

    def relink_account(self, account_id: str):
        acc = next((a for a in self.config_data["accounts"] if a["id"] == account_id), None)
        name = acc["name"] if acc else account_id

        confirm = messagebox.askyesno(
            "Re-login Account",
            f"Reset saved session for '{name}' and log in again?\n\n"
            "This will clear the saved profile and launch Claude Desktop so you can sign in to the correct account."
        )
        if not confirm:
            return

        self.status_bottom.configure(text=f"Clearing saved profile for {name} & opening Claude in login mode...")

        def run_relink():
            p_dir = os.path.join(native_switcher.PROFILES_DIR, account_id)
            if os.path.exists(p_dir):
                shutil.rmtree(p_dir, ignore_errors=True)
                os.makedirs(p_dir, exist_ok=True)

            native_switcher.ensure_claude_closed()
            for item in native_switcher.SESSION_ITEMS:
                p = os.path.join(native_switcher.CLAUDE_ROAMING, item)
                native_switcher.safe_remove(p)

            native_switcher.launch_native_claude()
            self.config_data["active_account"] = account_id
            launcher.save_config(self.config_data)
            self.after(500, self.render_account_cards)
            self.status_bottom.configure(
                text=f"Claude opened in login mode. Sign in to {name}, then click 'Snapshot Current Login'!"
            )

        threading.Thread(target=run_relink, daemon=True).start()


    def add_new_account(self):
        count = len(self.config_data["accounts"]) + 1
        new_id = f"account_{count}"
        new_name = f"Account {count}"
        colors = ["#10B981", "#F59E0B", "#8B5CF6", "#EC4899"]
        color = colors[(count - 1) % len(colors)]

        self.config_data["accounts"].append({
            "id": new_id,
            "name": new_name,
            "color": color,
            "email": ""
        })
        launcher.save_config(self.config_data)
        self.render_account_cards()
        self.status_bottom.configure(text=f"Added {new_name}. Click 'Set Up / Log In' to link it.")

    def on_closing(self):
        self.stop_polling = True
        self.destroy()

if __name__ == "__main__":
    import traceback
    try:
        app = ClaudeNativeMultiApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except Exception as e:
        with open(os.path.join(BASE_DIR, "debug_crash.log"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
