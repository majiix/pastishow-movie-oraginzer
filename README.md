# Movie & TV Show Organizer

A premium, modern desktop application designed to scan, fetch metadata for, and organize movie and TV show files into beautifully structured and named folders. Built with Python and CustomTkinter, it features a glassmorphic macOS-style dark user interface, rich integration with the OMDb API, automatic subtitle and media group handling, and a double-safety undo system.

---

## Key Features

- **Cinematic Dark Mode UI:** A gorgeous, responsive interface designed with glassmorphic cards, custom typography, status micro-animations, and visual indicators.
- **Smart Directory Structuring:** Dynamically groups media files into clean folders matching the naming pattern:
  `Title (Year) [IMDb Rating] [Genres]`
- **TV Show Identification:** Automatically detects multiple episodes mapping to the same series, groups them under a single directory, and queries the OMDb API with series-specific parameters.
- **In-Place Subfolder Renaming:** When recursive scanning is enabled, files located inside subfolders are renamed in-place rather than pulled out to the root, keeping your nested structures clean.
- **Associated File Support:** Automatically identifies and moves subtitles (`.srt`, `.ass`, `.vtt`), info files (`.nfo`, `.txt`), and graphic files alongside their primary video files.
- **Rich Offline Details Page (`about.html`):** Dynamically generates a beautiful, self-contained single-page HTML details card inside each movie folder, showcasing:
  - Official cover posters (cached locally).
  - Main plot summaries and cinematic metadata.
  - Directors, writers, and full cast lists.
  - Multi-source rating badges (IMDb, Rotten Tomatoes, Metacritic).
  - Laurel wreath banners highlighting industry awards.
  - Offline compatibility, utilizing responsive styling.
- **Windows Integration:** Right-click context menu integration for instant folder scanning directly from Windows Explorer (using custom app-themed icons).
- **Network Proxy & Override Controls:** Full support for custom HTTP, HTTPS, or SOCKS5 proxies to bypass ISP-level blockades, including a manual override to disable broken system proxies.
- **Dynamic Connectivity Warning:** Displays a real-time warning card in the sidebar if the OMDb server is unreachable or internet connectivity is lost, complete with an asynchronous "Retry Connection" check button to dynamically hide the warning once connection is restored.
- **Tuned Safety Undo:** Instantly revert all folder renames, file moves, and downloaded poster or generated details pages with a single click. Undo timeouts can be configured in settings (default: 15 seconds) to finalize changes automatically.

---

## Installation

### Prerequisites

- **Python 3.8 or higher**
- Dependencies: `customtkinter` (for the premium GUI)

Install the required library using pip:
```bash
pip install customtkinter
```

---

## How to Use

1. **Launch the Application:**
   Run `main.py` using Python:
   ```bash
   python main.py
   ```
2. **Select Target Directory:**
   Click **Browse** or type the absolute path of the directory containing your media files.
3. **Configure Preferences:**
   Open the **Preferences** modal to adjust:
   - **OMDb API Key:** Register a free key at [omdbapi.com](https://www.omdbapi.com/) and paste it here to enable rich cover art, ratings, and plot downloads.
   - **Minimum File Size:** Set the threshold (in MB) to filter out sample clips, trailers, and short videos.
   - **Proxy Configuration:** Input a proxy address if required to access OMDb (e.g. `http://127.0.0.1:7890` or SOCKS5 equivalents), or write `None` to bypass broken system-level proxy configurations.
   - **Recursive Scanning:** Toggle whether to look inside subdirectories.
   - **Explorer Integration:** Click **Register** to add "Organize with Movie Organizer" to your Windows right-click menu, or **Deregister** to remove it.
4. **Scan Directory:**
   Click **Scan Folder** to detect and list movies. The app will parse filenames, fetch OMDb records, and highlight matches on the dashboard.
5. **Adjust Titles and Years:**
   Double-click the edit boxes on any row to manually fine-tune titles or release years before starting the organization.
6. **Organize:**
   Select the movies you want to format and click **Organize Selected**.
7. **Undo:**
   If you change your mind, click the **Undo** button in the lower status bar before the configured safety timer expires.

---

## Visual Presentation of Movie Folders

When organized, each movie is placed inside its own directory. An organized movie folder contains:
- **`Movie_Name (Year) [Rating] [Genres]/`**
  - `Movie_Name.mp4` (the video file)
  - `Movie_Name.srt` (automatically grouped subtitles)
  - `poster.jpg` (cached cover artwork)
  - `about.html` (the premium offline movie profile details card)

Double-clicking `about.html` loads a high-end cinematic dashboard locally in your browser.

---

## Building a Standalone Executable

You can package the application into a single executable file (`.exe`) for Windows using PyInstaller.

### 1. Install PyInstaller
```bash
pip install pyinstaller
```

### 2. Run the Build Script
A pre-configured python build script is included:
```bash
python build_exe.py
```
This script packages the application, embeds the CustomTkinter asset structures, bundles the application's camera icon (`app_icon.ico`), and produces `dist/MovieOrganizer.exe`.

---

## Development and Testing

A testing suite is included to verify core filename parsers, subdirectory renaming logic, and history tracking/undo functions. Run it using:
```bash
python test_runner.py
```
All tests run in isolated temporary directories and clean up after themselves.
