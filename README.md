```
██╗  ██╗██████╗  ██████╗ ███████╗
██║ ██╔╝██╔══██╗██╔═══██╗╚══███╔╝      😻
█████╔╝ ██████╔╝██║   ██║  ███╔╝     Control
██╔═██╗ ██╔══██╗██║   ██║ ███╔╝       Deck
██║  ██╗██║  ██║╚██████╔╝███████╗
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
```

Extra OBS frontend controls for KROZ

## Installation
1. Save files to a known location. For example, `C:\Program Files\obs-studio\data\obs-plugins\frontend-tools\scripts\KROZControlDeck\`
2. Open OBS
3. Click `Tools > Scripts`
4. Click `+`
5. Browse to the path where you saved the files
6. Select `KROZControlDeck.py`

*Note: (you do not need to add the other python files, but they do need to be in the same folder)*

## Usage
The KROZ Control Deck has two sets of features: a recording controls GUI and a video file combiner. They are intended to be used together for users who record long sessions and don't like or want to do much editing.

Here's an example usage:
1. User starts recording
2. User reaches an arbitrary "checkpoint" in the recording where they are satisfied with their progress so far, so they hit the `Checkpoint` button
3. User continues recording and saving "checkpoints" as they go
4. User makes a mistake, so they hit the `Reset` button. This essentially takes them back to their last checkpoint and they must resume from there.
5. After the user has finished all of their recordings, they use the `Combine` button to concatenate all of the checkpoints to a single file.

### Recording Controls
The recording controls GUI is designed to be an obscenely large recording indicator, so that the user (or passers by) can easily see whether or not a recording is in progress. Pressing the recording indicator will start, resume, pause, or stop the recording depending on the current state and the script settings.

The `Checkpoint` button will stop the current recording and begin a new one after a configurable delay.

The `Reset` button will stop the current recording, delete the saved file, and then begin a new recording after a configurable delay.


### File Combiner
The file combiner requires FFMPEG. For Windows, you should be able to find pre-built EXE's on https://ffmpeg.org/download.html#build-windows. Extract/save FFMPEG files to a known location, and use the script settings interface to tell the KROZ Control Deck where it is installed.

