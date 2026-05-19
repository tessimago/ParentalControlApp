"""
Fullscreen popup message that's impossible to miss.
Spawned as a subprocess so it works from both the service companion and run_dev.py.
Usage: python popup.py "Your message here" [timeout_seconds]
"""
import sys
import tkinter as tk


def show_popup(message, timeout=60, header_name="PARENTAL CONTROL",
               msg_from="MESSAGE FROM", closes_in_tpl="Closes in {seconds}s — or click OK",
               click_ok_text="Click OK to dismiss"):
    root = tk.Tk()
    root.title("Parental Control")
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.configure(bg="#1a1a2e")
    root.overrideredirect(True)

    root.protocol("WM_DELETE_WINDOW", lambda: None)

    frame = tk.Frame(root, bg="#1a1a2e")
    frame.place(relx=0.5, rely=0.5, anchor="center")

    header = tk.Label(
        frame,
        text=f"{msg_from} {header_name.upper()}",
        font=("Segoe UI", 18, "bold"),
        fg="#4fc3f7",
        bg="#1a1a2e"
    )
    header.pack(pady=(0, 30))

    msg_label = tk.Label(
        frame,
        text=message,
        font=("Segoe UI", 36, "bold"),
        fg="#ffffff",
        bg="#1a1a2e",
        wraplength=900,
        justify="center"
    )
    msg_label.pack(pady=(0, 40))

    remaining = tk.IntVar(value=timeout if timeout > 0 else 0)
    countdown_text = tk.StringVar()

    if timeout > 0:
        countdown_text.set(closes_in_tpl.replace("{seconds}", str(timeout)))
    else:
        countdown_text.set(click_ok_text)

    countdown_label = tk.Label(
        frame,
        textvariable=countdown_text,
        font=("Segoe UI", 14),
        fg="#90a4ae",
        bg="#1a1a2e"
    )
    countdown_label.pack(pady=(0, 20))

    # OK button
    btn = tk.Button(
        frame,
        text="OK",
        font=("Segoe UI", 16, "bold"),
        fg="#1a1a2e",
        bg="#4fc3f7",
        activebackground="#81d4fa",
        activeforeground="#1a1a2e",
        width=12,
        height=1,
        relief="flat",
        cursor="hand2",
        command=root.destroy
    )
    btn.pack()

    def tick():
        if timeout > 0:
            left = remaining.get() - 1
            if left <= 0:
                root.destroy()
                return
            remaining.set(left)
            countdown_text.set(closes_in_tpl.replace("{seconds}", str(left)))
        root.after(1000, tick)

    if timeout > 0:
        root.after(1000, tick)

    # Allow Escape to close after 3 seconds (so child can't instantly dismiss)
    def enable_escape():
        root.bind("<Escape>", lambda e: root.destroy())

    root.after(3000, enable_escape)

    # Keep on top
    def stay_on_top():
        try:
            root.attributes("-topmost", True)
            root.lift()
            root.after(500, stay_on_top)
        except tk.TclError:
            pass

    stay_on_top()

    root.mainloop()


if __name__ == "__main__":
    message = sys.argv[1] if len(sys.argv) > 1 else "Hello!"
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    header_name = sys.argv[3] if len(sys.argv) > 3 else "PARENTAL CONTROL"
    msg_from = sys.argv[4] if len(sys.argv) > 4 else "MESSAGE FROM"
    closes_in_tpl = sys.argv[5] if len(sys.argv) > 5 else "Closes in {seconds}s — or click OK"
    click_ok_text = sys.argv[6] if len(sys.argv) > 6 else "Click OK to dismiss"
    show_popup(message, timeout, header_name, msg_from, closes_in_tpl, click_ok_text)
