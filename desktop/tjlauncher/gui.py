"""Interface graphique (Tkinter) : assistant de premier lancement + fenêtre de contrôle.

Le travail se fait dans un thread ; chaque interaction avec l'utilisateur est transmise au thread principal Tk.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
from pathlib import Path
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk

from . import backup, paths
from .app import Launcher, LauncherError
from .singleton import SingleInstance
from .ui import SetupCancelled
from .version import APP_NAME, __version__

log = logging.getLogger("tjlauncher.gui")
FONT = ("Segoe UI", 10)
PAD = {"padx": 14, "pady": 6}


class _Dialog(tk.Toplevel):
    """Fenêtre modale simple : le résultat est dans `self.result` (None si fermée)."""

    def __init__(self, parent: tk.Misc, title: str, width: int = 440) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        self.body = ttk.Frame(self, padding=16)
        self.body.pack(fill="both", expand=True)
        self._width = width
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.transient(parent)

    def label(self, text: str, **kwargs) -> ttk.Label:
        widget = ttk.Label(self.body, text=text, wraplength=self._width - 32, justify="left", **kwargs)
        widget.pack(anchor="w", pady=(0, 8))
        return widget

    def show(self) -> None:
        self.update_idletasks()
        x = self.master.winfo_rootx() + 40
        y = self.master.winfo_rooty() + 40
        self.geometry(f"{self._width}x{self.winfo_reqheight()}+{x}+{y}")
        self.grab_set()
        self.focus_force()
        self.wait_window(self)


class TkUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._calls: queue.Queue = queue.Queue()
        self._closed = False
        self.frame = ttk.Frame(root, padding=18)
        self.frame.pack(fill="both", expand=True)
        ttk.Label(self.frame, text=APP_NAME, font=("Segoe UI Semibold", 16)).pack(anchor="w")
        self.status_var = tk.StringVar(value="Préparation…")
        ttk.Label(self.frame, textvariable=self.status_var, wraplength=470, justify="left").pack(anchor="w", pady=(14, 8))
        self.bar = ttk.Progressbar(self.frame, mode="indeterminate", length=470)
        self.bar.pack(anchor="w")
        self.bar.start(12)
        self.extra = ttk.Frame(self.frame)
        self.extra.pack(fill="both", expand=True, pady=(14, 0))
        root.after(40, self._pump)

    # -- marshalling vers le thread Tk ---------------------------------------------------------------
    def _pump(self) -> None:
        try:
            while True:
                fn, holder, done = self._calls.get_nowait()
                try:
                    holder.append(fn())
                except Exception as exc:  # noqa: BLE001
                    holder.append(exc)
                done.set()
        except queue.Empty:
            pass
        if not self._closed:
            self.root.after(40, self._pump)

    def on_main(self, fn: Callable):
        if threading.current_thread() is threading.main_thread():
            return fn()
        if self._closed:
            raise SetupCancelled()
        holder: list = []
        done = threading.Event()
        self._calls.put((fn, holder, done))
        done.wait()
        if isinstance(holder[0], Exception):
            raise holder[0]
        return holder[0]

    def close(self) -> None:
        self._closed = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # -- API UI -----------------------------------------------------------------------------------------
    def status(self, text: str) -> None:
        log.info(text)
        self.on_main(lambda: self.status_var.set(text))

    def progress(self, fraction: float | None) -> None:
        def apply() -> None:
            if fraction is None:
                self.bar.configure(mode="indeterminate")
                self.bar.start(12)
            else:
                self.bar.stop()
                self.bar.configure(mode="determinate", value=max(0.0, min(1.0, fraction)) * 100)

        self.on_main(apply)

    def confirm(self, title: str, message: str) -> bool:
        return bool(self.on_main(lambda: messagebox.askyesno(title, message, parent=self.root)))

    def error(self, title: str, message: str) -> None:
        self.on_main(lambda: messagebox.showerror(title, message, parent=self.root))

    def choose(self, title: str, message: str, options: list[str]) -> int | None:
        def run() -> int | None:
            dialog = _Dialog(self.root, title, width=500)
            dialog.label(message)
            for index, option in enumerate(options):
                def pick(i=index) -> None:
                    dialog.result = i
                    dialog.destroy()

                ttk.Button(dialog.body, text=option, command=pick).pack(fill="x", pady=3)
            dialog.show()
            return dialog.result

        return self.on_main(run)

    def ask_secret(self, title: str, message: str, error: str | None = None) -> str | None:
        def run() -> str | None:
            dialog = _Dialog(self.root, title, width=480)
            dialog.label(message)
            value = tk.StringVar()
            entry = ttk.Entry(dialog.body, textvariable=value, show="•", width=40)
            entry.pack(fill="x", pady=4)
            entry.focus_set()
            if error:
                ttk.Label(dialog.body, text=error, foreground="#c0392b").pack(anchor="w")

            def ok(_event=None) -> None:
                dialog.result = value.get()
                dialog.destroy()

            entry.bind("<Return>", ok)
            row = ttk.Frame(dialog.body)
            row.pack(anchor="e", pady=(10, 0))
            ttk.Button(row, text="Annuler", command=dialog.destroy).pack(side="right", padx=(6, 0))
            ttk.Button(row, text="Continuer", command=ok).pack(side="right")
            dialog.show()
            return dialog.result

        return self.on_main(run)

    def ask_connection(self) -> dict | None:
        def run() -> dict | None:
            dialog = _Dialog(self.root, "Serveur PostgreSQL existant", width=460)
            dialog.label("Indiquez un compte PostgreSQL autorisé à créer une base et un rôle (ex. « postgres »).")
            fields = {"host": tk.StringVar(value="127.0.0.1"), "port": tk.StringVar(value="5432"),
                      "user": tk.StringVar(value="postgres"), "password": tk.StringVar()}
            for key, label in (("host", "Hôte"), ("port", "Port"), ("user", "Utilisateur"), ("password", "Mot de passe")):
                ttk.Label(dialog.body, text=label).pack(anchor="w")
                ttk.Entry(dialog.body, textvariable=fields[key], show="•" if key == "password" else "").pack(fill="x", pady=(0, 6))
            message = ttk.Label(dialog.body, text="", foreground="#c0392b")
            message.pack(anchor="w")

            def ok() -> None:
                try:
                    port = int(fields["port"].get())
                except ValueError:
                    message.configure(text="Port invalide.")
                    return
                dialog.result = {"host": fields["host"].get().strip(), "port": port,
                                 "user": fields["user"].get().strip(), "password": fields["password"].get()}
                dialog.destroy()

            row = ttk.Frame(dialog.body)
            row.pack(anchor="e", pady=(8, 0))
            ttk.Button(row, text="Annuler", command=dialog.destroy).pack(side="right", padx=(6, 0))
            ttk.Button(row, text="Continuer", command=ok).pack(side="right")
            dialog.show()
            return dialog.result

        return self.on_main(run)

    def account_dialog(self, create: Callable[[dict], dict]) -> bool:
        def run() -> bool:
            dialog = _Dialog(self.root, "Créer un compte", width=470)
            dialog.label("Créez votre compte pour accéder à Trading Journal. Vous pourrez aussi le faire plus tard depuis la page de connexion.")
            vars_ = {name: tk.StringVar() for name in ("username", "email", "password", "confirm")}
            errors: dict[str, ttk.Label] = {}
            for key, label, secret in (("username", "Identifiant", False), ("email", "E-mail (facultatif)", False),
                                       ("password", "Mot de passe (8 caractères minimum)", True), ("confirm", "Confirmer le mot de passe", True)):
                ttk.Label(dialog.body, text=label).pack(anchor="w")
                ttk.Entry(dialog.body, textvariable=vars_[key], show="•" if secret else "").pack(fill="x", pady=(0, 2))
                errors[key] = ttk.Label(dialog.body, text="", foreground="#c0392b", wraplength=420, justify="left")
                errors[key].pack(anchor="w")
            created = {"ok": False}

            def submit() -> None:
                for label in errors.values():
                    label.configure(text="")
                if vars_["password"].get() != vars_["confirm"].get():
                    errors["confirm"].configure(text="Les mots de passe ne correspondent pas.")
                    return
                result = create({"username": vars_["username"].get().strip(), "email": vars_["email"].get().strip(),
                                 "password": vars_["password"].get()})
                if result.get("ok"):
                    created["ok"] = True
                    messagebox.showinfo("Compte créé", f"Le compte « {result.get('username', '')} » a été créé.", parent=dialog)
                    dialog.destroy()
                    return
                for field, messages in (result.get("errors") or {}).items():
                    target = errors.get({"password_confirm": "confirm"}.get(field, field), errors["username"])
                    target.configure(text=" ".join(messages))

            row = ttk.Frame(dialog.body)
            row.pack(anchor="e", pady=(8, 0))
            ttk.Button(row, text="Plus tard", command=dialog.destroy).pack(side="right", padx=(6, 0))
            ttk.Button(row, text="Créer le compte", command=submit).pack(side="right")
            dialog.show()
            return created["ok"]

        return bool(self.on_main(run))

    # -- fenêtre de contrôle ---------------------------------------------------------------------------------
    def show_running(self, launcher: Launcher) -> None:
        def running_text() -> str:
            text = f"Trading Journal est lancé.\n{launcher.cfg.ui_url}"
            if launcher.cfg.uses_sqlite:
                text += "\nBase de données : SQLite (mode de secours). PostgreSQL sera proposé dès que possible."
            return text

        def build() -> None:
            self.bar.stop()
            self.bar.pack_forget()
            self.status_var.set(running_text())
            for child in self.extra.winfo_children():
                child.destroy()

            def run_async(job: Callable[[], str], busy: str) -> None:
                self.status_var.set(busy)

                def target() -> None:
                    try:
                        message = job()
                    except Exception as exc:  # noqa: BLE001
                        log.exception("opération échouée")
                        message = f"Échec : {exc}"
                    self.on_main(lambda: self.status_var.set(running_text()))
                    self.on_main(lambda: messagebox.showinfo(APP_NAME, message, parent=self.root))

                threading.Thread(target=target, daemon=True).start()

            def do_backup() -> None:
                dest = filedialog.asksaveasfilename(parent=self.root, defaultextension=backup.EXTENSION, initialdir=str(paths.backups_dir()),
                                                    initialfile=backup.default_name(), filetypes=[("Sauvegarde Trading Journal", f"*{backup.EXTENSION}")])
                if dest:
                    run_async(lambda: f"Sauvegarde créée :\n{launcher.backup_now(Path(dest))}", "Sauvegarde en cours…")

            def do_restore() -> None:
                src = filedialog.askopenfilename(parent=self.root, initialdir=str(paths.backups_dir()),
                                                 filetypes=[("Sauvegarde Trading Journal", f"*{backup.EXTENSION}")])
                if not src:
                    return
                if not messagebox.askyesno("Restaurer", "La restauration REMPLACE vos données actuelles.\nUne sauvegarde de sécurité sera créée avant.\n\nContinuer ?", parent=self.root):
                    return
                run_async(lambda: f"Restauration terminée.\nSauvegarde de sécurité :\n{launcher.restore(Path(src))}", "Restauration en cours…")

            buttons = [
                ("Ouvrir dans le navigateur", launcher.open_browser),
                ("Créer un compte…", lambda: self.account_dialog(launcher.create_account)),
                ("Sauvegarder mes données…", do_backup),
                ("Restaurer une sauvegarde…", do_restore),
                ("Ouvrir le dossier des données", lambda: os.startfile(paths.data_dir())),  # noqa: S606
                ("Quitter", self.request_quit),
            ]
            for text, command in buttons:
                ttk.Button(self.extra, text=text, command=command).pack(fill="x", pady=3)

        self.on_main(build)

    def request_quit(self) -> None:
        if messagebox.askyesno(APP_NAME, "Arrêter Trading Journal ?\nL'application ne sera plus accessible dans le navigateur.", parent=self.root):
            self.close()


def run_gui() -> int:
    instance = SingleInstance()
    if instance.already_running:
        from . import config

        cfg = config.load()
        if cfg.configured:
            import webbrowser

            webbrowser.open(cfg.ui_url)
        return 0

    root = tk.Tk()
    root.title(f"{APP_NAME} {__version__}")
    root.geometry("520x380")
    root.minsize(520, 380)
    ttk.Style(root).theme_use("vista" if "vista" in ttk.Style(root).theme_names() else "clam")
    ui = TkUI(root)
    launcher = Launcher(ui)
    root.protocol("WM_DELETE_WINDOW", ui.request_quit)
    failure: list[str] = []

    def worker() -> None:
        try:
            launcher.prepare()
            launcher.start()
            launcher.ensure_account()
            ui.show_running(launcher)
            launcher.open_browser()
            launcher.auto_backup_if_due()
        except SetupCancelled:
            ui.on_main(ui.close) if not ui._closed else None  # noqa: SLF001
        except LauncherError as exc:
            failure.append(str(exc))
            log.error("%s", exc)
            try:
                ui.error(f"{APP_NAME} ne peut pas démarrer", str(exc))
            finally:
                ui.on_main(ui.close)
        except Exception as exc:  # noqa: BLE001
            log.exception("erreur inattendue")
            try:
                ui.error(APP_NAME, f"Erreur inattendue : {exc}\n\nJournal : {paths.logs_dir() / 'launcher.log'}")
            finally:
                ui.on_main(ui.close)

    threading.Thread(target=worker, daemon=True).start()
    try:
        root.mainloop()
    finally:
        launcher.stop()
        instance.release()
    return 1 if failure else 0
