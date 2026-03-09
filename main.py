from tkinter import Tk

from app import AutoClickerApp


if __name__ == "__main__":
    app_root = Tk()
    app = AutoClickerApp(app_root)
    app_root.mainloop()