# Live Hand Gesture Control — Cyberpunk Gesture Puzzle

An interactive hand gesture-controlled sliding and swapping puzzle game. The project uses advanced computer vision and machine learning (OpenCV & MediaPipe Hands) to track hands in real-time. It features both a modern **FastAPI Web Server** with SQLite database persistence and a native **Desktop Pygame Client**.

---

## Features

- **Double-Hand Framing (Phase 1 — Capture)**: Hold up both hands and pinch your thumb and index fingers. Move your hands to dynamically resize the green selection frame. Release the pinch to snap the frame and generate the puzzle!
- **Single-Hand Solving (Phase 2 — Solve)**: Use one hand to control a virtual cursor. Pinch to grab a puzzle piece, drag it to another slot, and release to swap pieces.
- **FastAPI Web Application**: Serves a styled HTML frontend with seamless API integration for the leaderboard database.
- **Smart Leaderboard System**:
  - High-performance **SQLite DB** to persist player completion times and moves.
  - Hybrid offline mode: falls back to browser `localStorage` if the server is offline.
- **Native Desktop Pygame Client**: Run the same hand gesture puzzle game locally on your desktop with optimized 30fps hand tracking, custom cyberpunk grid layout, and keyboard-driven scoreboard.
- **Clean Styling**: Sleek cyberpunk theme with glowing grids, custom micro-animations, neon cursor states, and share-tech mono typography.

---

## Project Structure

```
live hand gesture control/
├── .gitignore             # Git ignore file for Python & SQLite cache
├── README.md              # Project documentation (this file)
├── requirements.txt       # Python environment dependencies
├── main.py                # FastAPI Web Server (serves client + manages DB)
├── desktop_app.py         # Native Desktop Pygame Client (Pygame + OpenCV + MediaPipe)
├── db.sqlite3             # Local database file (auto-generated)
└── static/
    └── index.html         # Web client frontend (mirrored video, MediaPipe JS, API client)
```

---

## Installation & Setup

Ensure you have **Python 3.8+** installed.

1. **Clone or download** this repository folder.
2. Open your terminal/command prompt and navigate into the folder:
   ```bash
   cd "live hand gesture control"
   ```
3. (Recommended) Create and activate a Python virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS/Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Running the Web Version

1. Start the FastAPI backend server:
   ```bash
   python main.py
   ```
   *Alternative:* run `uvicorn main:app --reload`

2. Open your web browser and go to:
   ```
   http://127.0.0.1:8000
   ```
3. Allow camera access, pinch both hands to frame a region, release to capture, and complete the puzzle by grabbing tiles with a single pinch!

---

## Running the Desktop Version

1. Launch the native desktop application:
   ```bash
   python desktop_app.py
   ```
2. Controls:
   - **ESC**: Return to Phase 1 (Re-frame webcam image) at any point.
   - **Pinch (Index + Thumb)**: Select/drag region (Phase 1) or hold/drag tiles (Phase 2).
   - **Keyboard**: Type your name on completion and press **Enter** to save to the local leaderboard.
   - **R**: Restart/play again from the win screen.

---

## GitHub Upload Guide

To push this repository to your GitHub account:

1. Open your terminal in the project directory.
2. Initialize git:
   ```bash
   git init
   ```
3. Add all files to staging (our `.gitignore` ensures temporary files and environments are excluded):
   ```bash
   git add .
   ```
4. Create your initial commit:
   ```bash
   git commit -m "Initial commit: FastAPI server, Pygame desktop client, and SQLite leaderboard integration"
   ```
5. Create a new repository on GitHub (keep it empty, do not initialize with README or license).
6. Copy the repository URL from GitHub and run:
   ```bash
   git branch -M main
   git remote add origin <YOUR_GITHUB_REPO_URL>
   git push -u origin main
   ```
