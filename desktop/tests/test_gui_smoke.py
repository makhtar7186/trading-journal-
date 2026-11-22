"""Test automatisé de l'interface Tk : on pilote les vrais widgets (fenêtres placées hors écran). Ignoré sans affichage."""
import threading
import time
import tkinter as tk
from tkinter import ttk

import pytest

from tjlauncher import gui
from tjlauncher.ui import SetupCancelled


@pytest.fixture(scope="module")
def tk_root():
    """Une seule racine Tk pour tout le module : en recréer plusieurs dans un même processus échoue parfois sous Windows."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"pas d'affichage graphique : {exc}")
    root.geometry("520x380+4000+4000")  # hors écran : aucun clignotement chez l'utilisateur
    root.update()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def ui(tk_root):
    instance = gui.TkUI(tk_root)
    yield instance
    instance._closed = True  # noqa: SLF001 (arrête la pompe de ce TkUI)
    for child in tk_root.winfo_children():
        child.destroy()


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def dialog_of(root):
    return next((w for w in root.winfo_children() if isinstance(w, tk.Toplevel)), None)


def button(top, text):
    return next(w for w in walk(top) if isinstance(w, ttk.Button) and w.cget("text") == text)


def entries(top):
    return [w for w in walk(top) if isinstance(w, ttk.Entry)]


def labels(top):
    return [w.cget("text") for w in walk(top) if isinstance(w, ttk.Label)]


def schedule(root, action, delay=150):
    """Exécute `action(dialog)` dans le thread Tk dès que la boîte de dialogue modale est affichée."""
    def poll(tries=0):
        top = dialog_of(root)
        if top is None and tries < 60:
            root.after(50, poll, tries + 1)
        elif top is not None:
            action(top)

    root.after(delay, poll)


def test_status_and_progress_are_marshalled_from_a_worker_thread(ui):
    done = threading.Event()

    def worker():
        ui.status("Téléchargement de PostgreSQL…")
        ui.progress(0.5)
        ui.progress(None)
        done.set()

    threading.Thread(target=worker, daemon=True).start()
    deadline = time.monotonic() + 5
    while not done.is_set() and time.monotonic() < deadline:
        ui.root.update()  # le thread Tk traite la file d'appels (toutes les 40 ms)
        time.sleep(0.01)
    assert done.is_set() and ui.status_var.get() == "Téléchargement de PostgreSQL…"


def test_choose_returns_the_index_of_the_clicked_option(ui):
    schedule(ui.root, lambda top: button(top, "Utiliser un serveur PostgreSQL existant").invoke())
    assert ui.choose("PostgreSQL absent", "Que faire ?", ["Installer PostgreSQL", "Utiliser un serveur PostgreSQL existant", "Quitter"]) == 1


def test_closing_the_choice_dialog_means_cancel(ui):
    schedule(ui.root, lambda top: top.destroy())
    assert ui.choose("t", "m", ["a", "b"]) is None


def test_secret_prompt_masks_input_and_returns_the_typed_value(ui):
    def act(top):
        field = entries(top)[0]
        assert field.cget("show") == "•"  # jamais affiché en clair
        field.insert(0, "mon-mot-de-passe")
        button(top, "Continuer").invoke()

    schedule(ui.root, act)
    assert ui.ask_secret("PostgreSQL", "Mot de passe de postgres ?") == "mon-mot-de-passe"


def test_secret_prompt_cancel_and_error_message(ui):
    seen = {}

    def act(top):
        seen["labels"] = labels(top)
        button(top, "Annuler").invoke()

    schedule(ui.root, act)
    assert ui.ask_secret("t", "m", error="Mot de passe incorrect.") is None
    assert "Mot de passe incorrect." in seen["labels"]


def test_connection_dialog_validates_the_port(ui):
    def act(top):
        fields = entries(top)  # hôte, port, utilisateur, mot de passe
        fields[1].delete(0, "end")
        fields[1].insert(0, "pas-un-port")
        button(top, "Continuer").invoke()  # refusé : la fenêtre reste ouverte
        assert dialog_of(ui.root) is top and "Port invalide." in labels(top)
        fields[1].delete(0, "end")
        fields[1].insert(0, "5433")
        fields[3].insert(0, "secret")
        button(top, "Continuer").invoke()

    schedule(ui.root, act)
    assert ui.ask_connection() == {"host": "127.0.0.1", "port": 5433, "user": "postgres", "password": "secret"}


def test_account_dialog_shows_server_errors_then_accepts_a_correction(ui):
    calls = []

    def create(values):
        calls.append(values)
        if len(calls) == 1:
            return {"ok": False, "errors": {"password": ["Ce mot de passe est trop courant."]}}
        return {"ok": True, "username": values["username"]}

    def act(top):
        fields = entries(top)  # identifiant, e-mail, mot de passe, confirmation
        assert [f.cget("show") for f in fields] == ["", "", "•", "•"]
        fields[0].insert(0, "alice")
        fields[2].insert(0, "password123")
        fields[3].insert(0, "autre")
        button(top, "Créer le compte").invoke()  # confirmation différente : refusé AVANT tout appel serveur
        assert calls == [] and "Les mots de passe ne correspondent pas." in labels(top)
        fields[3].delete(0, "end")
        fields[3].insert(0, "password123")
        button(top, "Créer le compte").invoke()  # le serveur refuse : message affiché, fenêtre ouverte
        assert len(calls) == 1 and "Ce mot de passe est trop courant." in labels(top) and dialog_of(ui.root) is top
        fields[2].delete(0, "end")
        fields[3].delete(0, "end")
        for f in (fields[2], fields[3]):
            f.insert(0, "Correct-horse-battery-9")
        # messagebox.showinfo bloquerait : on la neutralise pour ce test
        gui.messagebox.showinfo = lambda *a, **k: None
        button(top, "Créer le compte").invoke()

    schedule(ui.root, act)
    assert ui.account_dialog(create) is True
    assert calls[1]["username"] == "alice" and calls[1]["password"] == "Correct-horse-battery-9"
    assert "confirm" not in calls[1]  # la confirmation n'est jamais envoyée au lanceur


def test_account_dialog_later_returns_false_without_creating_anything(ui):
    created = []
    schedule(ui.root, lambda top: button(top, "Plus tard").invoke())
    assert ui.account_dialog(lambda values: created.append(values) or {"ok": True}) is False and created == []


def test_calls_after_the_window_is_closed_cancel_the_setup_instead_of_hanging(ui):
    ui._closed = True  # noqa: SLF001 (état après fermeture de la fenêtre ; close() détruirait la racine partagée)
    errors = []

    def worker():
        try:
            ui.status("x")
        except SetupCancelled:
            errors.append("annulé")

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=3)
    assert not thread.is_alive() and errors == ["annulé"]
