import pygame
from .settings import FLOOR_Y


def rotate_bird(bird_surface, bird_movement):
    return pygame.transform.rotozoom(bird_surface, -bird_movement * 3, 1)


def bird_animation(bird_frames, bird_index, bird_rect):
    new_bird = bird_frames[bird_index]
    new_bird_rect = new_bird.get_rect(center=(100, bird_rect.centery))
    return new_bird, new_bird_rect


def check_collision(bird_rect, pipes, death_sound):
    for pipe in pipes:
        if bird_rect.colliderect(pipe):
            death_sound.play()
            return False
    if bird_rect.top <= -100 or bird_rect.bottom >= FLOOR_Y:
        death_sound.play()
        return False
    return True
