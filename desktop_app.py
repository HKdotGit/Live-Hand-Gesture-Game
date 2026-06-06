import os
import cv2
import json
import time
import math
import numpy as np
import pygame
import mediapipe as mp

# Initialize Pygame
pygame.init()
pygame.mixer.init()  # for sound capabilities if added

# Constants
WIDTH, HEIGHT = 1120, 680
VP_W, VP_H = 800, 580
GAP = 3
PINCH_THRESH = 0.055
LB_FILE = "leaderboard_desktop.json"

# Colors
BG_COLOR = (5, 10, 14)       # Sleek dark cyber background
NEON_GREEN = (0, 255, 136)   # Phase 1 / Success
NEON_CYAN = (0, 229, 255)    # Phase 2 / Dragging
NEON_YELLOW = (245, 255, 0)  # Warning / Action
NEON_RED = (255, 61, 90)     # Alert
NEON_PURPLE = (191, 95, 255) # Leaderboard
TEXT_DIM = (100, 140, 120)   # Cyan-tinted gray
BORDER_COLOR = (0, 64, 45)   # Dim green for borders
DARK_GLASS = (10, 24, 20)    # Glassmorphism container background

# Screen setup
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Gesture Puzzle - Desktop Edition")
clock = pygame.Clock()

# Fonts
try:
    font_mono_s = pygame.font.SysFont("Consolas", 12)
    font_mono_m = pygame.font.SysFont("Consolas", 16)
    font_mono_l = pygame.font.SysFont("Consolas", 28)
    font_mono_xl = pygame.font.SysFont("Consolas", 42)
except:
    font_mono_s = pygame.font.Font(None, 16)
    font_mono_m = pygame.font.Font(None, 22)
    font_mono_l = pygame.font.Font(None, 36)
    font_mono_xl = pygame.font.Font(None, 54)

# MediaPipe Setup
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(
    max_num_hands=2,
    model_complexity=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6
)

# Leaderboard Helpers
def load_leaderboard():
    if os.path.exists(LB_FILE):
        try:
            with open(LB_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_score(name, elapsed_time, moves):
    board = load_leaderboard()
    norm_name = name.strip().upper()
    existing = next((e for e in board if e["name"] == norm_name), None)
    
    if existing:
        if elapsed_time < existing["time"]:
            existing["time"] = elapsed_time
            existing["moves"] = moves
            existing["date"] = time.strftime("%d/%m/%Y")
    else:
        board.append({
            "name": norm_name,
            "time": elapsed_time,
            "moves": moves,
            "date": time.strftime("%d/%m/%Y")
        })
        
    board = sorted(board, key=lambda x: (x["time"], x["moves"]))[:5]
    with open(LB_FILE, "w") as f:
        json.dump(board, f, indent=2)
    return board

# Helper functions
def dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def to_vp_px(norm_pt, w, h, offset_y=0):
    # Mirror x coordinates for natural webcam preview
    x = int((1.0 - norm_pt[0]) * w) + 20
    y = int(norm_pt[1] * h) + 40 + offset_y
    return (x, y)

def draw_cyber_border(surf, rect, color, label=""):
    x, y, w, h = rect
    pygame.draw.rect(surf, color, rect, 1)
    # Draw corners
    pygame.draw.line(surf, color, (x, y), (x + 15, y), 3)
    pygame.draw.line(surf, color, (x, y), (x, y + 15), 3)
    pygame.draw.line(surf, color, (x + w, y), (x + w - 15, y), 3)
    pygame.draw.line(surf, color, (x + w, y), (x + w, y + 15), 3)
    pygame.draw.line(surf, color, (x, y + h), (x + 15, y + h), 3)
    pygame.draw.line(surf, color, (x, y + h), (x, y + h - 15), 3)
    pygame.draw.line(surf, color, (x + w, y + h), (x + w - 15, y + h), 3)
    pygame.draw.line(surf, color, (x + w, y + h), (x + w, y + h - 15), 3)
    
    if label:
        txt = font_mono_s.render(label, True, color)
        surf.blit(txt, (x + 8, y + 5))

# Main loop variables
cap = cv2.VideoCapture(0)
cam_connected = cap.isOpened()

# Game State
# 'FRAMING' | 'SOLVING' | 'WIN'
state = 'FRAMING'

# Framing state variables
both_was_pinching = False
last_l_mid = None
last_r_mid = None
captured_surface = None

# Solving state variables
tile_surfs = []      # list of 9 scaled surfaces
tile_order = []      # indices in grid 0-8
drag_start_slot = None
held_tile_idx = None
is_pinching = False
current_drop_target = None
moves = 0
correct_count = 0
timer_start = 0
final_time_str = ""
elapsed_seconds = 0

# Cursor smoothing
cur_x, cur_y = WIDTH // 2, HEIGHT // 2

# Leaderboard win input
win_name = ""
saved_score_board = None

# Guide variables
guide_dot_l = None
guide_dot_r = None

def start_solving(frame_crop):
    global state, tile_surfs, tile_order, moves, timer_start, held_tile_idx, drag_start_slot, is_pinching, win_name, saved_score_board
    state = 'SOLVING'
    moves = 0
    held_tile_idx = None
    drag_start_slot = None
    is_pinching = False
    win_name = ""
    saved_score_board = None
    
    crop_h, crop_w, _ = frame_crop.shape
    aspect = crop_w / crop_h
    
    # Calculate grid sizes to fit inside 800x580 viewport
    if aspect >= 800 / 580:
        grid_disp_w = 720
        grid_disp_h = int(720 / aspect)
    else:
        grid_disp_h = 500
        grid_disp_w = int(500 * aspect)
        
    grid_x = 20 + (800 - grid_disp_w) // 2
    grid_y = 40 + (580 - grid_disp_h) // 2
    
    cell_w = grid_disp_w // 3
    cell_h = grid_disp_h // 3
    
    # Crop source dimensions
    src_cell_w = crop_w // 3
    src_cell_h = crop_h // 3
    
    # Create py game surface from OpenCV cropped frame
    crop_rgb = cv2.cvtColor(frame_crop, cv2.COLOR_BGR2RGB)
    crop_surf = pygame.image.frombuffer(crop_rgb.tobytes(), (crop_w, crop_h), 'RGB')
    
    tile_surfs.clear()
    for id_val in range(9):
        row = id_val // 3
        col = id_val % 3
        rect = pygame.Rect(col * src_cell_w, row * src_cell_h, src_cell_w, src_cell_h)
        sub = crop_surf.subsurface(rect).copy()
        # Scale to fit
        scaled = pygame.transform.scale(sub, (cell_w, cell_h))
        tile_surfs.append(scaled)
        
    # Shuffling (must not be identity)
    tile_order.clear()
    tile_order.extend(range(9))
    while True:
        np.random.shuffle(tile_order)
        # Check if solved
        correct = sum(1 for i, v in enumerate(tile_order) if v == i)
        if correct < 9:
            break
            
    timer_start = time.time()
    
    # Save dimensions to global dict for easy access
    global grid_dims
    grid_dims = {
        "x": grid_x, "y": grid_y,
        "w": grid_disp_w, "h": grid_disp_h,
        "cell_w": cell_w, "cell_h": cell_h
    }

def get_slot_at(px, py):
    if 'grid_dims' not in globals():
        return None
    g = grid_dims
    x_rel = px - g["x"]
    y_rel = py - g["y"]
    col = int(x_rel // (g["cell_w"] + GAP))
    row = int(y_rel // (g["cell_h"] + GAP))
    if 0 <= col < 3 and 0 <= row < 3:
        return row * 3 + col
    return None

# Game Loop
running = True
while running:
    # 1. PROCESS PYGAME EVENTS
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                state = 'FRAMING'
                both_was_pinching = False
                captured_surface = None
                held_tile_idx = None
            elif state == 'WIN':
                if event.key == pygame.K_BACKSPACE:
                    win_name = win_name[:-1]
                elif event.key == pygame.K_RETURN:
                    if win_name.strip():
                        saved_score_board = save_score(win_name, elapsed_seconds, moves)
                elif event.key == pygame.K_r: # R to restart
                    state = 'FRAMING'
                    both_was_pinching = False
                else:
                    if len(win_name) < 14 and event.unicode.isalnum() or event.key == pygame.K_SPACE:
                        win_name += event.unicode
                        
    # 2. CAPTURE WEBCAM FRAME
    raw_frame = None
    if cam_connected:
        ret, raw_frame = cap.read()
        if not ret:
            cam_connected = False
            
    # Process hands with MediaPipe
    results = None
    cam_h, cam_w = 480, 640
    if raw_frame is not None:
        cam_h, cam_w, _ = raw_frame.shape
        # Flip image horizontally for natural mirroring
        flipped = cv2.flip(raw_frame, 1)
        rgb_frame = cv2.cvtColor(flipped, cv2.COLOR_BGR2RGB)
        results = hands_detector.process(rgb_frame)
        
    # Standard screen background
    screen.fill(BG_COLOR)
    
    # 3. DRAW SYSTEM HEADER
    # Title GESTURE PUZZLE
    title_lbl = font_mono_l.render("GESTURE PUZZLE", True, NEON_GREEN)
    screen.blit(title_lbl, (20, 10))
    phase_label = "PHASE 1 - FRAME REGION" if state == 'FRAMING' else ("PHASE 2 - SOLVE" if state == 'SOLVING' else "PUZZLE SOLVED")
    phase_color = NEON_YELLOW if state == 'FRAMING' else (NEON_CYAN if state == 'SOLVING' else NEON_GREEN)
    phase_txt = font_mono_m.render(phase_label, True, phase_color)
    screen.blit(phase_txt, (840, 15))
    pygame.draw.line(screen, BORDER_COLOR, (20, 32), (WIDTH - 20, 32), 1)
    
    # Left Main Viewport bounding box
    draw_cyber_border(screen, (20, 40, VP_W, VP_H), BORDER_COLOR)
    
    # 4. PHASE SPECIFIC LOGIC
    # ───────────────────────────────────────────────────────────
    # PHASE 1: FRAMING STATE
    # ───────────────────────────────────────────────────────────
    if state == 'FRAMING':
        l_pin, r_pin = False, False
        l_mid, r_mid = None, None
        guide_dot_l, guide_dot_r = None, None
        
        # Draw camera frame in viewport scaled
        if raw_frame is not None:
            # Map aspect ratio to fit viewport
            aspect = cam_w / cam_h
            if aspect >= VP_W / VP_H:
                disp_w = VP_W
                disp_h = int(VP_W / aspect)
            else:
                disp_h = VP_H
                disp_w = int(VP_H * aspect)
                
            offset_x = (VP_W - disp_w) // 2
            offset_y = (VP_H - disp_h) // 2
            
            # Convert raw frame (BGR) to Pygame surface
            raw_rgb = cv2.cvtColor(flipped, cv2.COLOR_BGR2RGB)
            cam_surface = pygame.image.frombuffer(raw_rgb.tobytes(), (cam_w, cam_h), 'RGB')
            scaled_cam = pygame.transform.scale(cam_surface, (disp_w, disp_h))
            screen.blit(scaled_cam, (20 + offset_x, 40 + offset_y))
            
            # Map hands to viewport coordinates
            hands_found = []
            if results and results.multi_hand_landmarks:
                for idx, lm in enumerate(results.multi_hand_landmarks):
                    # We want to identify Left vs Right
                    handedness = results.multi_handedness[idx].classification[0].label
                    # Since frame is already flipped, we adjust handedness mapping
                    lbl = "RIGHT" if handedness == "Left" else "LEFT"
                    
                    # 4 is thumb tip, 8 is index tip
                    t_pt = (lm.landmark[4].x, lm.landmark[4].y)
                    i_pt = (lm.landmark[8].x, lm.landmark[8].y)
                    
                    p_dist = dist(t_pt, i_pt)
                    pinching = p_dist < PINCH_THRESH
                    
                    mid = ((t_pt[0] + i_pt[0]) / 2, (t_pt[1] + i_pt[1]) / 2)
                    # Convert to viewport px coordinates
                    mid_px = (
                        int(mid[0] * disp_w) + 20 + offset_x,
                        int(mid[1] * disp_h) + 40 + offset_y
                    )
                    
                    if lbl == "LEFT":
                        l_pin = pinching
                        l_mid = mid
                        guide_dot_l = mid_px
                    else:
                        r_pin = pinching
                        r_mid = mid
                        guide_dot_r = mid_px
                        
                    # Draw skeletal connections in Pygame
                    # Draw simple hand representation
                    for point_id in [4, 8, 12, 16, 20]: # fingertips
                        pt_norm = lm.landmark[point_id]
                        pt_px = (int(pt_norm.x * disp_w) + 20 + offset_x, int(pt_norm.y * disp_h) + 40 + offset_y)
                        color = NEON_RED if pinching and point_id in [4,8] else NEON_GREEN
                        pygame.draw.circle(screen, color, pt_px, 5)
                        
                    # Wrist
                    w_norm = lm.landmark[0]
                    w_px = (int(w_norm.x * disp_w) + 20 + offset_x, int(w_norm.y * disp_h) + 40 + offset_y)
                    pygame.draw.circle(screen, TEXT_DIM, w_px, 3)
                    
            # Check for double pinch framing
            both_pinching = l_pin and r_pin and l_mid is not None and r_mid is not None
            
            if both_pinching:
                both_was_pinching = True
                last_l_mid = l_mid
                last_r_mid = r_mid
                
                # Draw live ROI
                lx, ly = int(l_mid[0] * disp_w) + 20 + offset_x, int(l_mid[1] * disp_h) + 40 + offset_y
                rx, ry = int(r_mid[0] * disp_w) + 20 + offset_x, int(r_mid[1] * disp_h) + 40 + offset_y
                rx_box = pygame.Rect(min(lx, rx), min(ly, ry), abs(rx - lx), abs(ry - ly))
                
                pygame.draw.rect(screen, NEON_YELLOW, rx_box, 2)
                # Corner markers
                for pt in [(rx_box.left, rx_box.top), (rx_box.right, rx_box.top), (rx_box.left, rx_box.bottom), (rx_box.right, rx_box.bottom)]:
                    pygame.draw.circle(screen, NEON_YELLOW, pt, 6)
                    
            elif both_was_pinching:
                # Pinch released -> Crop and capture!
                both_was_pinching = False
                if last_l_mid and last_r_mid:
                    # Capture exact region from original webcam frame (flipped)
                    x1 = int(min(last_l_mid[0], last_r_mid[0]) * cam_w)
                    y1 = int(min(last_l_mid[1], last_r_mid[1]) * cam_h)
                    x2 = int(max(last_l_mid[0], last_r_mid[0]) * cam_w)
                    y2 = int(max(last_l_mid[1], last_r_mid[1]) * cam_h)
                    
                    crop_w, crop_h = x2 - x1, y2 - y1
                    if crop_w > 40 and crop_h > 40:
                        crop_img = flipped[y1:y2, x1:x2]
                        # Store reference thumbnail
                        captured_surface = pygame.image.frombuffer(
                            cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB).tobytes(), 
                            (crop_w, crop_h), 'RGB'
                        )
                        start_solving(crop_img)
            else:
                # Guide dots when hands tracked but not framing
                if guide_dot_l: pygame.draw.circle(screen, NEON_CYAN, guide_dot_l, 8, 1)
                if guide_dot_r: pygame.draw.circle(screen, NEON_CYAN, guide_dot_r, 8, 1)
        else:
            # Camera error panel
            err_lbl = font_mono_m.render("WEBCAM FEED UNAVAILABLE", True, NEON_RED)
            screen.blit(err_lbl, (280, 280))
            err_sub = font_mono_s.render("Please verify camera permissions or connection.", True, TEXT_DIM)
            screen.blit(err_sub, (250, 310))
            
        # Draw instructions panel inside sidebar
        sidebar_rect = (840, 40, 260, VP_H)
        pygame.draw.rect(screen, DARK_GLASS, sidebar_rect)
        draw_cyber_border(screen, sidebar_rect, BORDER_COLOR, "INSTRUCTIONS")
        
        # Show text rules
        rules = [
            "HOW TO CAPTURE",
            "-------------------",
            "1. Show both hands.",
            "2. Pinch index & thumb",
            "   on BOTH hands",
            "   simultaneously.",
            "3. Move hands to adjust",
            "   the bounding frame.",
            "4. Release both pinches",
            "   to SNAP & start",
            "   the puzzle!",
            "",
            "FEED: " + ("LIVE" if cam_connected else "DISCONNECTED"),
            "HANDS DETECTED: " + str(len(results.multi_hand_landmarks) if results and results.multi_hand_landmarks else 0)
        ]
        y_pos = 75
        for rule in rules:
            color = NEON_YELLOW if "HOW" in rule or "SNAP" in rule else (NEON_GREEN if "LIVE" in rule else TEXT_DIM)
            rule_lbl = font_mono_m.render(rule, True, color)
            screen.blit(rule_lbl, (860, y_pos))
            y_pos += 24
            
    # ───────────────────────────────────────────────────────────
    # PHASE 2: SOLVING STATE
    # ───────────────────────────────────────────────────────────
    elif state == 'SOLVING':
        g = grid_dims
        elapsed_seconds = int(time.time() - timer_start)
        mins = elapsed_seconds // 60
        secs = elapsed_seconds % 60
        time_str = f"{mins}:{secs:02d}"
        
        # 1. Hand gesture parsing (Single cursor control)
        # Find index finger tip of dominant hand
        active_hand_lm = None
        if results and results.multi_hand_landmarks:
            # If we were pinching, try to stay locked on the same hand index if possible
            # For simplicity, we choose the hand closest to the screen cursor
            best_idx = 0
            best_dist = 99999
            for idx, lm in enumerate(results.multi_hand_landmarks):
                # Landmark 8 is index tip
                sx = int((1.0 - lm.landmark[8].x) * WIDTH)
                sy = int(lm.landmark[8].y * HEIGHT)
                d = dist((sx, sy), (cur_x, cur_y))
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            active_hand_lm = results.multi_hand_landmarks[best_idx]
            
        if active_hand_lm:
            # Thumb (4) and Index (8)
            t_pt = (active_hand_lm.landmark[4].x, active_hand_lm.landmark[4].y)
            i_pt = (active_hand_lm.landmark[8].x, active_hand_lm.landmark[8].y)
            
            # Pinch check
            p_dist = dist(t_pt, i_pt)
            pinch = p_dist < PINCH_THRESH
            
            # Cursor mapping
            raw_cx = int(((1.0 - (t_pt[0] + i_pt[0]) / 2)) * WIDTH)
            raw_cy = int(((t_pt[1] + i_pt[1]) / 2) * HEIGHT)
            
            # Lerp smoothing
            cur_x += int((raw_cx - cur_x) * 0.35)
            cur_y += int((raw_cy - cur_y) * 0.35)
            
            # Handle pinch start / drag / release
            if pinch:
                if not is_pinching:
                    is_pinching = True
                    slot_hover = get_slot_at(cur_x, cur_y)
                    if slot_hover is not None:
                        drag_start_slot = slot_hover
                        held_tile_idx = tile_order[slot_hover]
            else:
                if is_pinching:
                    is_pinching = False
                    if held_tile_idx is not None:
                        slot_drop = get_slot_at(cur_x, cur_y)
                        if slot_drop is not None and slot_drop != drag_start_slot:
                            # Swap
                            swap_val = tile_order[slot_drop]
                            tile_order[slot_drop] = held_tile_idx
                            tile_order[drag_start_slot] = swap_val
                            moves += 1
                        held_tile_idx = None
                        drag_start_slot = None
        else:
            is_pinching = False
            held_tile_idx = None
            drag_start_slot = None
            
        # 2. Render puzzle board inside Main Viewport
        correct_count = 0
        current_drop_target = get_slot_at(cur_x, cur_y) if held_tile_idx is not None else None
        
        for idx in range(9):
            if idx == drag_start_slot and held_tile_idx is not None:
                # Skip rendering here, we will render it at the cursor position
                continue
                
            tile_val = tile_order[idx]
            row = idx // 3
            col = idx % 3
            tx = g["x"] + col * (g["cell_w"] + GAP)
            ty = g["y"] + row * (g["cell_h"] + GAP)
            
            # Draw actual image tile
            screen.blit(tile_surfs[tile_val], (tx, ty))
            
            # Draw success indicator
            is_correct = (tile_val == idx)
            if is_correct:
                correct_count += 1
                pygame.draw.rect(screen, NEON_GREEN, (tx, ty, g["cell_w"], g["cell_h"]), 1)
            else:
                pygame.draw.rect(screen, NEON_CYAN, (tx, ty, g["cell_w"], g["cell_h"]), 1)
                
            # Drop target highlighting
            if current_drop_target == idx and idx != drag_start_slot:
                pygame.draw.rect(screen, NEON_YELLOW, (tx, ty, g["cell_w"], g["cell_h"]), 4)
                
        # Draw dragged tile
        if held_tile_idx is not None:
            # Center tile on cursor
            dtx = cur_x - g["cell_w"] // 2
            dty = cur_y - g["cell_h"] // 2
            screen.blit(tile_surfs[held_tile_idx], (dtx, dty))
            pygame.draw.rect(screen, NEON_YELLOW, (dtx, dty, g["cell_w"], g["cell_h"]), 2)
            
        # Check Win state transition
        if correct_count == 9 and held_tile_idx is None:
            state = 'WIN'
            final_time_str = time_str
            
        # Draw Sidebar panel
        sidebar_rect = (840, 40, 260, VP_H)
        pygame.draw.rect(screen, DARK_GLASS, sidebar_rect)
        draw_cyber_border(screen, sidebar_rect, BORDER_COLOR, "PUZZLE HUDS")
        
        # Sidebar webcam feed thumbnail (180x130)
        thumb_rect = (880, 75, 180, 120)
        if raw_frame is not None:
            thumb_surface = pygame.transform.scale(cam_surface, (180, 120))
            screen.blit(thumb_surface, (880, 75))
            pygame.draw.rect(screen, BORDER_COLOR, thumb_rect, 1)
            # Render virtual pointer dot on thumbnail
            if active_hand_lm:
                h_tx = int((1.0 - active_hand_lm.landmark[8].x) * 180) + 880
                h_ty = int(active_hand_lm.landmark[8].y * 120) + 75
                pygame.draw.circle(screen, NEON_YELLOW, (h_tx, h_ty), 4)
        else:
            pygame.draw.rect(screen, (0,0,0), thumb_rect)
            
        # Reference Thumbnail (180x120)
        ref_rect = (880, 215, 180, 120)
        if captured_surface:
            scaled_ref = pygame.transform.scale(captured_surface, (180, 120))
            screen.blit(scaled_ref, (880, 215))
            pygame.draw.rect(screen, BORDER_COLOR, ref_rect, 1)
            
        # Stats panel
        stats_y = 355
        time_lbl = font_mono_m.render(f"TIME: {time_str}", True, NEON_YELLOW)
        screen.blit(time_lbl, (880, stats_y))
        
        swaps_lbl = font_mono_m.render(f"SWAPS: {moves}", True, NEON_CYAN)
        screen.blit(swaps_lbl, (880, stats_y + 25))
        
        prog_lbl = font_mono_m.render(f"TILES CORRECT: {correct_count}/9", True, NEON_GREEN)
        screen.blit(prog_lbl, (880, stats_y + 50))
        
        # Progress Bar
        pygame.draw.rect(screen, (20, 40, 30), (880, stats_y + 80, 180, 8))
        pygame.draw.rect(screen, NEON_GREEN, (880, stats_y + 80, int(180 * (correct_count / 9)), 8))
        
        # Hint
        hint_lbl = font_mono_s.render("Pinch and drag to swap.", True, TEXT_DIM)
        screen.blit(hint_lbl, (880, stats_y + 105))
        hint_lbl2 = font_mono_s.render("Press ESC to Reframe.", True, TEXT_DIM)
        screen.blit(hint_lbl2, (880, stats_y + 122))
        
        # Draw floating cursor dot
        c_color = NEON_CYAN if is_pinching else NEON_YELLOW
        c_radius = 6 if is_pinching else 10
        pygame.draw.circle(screen, c_color, (cur_x, cur_y), c_radius)
        pygame.draw.circle(screen, c_color, (cur_x, cur_y), c_radius + 4, 1)
        
    # ───────────────────────────────────────────────────────────
    # STATE: WIN / LEADERBOARD STATE
    # ───────────────────────────────────────────────────────────
    elif state == 'WIN':
        # Render static puzzle pieces
        g = grid_dims
        for idx in range(9):
            tile_val = tile_order[idx]
            row = idx // 3
            col = idx % 3
            tx = g["x"] + col * (g["cell_w"] + GAP)
            ty = g["y"] + row * (g["cell_h"] + GAP)
            screen.blit(tile_surfs[tile_val], (tx, ty))
            pygame.draw.rect(screen, NEON_GREEN, (tx, ty, g["cell_w"], g["cell_h"]), 1)
            
        # Draw glass win overlay panel
        overlay_rect = pygame.Rect(180, 100, 440, 440)
        # semi-transparent background
        bg_surf = pygame.Surface((440, 440))
        bg_surf.set_alpha(240)
        bg_surf.fill((10, 16, 22))
        screen.blit(bg_surf, (180, 100))
        
        draw_cyber_border(screen, (180, 100, 440, 440), NEON_CYAN, "VICTORY REPORT")
        
        win_title = font_mono_l.render("PUZZLE SOLVED", True, NEON_CYAN)
        screen.blit(win_title, (210, 125))
        
        time_desc = font_mono_m.render("Completion Time:", True, TEXT_DIM)
        screen.blit(time_desc, (210, 175))
        
        time_val_lbl = font_mono_xl.render(final_time_str, True, NEON_YELLOW)
        screen.blit(time_val_lbl, (210, 195))
        
        swaps_desc = font_mono_m.render(f"{moves} swaps recorded.", True, NEON_GREEN)
        screen.blit(swaps_desc, (210, 255))
        
        # Leaderboard name entry
        if saved_score_board is None:
            prompt_lbl = font_mono_m.render("Enter Name for Leaderboard:", True, TEXT_DIM)
            screen.blit(prompt_lbl, (210, 295))
            
            # Render entry text field box
            pygame.draw.rect(screen, (20, 32, 28), (210, 325, 380, 36))
            pygame.draw.rect(screen, BORDER_COLOR, (210, 325, 380, 36), 1)
            
            name_surf = font_mono_l.render(win_name + ("|" if time.time() % 1.0 < 0.5 else ""), True, NEON_GREEN)
            screen.blit(name_surf, (220, 330))
            
            save_lbl = font_mono_s.render("PRESS ENTER TO SAVE SCORE", True, NEON_YELLOW)
            screen.blit(save_lbl, (210, 370))
        else:
            # Draw Leaderboard scores
            lb_title = font_mono_m.render("LEADERBOARD TOP 5", True, NEON_PURPLE)
            screen.blit(lb_title, (210, 290))
            y_lb = 315
            for rank_idx, record in enumerate(saved_score_board):
                mins_rec = record["time"] // 60
                secs_rec = record["time"] % 60
                rec_time = f"{mins_rec}:{secs_rec:02d}"
                is_me = record["name"] == win_name.strip().upper()
                row_color = NEON_CYAN if is_me else NEON_GREEN
                
                row_text = f"#{rank_idx+1} {record['name']:<12} {rec_time:>5} ({record['moves']}sw)"
                rec_lbl = font_mono_m.render(row_text, True, row_color)
                screen.blit(rec_lbl, (210, y_lb))
                y_lb += 22
                
            again_lbl = font_mono_s.render("PRESS R TO PLAY AGAIN", True, NEON_YELLOW)
            screen.blit(again_lbl, (210, 440))
            
        # Draw instructions inside sidebar (Solving stats display freezes here)
        sidebar_rect = (840, 40, 260, VP_H)
        pygame.draw.rect(screen, DARK_GLASS, sidebar_rect)
        draw_cyber_border(screen, sidebar_rect, BORDER_COLOR, "VICTORY STATS")
        
        stats_y = 75
        lbl = font_mono_m.render("RECORDED STATS", True, NEON_GREEN)
        screen.blit(lbl, (860, stats_y))
        
        lbl_t = font_mono_m.render(f"TIME: {final_time_str}", True, NEON_YELLOW)
        screen.blit(lbl_t, (860, stats_y + 35))
        
        lbl_s = font_mono_m.render(f"SWAPS: {moves}", True, NEON_CYAN)
        screen.blit(lbl_s, (860, stats_y + 65))
        
        # Load local board for display on right side
        lbl_lb = font_mono_m.render("LOCAL BOARD:", True, NEON_PURPLE)
        screen.blit(lbl_lb, (860, stats_y + 115))
        
        board_data = load_leaderboard()
        y_pos = stats_y + 145
        if not board_data:
            lbl_no = font_mono_s.render("No scores yet.", True, TEXT_DIM)
            screen.blit(lbl_no, (860, y_pos))
        else:
            for r_idx, entry in enumerate(board_data[:4]):
                entry_str = f"#{r_idx+1} {entry['name'][:7]:<7} {entry['time']//60}:{entry['time']%60:02d}"
                lbl_entry = font_mono_s.render(entry_str, True, NEON_GREEN)
                screen.blit(lbl_entry, (860, y_pos))
                y_pos += 20
                
        lbl_reset = font_mono_s.render("Press ESC to reframe.", True, TEXT_DIM)
        screen.blit(lbl_reset, (860, stats_y + 250))
        
    # Draw FPS value in footer
    fps_val = int(clock.get_fps())
    fps_lbl = font_mono_s.render(f"FPS: {fps_val}", True, TEXT_DIM)
    screen.blit(fps_lbl, (20, HEIGHT - 25))
    
    # 5. FLIP AND TICK
    pygame.display.flip()
    clock.tick(30) # Lock to 30 FPS for consistent hand tracking performance

# Clean up
cap.release()
pygame.quit()
cv2.destroyAllWindows()
