import pygame
from .settings import (
    FLOOR_Y, SCREEN_WIDTH,
    MEDAL_BRONZE, MEDAL_SILVER, MEDAL_GOLD, MEDAL_PLATINUM,
)

# Medal colours (drawn as circles, no image needed)
_MEDAL_COLORS = {
    "platinum": (180, 210, 255),
    "gold":     (255, 210, 0),
    "silver":   (200, 200, 200),
    "bronze":   (200, 120, 40),
}


def get_medal(score):
    if score >= MEDAL_PLATINUM:
        return "platinum"
    if score >= MEDAL_GOLD:
        return "gold"
    if score >= MEDAL_SILVER:
        return "silver"
    if score >= MEDAL_BRONZE:
        return "bronze"
    return None


def _draw_medal(screen, medal, center):
    color = _MEDAL_COLORS[medal]
    pygame.draw.circle(screen, color, center, 28)
    pygame.draw.circle(screen, (40, 40, 40), center, 28, 3)
    font = pygame.font.SysFont("Arial", 18, bold=True)
    label = font.render(medal[0].upper(), True, (40, 40, 40))
    screen.blit(label, label.get_rect(center=center))


def draw_floor(screen, floor_surface, floor_x_pos):
    screen.blit(floor_surface, (floor_x_pos, FLOOR_Y))
    screen.blit(floor_surface, (floor_x_pos + SCREEN_WIDTH, FLOOR_Y))


def score_display(screen, game_font, game_state, score, high_score):
    if game_state == "playing":
        surf = game_font.render(str(score), True, (255, 255, 255))
        screen.blit(surf, surf.get_rect(center=(288, 100)))

    elif game_state == "game_over":
        surf = game_font.render(f"Score: {score}", True, (255, 255, 255))
        screen.blit(surf, surf.get_rect(center=(288, 100)))

        hi_surf = game_font.render(f"Best: {high_score}", True, (255, 215, 0))
        screen.blit(hi_surf, hi_surf.get_rect(center=(288, 860)))

        medal = get_medal(score)
        if medal:
            _draw_medal(screen, medal, (288, 800))


def update_score(score, high_score):
    return max(score, high_score)


class ScorePopup:
    """Floating +1 text that fades out upward when a pipe is cleared."""

    def __init__(self, x, y, font):
        self.x = x
        self.y = float(y)
        self.font = font
        self._age = 0
        self._lifetime = 45  # frames

    def update(self):
        self._age += 1
        self.y -= 1.2

    def draw(self, screen):
        alpha = max(0, 255 - int(self._age * (255 / self._lifetime)))
        surf = self.font.render("+1", True, (255, 255, 80))
        surf.set_alpha(alpha)
        screen.blit(surf, surf.get_rect(center=(self.x, int(self.y))))

    @property
    def alive(self):
        return self._age < self._lifetime
