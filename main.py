__version__ = "1.0.0"

import asyncio
import threading
import queue
import traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen

from telethon import TelegramClient, functions
from telethon.sessions import StringSession


# ============================================================
# TELEGRAM API CONFIG
# ============================================================

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"


# ============================================================
# ASYNC TELEGRAM WORKER
# ============================================================

class TelegramWorker:

    def __init__(self, callback):
        self.callback = callback
        self.thread = None
        self.loop = None
        self.client = None
        self.started = threading.Event()
        self.stopped = False

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.thread = threading.Thread(
            target=self._thread_main,
            name="TelegramAsyncWorker",
            daemon=True
        )

        self.thread.start()
        self.started.wait(timeout=5)

    def _thread_main(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.started.set()

        try:
            self.loop.run_forever()
        finally:
            try:
                if self.client:
                    self.loop.run_until_complete(
                        self.client.disconnect()
                    )
            except Exception:
                pass

            self.loop.close()

    def run(self, coro):
        self.start()

        if not self.loop:
            raise RuntimeError("Async loop was not created.")

        future = asyncio.run_coroutine_threadsafe(
            coro,
            self.loop
        )

        future.add_done_callback(self._future_done)

    def _future_done(self, future):
        try:
            result = future.result()

            self.callback(("result", result))

        except Exception as exc:
            self.callback(("error", exc))

    # ========================================================
    # LOGIN
    # ========================================================

    async def login(self, session_string):

        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass

        self.client = TelegramClient(
            StringSession(session_string.strip()),
            API_ID,
            API_HASH
        )

        await self.client.connect()

        authorized = await self.client.is_user_authorized()

        if not authorized:
            await self.client.disconnect()
            self.client = None

            raise ValueError(
                "This Session String is not authorized."
            )

        me = await self.client.get_me()

        return {
            "id": me.id,
            "name": (
                " ".join(
                    x for x in [
                        me.first_name,
                        me.last_name
                    ]
                    if x
                )
                or me.username
                or str(me.id)
            ),
            "username": me.username or ""
        }

    # ========================================================
    # GET TELEGRAM FOLDERS
    # ========================================================

    async def get_folders(self):

        result = await self.client(
            functions.messages.GetDialogFiltersRequest()
        )

        folders = []

        for item in result:

            if not hasattr(item, "id"):
                continue

            folder_id = item.id
            title = getattr(item, "title", None)

            if not title:
                continue

            folders.append({
                "id": int(folder_id),
                "title": str(title)
            })

        return [
            {
                "id": 0,
                "title": "All Chats"
            }
        ] + folders

    # ========================================================
    # GET DIALOGS
    # ========================================================

    async def get_dialogs(self, folder_id=0, limit=50):

        dialogs = []

        async for dialog in self.client.iter_dialogs(
            limit=limit,
            folder=folder_id
        ):

            name = dialog.name or "Unknown"

            if dialog.message:
                text = dialog.message.message or ""
            else:
                text = ""

            dialogs.append({
                "id": int(dialog.id),
                "name": name,
                "text": text.replace("\n", " "),
                "unread": int(dialog.unread_count or 0)
            })

        return dialogs

    # ========================================================
    # GET MESSAGES
    # ========================================================

    async def get_messages(self, chat_id, limit=50):

        messages = []

        async for message in self.client.iter_messages(
            chat_id,
            limit=limit
        ):

            text = message.message or ""

            if not text:
                continue

            sender_name = "Unknown"

            try:
                sender = await message.get_sender()

                if sender:
                    sender_name = (
                        getattr(sender, "first_name", None)
                        or getattr(sender, "title", None)
                        or getattr(sender, "username", None)
                        or "Unknown"
                    )

                    last_name = getattr(
                        sender,
                        "last_name",
                        None
                    )

                    if last_name:
                        sender_name = (
                            f"{sender_name} {last_name}"
                        )

            except Exception:
                pass

            messages.append({
                "id": int(message.id),
                "sender": sender_name,
                "text": text,
                "date": (
                    message.date.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if message.date
                    else ""
                ),
                "out": bool(message.out)
            })

        messages.reverse()

        return messages

    # ========================================================
    # SEND MESSAGE
    # ========================================================

    async def send_message(self, chat_id, text):

        text = text.strip()

        if not text:
            raise ValueError("Message is empty.")

        message = await self.client.send_message(
            chat_id,
            text
        )

        return {
            "id": int(message.id),
            "text": message.message or text
        }

    # ========================================================
    # ASYNC HELPERS
    # ========================================================

    def login_async(self, session_string):
        self.run(self.login(session_string))

    def folders_async(self):
        self.run(self.get_folders())

    def dialogs_async(self, folder_id):
        self.run(self.get_dialogs(folder_id))

    def messages_async(self, chat_id):
        self.run(self.get_messages(chat_id))

    def send_message_async(self, chat_id, text):
        self.run(self.send_message(chat_id, text))

    def stop(self):

        self.stopped = True

        if self.loop:
            self.loop.call_soon_threadsafe(
                self.loop.stop
            )


# ============================================================
# UI HELPERS
# ============================================================

def make_button(text, callback=None, height=dp(48)):

    button = Button(
        text=text,
        size_hint_y=None,
        height=height
    )

    if callback:
        button.bind(on_release=callback)

    return button


# ============================================================
# LOGIN SCREEN
# ============================================================

class LoginScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            padding=dp(20),
            spacing=dp(12)
        )

        root.add_widget(
            Label(
                text="Telegram Client",
                font_size="28sp",
                size_hint_y=None,
                height=dp(60)
            )
        )

        root.add_widget(
            Label(
                text=(
                    "Paste your Telethon Session String\n"
                    "to connect to your Telegram account."
                ),
                font_size="16sp",
                halign="center",
                valign="middle",
                size_hint_y=None,
                height=dp(70)
            )
        )

        self.session_input = TextInput(
            hint_text="Session String",
            multiline=True,
            size_hint_y=None,
            height=dp(130),
            padding=dp(12)
        )

        root.add_widget(self.session_input)

        self.status = Label(
            text="",
            size_hint_y=None,
            height=dp(50),
            halign="center",
            valign="middle"
        )

        root.add_widget(self.status)

        login_button = make_button(
            "Login",
            self.login
        )

        root.add_widget(login_button)

        root.add_widget(
            Label(
                text=(
                    "Keep your Session String private."
                ),
                font_size="12sp",
                halign="center",
                valign="middle"
            )
        )

        self.add_widget(root)

    def login(self, *_):

        session = self.session_input.text.strip()

        if not session:
            self.status.text = (
                "Please paste a Session String."
            )
            return

        self.status.text = "Connecting..."

        app = App.get_running_app()

        app.telegram.login_async(session)


# ============================================================
# DASHBOARD SCREEN
# ============================================================

class DashboardScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            padding=dp(8)
        )

        header = BoxLayout(
            size_hint_y=None,
            height=dp(55),
            spacing=dp(5)
        )

        self.account_label = Label(
            text="Telegram",
            font_size="20sp"
        )

        refresh = Button(
            text="Refresh",
            size_hint_x=None,
            width=dp(100)
        )

        refresh.bind(
            on_release=self.refresh_current_folder
        )

        header.add_widget(self.account_label)
        header.add_widget(refresh)

        root.add_widget(header)

        # ----------------------------------------------------
        # FOLDER BAR
        # ----------------------------------------------------

        self.folder_bar = ScrollView(
            size_hint_y=None,
            height=dp(52),
            do_scroll_y=False
        )

        self.folder_layout = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            spacing=dp(5)
        )

        self.folder_bar.add_widget(
            self.folder_layout
        )

        root.add_widget(self.folder_bar)

        # ----------------------------------------------------
        # CHAT LIST
        # ----------------------------------------------------

        self.chat_scroll = ScrollView()

        self.chat_layout = GridLayout(
            cols=1,
            spacing=dp(4),
            padding=dp(3),
            size_hint_y=None
        )

        self.chat_layout.bind(
            minimum_height=self.chat_layout.setter(
                "height"
            )
        )

        self.chat_scroll.add_widget(
            self.chat_layout
        )

        root.add_widget(self.chat_scroll)

        self.status = Label(
            text="",
            size_hint_y=None,
            height=dp(30),
            font_size="12sp"
        )

        root.add_widget(self.status)

        self.add_widget(root)

        self.current_folder = 0

    def set_account(self, name, username):

        if username:
            self.account_label.text = (
                f"{name}  @{username}"
            )
        else:
            self.account_label.text = name

    def set_folders(self, folders):

        self.folder_layout.clear_widgets()

        for folder in folders:

            button = Button(
                text=folder["title"],
                size_hint_x=None,
                width=max(
                    dp(105),
                    dp(18 * len(folder["title"]))
                )
            )

            folder_id = folder["id"]

            button.bind(
                on_release=lambda btn,
                fid=folder_id:
                    self.select_folder(fid)
            )

            self.folder_layout.add_widget(button)

        self.folder_layout.width = sum(
            child.width + dp(5)
            for child in self.folder_layout.children
        )

        if folders:
            self.select_folder(
                folders[0]["id"]
            )

    def select_folder(self, folder_id):

        self.current_folder = folder_id

        self.status.text = "Loading chats..."

        App.get_running_app().telegram.dialogs_async(
            folder_id
        )

    def refresh_current_folder(self, *_):

        self.select_folder(
            self.current_folder
        )

    def show_dialogs(self, dialogs):

        self.chat_layout.clear_widgets()

        if not dialogs:

            self.chat_layout.add_widget(
                Label(
                    text="No chats in this folder.",
                    size_hint_y=None,
                    height=dp(60)
                )
            )

        for dialog in dialogs:

            title = dialog["name"]

            if dialog["unread"]:
                title += (
                    f"  ({dialog['unread']} unread)"
                )

            text = dialog["text"]

            button = Button(
                text=(
                    f"{title}\n"
                    f"{text[:100]}"
                ),
                size_hint_y=None,
                height=dp(70),
                halign="left",
                valign="middle"
            )

            button.bind(
                on_release=lambda btn,
                chat_id=dialog["id"],
                name=dialog["name"]:
                    self.open_chat(
                        chat_id,
                        name
                    )
            )

            self.chat_layout.add_widget(button)

        self.status.text = (
            f"{len(dialogs)} chats"
        )

    def open_chat(self, chat_id, name):

        app = App.get_running_app()

        chat_screen = app.screen_manager.get_screen(
            "chat"
        )

        chat_screen.set_chat(
            chat_id,
            name
        )

        app.screen_manager.current = "chat"

        app.telegram.messages_async(
            chat_id
          )
      # ============================================================
# CHAT SCREEN
# ============================================================

class ChatScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(5),
            padding=dp(7)
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = BoxLayout(
            size_hint_y=None,
            height=dp(55),
            spacing=dp(5)
        )

        back = Button(
            text="Back",
            size_hint_x=None,
            width=dp(75)
        )

        back.bind(
            on_release=self.go_back
        )

        self.title_label = Label(
            text="Chat",
            font_size="19sp"
        )

        header.add_widget(back)
        header.add_widget(self.title_label)

        root.add_widget(header)

        # ----------------------------------------------------
        # MESSAGES
        # ----------------------------------------------------

        self.message_scroll = ScrollView()

        self.message_layout = GridLayout(
            cols=1,
            spacing=dp(7),
            padding=dp(5),
            size_hint_y=None
        )

        self.message_layout.bind(
            minimum_height=self.message_layout.setter(
                "height"
            )
        )

        self.message_scroll.add_widget(
            self.message_layout
        )

        root.add_widget(self.message_scroll)

        # ----------------------------------------------------
        # MESSAGE INPUT
        # ----------------------------------------------------

        input_bar = BoxLayout(
            size_hint_y=None,
            height=dp(55),
            spacing=dp(5)
        )

        self.message_input = TextInput(
            hint_text="Write a message...",
            multiline=False
        )

        send = Button(
            text="Send",
            size_hint_x=None,
            width=dp(80)
        )

        send.bind(
            on_release=self.send_message
        )

        self.message_input.bind(
            on_text_validate=self.send_message
        )

        input_bar.add_widget(
            self.message_input
        )

        input_bar.add_widget(send)

        root.add_widget(input_bar)

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status = Label(
            text="",
            size_hint_y=None,
            height=dp(25),
            font_size="11sp"
        )

        root.add_widget(self.status)

        self.add_widget(root)

        self.chat_id = None

    # ========================================================
    # SET CURRENT CHAT
    # ========================================================

    def set_chat(self, chat_id, name):

        self.chat_id = chat_id

        self.title_label.text = name

        self.message_layout.clear_widgets()

        self.status.text = "Loading messages..."

    # ========================================================
    # DISPLAY MESSAGES
    # ========================================================

    def show_messages(self, messages):

        self.message_layout.clear_widgets()

        if not messages:

            self.message_layout.add_widget(
                Label(
                    text="No text messages.",
                    size_hint_y=None,
                    height=dp(50)
                )
            )

        for message in messages:

            sender = message["sender"]
            text = message["text"]
            date = message["date"]

            if message["out"]:
                direction = "You"
            else:
                direction = sender

            label = Label(
                text=(
                    f"{direction}\n"
                    f"{text}\n"
                    f"{date}"
                ),
                size_hint_y=None,
                halign="left",
                valign="middle",
                padding=(dp(10), dp(7))
            )

            label.bind(
                texture_size=lambda instance, value:
                    setattr(
                        instance,
                        "height",
                        max(
                            dp(55),
                            value[1] + dp(14)
                        )
                    )
            )

            self.message_layout.add_widget(
                label
            )

        self.status.text = (
            f"{len(messages)} messages"
        )

        Clock.schedule_once(
            self.scroll_bottom,
            0.1
        )

    # ========================================================
    # SCROLL TO BOTTOM
    # ========================================================

    def scroll_bottom(self, *_):

        self.message_scroll.scroll_y = 0

    # ========================================================
    # SEND MESSAGE
    # ========================================================

    def send_message(self, *_):

        if not self.chat_id:
            return

        text = self.message_input.text.strip()

        if not text:
            return

        self.message_input.text = ""

        self.status.text = "Sending..."

        App.get_running_app().telegram.send_message_async(
            self.chat_id,
            text
        )

    # ========================================================
    # BACK TO DASHBOARD
    # ========================================================

    def go_back(self, *_):

        App.get_running_app().screen_manager.current = (
            "dashboard"
        )


# ============================================================
# MAIN APPLICATION
# ============================================================

class TelegramKivyApp(App):

    def build(self):

        self.title = "Telegram Client"

        # ----------------------------------------------------
        # THREAD → KIVY EVENT QUEUE
        # ----------------------------------------------------

        self.event_queue = queue.Queue()

        # ----------------------------------------------------
        # TELEGRAM WORKER
        # ----------------------------------------------------

        self.telegram = TelegramWorker(
            self.telegram_callback
        )

        # ----------------------------------------------------
        # SCREEN MANAGER
        # ----------------------------------------------------

        self.screen_manager = ScreenManager()

        # ----------------------------------------------------
        # LOGIN SCREEN
        # ----------------------------------------------------

        self.login_screen = LoginScreen(
            name="login"
        )

        # ----------------------------------------------------
        # DASHBOARD SCREEN
        # ----------------------------------------------------

        self.dashboard_screen = DashboardScreen(
            name="dashboard"
        )

        # ----------------------------------------------------
        # CHAT SCREEN
        # ----------------------------------------------------

        self.chat_screen = ChatScreen(
            name="chat"
        )

        # ----------------------------------------------------
        # ADD SCREENS
        # ----------------------------------------------------

        self.screen_manager.add_widget(
            self.login_screen
        )

        self.screen_manager.add_widget(
            self.dashboard_screen
        )

        self.screen_manager.add_widget(
            self.chat_screen
        )

        # ----------------------------------------------------
        # CHECK TELEGRAM EVENTS
        # ----------------------------------------------------

        Clock.schedule_interval(
            self.process_events,
            0.1
        )

        return self.screen_manager

    # ========================================================
    # TELEGRAM CALLBACK
    # ========================================================

    def telegram_callback(self, event):

        # This function runs from the Telegram thread.
        #
        # Kivy widgets must NOT be modified directly
        # from this thread.

        self.event_queue.put(event)

    # ========================================================
    # PROCESS BACKGROUND EVENTS
    # ========================================================

    def process_events(self, *_):

        while True:

            try:
                event_type, data = (
                    self.event_queue.get_nowait()
                )

            except queue.Empty:
                break

            if event_type == "error":

                self.handle_error(data)

            elif event_type == "result":

                self.handle_result(data)

    # ========================================================
    # HANDLE TELEGRAM RESULTS
    # ========================================================

    def handle_result(self, data):

        # ----------------------------------------------------
        # LOGIN RESULT
        # ----------------------------------------------------

        if (
            isinstance(data, dict)
            and "id" in data
            and "name" in data
            and "username" in data
        ):

            self.dashboard_screen.set_account(
                data["name"],
                data["username"]
            )

            self.login_screen.status.text = (
                "Login successful."
            )

            self.screen_manager.current = (
                "dashboard"
            )

            # Load folders after login.
            self.telegram.folders_async()

            return

        # ----------------------------------------------------
        # FOLDERS RESULT
        # ----------------------------------------------------

        if (
            isinstance(data, list)
            and all(
                isinstance(x, dict)
                and "id" in x
                and "title" in x
                for x in data
            )
        ):

            self.dashboard_screen.set_folders(
                data
            )

            return

        # ----------------------------------------------------
        # MESSAGES RESULT
        # ----------------------------------------------------

        if (
            isinstance(data, list)
            and all(
                isinstance(x, dict)
                and "sender" in x
                and "text" in x
                for x in data
            )
        ):

            self.chat_screen.show_messages(
                data
            )

            return

        # ----------------------------------------------------
        # DIALOGS RESULT
        # ----------------------------------------------------

        if (
            isinstance(data, list)
            and all(
                isinstance(x, dict)
                and "name" in x
                and "unread" in x
                for x in data
            )
        ):

            self.dashboard_screen.show_dialogs(
                data
            )

            return

        # ----------------------------------------------------
        # SENT MESSAGE RESULT
        # ----------------------------------------------------

        if (
            isinstance(data, dict)
            and "text" in data
            and "id" in data
        ):

            self.chat_screen.status.text = (
                "Message sent."
            )

            # Refresh messages after sending.
            if self.chat_screen.chat_id:

                self.telegram.messages_async(
                    self.chat_screen.chat_id
                )

    # ========================================================
    # HANDLE ERRORS
    # ========================================================

    def handle_error(self, error):

        message = str(error)

        # Keep UI error messages reasonably short.
        if len(message) > 500:
            message = (
                message[:500] + "..."
            )

        traceback.print_exc()

        current = self.screen_manager.current

        # ----------------------------------------------------
        # LOGIN ERROR
        # ----------------------------------------------------

        if current == "login":

            self.login_screen.status.text = (
                f"Login failed: {message}"
            )

        # ----------------------------------------------------
        # DASHBOARD ERROR
        # ----------------------------------------------------

        elif current == "dashboard":

            self.dashboard_screen.status.text = (
                f"Error: {message}"
            )

        # ----------------------------------------------------
        # CHAT ERROR
        # ----------------------------------------------------

        elif current == "chat":

            self.chat_screen.status.text = (
                f"Error: {message}"
            )

    # ========================================================
    # APP STOP
    # ========================================================

    def on_stop(self):

        try:
            self.telegram.stop()

        except Exception:
            pass


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    TelegramKivyApp().run()
