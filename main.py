import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Initialize FastAPI app
app = FastAPI(
    title="Gesture Puzzle API",
    description="Backend API for managing the gesture puzzle leaderboard.",
    version="1.0.0"
)

# Constants
DB_PATH = "db.sqlite3"
STATIC_DIR = "static"

# Ensure static directory exists
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            time INTEGER,
            moves INTEGER,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Models
class ScoreSubmission(BaseModel):
    name: str = Field(..., min_length=1, max_length=14, description="Player name (1-14 chars)")
    time: int = Field(..., ge=0, description="Time taken in seconds")
    moves: int = Field(..., ge=0, description="Number of puzzle piece swaps made")

# Helper to fetch leaderboard
def get_leaderboard_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, time, moves, date 
        FROM leaderboard 
        ORDER BY time ASC, moves ASC, id ASC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "name": row["name"],
            "time": row["time"],
            "moves": row["moves"],
            "date": row["date"]
        }
        for row in rows
    ]

# Serve Frontend at Root
@app.get("/")
async def read_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found in static folder.")

# API endpoints
@app.get("/api/leaderboard")
async def get_leaderboard():
    """Returns the top 5 scores from the database."""
    try:
        return get_leaderboard_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/leaderboard")
async def add_score(submission: ScoreSubmission):
    """Submits a score. Replaces player's previous score if the new one is faster."""
    try:
        name_normalized = submission.name.strip().upper()
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT time FROM leaderboard WHERE name = ?", (name_normalized,))
        row = cursor.fetchone()
        
        if row:
            existing_time = row[0]
            # Upsert: Update score only if the new run is faster
            if submission.time < existing_time:
                cursor.execute("""
                    UPDATE leaderboard 
                    SET time = ?, moves = ?, date = ? 
                    WHERE name = ?
                """, (submission.time, submission.moves, current_date, name_normalized))
        else:
            # Insert new user score
            cursor.execute("""
                INSERT INTO leaderboard (name, time, moves, date) 
                VALUES (?, ?, ?, ?)
            """, (name_normalized, submission.time, submission.moves, current_date))
            
        conn.commit()
        conn.close()
        
        # Return updated leaderboard
        return get_leaderboard_data()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Mount static files (fallback route for direct assets)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
