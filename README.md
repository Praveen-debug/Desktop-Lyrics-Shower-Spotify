# Desktop Lyrics Shower 

This is a program written in Python that allows you to display lyrics from Spotify on your desktop, similar to Rainmeter, using your Spotify client ID and secret. It utilizes the Spotify API to retrieve details about the song you are listening to, uses a package called Synced Lyrics to get the lyrics, and employs PyQt5 to display the lyrics directly on your desktop. Written by Praveen.

Windows Only!

# Installtion

First, get your client ID and client secret from the Spotify Developer Console. Then, create a file named `creds.ini` and paste your client ID and secret like this.

```
["SPOTIFY"]
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SCERET"
```

To Install the pacakages required for the program, run `pip install -r requirements.txt` on project directory.

# Usage

To run the app just run `python3 main.py` and it should work. 

Please let me know if there's any issue with the program.

By Praveen K