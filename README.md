# Flappy Bird — pygame

A feature-rich Flappy Bird clone built with Python and pygame, including difficulty scaling, a medal system, persistent high scores, and screen shake feedback.

## Features

- **Proper pipe-clear scoring** — score increments by 1 each time a pipe pair is cleared
- **Persistent high score** — saved to `highscore.json` between sessions
- **Medal system** — earn Bronze / Silver / Gold / Platinum based on your score
- **Difficulty scaling** — pipes speed up and spawn faster every 5 points
- **Day / Night cycle** — background toggles every 10 points
- **Screen shake** — camera shakes on death for game-feel feedback
- **Score popups** — floating +1 animation when clearing a pipe

## Project Structure

```
flappyBird_pygame/
├── main.py               # Entry point — game loop, state machine, asset loading
├── game/
│   ├── settings.py       # All tunable constants (gravity, speed, medals, etc.)
│   ├── bird.py           # Bird rotation, animation, collision detection
│   ├── pipes.py          # Pipe creation, movement, cleanup, score detection
│   └── ui.py             # Floor, score display, medals, score popups
├── assets/
│   ├── fonts/            # 04B_19.TTF
│   ├── images/           # Backgrounds, bird sprites, pipes, UI
│   └── sounds/           # WAV sound effects
├── requirements.txt
└── highscore.json        # Auto-generated on first run
```

## Requirements

- Python 3.13 (pygame does not yet ship wheels for 3.14)
- pygame

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

# 4. Run the game
python main.py
```

## Controls

| Key       | Action              |
|-----------|---------------------|
| `Space`   | Flap / Start / Restart |
| Close window | Quit            |

## Medal Thresholds

| Medal    | Score Required |
|----------|---------------|
| Bronze   | 5             |
| Silver   | 10            |
| Gold     | 20            |
| Platinum | 40            |

## Difficulty Progression

Every 5 points the game increases in difficulty:

| Points | Pipe Speed | Spawn Interval |
|--------|-----------|----------------|
| 0      | 5 px/f    | 1200 ms        |
| 5      | 6 px/f    | 1150 ms        |
| 10     | 7 px/f    | 1100 ms        |
| ...    | ...        | ...            |
| 25+    | 10 px/f *(cap)* | 750 ms *(cap)* |

## Tuning

All game constants are in `game/settings.py`. Key values:

```python
GRAVITY               = 0.25
FLAP_STRENGTH         = -12
BASE_PIPE_SPEED       = 5
BASE_PIPE_SPAWN_INTERVAL = 1200  # ms
DIFFICULTY_STEP       = 5        # points per difficulty level
BG_SWITCH_EVERY       = 10       # points between day/night toggle
MEDAL_BRONZE/SILVER/GOLD/PLATINUM = 5 / 10 / 20 / 40
```
