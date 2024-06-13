import os
import sys
import time
import threading
import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QFont, QIcon, QPainter, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QPropertyAnimation, QEventLoop
import spotipy
import syncedlyrics
import configparser

class LyricsFetcher:
    """Class to handle lyrics fetching and storage."""
    LYRICS_DIR = "./Lyrics"
    NO_LYRICS_FILE = os.path.join(LYRICS_DIR, "no_lyrics_list.txt")
    CONFIG = configparser.ConfigParser("./config.ini")
    
    @staticmethod
    def check_if_no_lyrics(song):
        with open(LyricsFetcher.NO_LYRICS_FILE, "r") as f:
            for line in f:
                if line.strip() == song:
                    return True
        return False

    @staticmethod
    def fetch_lyrics(song):
        try:
            lrc = syncedlyrics.search(song)
            if lrc:
                with open(f"{LyricsFetcher.LYRICS_DIR}/{song}.lrc", "w", encoding="utf-8") as f:
                    f.write(lrc)
                return lrc
            else:
                with open(LyricsFetcher.NO_LYRICS_FILE, "a") as f:
                    f.write(f"{song}\n")
                return None
        except Exception as e:
            with open(LyricsFetcher.NO_LYRICS_FILE, "a") as f:
                f.write(f"{song}\n")
            raise e

class SpotifyClient:
    """Class to interact with Spotify API."""
    SCOPE = "user-read-currently-playing"
    
    def __init__(self):
        self.spotify_oauth = spotipy.SpotifyOAuth(client_id=self.CONFIG["SPOTIFY"]["CLIENT_ID"],
                                            client_secret=self.CONFIG["SPOTIFY"]["CLIENT_SECRET"],
                                            redirect_uri="https://google.com",
                                            scope=self.SCOPE)
        self.spotify = None
    
    def get_current_track(self):
        try:
            token = self.spotify_oauth.get_cached_token()
            if token:
                self.spotify = spotipy.Spotify(auth=token['access_token'])
                return self.spotify.currently_playing()
            else:
                return None
        except Exception as e:
            print(f"Error getting current track: {e}")
            return None

    @staticmethod
    def ms_to_sec(ms):
        return int(ms / 1000)

    @staticmethod
    def ts_to_sec(ts):
        ts = ts.strip("[]")
        minutes, seconds = map(int, ts.split(":"))
        return minutes * 60 + seconds

class Main(QObject):
    new_message = pyqtSignal(str)
    detail_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.spotify_client = SpotifyClient()
        self.song = None
        self.raw_song = ""
        self.updated_time = 0
        self.blast = False

    def start(self):
        while not self.blast:
            result = self.get_song()
            if result is True:
                lyrics_result = self.get_lyrics()
                if lyrics_result is True:
                    self.show_lyrics()
                else:
                    self.new_message.emit(lyrics_result)
            else:
                self.detail_message.emit(result)
                self.new_message.emit("....")
            time.sleep(1)

    def get_song(self):
        current = self.spotify_client.get_current_track()
        if current:
            current_type = current['currently_playing_type']
            if current_type == "track":
                title = f"[{current['item']['name']}] [{current['item']['artists'][0]['name']}]"
                self.raw_song = f"{current['item']['name']} - {current['item']['artists'][0]['name']}"
                length_ms = current['item']['duration_ms']
                progress_ms = current['progress_ms']
                self.updated_time = SpotifyClient.ms_to_sec(progress_ms)
                self.song = title
                if LyricsFetcher.check_if_no_lyrics(self.song):
                    return f"{self.raw_song} - No Lyrics"
                return True
            elif current_type == "ad":
                return "Ad Is Playing"
        else:
            return "Nothing Playing On Spotify"

    def get_lyrics(self):
        if not LyricsFetcher.check_if_no_lyrics(self.song):
            lyrics_path = f"{LyricsFetcher.LYRICS_DIR}/{self.song}.lrc"
            if not os.path.exists(lyrics_path):
                try:
                    self.new_message.emit("Getting Lyrics...")
                    lyrics = LyricsFetcher.fetch_lyrics(self.song)
                    if lyrics:
                        return True
                    else:
                        return f"{self.raw_song} - No Lyrics"
                except Exception as e:
                    return f"Error occurred while getting lyrics: {e}"
            else:
                return True
        else:
            return f"{self.raw_song} - No Lyrics"

    def play_line(self, pause_event, skip_event, kill_event):
        self.new_message.emit("...")
        self.detail_message.emit(f"{self.raw_song} - Playing")
        current = self.spotify_client.get_current_track()
        progress_ms = SpotifyClient.ms_to_sec(current["progress_ms"])
        
        with open(f"{LyricsFetcher.LYRICS_DIR}/{self.song}.lrc", "r", encoding="utf-8") as f:
            lines = f.readlines()

        i = 0
        last_time = 0
        while i < len(lines):
            if kill_event.is_set():
                return
            if pause_event.is_set():
                while pause_event.is_set():
                    time.sleep(0.1)
            if skip_event.is_set():
                i = 0
                new_time = SpotifyClient.ms_to_sec(self.spotify_client.get_current_track()["progress_ms"])
                progress_ms = new_time
                self.updated_time = new_time
                skip_event.clear()
                continue

            ts = SpotifyClient.ts_to_sec(lines[i].split("]")[0])
            self.updated_time = ts
            if ts >= progress_ms:
                self.sleep_check_pause(ts - progress_ms, pause_event)
                self.new_message.emit(lines[i].split("]")[1].strip())
                last_time = ts
            else:
                i += 1
                continue

            i += 1

    def show_lyrics(self):
        pause_event = threading.Event()
        skip_event = threading.Event()
        kill_event = threading.Event()
        thread = threading.Thread(target=self.play_line, args=(pause_event, skip_event, kill_event))
        thread.start()
        paused = False

        while not self.blast:
            if not thread.is_alive():
                self.detail_message.emit("Spotify Lyrics Shower...")
                return "Song Ended"
            current = self.spotify_client.get_current_track()
            if not current:
                kill_event.set()
                self.detail_message.emit("Spotify Lyrics Shower...")
                return "Spotify OFF!"
            try:
                title = f"[{current['item']['name']}] [{current['item']['artists'][0]['name']}]"
                if self.song != title:
                    kill_event.set()
                    return "Song Changed"
                new_time = SpotifyClient.ms_to_sec(current["progress_ms"])
                if abs(new_time - self.updated_time) > 10:
                    skip_event.set()
                self.detail_message.emit(f"{self.raw_song} - Playing")
            except Exception as e:
                if not paused:
                    self.detail_message.emit(f"{self.raw_song} - Paused")
                    pause_event.set()
                    paused = True
            time.sleep(1)

    @staticmethod
    def sleep_check_pause(duration, pause_event):
        start_time = time.time()
        while time.time() - start_time < duration:
            if pause_event.is_set():
                while pause_event.is_set():
                    time.sleep(0.1)
                return
            time.sleep(0.1)

class TextOverlayApp:
    def __init__(self):
        self.app = QApplication([])
        self.window = QWidget()
        self.window.setAttribute(Qt.WA_TranslucentBackground)
        self.window.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
        self.window.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.layout.setContentsMargins(0, 0, 30, 50)
        
        self.label = QLabel("....")
        self.label.setStyleSheet("color: rgba(255, 255, 255, 255);")
        self.label.setFont(QFont("Dancing Script", 25))
        self.label.setAlignment(Qt.AlignRight)

        self.details = QLabel("Spotify Lyrics Shower!")
        self.details.setStyleSheet("color: rgba(255, 255, 255, 255); font-weight: 500px")
        self.details.setFont(QFont("Dancing Script", 20))
        self.details.setAlignment(Qt.AlignRight)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.details)
        self.window.setLayout(self.layout)
        
        self.setup_tray_icon()

        self.main = Main()
        self.main.new_message.connect(self.update_label_text)
        self.main.detail_message.connect(self.update_detail_text)

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self.window)
        self.tray_icon.setIcon(QIcon("icon.png"))

        show_action = QAction("Show", self.window)
        hide_action = QAction("Hide", self.window)
        quit_action = QAction("Exit", self.window)
        show_action.triggered.connect(self.window.show)
        hide_action.triggered.connect(self.window.hide)
        quit_action.triggered.connect(self.quit_app)

        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def update_label_text(self, text):
        self.label.setText(text)
        self.animate_label_opacity(self.label)

    def update_detail_text(self, text):
        self.details.setText(text)
        self.animate_label_opacity(self.details)

    @staticmethod
    def animate_label_opacity(label):
        opacity_effect = QGraphicsOpacityEffect()
        label.setGraphicsEffect(opacity_effect)
        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(1000)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.start()

    def quit_app(self):
        self.main.blast = True
        self.app.quit()

    def run(self):
        self.window.show()
        self.main_thread = threading.Thread(target=self.main.start)
        self.main_thread.start()
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    print("Program Made By Praveen, Github:- https://github.com/Praveen-debug")
    app = TextOverlayApp()
    app.run()
