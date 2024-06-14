import time
import spotipy
import datetime
import syncedlyrics
import threading
import os
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QPainter
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QPropertyAnimation, QSequentialAnimationGroup, QParallelAnimationGroup, QEasingCurve, QEventLoop
from PyQt5.QtGui import QIcon
import configparser

class Main(QObject):
    scope = "user-read-currently-playing"
    song = None
    counter = 0
    oldTime = 0
    startAgain = False

    count = 0

    current_time = datetime.datetime.now()
    startTime = float(current_time.minute) * 60 + float(str(current_time.second) + "." + str(current_time.microsecond))
    config = configparser.ConfigParser()
    config.read("creds.ini")
    print(config.get("SPOTIFY", "CLIENT_ID"))
    print(config.get("SPOTIFY", "CLIENT_SECRET"))
    spotifyOAuth = spotipy.SpotifyOAuth(client_id=config.get("SPOTIFY", "CLIENT_ID"),
                                            client_secret=config.get("SPOTIFY", "CLIENT_SECRET"),
                                            redirect_uri="https://google.com",
                                            scope=scope)
    paused = False

    skiped = False

    updated_time = 0
    blast = False

    stop_thread = False
    new_message = pyqtSignal(str)
    detail_message = pyqtSignal(str)

    raw_song = ""


    def check_if_song(self):
        with open("./Lyrics/no_lyrics_list.txt", "r") as f:
            f.readline()
            for line in f:
                if line == self.song or line == self.song + "\n":
                    return True
                
            return False

    def start(self):
        while True:
            if self.blast:
                exit()
            result = self.get_song()
            if result != True:
                self.detail_message.emit(result)
                self.new_message.emit("....")
                continue
            else:
                result = self.getlyrics()
                if result != True:
                    self.new_message.emit(result)
                else:
                    self.new_message.emit("...")
                    result = self.show_lyrics()

    def get_current(self):
        try:
            token = self.spotifyOAuth.get_cached_token()
            spotifyObject = spotipy.Spotify(auth=token['access_token'])
            current = spotifyObject.currently_playing()
            return current
        except:
            return None
    def ms_to_sec(self, ms):
        total_seconds = ms / 1000
        minutes = int(total_seconds // 60)
        min_secs = int(minutes * 60)
        seconds = int(total_seconds % 60) + min_secs
        time_str = f"{seconds}"
        return time_str

    def ts_to_sec(self, ts):
        ts = str(ts)
        ts = ts.replace("]", "").replace("[", "")
        ts = ts.split(".")[0]
        seconds = int(ts.split(":")[0]) * 60 + int(ts.split(":")[1])
        return seconds

    def get_song(self):
        try:
            current = self.get_current()
            # print("Current is", current)
            if current:
                current_type = current['currently_playing_type']
                if current_type == "track":
                    title = "[" + current['item']['name'] + "] [" + current["item"]["artists"][0]["name"] + "]"
                    self.raw_song = current['item']['name'] + " - " + current["item"]["artists"][0]["name"]
                    print("Got track", title)
                    length_ms = current['item']['duration_ms']
                    progress_ms = current['progress_ms']
                    self.updated_time = int(self.ms_to_sec(int(current["progress_ms"])))
                    self.song = title
                    with open("./Lyrics/no_lyrics_list.txt", "r") as f:
                        lines = f.readlines()
                        for line in lines:
                            if line == self.song + "\n":
                                return self.raw_song + " - No Lyrics"
                    return True
                elif current_type == "ad":
                    print(">> ad popped up -- sleeping...")
                    return "Ad Is playing"
            else:
                return "Nothing Playing On Spotify"
        except Exception as e:
            return "Error Occured While Trying To Get Song!" + str(e)

    def getlyrics(self):
        print("Getting lyrics")
        if not self.check_if_song():
            if not os.path.exists(f"./Lyrics/{self.song}" + ".lrc"):
                try:
                    self.new_message.emit("Getting Lyrics...")
                    lrc = syncedlyrics.search(self.song)
                    if lrc or lrc == "":
                        with open(f"Lyrics/{self.song}" + ".lrc", "w", encoding="utf-8") as f:
                            f.write(lrc)
                            f.close()
                        return True
                    else:
                        with open("./Lyrics/no_lyrics_list.txt", "a") as f:
                            f.write(self.song + "\n")
                            f.close()
                        return self.raw_song + " - No Lyrics"
                except Exception as e:
                    with open("./Lyrics/no_lyrics_list.txt", "a") as f:
                            f.write(self.song + "\n")
                            f.close()
                    return "Error occured while getting lyrics"
            else:
                return True
        else:
            return "Error occured while getting lyrics"

    def play_line(self, pause_event, skip_event, kill_event):
        self.new_message.emit("...")
        self.detail_message.emit(self.raw_song + " - Playing")
        current = self.get_current()
        progress_ms = int(self.ms_to_sec(int(current["progress_ms"])))
        lines = None
        counter = 0
        last_time = 0
        with open(f"Lyrics/{self.song}" + ".lrc", "r", encoding="utf-8") as f:
            lines = f.read()
            lines = lines.split("\n")
        i = 0
        kill_trigger = False
        while i <= len(lines) - 1:
            try:
                test = lines[i+1]
            except:
                kill_trigger = True
            if kill_event.is_set():
                return
            if pause_event.is_set():
                print("Song paused!")
                while pause_event.is_set():
                    time.sleep(0.1)
                print("Song resumed")
            if skip_event.is_set():
                self.new_message.emit("...")
                print("Song skipped\n\n\n\n")
                i = 0
                counter = 0
                new_time = int(self.ms_to_sec(self.get_current()["progress_ms"]))
                progress_ms = new_time
                self.skiped = False
                self.updated_time = new_time
                skip_event.clear()
                continue
            ts = lines[i].split("]")[0]
            ts = self.ts_to_sec(ts)
            self.updated_time = ts
            if counter == 0:
                self.new_message.emit("...")
                if ts >= progress_ms:
                    self.sleep_check_pause(int(ts) - int(progress_ms), pause_event)
                    emmit_lyrics = lines[i].split("]")[1]
                    self.new_message.emit(emmit_lyrics)
                    if self.paused:
                        i = 0
                        counter = 0
                        self.paused = False
                        continue
                    last_time = ts
                    counter += 1
                else:
                    i += 1
                    continue
            else:
                ts = lines[i].split("]")[0]
                ts = self.ts_to_sec(ts)
                self.sleep_check_pause(ts - last_time, pause_event)
                if self.paused:
                    i = 0
                    counter = 0
                    self.paused = False
                    progress_ms = int(self.ms_to_sec(self.get_current()["progress_ms"]))
                    continue
                emmit_lyrics = lines[i].split("]")[1]
                self.new_message.emit(emmit_lyrics)
                last_time = ts
            i += 1
            if kill_trigger:
                return

    def show_lyrics(self):
        """
        Starts a thread to play the lyrics for the current song.
        """

        pause_event = threading.Event()
        skip_event = threading.Event()
        kill_event = threading.Event()
        thread = threading.Thread(target=self.play_line, args=(pause_event, skip_event, kill_event, ))
        thread.start()
        paused = False
        resumed = True
        while True:
            if self.blast:
                kill_event.set()
                return
            if not thread.is_alive():
                self.detail_message.emit("Spotify Lyrics Shower...")
                return "Song Ended"
            current = self.get_current()
            if not current:
                kill_event.set()
                self.detail_message.emit("Spotify Lyrics Shower...")
                return "Spotify OFF!"
            try:
                resuming = current["actions"]["disallows"]["resuming"]
                title = "[" + current['item']['name'] + "] [" + current["item"]["artists"][0]["name"] + "]"
                if self.song != title:
                    print("Song changed! Breaking!")
                    kill_event.set()
                    return
                new_time = int(self.ms_to_sec(int(current["progress_ms"])))

                if not new_time <= self.updated_time+10 or not new_time >= self.updated_time-10:
                    skip_event.set()
                    self.skiped = True
                if not resumed:
                    pause_event.clear()
                    resumed = True
                    paused = False
                self.detail_message.emit(self.raw_song + " - Playing")
            except Exception as e:
                if not paused:
                    self.detail_message.emit(self.raw_song + " - Paused")
                    pause_event.set()
                    resumed = False
                    paused = True
            time.sleep(1)

    def sleep_check_pause(self, duration, pause_event):

        start_time = time.time()
        while time.time() - start_time < duration:
            if pause_event.is_set():
                print("Song paused!")
                while pause_event.is_set():
                    time.sleep(0.1)
                self.paused = True
                if not pause_event.is_set():
                    print("Song resumed!")
                return
            time.sleep(0.1)
class text_class:
    def window(self):
        app = QApplication([])
        window = QWidget()
        # window.setWindowFlags(Qt.FramelessWindowHint)
        window.setAttribute(Qt.WA_TranslucentBackground)
        window.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
        screen_geometry = app.primaryScreen().geometry()
        window.setGeometry(screen_geometry)

        window.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Tool
        )

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        layout.setContentsMargins(0, 0, 30, 50)

        self.label = QLabel()
        self.label.setText("....")
        self.label.setStyleSheet("color: rgba(255, 255, 255, 255);")
        self.label.setFont(QFont("Dancing Script", 25))
        self.label.setFixedWidth(screen_geometry.width() - 100) 
        self.label.setAlignment(Qt.AlignRight)

        self.details = QLabel()
        self.details.setText("Spotify Lyrics Shower!")
        self.details.setStyleSheet("color: rgba(255, 255, 255, 255); font-weight: 500px")
        self.details.setFont(QFont("Dancing Script", 20))
        self.details.setFixedWidth(screen_geometry.width() - 100) 
        self.details.setAlignment(Qt.AlignRight)


        label_effect = QGraphicsOpacityEffect(self.label, opacity=1.0)
        self.label.setGraphicsEffect(label_effect)
        self._animation = QPropertyAnimation(
            self.label,
            propertyName=b"opacity",
            targetObject=label_effect,
            duration=300,
            startValue=0.0,
            endValue=1.0,
        )


        details_effect = QGraphicsOpacityEffect(self.details, opacity=1.0)
        self.details.setGraphicsEffect(details_effect)
        self._animation_details = QPropertyAnimation(
            self.details,
            propertyName=b"opacity",
            targetObject=details_effect,
            duration=100,
            startValue=0.0,
            endValue=1.0,
        )


        layout.addWidget(self.label)
        layout.addWidget(self.details)

        window.setLayout(layout)
        
        self.main = Main()
        self.main.new_message.connect(self.update_label_text)
        self.main.detail_message.connect(self.update_detail_Text)
        self.tray_icon = QSystemTrayIcon(window)
        self.tray_icon.setIcon(QIcon("icon.png")) 

        show_action = QAction("Show", window)
        quit_action = QAction("Exit", window)
        hide_action = QAction("Hide", window)
        show_action.triggered.connect(window.show)
        hide_action.triggered.connect(window.hide)
        quit_action.triggered.connect(self.quit_app)

        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.win_copy = window
        return window, app

    def update_label_text(self, lyrics):
        if self.label.text() != lyrics:
            self.fade_out()
            self.label.setText(lyrics)
            self.fade_in()

    def quit_app(self):
        self.tray_icon.hide()
        self.win_copy.hide()
        self.main.blast = True
        QApplication.exit()
        app.exit()
        exit(0)

    def update_detail_Text(self, details):
        if details != self.details.text():
            loop = QEventLoop()
            self._animation_details.finished.connect(loop.quit)
            self._animation_details.setDirection(QPropertyAnimation.Backward)
            self._animation_details.start()
            loop.exec_()
            self.details.setText(details)
            self._animation_details.setDirection(QPropertyAnimation.Forward)
            self._animation_details.start()

    def fade_in(self):
        self._animation.setDirection(QPropertyAnimation.Forward)
        self._animation.start()

    def fade_out(self):
        loop = QEventLoop()
        self._animation.finished.connect(loop.quit)
        self._animation.setDirection(QPropertyAnimation.Backward)
        self._animation.start()
        loop.exec_()

if __name__ == "__main__":
    program = text_class()
    window, app = program.window()
    window.show()
    threading.Thread(target=program.main.start).start()
    app.exec()