"""
run_ai.py — Watch the trained NEAT model play Flappy Bird.

Loads the best genome from models/generation/best_genome.pkl and runs it
against the game in real time.

Controls:
  R          — restart current run
  Q / Escape — quit
"""

import pickle
import sys
from pathlib import Path

import neat
import pygame

from game.pipes import create_pipe, draw_pipes, move_pipes
from game.settings import (
    BASE_PIPE_SPEED,
    BIRD_FLAP_INTERVAL,
    FLAP_STRENGTH,
    FLOOR_SPEED,
    FLOOR_Y,
    GRAVITY,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from game.ui import draw_floor

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
IMAGES = ROOT / "assets" / "images"
FONTS = ROOT / "assets" / "fonts"
CONFIG_PATH = ROOT / "neat_config.txt"
BEST_GENOME_PATH = ROOT / "models" / "generation" / "best_genome.pkl"

# ---------------------------------------------------------------------------
# Constants — MUST match neat_player.py exactly
# ---------------------------------------------------------------------------
FPS = 60
PIPE_SPAWN_FRAMES = 100  # was 72 — matches updated trainer
BIRD_X = 100
BIRD_START_Y = 512
FLAP_COOLDOWN = 2  # was 15 — matches updated trainer (burst-tapping)
VEL_NORM = 12.0  # was 15.0 — matches FLAP_STRENGTH=-9

# ---------------------------------------------------------------------------
# Pygame init
# ---------------------------------------------------------------------------
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Flappy Bird — AI Playback")
clock = pygame.time.Clock()
game_font = pygame.font.Font(FONTS / "04B_19.TTF", 40)
hud_font = pygame.font.SysFont("Arial", 22, bold=True)

bg_surface = pygame.transform.scale2x(
    pygame.image.load(IMAGES / "background-day.png").convert()
)
floor_surface = pygame.transform.scale2x(
    pygame.image.load(IMAGES / "base.png").convert()
)
pipe_surface = pygame.transform.scale2x(pygame.image.load(IMAGES / "pipe-green.png"))
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

# ---------------------------------------------------------------------------
# Helpers — identical to neat_player.py so the same genome runs correctly
# ---------------------------------------------------------------------------


def get_pipe_pairs(pipes):
    """Uses BIRD_X + 40 margin — must match trainer exactly."""
    bird_clear_x = BIRD_X + 40  # don't switch target until bird is fully past
    bottom_pipes = sorted(
        [p for p in pipes if p.bottom >= SCREEN_HEIGHT and p.right > bird_clear_x],
        key=lambda p: p.centerx,
    )
    top_pipes = [p for p in pipes if p.bottom < SCREEN_HEIGHT]
    pairs = []
    for bp in bottom_pipes[:2]:
        if not top_pipes:
            break
        tp = min(top_pipes, key=lambda p: abs(p.centerx - bp.centerx))
        pairs.append((bp, tp))
    return pairs


def gap_centre(bp, tp):
    return (tp.bottom + bp.top) / 2.0


def build_inputs(bird_y, bird_vel, pairs):
    if pairs:
        bp, tp = pairs[0]
        gc = gap_centre(bp, tp)
        inputs = [
            bird_y / SCREEN_HEIGHT,
            bird_vel / VEL_NORM,
            (bp.centerx - BIRD_X) / SCREEN_WIDTH,
            gc / SCREEN_HEIGHT,
            (bird_y - gc) / SCREEN_HEIGHT,
        ]
        if len(pairs) >= 2:
            bp2, tp2 = pairs[1]
            gc2 = gap_centre(bp2, tp2)
            inputs += [(bp2.centerx - BIRD_X) / SCREEN_WIDTH, gc2 / SCREEN_HEIGHT]
        else:
            inputs += [1.0, 0.5]
    else:
        inputs = [bird_y / SCREEN_HEIGHT, bird_vel / VEL_NORM, 1.0, 0.5, 0.0, 1.0, 0.5]
    return inputs


def draw_hud(score, best, run):
    panel = pygame.Surface((230, 100), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 140))
    screen.blit(panel, (6, 6))
    lines = [
        (f"Run         : {run}", (180, 180, 255)),
        (f"Score       : {score}", (255, 255, 100)),
        (f"Best        : {best}", (255, 165, 0)),
        ("R=Restart  Q=Quit", (160, 160, 160)),
    ]
    for i, (text, color) in enumerate(lines):
        surf = hud_font.render(text, True, color)
        screen.blit(surf, (14, 12 + i * 22))


# ---------------------------------------------------------------------------
# Load genome + build network
# ---------------------------------------------------------------------------

if not BEST_GENOME_PATH.exists():
    print(f"No trained model found at {BEST_GENOME_PATH}")
    print("Run  python neat_player.py  first to train the AI.")
    sys.exit(1)

config = neat.Config(
    neat.DefaultGenome,
    neat.DefaultReproduction,
    neat.DefaultSpeciesSet,
    neat.DefaultStagnation,
    str(CONFIG_PATH),
)

with open(BEST_GENOME_PATH, "rb") as f:
    genome = pickle.load(f)

net = neat.nn.FeedForwardNetwork.create(genome, config)
print(f"Loaded genome  fitness={genome.fitness:.1f}")

# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------

BIRDFLAP = pygame.USEREVENT + 1
pygame.time.set_timer(BIRDFLAP, BIRD_FLAP_INTERVAL)


def new_run_state():
    return {
        "bird_y": float(BIRD_START_Y),
        "bird_vel": 0.0,
        "bird_idx": 0,
        "bird_surface": bird_frames[0],
        "bird_rect": bird_frames[0].get_rect(center=(BIRD_X, BIRD_START_Y)),
        "flap_cooldown": 0,
        "pipes": [],
        "floor_x": 0,
        "frame": 0,
        "score": 0,
        "alive": True,
    }


best_score = 0
run_number = 0

state = new_run_state()
run_number += 1
state["pipes"].extend(create_pipe(pipe_surface))

while True:
    # ── Events ────────────────────────────────────────────────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_q, pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.key == pygame.K_r:
                state = new_run_state()
                run_number += 1
                state["pipes"].extend(create_pipe(pipe_surface))
        if event.type == BIRDFLAP and state["alive"]:
            state["bird_idx"] = (state["bird_idx"] + 1) % len(bird_frames)
            state["bird_surface"] = bird_frames[state["bird_idx"]]
            state["bird_rect"] = state["bird_surface"].get_rect(
                center=(BIRD_X, int(state["bird_y"]))
            )

    # ── Auto-restart after death (2-second pause) ─────────────────────────
    if not state["alive"]:
        state["_dead_timer"] = state.get("_dead_timer", 0) + 1
        if state["_dead_timer"] >= FPS * 2:
            state = new_run_state()
            run_number += 1
            state["pipes"].extend(create_pipe(pipe_surface))

    if state["alive"]:
        state["frame"] += 1

        # ── Pipes ─────────────────────────────────────────────────────────
        if state["frame"] % PIPE_SPAWN_FRAMES == 0:
            state["pipes"].extend(create_pipe(pipe_surface))
        state["pipes"] = move_pipes(state["pipes"], BASE_PIPE_SPEED)

        # ── Score — frame-crossing detection, no id() ─────────────────────
        for pipe in state["pipes"]:
            if (
                pipe.bottom >= SCREEN_HEIGHT
                and pipe.right < BIRD_X
                and pipe.right >= BIRD_X - BASE_PIPE_SPEED
            ):
                state["score"] += 1
                if state["score"] > best_score:
                    best_score = state["score"]

        # ── Neural net decision — threshold must match trainer ────────────
        pairs = get_pipe_pairs(state["pipes"])
        inputs = build_inputs(
            float(state["bird_rect"].centery), state["bird_vel"], pairs
        )
        output = net.activate(inputs)

        if output[0] > -0.2 and state["flap_cooldown"] <= 0:
            state["bird_vel"] = FLAP_STRENGTH
            state["flap_cooldown"] = FLAP_COOLDOWN

        # ── Physics — mirrors training: centery += int(vel) each frame ──
        state["bird_vel"] += GRAVITY
        state["bird_rect"].centery += int(state["bird_vel"])
        state["bird_y"] = float(state["bird_rect"].centery)
        if state["flap_cooldown"] > 0:
            state["flap_cooldown"] -= 1

        # ── Collision ─────────────────────────────────────────────────────
        dead = (
            state["bird_rect"].top <= -100
            or state["bird_rect"].bottom >= FLOOR_Y
            or any(state["bird_rect"].colliderect(p) for p in state["pipes"])
        )
        if dead:
            state["alive"] = False
            state["_dead_timer"] = 0

        # ── Floor scroll ──────────────────────────────────────────────────
        state["floor_x"] -= FLOOR_SPEED
        if state["floor_x"] <= -SCREEN_WIDTH:
            state["floor_x"] = 0

    # ── Draw ──────────────────────────────────────────────────────────────
    screen.blit(bg_surface, (0, 0))
    draw_pipes(screen, pipe_surface, state["pipes"])

    rotated = pygame.transform.rotozoom(
        state["bird_surface"], -state["bird_vel"] * 3, 1
    )
    screen.blit(rotated, rotated.get_rect(center=state["bird_rect"].center))

    draw_floor(screen, floor_surface, state["floor_x"])
    draw_hud(state["score"], best_score, run_number)

    if not state["alive"]:
        msg = game_font.render("Game Over", True, (255, 80, 80))
        screen.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
        sub = hud_font.render("Restarting...", True, (220, 220, 220))
        screen.blit(
            sub, sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
        )

    pygame.display.update()
    clock.tick(FPS)
