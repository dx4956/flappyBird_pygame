# Flappy Bird — pygame + NEAT AI

A feature-rich Flappy Bird clone built with Python and pygame, with a NEAT neural network that learns to play the game autonomously.

## Features

### Game
- **Proper pipe-clear scoring** — score increments by 1 each time a pipe pair is cleared
- **Persistent high score** — saved to `gamedata/highscore.json` between sessions
- **Medal system** — earn Bronze / Silver / Gold / Platinum based on your score
- **Difficulty scaling** — pipes speed up and spawn faster every 5 points
- **Day / Night cycle** — background toggles every 10 points
- **Screen shake** — camera shakes on death for game-feel feedback
- **Score popups** — floating +1 animation when clearing a pipe

### AI (NEAT)
- **Neuroevolution** — a population of 150 birds evolves over generations using the NEAT algorithm
- **7-input neural network** — bird height, velocity, pipe distance, gap centre, signed offset from gap, lookahead to next pipe
- **Fast mode** — skip rendering to train at maximum speed
- **Auto-resume** — checkpoints save every 5 generations and are restored on next run
- **Save & Quit** — press `S` at any point to save the current best genome and close the trainer
- **Best genome export** — saved to `models/generation/best_genome.pkl`
- **AI playback** — watch the trained model play in real time with `run_ai.py`

## Project Structure

```
flappyBird_pygame/
├── main.py               # Human-playable game — loop, state machine, asset loading
├── neat_player.py        # NEAT AI training script
├── run_ai.py             # Watch the trained AI play
├── neat_config.txt       # NEAT hyperparameters (population, mutation rates, etc.)
├── game/
│   ├── settings.py       # All tunable constants (gravity, speed, medals, etc.)
│   ├── bird.py           # Bird rotation, animation, collision detection
│   ├── pipes.py          # Pipe creation, movement, cleanup, score detection
│   └── ui.py             # Floor, score display, medals, score popups
├── assets/
│   ├── fonts/            # 04B_19.TTF
│   ├── images/           # Backgrounds, bird sprites, pipes, UI
│   └── sounds/           # WAV sound effects
├── models/
│   ├── generation/       # best_genome.pkl — saved after training
│   └── checkpoints/      # neat-checkpoint-N — auto-saved every 5 generations
├── gamedata/
│   └── highscore.json    # Auto-generated on first run
└── requirements.txt
```

## Requirements

- Python 3.13 (pygame does not yet ship wheels for Python 3.14)
- pygame
- neat-python

> **Note:** pygame 2.6.x has no pre-built wheel for Python 3.14. Install Python 3.13 from [python.org](https://www.python.org/downloads/) and create a fresh virtual environment with it.

## Setup

```bash
# 1. Create a virtual environment with Python 3.13
py -3.13 -m venv .venv

# 2. Activate it
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4a. Play the game yourself
python main.py

# 4b. Train the AI
python neat_player.py

# 4c. Watch the trained AI play
python run_ai.py
```

## Controls

### Human game (`main.py`)

| Key          | Action                  |
|--------------|-------------------------|
| `Space`      | Flap / Start / Restart  |
| Close window | Quit                    |

### AI training (`neat_player.py`)

| Key      | Action                                         |
|----------|------------------------------------------------|
| `F`      | Toggle fast mode (no rendering, trains faster) |
| `S`      | Save current best genome as final model & quit |
| `ESC`    | Skip current generation early                  |
| `Ctrl+C` | Stop training and save best genome             |

### AI playback (`run_ai.py`)

| Key          | Action           |
|--------------|------------------|
| `R`          | Restart current run |
| `Q` / `ESC`  | Quit             |

## NEAT — How It Works

Each bird is controlled by a small feed-forward neural network. Birds that survive longer and clear more pipes receive higher fitness scores. After every generation the worst performers are culled and the best are mutated and bred to form the next generation.

### Neural Network Inputs (7)

| # | Input | Range |
|---|-------|-------|
| 1 | Bird Y position | `0 – 1` |
| 2 | Bird velocity (signed) | `~-1 – 1` |
| 3 | Horizontal distance to current pipe | `0 – 1` |
| 4 | Gap centre Y of current pipe | `0 – 1` |
| 5 | Signed offset from gap centre | `-1 – 1` |
| 6 | Horizontal distance to next pipe | `0 – 1` |
| 7 | Gap centre Y of next pipe | `0 – 1` |

**Output:** single value — if `> -0.2`, the bird flaps (biased toward flapping; NEAT learns when *not* to).

### Fitness Function

| Event | Reward / Penalty |
|-------|-----------------|
| Each frame alive | +0.1 |
| Each frame near gap centre (scaled) | up to +1.0 |
| Pipe cleared | +50.0 |
| Hit a pipe | −5.0 |
| Out of bounds (floor / ceiling) | −5.0 |

### NEAT Config Highlights (`neat_config.txt`)

| Parameter | Value |
|-----------|-------|
| Population size | 150 |
| Activation | tanh |
| Inputs / Outputs | 7 / 1 |
| Initial hidden nodes | 0 |
| Max generations | 50 000 |
| Checkpoint interval | every 5 generations |

## Medal Thresholds

| Medal    | Score Required |
|----------|----------------|
| Bronze   | 5              |
| Silver   | 10             |
| Gold     | 20             |
| Platinum | 40             |

## Difficulty Progression

Every 5 points the game increases in difficulty:

| Points | Pipe Speed | Spawn Interval |
|--------|------------|----------------|
| 0      | 5 px/f     | 1200 ms        |
| 5      | 6 px/f     | 1150 ms        |
| 10     | 7 px/f     | 1100 ms        |
| ...    | ...        | ...            |
| 25+    | 10 px/f *(cap)* | 750 ms *(cap)* |

## Tuning

All game constants are in `game/settings.py`:

```python
GRAVITY                  = 0.25
FLAP_STRENGTH            = -9
BASE_PIPE_SPEED          = 5
BASE_PIPE_SPAWN_INTERVAL = 1200   # ms
PIPE_GAP                 = 375    # px between top and bottom pipe
DIFFICULTY_STEP          = 5      # points per difficulty level
BG_SWITCH_EVERY          = 10     # points between day/night toggle
MEDAL_BRONZE/SILVER/GOLD/PLATINUM = 5 / 10 / 20 / 40
```

NEAT hyperparameters (population size, mutation rates, fitness threshold, etc.) are all in `neat_config.txt`.
