import pygame
import time
import os
#os.environ['DISPLAY'] = ".:0"
os.environ['SDL_VIDEODRIVER'] = "x11"
try:    
    pygame.init()
    screen = pygame.display.set_mode((800, 480))
    pygame.display.set_caption("display test")
    clock = pygame.time.Clock()

    print("window should stay open")
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                runnning = False
            screen.fill((20,20,40))
            pygame.draw.rect(screen, (80,180,255), (100,100,200,150))
            pygame.display.flip()
            clock.tick(30)
        
        pygame.quit()
        print("close normally")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("ERROR: ", e)