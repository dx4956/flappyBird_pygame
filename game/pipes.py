import random

import pygame

from .settings import PIPE_GAP, PIPE_HEIGHTS, SCREEN_HEIGHT


def create_pipe(pipe_surface):
    random_pipe_pos = random.choice(PIPE_HEIGHTS)
    bottom_pipe = pipe_surface.get_rect(midtop=(700, random_pipe_pos))
    top_pipe = pipe_surface.get_rect(midbottom=(700, random_pipe_pos - PIPE_GAP))
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


def check_pipe_score(pipes, bird_rect, speed):
    """Return points scored this frame using frame-crossing detection.
    No tracking set needed — scores on the exact frame a pipe clears the bird.
    """
    points = 0
    for pipe in pipes:
        if (
            pipe.bottom >= SCREEN_HEIGHT
            and pipe.right < bird_rect.left
            and pipe.right >= bird_rect.left - speed
        ):
            points += 1
    return points
