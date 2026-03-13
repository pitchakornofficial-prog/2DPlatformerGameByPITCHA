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

def get_current_level_num(level_path: Path) -> int:
    """Extract level number from level filename (e.g., 'level1.json' -> 1)"""
    name = level_path.stem
    if name.startswith('level'):
        try:
            return int(name[5:])  # Extract number after 'level'
        except ValueError:
            return 1
    return 1

def get_next_level_path(current_level_num: int) -> Path:
    """Get path to next level file"""
    next_num = current_level_num + 1
    return BASE_DIR / "levels" / f"level{next_num}.json"

def get_all_level_files() -> list:
    """Get list of all level files sorted by number"""
    levels_dir = BASE_DIR / "levels"
    if not levels_dir.exists():
        return []
    level_files = sorted(levels_dir.glob("level*.json"), 
                        key=lambda p: get_current_level_num(p))
    return level_files

# ─────────────────────────── TILE BANK ───────────────────────────

class TileBank:
    def __init__(self):
        self.tilesets = {}
        self.chest_anims = {}
        self.backgrounds = {} 
        self.wizard_frames = []
        self.load_tiles()
        self.load_backgrounds()
        self.load_chests()
        self.load_wizard()

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

    def load_backgrounds(self):
        bg_dir = ASSETS_DIR / "backgrond"
        if not bg_dir.exists(): return
        for p in bg_dir.rglob("*"):
            if p.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                try:
                    surf = pygame.image.load(str(p)).convert_alpha()
                    self.backgrounds[p.stem] = surf
                except Exception as e:
                    print(f"Error loading background {p.name}: {e}")

    def load_chests(self):
        chest_path = ASSETS_DIR / "box" / "TX Chest Animation.png"
        if not chest_path.exists(): return
        try:
            surf = pygame.image.load(str(chest_path)).convert_alpha()
            types = ["Wood Chest", "Iron Chest", "Silver Chest", "Gold Chest"]
            for i, tname in enumerate(types):
                frames = []
                for f in range(6): 
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

    def load_wizard(self):
        wizard_path = ASSETS_DIR / "enamy" / "GandalfHardcore Portal sheet.png"
        if wizard_path.exists():
            try:
                sheet = pygame.image.load(str(wizard_path)).convert_alpha()
                for i in range(10):
                    frame = sheet.subsurface((i * 64, 0, 64, 64)).copy()
                    self.wizard_frames.append(frame)
            except Exception as e:
                print(f"Error loading wizard: {e}")

    def get_tile(self, tile_ref):
        if not tile_ref: return None
        
        # If it's a direct background reference (no _X_Y suffix)
        if tile_ref in self.backgrounds:
            return self.backgrounds[tile_ref]
            
        parts = tile_ref.split("_")
        if len(parts) < 3: return None
        ts_name = "_".join(parts[:-2])
        try:
            col, row = int(parts[-2]), int(parts[-1])
            if ts_name in self.tilesets:
                ts = self.tilesets[ts_name]
                if 0 <= row < len(ts) and 0 <= col < len(ts[row]):
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

    def draw(self, surf, cam_x, cam_y, zoom, show_prompt, font):
        # Unified draw logic: round((world - cam * parallax) * zoom)
        
        frames = self.tb.chest_anims.get(self.type)
        if not frames: return
        
        # sx, sy based on unified rounding
        sx = round((self.world_x - cam_x) * zoom)
        sy = round((self.world_y - 32 - cam_y) * zoom) # Chest sits on tile above (32px offset)
        
        sz_w = round(32 * zoom)
        sz_h = round(64 * zoom)
        img = frames[int(self.frame)]
        img = pygame.transform.scale(img, (sz_w, sz_h))
        surf.blit(img, (sx, sy))
        
        # Draw loot emergence & shuffling
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
        self.bg_layers = data.get("bg_layers", {})
        self.tb = tb
        
        entities = data.get("entities", {})
        self.player_spawn = entities.get("player_spawn", [2, 2])
        self.exit_pos = entities.get("exit", [self.width - 2, self.height - 2])
        
        self.collision_data = self.layers.get("6", {})
        
        # Load Chests
        self.chests = []
        self.enemies = []
        
        # Load Chests
        chest_data = entities.get("chests", {})
        for pos_key, config in chest_data.items():
            cx, cy = map(int, pos_key.split(","))
            self.chests.append(Chest(cx, cy, config["type"], config.get("items", ""), tb))
            
        # Load Enemies
        enemy_data = entities.get("enemies", {})
        for pos_key, config in enemy_data.items():
            ex, ey = map(int, pos_key.split(","))
            self.enemies.append(Enemy(ex, ey, config.get("hp", 100), tb))

    def is_solid(self, col, row):
        return f"{col},{row}" in self.collision_data

    def draw(self, surf, camera_x, camera_y, zoom, font):
        ts_zoomed = round(TILE_SIZE * zoom)
        cam_ix, cam_iy = round(camera_x), round(camera_y)
        
        # Draw Layers (0,1,2 handle parallax)
        for layer_str in sorted(self.layers.keys(), key=int):
            layer_id = int(layer_str)
            layer = self.layers[layer_str]
            
            # Parallax factor for layers 0, 1, 2
            fac = 1.0
            if layer_id in [0, 1, 2]:
                bg_cfg = self.bg_layers.get(layer_str, {})
                fac = float(bg_cfg.get("parallax", 1.0))
            for pos_key, tile_ref in layer.items():
                try:
                    c, r = map(int, pos_key.split(","))
                    tile_img = self.tb.get_tile(tile_ref)
                    if tile_img:
                        # Boundary-based rounding to avoid gaps
                        x = round((c * TILE_SIZE - camera_x * fac) * zoom)
                        next_x = round(((c + 1) * TILE_SIZE - camera_x * fac) * zoom)
                        y = round((r * TILE_SIZE - camera_y * fac) * zoom)
                        next_y = round(((r + 1) * TILE_SIZE - camera_y * fac) * zoom)
                        tw = next_x - x
                        th = next_y - y
                        
                        if -tw < SCREEN_W and x < SCREEN_W and -th < SCREEN_H and y < SCREEN_H:
                            img = pygame.transform.scale(tile_img, (tw, th))
                            surf.blit(img, (x, y))
                except: continue

# ─────────────────────────── ENEMY ───────────────────────────────

class Enemy:
    def __init__(self, x, y, hp, tb: TileBank):
        # Portal Wizard is 64x64
        self.world_x = x * TILE_SIZE
        self.world_y = (y + 1) * TILE_SIZE - 64 # Bottom aligned with tile
        self.rect = pygame.Rect(self.world_x, self.world_y, 64, 64)
        self.hp = hp
        self.tb = tb
        self.dir = 1 # 1=right, -1=left
        self.speed = 1.2
        self.frame = 0.0
        self.anim_speed = 8.0 # FPS
        
    def update(self, dt, gmap: GameMap):
        # Pacing logic
        self.frame = (self.frame + self.anim_speed * dt) % 10
        
        move_dist = self.speed * self.dir
        next_x = self.rect.x + move_dist
        
        # Wall Collision & Edge detection
        grid_y = int((self.rect.bottom - 1) // TILE_SIZE)
        
        # Wall ahead? (Check leading edge)
        check_x = next_x + (64 if self.dir > 0 else 0)
        hit_wall = gmap.is_solid(int(check_x // TILE_SIZE), grid_y) or \
                   gmap.is_solid(int(check_x // TILE_SIZE), grid_y - 1)
        
        # Floor ahead? (Check bottom middle or leading edge)
        # Using a point slightly ahead of the hitbox center to detect edges
        floor_check_x = next_x + (48 if self.dir > 0 else 16)
        no_floor = not gmap.is_solid(int(floor_check_x // TILE_SIZE), grid_y + 1)
        
        if hit_wall or no_floor:
            self.dir *= -1
        else:
            self.rect.x += move_dist
            self.world_x = self.rect.x
            
    def draw(self, surf, cam_x, cam_y, zoom):
        sx = round((self.world_x - cam_x) * zoom)
        sy = round((self.world_y - cam_y) * zoom)
        
        sz = round(64 * zoom)
        if 0 <= int(self.frame) < len(self.tb.wizard_frames):
            img = self.tb.wizard_frames[int(self.frame)]
            if self.dir < 0:
                img = pygame.transform.flip(img, True, False)
            scaled = pygame.transform.scale(img, (sz, sz))
            surf.blit(scaled, (sx, sy))

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
        # Unified draw: round((world - cam) * zoom)
        sx = round((self.rect.x - cam_x) * zoom)
        next_sx = round((self.rect.x + self.rect.width - cam_x) * zoom)
        sy = round((self.rect.y - cam_y) * zoom)
        next_sy = round((self.rect.y + self.rect.height - cam_y) * zoom)
        sw = next_sx - sx
        sh = next_sy - sy
        
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
    
    # Get all available level files
    all_levels = get_all_level_files()
    if not all_levels:
        print("No level files found in levels/ directory")
        sys.exit()
    
    # Start with level1.json or first available level
    current_level_idx = 0
    current_level_path = all_levels[0]
    is_last_level = (current_level_idx == len(all_levels) - 1)
    
    # Load initial level
    with open(current_level_path, "r", encoding="utf-8") as f:
        level_data = json.load(f)
    
    tb = TileBank()
    gmap = GameMap(level_data, tb)
    player = Player(gmap.player_spawn[0], gmap.player_spawn[1])
    
    # World-Space Camera initialization
    camera_x = player.rect.centerx - (SCREEN_W / 2) / ZOOM
    camera_y = player.rect.centery - (SCREEN_H / 2) / ZOOM
    
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
            
            
            if active_chest and not keys[pygame.K_e]:
                if active_chest.state == "opening":
                    # Slam shut if released before 3s or reaching last frame
                    active_chest.reset()
                active_chest.hold_timer = 0

            can_move = not ((active_chest and active_chest.state == "opening") or interacting_with_exit)
            player.update(gmap, can_move)
            
            # Update Enemies
            for enemy in gmap.enemies:
                enemy.update(dt, gmap)
            
            # Camera Smoothing (Lerp) in World Space
            target_cam_x = player.rect.centerx - (SCREEN_W / 2) / ZOOM
            target_cam_y = player.rect.centery - (SCREEN_H / 2) / ZOOM
            
            camera_x += (target_cam_x - camera_x) * 0.1
            camera_y += (target_cam_y - camera_y) * 0.1
            
            # Clamp camera in World Space
            camera_x = max(0, min(camera_x, gmap.width * TILE_SIZE - SCREEN_W / ZOOM))
            camera_y = max(0, min(camera_y, gmap.height * TILE_SIZE - SCREEN_H / ZOOM))

        # Drawing
        screen.fill((20, 20, 25))
        gmap.draw(screen, camera_x, camera_y, ZOOM, font_sm)
        
        # Draw entities with z-order priority (chests -> enemies -> player)
        # Format: (z_order, y_coord, entity_type, entity)
        entities = []
        
        # Chests (z=0, behind)
        for chest in gmap.chests:
            entities.append((0, chest.world_y, "chest", chest))
        
        # Enemies (z=1, middle)
        for enemy in gmap.enemies:
            entities.append((1, enemy.world_y, "enemy", enemy))
        
        # Player (z=2, front)
        entities.append((2, player.rect.centery, "player", player))
        
        # Sort by z-order first, then by y-coordinate
        entities.sort(key=lambda e: (e[0], e[1]))
        
        # Draw in sorted order
        for z_order, _, entity_type, entity in entities:
            if entity_type == "player":
                entity.draw(screen, camera_x, camera_y, ZOOM)
            elif entity_type == "enemy":
                entity.draw(screen, camera_x, camera_y, ZOOM)
            elif entity_type == "chest":
                entity.draw(screen, camera_x, camera_y, ZOOM, True, font_sm)
        
        # Interaction Prompts (for Exits or Chests)
        if not game_over:
            if dist_to_exit < 80:
                if exit_hold_t <= 0:
                    txt = "Hold [E] to Exit"
                    tw, _ = font_md.size(txt)
                    ex_x = round(((ex + 0.5) * TILE_SIZE - camera_x) * ZOOM)
                    ex_y = round((ey * TILE_SIZE - camera_y) * ZOOM)
                    draw_text(screen, font_md, txt, ex_x - tw//2, ex_y - round(40*ZOOM), (255, 255, 100))
                else:
                    px = round((player.rect.centerx - camera_x) * ZOOM)
                    py = round((player.rect.top - 20 - camera_y) * ZOOM)
                    draw_circle(screen, (px, py), round(15 * ZOOM), (255, 255, 255), max(1, round(3 * ZOOM)), exit_hold_t / 5.0)
            
            elif active_chest and active_chest.state in ["closed", "opening"]:
                if active_chest.state == "closed":
                    txt = f"Hold [E] to Open"
                    tw, _ = font_md.size(txt)
                    cx_x = round(((active_chest.world_x + 16) - camera_x) * ZOOM)
                    cx_y = round((active_chest.world_y - camera_y) * ZOOM)
                    draw_text(screen, font_md, txt, cx_x - tw//2, cx_y - round(8*ZOOM), (200, 255, 100))
        
        # Game Over Screen
        if game_over:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 230))
            screen.blit(overlay, (0, 0))
            
            msg = font_lg.render("จบเกมแล้ว", True, (255, 255, 255))
            screen.blit(msg, (SCREEN_W//2 - msg.get_width()//2, SCREEN_H//2 - msg.get_height()//2))
            
            if is_last_level:
                # Last level reached - show game end message
                next_msg = font_md.render("ยินดีด้วย! คุณชนะเกมแล้ว", True, (255, 255, 100))
                screen.blit(next_msg, (SCREEN_W//2 - next_msg.get_width()//2, SCREEN_H//2 + 50))
                restart_txt = font_md.render("Press R to Restart Level / Enter to New Game", True, (200, 200, 200))
                screen.blit(restart_txt, (SCREEN_W//2 - restart_txt.get_width()//2, SCREEN_H//2 + 100))
                
                # R = Restart current level5
                if pygame.key.get_pressed()[pygame.K_r]:
                    player = Player(gmap.player_spawn[0], gmap.player_spawn[1])
                    for c in gmap.chests: c.reset()
                    exit_hold_t = 0
                    game_over = False
                
                # Enter = New Game (go back to level1)
                if pygame.key.get_pressed()[pygame.K_RETURN]:
                    current_level_idx = 0
                    current_level_path = all_levels[0]
                    is_last_level = (current_level_idx == len(all_levels) - 1)
                    
                    with open(current_level_path, "r", encoding="utf-8") as f:
                        level_data = json.load(f)
                    
                    gmap = GameMap(level_data, tb)
                    player = Player(gmap.player_spawn[0], gmap.player_spawn[1])
                    camera_x = player.rect.centerx - (SCREEN_W / 2) / ZOOM
                    camera_y = player.rect.centery - (SCREEN_H / 2) / ZOOM
                    exit_hold_t = 0
                    game_over = False
            else:
                # More levels available
                next_msg = font_md.render("Press ENTER for Next Level", True, (100, 255, 100))
                screen.blit(next_msg, (SCREEN_W//2 - next_msg.get_width()//2, SCREEN_H//2 + 50))
                restart_txt = font_md.render("Press R to Restart", True, (200, 200, 200))
                screen.blit(restart_txt, (SCREEN_W//2 - restart_txt.get_width()//2, SCREEN_H//2 + 100))
                
                if pygame.key.get_pressed()[pygame.K_RETURN]:
                    # Load next level
                    current_level_idx += 1
                    if current_level_idx < len(all_levels):
                        current_level_path = all_levels[current_level_idx]
                        is_last_level = (current_level_idx == len(all_levels) - 1)
                        
                        with open(current_level_path, "r", encoding="utf-8") as f:
                            level_data = json.load(f)
                        
                        gmap = GameMap(level_data, tb)
                        player = Player(gmap.player_spawn[0], gmap.player_spawn[1])
                        camera_x = player.rect.centerx - (SCREEN_W / 2) / ZOOM
                        camera_y = player.rect.centery - (SCREEN_H / 2) / ZOOM
                        exit_hold_t = 0
                        game_over = False
                
                if pygame.key.get_pressed()[pygame.K_r]:
                    player = Player(gmap.player_spawn[0], gmap.player_spawn[1])
                    for c in gmap.chests: c.reset()
                    exit_hold_t = 0
                    game_over = False

        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()
