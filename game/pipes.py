import random
import pygame
from .settings import PIPE_HEIGHTS, SCREEN_HEIGHT


def create_pipe(pipe_surface):
    random_pipe_pos = random.choice(PIPE_HEIGHTS)
    bottom_pipe = pipe_surface.get_rect(midtop=(700, random_pipe_pos))
    top_pipe = pipe_surface.get_rect(midbottom=(700, random_pipe_pos - 300))
    return bottom_pipe, top_pipe


def move_pipes(pipes, speed):
    for pipe in pipes:
        pipe.centerx -= speed
    return [p for p in pipes if p.right > -50]


def draw_pipes(screen, pipe_surface, pipes):
    for pipe in pipes:
        if pipe.bottom >= SCREEN_HEIGHT:
            screen.blit(pipe_surface, pipe)
        else:
            flip_pipe = pygame.transform.flip(pipe_surface, False, True)
            screen.blit(flip_pipe, pipe)


def check_pipe_score(pipes, bird_rect, scored_ids):
    """Return points scored this frame and updated scored_ids set."""
    points = 0
    for pipe in pipes:
        pid = id(pipe)
        if pid not in scored_ids and pipe.right < bird_rect.left:
            scored_ids.add(pid)
            if pipe.bottom >= SCREEN_HEIGHT:  # count bottom pipe only (avoid double)
                points += 1
    return points, scored_ids
