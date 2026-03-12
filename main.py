import pygame
import json
import sys
import math
import time
from pathlib import Path
import random

# ─────────────────────────── CONSTANTS ───────────────────────────
TILE_SIZE   = 32
SCREEN_W    = 1280
SCREEN_H    = 720
FPS         = 60

GRAVITY     = 0.5
JUMP_FORCE  = -8.5  
MOVE_SPEED  = 2.2  
MAX_FALL    = 15.0

# Zoom Factor
ZOOM = 4.5 

BASE_DIR   = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
LEVEL_PATH = BASE_DIR / "levels" / "level1.json"

# ─────────────────────────── HELPERS ─────────────────────────────

def load_font(size):
    font_path = next(ASSETS_DIR.rglob("*.ttf"), None)
    if font_path and font_path.exists():
        return pygame.font.Font(str(font_path), size)
    return pygame.font.SysFont("Arial", size)

def draw_text(surf, font, text, x, y, color=(255, 255, 255), shadow=True):
    if shadow:
        shad = font.render(text, True, (20, 20, 20))
        surf.blit(shad, (round(x) + 2, round(y) + 2))
    txt = font.render(text, True, color)
    surf.blit(txt, (round(x), round(y)))

def draw_circle(surf, center, radius, color, width, progress=1.0):
    # progress [0.0, 1.0] for the circular bar
    rect = pygame.Rect(center[0]-radius, center[1]-radius, radius*2, radius*2)
    # Background ring
    pygame.draw.arc(surf, (40, 40, 45), rect, 0, math.pi*2, width)
    # Progress ring
    if progress > 0:
        pygame.draw.arc(surf, color, rect, -math.pi/2, -math.pi/2 + (math.pi*2*progress), width + 2)

# ─────────────────────────── TILE BANK ───────────────────────────

class TileBank:
    def __init__(self):
        self.tilesets = {}
        self.chest_anims = {} # {type_name: [surfaces]}
        self.load_tiles()
        self.load_chests()

    def load_tiles(self):
        tiles_dir = ASSETS_DIR / "tiles"
        if not tiles_dir.exists(): return
        for p in tiles_dir.glob("*.png"):
            try:
                surf = pygame.image.load(str(p)).convert_alpha()
                sw, sh = surf.get_size()
                tiles = []
                for r in range(sh // TILE_SIZE):
                    row = []
                    for c in range(sw // TILE_SIZE):
                        tile = surf.subsurface(pygame.Rect(c*TILE_SIZE, r*TILE_SIZE, TILE_SIZE, TILE_SIZE)).copy()
                        row.append(tile)
                    tiles.append(row)
                self.tilesets[p.stem] = tiles
            except Exception as e:
                print(f"Error loading tileset {p.name}: {e}")

    def load_chests(self):
        chest_path = ASSETS_DIR / "box" / "TX Chest Animation.png"
        if not chest_path.exists(): return
        try:
            surf = pygame.image.load(str(chest_path)).convert_alpha()
            types = ["Wood Chest", "Iron Chest", "Silver Chest", "Gold Chest"]
            for i, tname in enumerate(types):
                frames = []
                for f in range(6): # 6 frames total (Col 1, 3, 5, 7, 9, 11)
                    # User: 0 1.5 0 1.5 layout (1.5=top, 1=bot). Skipping Col 0.
                    # Row 0=WoodTop, 1=WoodBot, 2=IronTop, 3=IronBot...
                    frame_surf = pygame.Surface((32, 64), pygame.SRCALPHA)
                    tx = (f * 2 + 1) * 32
                    ty_top = (i * 2 + 0) * 32
                    ty_bot = (i * 2 + 1) * 32
                    
                    if tx + 32 <= surf.get_width() and ty_bot + 32 <= surf.get_height():
                        top = surf.subsurface(pygame.Rect(tx, ty_top, 32, 32))
                        bottom = surf.subsurface(pygame.Rect(tx, ty_bot, 32, 32))
                        frame_surf.blit(top, (0, 0))
                        frame_surf.blit(bottom, (0, 32))
                    frames.append(frame_surf)
                self.chest_anims[tname] = frames
        except Exception as e:
            print(f"Error loading chest sheet: {e}")

    def get_tile(self, tile_ref):
        if not tile_ref: return None
        parts = tile_ref.split("_")
        if len(parts) < 3: return None
        ts_name = "_".join(parts[:-2])
        try:
            col, row = int(parts[-2]), int(parts[-1])
            ts = self.tilesets.get(ts_name)
            if ts and row < len(ts) and col < len(ts[row]):
                return ts[row][col]
        except: pass
        return None

# ─────────────────────────── CHEST ───────────────────────────────

class Chest:
    def __init__(self, x, y, ctype, items, tb: TileBank):
        self.world_x = x * TILE_SIZE
        self.world_y = y * TILE_SIZE
        self.type = ctype
        self.items_pool = items.split(",") if items else ["อาหาร", "ยา", "กุญแจ", "น้ำ", "ผลไม้"]
        self.loot_reveal = ""
        self.hud_scale = 0.0
        self.hold_timer = 0.0
        self.spin_timer = 0.0
        self.anim_timer = 0.0
        self.tb = tb
        self.state = "closed"
        self.frame = 0.0
        
    def reset(self):
        self.state = "closed"
        self.frame = 0
        self.hold_timer = 0
        self.spin_timer = 0
        self.anim_timer = 0
        self.loot_reveal = ""
        self.hud_scale = 0.0

    def update(self, dt, player_pos):
        frames = self.tb.chest_anims.get(self.type, [])
        max_f = len(frames) - 1 if frames else 0
        
        if self.state == "closed":
            self.frame = 0
        
        elif self.state == "opening":
            self.frame = min(max_f, int((self.hold_timer / 3.0) * (max_f + 1)))
            if self.hold_timer >= 3.0:
                self.state = "spinning"
                self.spin_timer = 1.0 # 1 second spinning animation
                self.loot_reveal = random.choice(self.items_pool)
                self.hud_scale = 1.0 # Show text immediately for shuffle visibility
                
        elif self.state == "spinning":
            self.spin_timer -= dt
            self.anim_timer += dt
            if self.anim_timer >= 0.08: # Slightly faster shuffle (0.08s)
                self.anim_timer = 0
                self.loot_reveal = random.choice(self.items_pool)
            if self.spin_timer <= 0:
                self.state = "awarding"
                self.loot_reveal = random.choice(self.items_pool)

        # Proximity HUD Scaling (Emergence)
        target_scale = 0.0
        if self.state in ["spinning", "awarding"]:
            cx, cy = self.world_x + 16, self.world_y + 32
            px, py = player_pos
            dist = math.hypot(cx - px, cy - py)
            if dist < 100: # Slightly larger trigger range
                target_scale = 1.0
        self.hud_scale += (target_scale - self.hud_scale) * 0.12 # Smooth transition

    def draw(self, surf, cam_x, cam_y, zoom, font, show_prompt=False):
        frames = self.tb.chest_anims.get(self.type)
        if not frames: return
        
        img = frames[int(self.frame)]
        sz_w = round(32 * zoom)
        sz_h = round(64 * zoom)
        img = pygame.transform.scale(img, (sz_w, sz_h))
        
        sx = round(self.world_x * zoom - cam_x)
        sy = round((self.world_y - 32) * zoom - cam_y)
        surf.blit(img, (sx, sy))
        
        # Draw prompts & loot
        if self.state == "closed" and show_prompt:
            p_tw, _ = font.size(f"Hold [E] to Open")
            # Positioning above the chest: sy is top of 64px chest (which is 1 tile above ground)
            # So sy - 10*zoom is roughly 1.3 tiles above ground.
            draw_text(surf, font, f"Hold [E] to Open", sx + sz_w//2 - p_tw//2, sy - round(10 * zoom), (200, 255, 100))

        if self.hud_scale > 0.01:
            # Color: Yellow for final, Gray for spinning
            col = (255, 255, 100) if self.state == "awarding" else (180, 180, 180)
            
            # Emergence Effect: Text rises from chest body and grows
            # Rising from sy + 32 (middle) up to sy + 17 (lower target)
            base_y = sy + round(32 * zoom)
            target_y = sy + round(17 * zoom) # Lowered from -15 to +17 (approx 1 tile)
            current_y = base_y + (target_y - base_y) * self.hud_scale
            
            # Loot Text
            loot_surf = font.render(self.loot_reveal, True, col)
            lw = int(loot_surf.get_width() * self.hud_scale)
            lh = int(loot_surf.get_height() * self.hud_scale)
            
            if lw > 0 and lh > 0:
                scaled_loot = pygame.transform.scale(loot_surf, (lw, lh))
                surf.blit(scaled_loot, (sx + sz_w//2 - lw//2, round(current_y - lh//2)))
                
                # Collection Prompt
                if self.state == "awarding":
                    prompt_txt = "Press [E] to Receive"
                    p_surf = font.render(prompt_txt, True, (255, 255, 255))
                    pw = int(p_surf.get_width() * self.hud_scale)
                    ph = int(p_surf.get_height() * self.hud_scale)
                    if pw > 0 and ph > 0:
                        scaled_p = pygame.transform.scale(p_surf, (pw, ph))
                        # Spacing: Place prompt above the item text with a gap
                        py = (current_y - lh//2) - ph - round(6 * zoom)
                        surf.blit(scaled_p, (sx + sz_w//2 - pw//2, round(py)))

# ─────────────────────────── GAME MAP ────────────────────────────

class GameMap:
    def __init__(self, data, tb: TileBank):
        self.width = data["map_width"]
        self.height = data["map_height"]
        self.layers = data["layers"]
        self.tb = tb
        
        entities = data.get("entities", {})
        self.player_spawn = entities.get("player_spawn", [2, 2])
        self.exit_pos = entities.get("exit", [self.width - 2, self.height - 2])
        
        self.collision_data = self.layers.get("6", {})
        
        # Load Chests
        self.chests = []
        chest_data = entities.get("chests", {})
        for pos_key, config in chest_data.items():
            cx, cy = map(int, pos_key.split(","))
            self.chests.append(Chest(cx, cy, config["type"], config.get("items", ""), tb))

    def is_solid(self, col, row):
        return f"{col},{row}" in self.collision_data

    def draw(self, surf, camera_x, camera_y, zoom, font):
        ts_zoomed = round(TILE_SIZE * zoom)
        cam_ix, cam_iy = round(camera_x), round(camera_y)
        
        for layer_id in sorted(self.layers.keys(), key=int):
            layer = self.layers[layer_id]
            for pos_key, tile_ref in layer.items():
                try:
                    c, r = map(int, pos_key.split(","))
                    tile_img = self.tb.get_tile(tile_ref)
                    if tile_img:
                        x = round(c * TILE_SIZE * zoom) - cam_ix
                        y = round(r * TILE_SIZE * zoom) - cam_iy
                        if -ts_zoomed < x < SCREEN_W and -ts_zoomed < y < SCREEN_H:
                            img = pygame.transform.scale(tile_img, (ts_zoomed, ts_zoomed))
                            surf.blit(img, (x, y))
                except: continue
        
        # Draw Chests
        for chest in self.chests:
            chest.draw(surf, camera_x, camera_y, zoom, font)

# ─────────────────────────── PLAYER ──────────────────────────────

class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, 24, 30)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.jump_cd = 0 
        self.fall_start_y = self.rect.y
        self.stun_timer = 0 
        
    def update(self, gmap: GameMap, can_move=True):
        keys = pygame.key.get_pressed()
        self.vx = 0
        if self.jump_cd > 0: self.jump_cd -= 1
        if self.stun_timer > 0: self.stun_timer -= 1
        
        speed = MOVE_SPEED
        if self.stun_timer > 0: speed *= 0.5
            
        if can_move:
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: self.vx = -speed
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.vx = speed
                
        self.rect.x += round(self.vx)
        self.collide(gmap, "horizontal")
        
        if not self.on_ground and self.vy < 0:
            self.fall_start_y = self.rect.y
        
        self.vy = min(self.vy + GRAVITY, MAX_FALL)
        if can_move and (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]):
            if self.on_ground and self.jump_cd == 0:
                self.vy = JUMP_FORCE
                self.on_ground = False
                self.jump_cd = 60 
                self.fall_start_y = self.rect.y
            
        self.rect.y += round(self.vy)
        self.collide(gmap, "vertical")

    def collide(self, gmap: GameMap, direction):
        if direction == "horizontal":
            for tx in (self.rect.left, self.rect.right - 1):
                for ty in (self.rect.top, self.rect.centery, self.rect.bottom - 1):
                    if gmap.is_solid(tx // TILE_SIZE, ty // TILE_SIZE):
                        if self.vx > 0: self.rect.right = (tx // TILE_SIZE) * TILE_SIZE
                        elif self.vx < 0: self.rect.left = (tx // TILE_SIZE + 1) * TILE_SIZE
                        self.vx = 0
                        return
        else:
            was_in_air = not self.on_ground
            self.on_ground = False
            for tx in (self.rect.left + 2, self.rect.centerx, self.rect.right - 2):
                for ty in (self.rect.top, self.rect.bottom - 1):
                    if gmap.is_solid(tx // TILE_SIZE, ty // TILE_SIZE):
                        if self.vy > 0:
                            self.rect.bottom = (ty // TILE_SIZE) * TILE_SIZE
                            if was_in_air:
                                fall_dist = self.rect.y - self.fall_start_y
                                if fall_dist >= 4 * TILE_SIZE: self.stun_timer = 30 
                            self.vy = 0
                            self.on_ground = True
                            self.fall_start_y = self.rect.y 
                        elif self.vy < 0:
                            self.rect.top = (ty // TILE_SIZE + 1) * TILE_SIZE
                            self.vy = 0
                        return

    def draw(self, surf, cam_x, cam_y, zoom):
        sw, sh = round(self.rect.width * zoom), round(self.rect.height * zoom)
        sx, sy = round(self.rect.x * zoom) - round(cam_x), round(self.rect.y * zoom) - round(cam_y)
        col = (200, 100, 100) if self.stun_timer > 0 else (100, 200, 255)
        pygame.draw.rect(surf, col, (sx, sy, sw, sh))
        pygame.draw.rect(surf, (255, 255, 255), (sx, sy, sw, sh), max(1, round(1.5 * zoom)))

# ─────────────────────────── MAIN GAME ───────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("2D Platformer by PITCHA")
    clock = pygame.time.Clock()
    
    font_lg = load_font(72); font_md = load_font(32); font_sm = load_font(16)
    
    if not LEVEL_PATH.exists(): sys.exit()
    with open(LEVEL_PATH, "r", encoding="utf-8") as f:
        level_data = json.load(f)
        
    tb = TileBank()
    gmap = GameMap(level_data, tb)
    player = Player(gmap.player_spawn[0], gmap.player_spawn[1])
    
    # Smooth Camera state
    camera_x = (player.rect.centerx * ZOOM) - SCREEN_W // 2
    camera_y = (player.rect.centery * ZOOM) - SCREEN_H // 2
    
    exit_hold_t = 0.0
    game_over = False
    
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
                
        if not game_over:
            # Check interaction
            keys = pygame.key.get_pressed()
            p_grid_x = player.rect.centerx // TILE_SIZE
            p_grid_y = player.rect.centery // TILE_SIZE
            
            # Find closest chest
            active_chest = None
            min_dist = 999999
            for chest in gmap.chests:
                chest.update(dt, player.rect.center)
                cx, cy = chest.world_x + 16, chest.world_y + 32
                dist = math.hypot(cx - player.rect.centerx, cy - player.rect.centery)
                if dist < TILE_SIZE * 1.5:
                    if chest.state in ["closed", "opening", "awarding"] and dist < min_dist:
                        min_dist = dist
                        active_chest = chest
            
            interacting_with_chest = False
            if active_chest and keys[pygame.K_e]:
                interacting_with_chest = True
                if active_chest.state == "closed":
                    active_chest.state = "opening"
                    active_chest.hold_timer = 0
                
                if active_chest.state == "opening":
                    active_chest.hold_timer += dt
                    if active_chest.hold_timer >= 3.0:
                        pass # State changed in update
                elif active_chest.state == "awarding":
                    active_chest.state = "open"
                    active_chest.hold_timer = 0
            # Interaction Circle (for Exits or Chests)
            ex, ey = gmap.exit_pos
            dist_to_exit = math.hypot(player.rect.centerx - (ex * TILE_SIZE + 32), player.rect.centery - (ey * TILE_SIZE + 32))
            
            interacting_with_exit = False
            if dist_to_exit < 80:
                if keys[pygame.K_e] and not interacting_with_chest:
                    exit_hold_t += dt
                    interacting_with_exit = True
                    if exit_hold_t >= 5.0:
                        game_over = True
                else:
                    exit_hold_t = 0
                
                # Draw exit prompt and circle
                px = player.rect.centerx * ZOOM - camera_x
                py = (player.rect.top - 20) * ZOOM - camera_y
                
                if exit_hold_t <= 0:
                    txt = "Hold [E] to Exit"
                    tw, _ = font_md.size(txt)
                    ex_x = round((ex + 0.5) * TILE_SIZE * ZOOM) - camera_x
                    ex_y = round(ey * TILE_SIZE * ZOOM) - camera_y
                    draw_text(screen, font_md, txt, ex_x - tw//2, ex_y - round(40*ZOOM), (255, 255, 100))
                else:
                    draw_circle(screen, (px, py), round(15 * ZOOM), (255, 255, 255), max(1, round(3 * ZOOM)), exit_hold_t / 5.0)
            
            
            if active_chest and not keys[pygame.K_e]:
                if active_chest.state == "opening":
                    # Slam shut if released before 3s or reaching last frame
                    active_chest.reset()
                active_chest.hold_timer = 0

            can_move = not ((active_chest and active_chest.state == "opening") or interacting_with_exit)
            player.update(gmap, can_move)
            
            # Camera Smoothing (Lerp)
            target_cam_x = (player.rect.centerx * ZOOM) - SCREEN_W // 2
            target_cam_y = (player.rect.centery * ZOOM) - SCREEN_H // 2
            
            camera_x += (target_cam_x - camera_x) * 0.1
            camera_y += (target_cam_y - camera_y) * 0.1
            
            # Clamp camera
            camera_x = max(0, min(camera_x, gmap.width * TILE_SIZE * ZOOM - SCREEN_W))
            camera_y = max(0, min(camera_y, gmap.height * TILE_SIZE * ZOOM - SCREEN_H))

        # Drawing
        screen.fill((20, 20, 25))
        gmap.draw(screen, camera_x, camera_y, ZOOM, font_sm)
        player.draw(screen, camera_x, camera_y, ZOOM)
        
        # Interaction Circle (for Exits or Chests)
        if not game_over:
            ex, ey = gmap.exit_pos
            dist_to_exit = math.hypot(player.rect.centerx - (ex * TILE_SIZE + 32), player.rect.centery - (ey * TILE_SIZE + 32))
            
            px = player.rect.centerx * ZOOM - camera_x
            py = (player.rect.top - 20) * ZOOM - camera_y

            if dist_to_exit < 80:
                if exit_hold_t <= 0:
                    txt = "Hold [E] to Exit"
                    tw, _ = font_md.size(txt)
                    ex_x = round((ex + 0.5) * TILE_SIZE * ZOOM) - camera_x
                    ex_y = round(ey * TILE_SIZE * ZOOM) - camera_y
                    draw_text(screen, font_md, txt, ex_x - tw//2, ex_y - round(40*ZOOM), (255, 255, 100))
                else:
                    draw_circle(screen, (px, py), round(15 * ZOOM), (255, 255, 255), max(1, round(3 * ZOOM)), exit_hold_t / 5.0)
            
            elif active_chest and active_chest.state in ["closed", "opening"]:
                if active_chest.state == "closed":
                    txt = f"Hold [E] to Open"
                    tw, _ = font_md.size(txt)
                    cx_x = round(active_chest.world_x + 16) * ZOOM - camera_x
                    cx_y = round(active_chest.world_y * ZOOM) - camera_y
                    # Positioned world: cx_y is the top of the target tile.
                    # Chest top is at cx_y - 32. Lowering by 8px means 40 -> 8.
                    # We want it UP 1 tile from the previous "lowered" state.
                    # Previous was: cx_y + skip(24) = lower.
                    # Now: cx_y - skip(8) = higher (above chest).
                    draw_text(screen, font_md, txt, cx_x - tw//2, cx_y - round(8*ZOOM), (200, 255, 100))
                # Removed draw_circle for chests as per user request
        
        # UI section removed (redundant)

        if game_over:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 230)); screen.blit(overlay, (0, 0))
            msg = font_lg.render("จบเกมแล้ว", True, (255, 255, 255))
            screen.blit(msg, (SCREEN_W//2 - msg.get_width()//2, SCREEN_H//2 - msg.get_height()//2))
            restart_txt = font_md.render("Press R to Restart", True, (200, 200, 200))
            screen.blit(restart_txt, (SCREEN_W//2 - restart_txt.get_width()//2, SCREEN_H//2 + 80))
            if pygame.key.get_pressed()[pygame.K_r]:
                player = Player(gmap.player_spawn[0], gmap.player_spawn[1])
                for c in gmap.chests: c.reset()
                exit_hold_t = 0
                game_over = False

        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()
