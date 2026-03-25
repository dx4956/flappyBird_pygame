"""
neat_player.py — Train a neural network to play Flappy Bird using NEAT.

Controls during training:
  F      — toggle fast mode (skip rendering, trains much faster)
  S      — save current best genome as final model and close training
  ESC    — skip current generation early
  Ctrl+C — stop and save best genome found so far

Inputs to the network (7):
  1. bird_y / screen_height              — absolute height (0–1)
  2. bird_vel / 15                        — velocity, signed (-1..+1 range)
  3. dist_to_pipe / screen_width          — horizontal distance to current pipe
  4. gap_centre_y / screen_height         — vertical centre of current opening (location)
  5. (bird_y - gap_centre) / screen_h     — signed offset from gap centre ← key signal
  6. dist_to_next_pipe / screen_width     — lookahead: distance to next pipe
  7. next_gap_centre_y / screen_height    — lookahead: centre of next opening (location)
"""

import pickle
import sys
from pathlib import Path

import neat
import pygame

from game.pipes import create_pipe, draw_pipes, move_pipes
from game.settings import (
    BASE_PIPE_SPEED,
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
MODELS_DIR = ROOT / "models"
GENERATION_DIR = MODELS_DIR / "generation"
CHECKPOINTS_DIR = MODELS_DIR / "checkpoints"
BEST_GENOME_PATH = GENERATION_DIR / "best_genome.pkl"
CHECKPOINT_PREFIX = str(CHECKPOINTS_DIR / "neat-checkpoint-")

# Ensure directories exist
GENERATION_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Training constants
# ---------------------------------------------------------------------------
FPS = 60
PIPE_SPAWN_FRAMES = 100  # ~1667ms at 60fps — more breathing room between pipes
BIRD_X = 100
BIRD_START_Y = 512
FLAP_COOLDOWN = 2  # 2 frames (~33ms) — allows rapid burst-tapping like a human
VEL_NORM = 12.0  # divisor for velocity normalisation (matches FLAP_STRENGTH=-9)

# Fitness rewards / penalties  (rebalanced — pipe clearing is now dominant)
REWARD_SURVIVE = 0.1  # per frame alive (tiny — survival alone isn't the goal)
REWARD_PIPE = 50.0  # per pipe cleared (the PRIMARY fitness signal)
REWARD_PROXIMITY = 1.0  # per frame, scaled by closeness to gap centre
PENALTY_OOB = 5.0  # out of bounds (floor / ceiling)
PENALTY_PIPE = 5.0  # hit a pipe
PENALTY_FLAP = 0.0  # no penalty — let NEAT learn to tap freely like a human

# Training length — increase this to train longer
MAX_GENERATIONS = 50000

# ---------------------------------------------------------------------------
# Pygame + assets
# ---------------------------------------------------------------------------
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Flappy Bird — NEAT Training")
clock = pygame.time.Clock()
hud_font = pygame.font.SysFont("Arial", 21, bold=True)

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
# Bird — one instance per genome per generation
# ---------------------------------------------------------------------------


class Bird:
    def __init__(self):
        self.vel = 0.0
        self._idx = 0
        self._anim_timer = 0
        self._flap_cooldown = 0
        self.surface = bird_frames[0]
        self.rect = bird_frames[0].get_rect(center=(BIRD_X, BIRD_START_Y))

    def flap(self):
        """Flap only if cooldown has expired. Returns True when a flap occurs."""
        if self._flap_cooldown <= 0:
            self.vel = FLAP_STRENGTH
            self._flap_cooldown = FLAP_COOLDOWN
            return True
        return False

    def update(self):
        self.vel += GRAVITY
        self.rect.centery += int(self.vel)
        if self._flap_cooldown > 0:
            self._flap_cooldown -= 1
        self._anim_timer += 1
        if self._anim_timer >= 5:
            self._anim_timer = 0
            self._idx = (self._idx + 1) % len(bird_frames)
            self.surface = bird_frames[self._idx]

    def draw(self, surface):
        rotated = pygame.transform.rotozoom(self.surface, -self.vel * 3, 1)
        surface.blit(rotated, rotated.get_rect(center=self.rect.center))

    def hit_pipe(self, pipes):
        return any(self.rect.colliderect(p) for p in pipes)

    def out_of_bounds(self):
        return self.rect.top <= -100 or self.rect.bottom >= FLOOR_Y

    def is_dead(self, pipes):
        return self.hit_pipe(pipes) or self.out_of_bounds()


# ---------------------------------------------------------------------------
# Pipe helpers
# ---------------------------------------------------------------------------


def get_pipe_pairs(pipes):
    """
    Return a list of up to 2 (bottom_pipe, top_pipe) tuples for the next
    upcoming pipe pairs, sorted closest-first.

    We use BIRD_X + 40 (≈ half the bird sprite width) so the bird keeps
    targeting the current gap until it has fully cleared the pipe.
    Switching targets mid-crossing caused birds to veer into pipes.
    """
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


def gap_centre(bottom_pipe, top_pipe):
    """Y coordinate of the midpoint of the pipe opening."""
    return (top_pipe.bottom + bottom_pipe.top) / 2.0


def half_gap(bottom_pipe, top_pipe):
    """Half the vertical size of the pipe opening."""
    return max(1.0, (bottom_pipe.top - top_pipe.bottom) / 2.0)


def build_inputs(bird, pairs):
    """
    Build the 7-element normalised input vector for the neural network.
    Gap size is fixed (constant), so only gap LOCATION inputs are included.
    """
    by = bird.rect.centery

    if pairs:
        bp, tp = pairs[0]
        gc = gap_centre(bp, tp)
        inputs = [
            by / SCREEN_HEIGHT,  # 1. bird height
            bird.vel / VEL_NORM,  # 2. bird velocity (signed)
            (bp.centerx - BIRD_X) / SCREEN_WIDTH,  # 3. dist to current pipe
            gc / SCREEN_HEIGHT,  # 4. gap centre location
            (by - gc) / SCREEN_HEIGHT,  # 5. signed offset from centre
        ]
        if len(pairs) >= 2:
            bp2, tp2 = pairs[1]
            gc2 = gap_centre(bp2, tp2)
            inputs += [
                (bp2.centerx - BIRD_X) / SCREEN_WIDTH,  # 6. dist to next pipe
                gc2 / SCREEN_HEIGHT,  # 7. next gap centre location
            ]
        else:
            inputs += [1.0, 0.5]
    else:
        inputs = [by / SCREEN_HEIGHT, bird.vel / VEL_NORM, 1.0, 0.5, 0.0, 1.0, 0.5]

    return inputs


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------


def draw_hud(alive, pop_size, score, gen, best, best_fit, frame, n_species, fast):
    panel = pygame.Surface((270, 292), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 150))
    screen.blit(panel, (6, 6))

    lines = [
        ("── NEAT TRAINER ──", (160, 160, 255)),
        (f"Generation  : {gen}", (255, 255, 255)),
        (f"Species     : {n_species}", (180, 220, 255)),
        (f"Alive       : {alive} / {pop_size}", (100, 255, 100)),
        (f"Frame       : {frame}", (170, 170, 170)),
        ("", None),
        ("── SCORE ──", (160, 160, 255)),
        (f"This gen    : {score}", (255, 255, 100)),
        (f"All-time    : {best}", (255, 165, 0)),
        (f"Best fit    : {best_fit:.1f}", (255, 130, 80)),
        ("", None),
        (f"[F] Fast    : {'ON ⚡' if fast else 'OFF'}", (200, 120, 255)),
        ("[S] Save & Quit", (100, 255, 160)),
    ]
    for i, (text, color) in enumerate(lines):
        if text and color:
            surf = hud_font.render(text, True, color)
            screen.blit(surf, (14, 14 + i * 21))


# ---------------------------------------------------------------------------
# Global cross-generation state
# ---------------------------------------------------------------------------
generation = 0
best_score = 0
best_fitness = 0.0
fast_mode = False
species_count = 0
best_genome_ever = None

# ---------------------------------------------------------------------------
# Species reporter
# ---------------------------------------------------------------------------


class SpeciesCountReporter(neat.reporting.BaseReporter):
    def post_evaluate(self, config, population, species_set, best_genome):
        global species_count
        species_count = len(species_set.species)


# ---------------------------------------------------------------------------
# NEAT evaluation — called once per generation
# ---------------------------------------------------------------------------


def eval_genomes(genomes, config):
    global generation, best_score, best_fitness, fast_mode, best_genome_ever

    generation += 1
    pop_size = len(genomes)

    # One Bird + network + genome entry per individual
    nets = []
    birds = []
    ge = []
    for _, genome in genomes:
        genome.fitness = 0.0
        ge.append(genome)
        nets.append(neat.nn.FeedForwardNetwork.create(genome, config))
        birds.append(Bird())

    pipes = []
    floor_x = 0
    frame = 0
    score = 0

    # No tracking set needed — we score by detecting the exact frame
    # a pipe's right edge crosses BIRD_X (geometry-only, no id/set bugs).

    pipes.extend(create_pipe(pipe_surface))  # first pipe right away

    while birds:
        # ── Events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    fast_mode = not fast_mode
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_s:
                    to_save = best_genome_ever
                    if to_save is None and ge:
                        to_save = max(ge, key=lambda genome: genome.fitness)
                    if to_save is not None:
                        with open(BEST_GENOME_PATH, "wb") as f:
                            pickle.dump(to_save, f)
                        print(f"\nSaved genome (S key) → {BEST_GENOME_PATH}")
                        print(f"Fitness: {to_save.fitness:.1f}  |  Best score: {best_score}")
                    pygame.quit()
                    sys.exit()

        frame += 1

        # ── Spawn pipes ───────────────────────────────────────────────────
        if frame % PIPE_SPAWN_FRAMES == 0:
            pipes.extend(create_pipe(pipe_surface))

        pipes = move_pipes(pipes, BASE_PIPE_SPEED)

        # ── Score: reward all living genomes when a pipe is cleared ───────
        # Score on the EXACT frame the pipe's right edge crosses BIRD_X.
        # pipe.right was >= BIRD_X last frame and < BIRD_X now, so:
        #   pipe.right < BIRD_X  AND  pipe.right >= BIRD_X - speed
        for pipe in pipes:
            if (
                pipe.bottom >= SCREEN_HEIGHT
                and pipe.right < BIRD_X
                and pipe.right >= BIRD_X - BASE_PIPE_SPEED
            ):
                score += 1
                if score > best_score:
                    best_score = score
                for g in ge:
                    g.fitness += REWARD_PIPE

        # ── Proximity reward: bonus for flying close to the gap centre ────
        pairs = get_pipe_pairs(pipes)

        to_remove = []
        for i, bird in enumerate(birds):
            ge[i].fitness += REWARD_SURVIVE

            # Proximity to gap centre
            if pairs:
                bp, tp = pairs[0]
                gc = gap_centre(bp, tp)
                hg = half_gap(bp, tp)
                dist = abs(bird.rect.centery - gc)
                # 1.0 when perfectly centred, 0.0 when at the pipe edge
                closeness = max(0.0, 1.0 - dist / hg)
                ge[i].fitness += REWARD_PROXIMITY * closeness

            # Neural net decision — low threshold so bird taps eagerly
            output = nets[i].activate(build_inputs(bird, pairs))
            if output[0] > -0.2:  # biased toward flapping — NEAT learns when NOT to
                if bird.flap():
                    ge[i].fitness -= PENALTY_FLAP

            bird.update()

            if bird.hit_pipe(pipes):
                ge[i].fitness -= PENALTY_PIPE
                to_remove.append(i)
            elif bird.out_of_bounds():
                ge[i].fitness -= PENALTY_OOB
                to_remove.append(i)

        for i in reversed(to_remove):
            birds.pop(i)
            nets.pop(i)
            ge.pop(i)

        # Update global best fitness + best genome ever
        if ge:
            best_g = max(ge, key=lambda g: g.fitness)
            if best_g.fitness > best_fitness:
                best_fitness = best_g.fitness
                best_genome_ever = best_g

        # ── Floor scroll ──────────────────────────────────────────────────
        floor_x -= FLOOR_SPEED
        if floor_x <= -SCREEN_WIDTH:
            floor_x = 0

        # ── Render ────────────────────────────────────────────────────────
        if not fast_mode:
            screen.blit(bg_surface, (0, 0))
            draw_pipes(screen, pipe_surface, pipes)
            for bird in birds:
                bird.draw(screen)
            draw_floor(screen, floor_surface, floor_x)
            draw_hud(
                len(birds),
                pop_size,
                score,
                generation,
                best_score,
                best_fitness,
                frame,
                species_count,
                fast_mode,
            )
            pygame.display.update()
            clock.tick(FPS)
        else:
            if frame % 120 == 0:
                screen.fill((15, 15, 30))
                draw_hud(
                    len(birds),
                    pop_size,
                    score,
                    generation,
                    best_score,
                    best_fitness,
                    frame,
                    species_count,
                    fast_mode,
                )
                label = hud_font.render(
                    "FAST MODE — press F to watch", True, (180, 90, 255)
                )
                screen.blit(
                    label,
                    label.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)),
                )
                pygame.display.update()
            clock.tick(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run():
    def _checkpoint_gen(p):
        try:
            return int(p.name.split("-")[-1])
        except ValueError:
            return -1

    checkpoints = sorted(CHECKPOINTS_DIR.glob("neat-checkpoint-*"), key=_checkpoint_gen)

    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        str(CONFIG_PATH),
    )

    if checkpoints:
        latest = checkpoints[-1]
        try:
            pop = neat.Checkpointer.restore_checkpoint(str(latest))
            print(f"Resumed from checkpoint: {latest.name}")
        except Exception as e:
            print(f"Checkpoint load failed ({e}), starting fresh.")
            pop = neat.Population(config)
    else:
        pop = neat.Population(config)

    pop.add_reporter(neat.StdOutReporter(True))
    pop.add_reporter(neat.StatisticsReporter())
    pop.add_reporter(SpeciesCountReporter())
    pop.add_reporter(
        neat.Checkpointer(
            generation_interval=5,
            filename_prefix=CHECKPOINT_PREFIX,
        )
    )

    try:
        winner = pop.run(eval_genomes, n=MAX_GENERATIONS)
    except KeyboardInterrupt:
        print("\nTraining interrupted — saving best genome found so far.")
        winner = pop.best_genome
    except SystemExit:
        # S key was pressed — genome already saved inside eval_genomes
        return

    with open(BEST_GENOME_PATH, "wb") as f:
        pickle.dump(winner, f)
    print(f"\nBest genome saved → {BEST_GENOME_PATH}")
    print(f"Best fitness: {winner.fitness:.1f}  |  Best score: {best_score}")


if __name__ == "__main__":
    run()
