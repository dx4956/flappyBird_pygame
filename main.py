import json
import random
import sys
from pathlib import Path

import pygame

from game.bird import bird_animation, check_collision, rotate_bird
from game.pipes import check_pipe_score, create_pipe, draw_pipes, move_pipes
from game.settings import (
    BASE_PIPE_SPAWN_INTERVAL,
    BASE_PIPE_SPEED,
    BG_SWITCH_EVERY,
    BIRD_FLAP_INTERVAL,
    DIFFICULTY_STEP,
    FLAP_STRENGTH,
    FLOOR_SPEED,
    GRAVITY,
    MAX_PIPE_SPEED,
    MIN_SPAWN_INTERVAL,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHAKE_DURATION,
    SHAKE_INTENSITY,
)
from game.ui import ScorePopup, draw_floor, score_display, update_score

ASSETS = Path(__file__).parent / "assets"
IMAGES = ASSETS / "images"
FONTS = ASSETS / "fonts"
SOUNDS = ASSETS / "sounds"
HIGHSCORE_FILE = Path(__file__).parent / "gamedata" / "highscore.json"

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def load_high_score():
    if HIGHSCORE_FILE.exists():
        try:
            return json.loads(HIGHSCORE_FILE.read_text()).get("high_score", 0)
        except Exception:
            pass
    return 0


def save_high_score(score):
    HIGHSCORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    HIGHSCORE_FILE.write_text(json.dumps({"high_score": score}))


# ---------------------------------------------------------------------------
# Difficulty
# ---------------------------------------------------------------------------


def get_difficulty(score):
    """Return (pipe_speed, spawn_interval_ms) for the current score."""
    level = score // DIFFICULTY_STEP
    speed = min(BASE_PIPE_SPEED + level, MAX_PIPE_SPEED)
    interval = max(BASE_PIPE_SPAWN_INTERVAL - level * 50, MIN_SPAWN_INTERVAL)
    return speed, interval


# ---------------------------------------------------------------------------
# Pygame init
# ---------------------------------------------------------------------------

pygame.mixer.pre_init(frequency=44100, size=16, channels=1, buffer=512)
pygame.init()

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
draw_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))  # shake canvas
pygame.display.set_caption("Flappy Bird")
clock = pygame.time.Clock()
game_font = pygame.font.Font(FONTS / "04B_19.TTF", 40)
small_font = pygame.font.Font(FONTS / "04B_19.TTF", 26)

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

bg_day = pygame.transform.scale2x(
    pygame.image.load(IMAGES / "background-day.png").convert()
)
bg_night = pygame.transform.scale2x(
    pygame.image.load(IMAGES / "background-night.png").convert()
)
floor_surface = pygame.transform.scale2x(
    pygame.image.load(IMAGES / "base.png").convert()
)

bird_frames = [
    pygame.transform.scale2x(
        pygame.image.load(IMAGES / "bluebird-downflap.png").convert_alpha()
    ),
    pygame.transform.scale2x(
        pygame.image.load(IMAGES / "bluebird-midflap.png").convert_alpha()
    ),
    pygame.transform.scale2x(
        pygame.image.load(IMAGES / "bluebird-upflap.png").convert_alpha()
    ),
]

pipe_surface = pygame.transform.scale2x(pygame.image.load(IMAGES / "pipe-green.png"))

game_over_surface = pygame.transform.scale2x(
    pygame.image.load(IMAGES / "message.png").convert_alpha()
)
game_over_rect = game_over_surface.get_rect(center=(288, 512))

flap_sound = pygame.mixer.Sound(SOUNDS / "sfx_wing.wav")
death_sound = pygame.mixer.Sound(SOUNDS / "sfx_hit.wav")
score_sound = pygame.mixer.Sound(SOUNDS / "sfx_point.wav")

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

SPAWNPIPE = pygame.USEREVENT
BIRDFLAP = pygame.USEREVENT + 1
pygame.time.set_timer(SPAWNPIPE, BASE_PIPE_SPAWN_INTERVAL)
pygame.time.set_timer(BIRDFLAP, BIRD_FLAP_INTERVAL)

# ---------------------------------------------------------------------------
# Game state helpers
# ---------------------------------------------------------------------------


def new_game():
    return {
        "state": "menu",  # menu | playing | game_over
        "bird_movement": 0,
        "bird_index": 0,
        "bird_surface": bird_frames[0],
        "bird_rect": bird_frames[0].get_rect(center=(100, 512)),
        "pipe_list": [],
        "score": 0,
        "floor_x_pos": 0,
        "shake_frames": 0,
        "score_popups": [],
        "pipe_speed": BASE_PIPE_SPEED,
        "spawn_interval": BASE_PIPE_SPAWN_INTERVAL,
        "is_night": False,
    }


g = new_game()
high_score = load_high_score()

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

while True:
    # --- Events -----------------------------------------------------------
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if g["state"] == "menu":
                g["state"] = "playing"
                g["bird_movement"] = FLAP_STRENGTH
                flap_sound.play()

            elif g["state"] == "playing":
                g["bird_movement"] = FLAP_STRENGTH
                flap_sound.play()

            elif g["state"] == "game_over":
                pygame.time.set_timer(SPAWNPIPE, BASE_PIPE_SPAWN_INTERVAL)
                g = new_game()
                g["state"] = "playing"
                g["bird_movement"] = FLAP_STRENGTH
                flap_sound.play()

        if event.type == SPAWNPIPE and g["state"] == "playing":
            g["pipe_list"].extend(create_pipe(pipe_surface))

        if event.type == BIRDFLAP:
            g["bird_index"] = (g["bird_index"] + 1) % len(bird_frames)
            g["bird_surface"], g["bird_rect"] = bird_animation(
                bird_frames, g["bird_index"], g["bird_rect"]
            )

    # --- Update -----------------------------------------------------------
    if g["state"] == "playing":
        g["bird_movement"] += GRAVITY
        g["bird_rect"].centery += int(g["bird_movement"])

        g["pipe_list"] = move_pipes(g["pipe_list"], g["pipe_speed"])

        # Score — frame-crossing detection, no more id() bug
        points = check_pipe_score(g["pipe_list"], g["bird_rect"], g["pipe_speed"])
        if points:
            g["score"] += points
            score_sound.play()
            g["score_popups"].append(
                ScorePopup(170, g["bird_rect"].centery - 50, small_font)
            )
            # Difficulty
            new_speed, new_interval = get_difficulty(g["score"])
            if new_interval != g["spawn_interval"]:
                g["spawn_interval"] = new_interval
                pygame.time.set_timer(SPAWNPIPE, new_interval)
            g["pipe_speed"] = new_speed
            # Day / night toggle
            g["is_night"] = (g["score"] // BG_SWITCH_EVERY) % 2 == 1

        # Collision
        if not check_collision(g["bird_rect"], g["pipe_list"], death_sound):
            g["state"] = "game_over"
            g["shake_frames"] = SHAKE_DURATION
            high_score = update_score(g["score"], high_score)
            save_high_score(high_score)

    # --- Screen shake offset ----------------------------------------------
    ox, oy = 0, 0
    if g["shake_frames"] > 0:
        ox = random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY)
        oy = random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY)
        g["shake_frames"] -= 1

    # --- Draw (to off-screen canvas, then blit with shake offset) ---------
    bg = bg_night if g["is_night"] else bg_day
    draw_surface.blit(bg, (0, 0))

    draw_pipes(draw_surface, pipe_surface, g["pipe_list"])

    rotated_bird = rotate_bird(g["bird_surface"], g["bird_movement"])
    draw_surface.blit(rotated_bird, g["bird_rect"])

    if g["state"] == "menu":
        draw_surface.blit(game_over_surface, game_over_rect)

    elif g["state"] == "playing":
        for popup in g["score_popups"]:
            popup.update()
            popup.draw(draw_surface)
        g["score_popups"] = [p for p in g["score_popups"] if p.alive]
        score_display(draw_surface, game_font, "playing", g["score"], high_score)

    elif g["state"] == "game_over":
        draw_surface.blit(game_over_surface, game_over_rect)
        score_display(draw_surface, game_font, "game_over", g["score"], high_score)

    # Floor drawn last so it always sits on top of pipes / bird
    g["floor_x_pos"] -= FLOOR_SPEED
    draw_floor(draw_surface, floor_surface, g["floor_x_pos"])
    if g["floor_x_pos"] <= -SCREEN_WIDTH:
        g["floor_x_pos"] = 0

    # Blit canvas → window with shake offset
    screen.fill((0, 0, 0))
    screen.blit(draw_surface, (ox, oy))

    pygame.display.update()
    clock.tick(120)
