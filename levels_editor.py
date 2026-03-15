import pygame
import sys
import os
import json
import copy
import tkinter as tk
from tkinter import filedialog, simpledialog

# Single persistent hidden tkinter root - shared across all dialogs.
# Avoids 'application has been destroyed' errors from multiple Tk() instances.
_TK_ROOT: tk.Tk | None = None

def _get_tk_root() -> tk.Tk:
    global _TK_ROOT
    if _TK_ROOT is None or not _TK_ROOT.winfo_exists():
        _TK_ROOT = tk.Tk()
        _TK_ROOT.withdraw()
    return _TK_ROOT

pygame.init()
WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("2D Platformer Level Editor")
clock = pygame.time.Clock()
FPS = 60

# --- Constants & Colors ---
TILE_SIZE = 64
PANEL_WIDTH = 350
COLORS = {
    'bg': (40, 44, 52),
    'grid': (60, 64, 72),
    'panel': (30, 34, 42),
    'button': (75, 82, 99),
    'button_hover': (100, 110, 130),
    'button_active': (97, 175, 239),
    'text': (171, 178, 191),
    'highlight': (255, 255, 0),
    'layer_bg': [
        (45, 45, 60), (55, 55, 70), (65, 65, 80), (75, 75, 90),
        (85, 85, 100), (95, 95, 110), (105, 105, 120), (115, 115, 130)
    ]
}

font = pygame.font.SysFont('Consolas', 14)
font_bold = pygame.font.SysFont('Consolas', 14, bold=True)
font_large = pygame.font.SysFont('Consolas', 18, bold=True)

# --- Asset Manager ---
class AssetManager:
    def __init__(self):
        self.tiles = {}
        self.chests = {}
        self.items = {}
        self.wizard_frames = []
        self.load_assets("assets/tiles", self.tiles, is_spritesheet=True)
        self.load_assets("assets/backgrond", self.tiles, is_spritesheet=False) 
        self.load_assets("assets/box", self.chests, is_spritesheet=False, is_chest=True)
        self._load_items()
        self._load_wizard()

        if not self.tiles:
            surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
            surf.fill((200, 200, 200))
            pygame.draw.rect(surf, (100,100,100), surf.get_rect(), 2)
            self.tiles['default_tile'] = surf
        if not self.chests:
            # Fallback placeholder for each chest type
            fb_colors = {'Wood Chest': (139,90,43), 'Iron Chest': (120,120,120), 'Silver Chest': (180,180,200), 'Gold Chest': (220,180,50)}
            for c_name, color in fb_colors.items():
                s = pygame.Surface((TILE_SIZE, TILE_SIZE))
                s.fill(color)
                pygame.draw.rect(s, (255,255,0), s.get_rect(), 2)
                self.chests[f"{c_name}_icon"] = s
                self.chests[f"{c_name}_closed"] = s

    def _load_items(self):
        # Define where each item sits on the items spritesheet
        item_coords = {
            'Knife':  (0, 0),
            'Gun':    (32, 0),
            'Potion': (64, 0),
            'Armor':  (96, 0),
        }
        items_path = 'assets/items'
        os.makedirs(items_path, exist_ok=True)
        # Look for any png/jpg file in the folder to use as item sheet
        item_sheet = None
        if os.path.exists(items_path):
            for f in os.listdir(items_path):
                if f.endswith(('.png', '.jpg')):
                    try:
                        item_sheet = pygame.image.load(os.path.join(items_path, f)).convert_alpha()
                        break
                    except Exception as e:
                        print(f'Failed to load item sheet {f}: {e}')
        if item_sheet:
            w, h = item_sheet.get_size()
            for name, (ix, iy) in item_coords.items():
                if ix + 32 <= w and iy + 32 <= h:
                    sub = item_sheet.subsurface(pygame.Rect(ix, iy, 32, 32))
                    self.items[name] = pygame.transform.scale(sub, (TILE_SIZE, TILE_SIZE))
        # Fallback placeholder icons
        ITEM_COLORS = {'Knife': (200,200,50), 'Gun': (100,100,200), 'Potion': (200,50,50), 'Armor': (100,200,100)}
        for name, color in ITEM_COLORS.items():
            if name not in self.items:
                surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                pygame.draw.circle(surf, color, (32,32), 28)
                ts = font.render(name[:1], True, (0,0,0))
                surf.blit(ts, ts.get_rect(center=(32,32)))
                self.items[name] = surf

    def _load_wizard(self):
        w_path = "assets/enamy/GandalfHardcore Portal sheet.png"
        if os.path.exists(w_path):
            try:
                sheet = pygame.image.load(w_path).convert_alpha()
                for i in range(10):
                    frame = sheet.subsurface((i * 64, 0, 64, 64)).copy()
                    self.wizard_frames.append(frame)
            except Exception as e:
                print(f"Failed to load wizard: {e}")

    def load_assets(self, path, dictionary, is_spritesheet=False, is_chest=False):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            return

        # Recursive load for backgrounds, or flat for tiles/chests
        is_bg = "backgrond" in path.lower()
        
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith((".png", ".jpg")):
                    try:
                        img = pygame.image.load(os.path.join(root, file)).convert_alpha()
                        name = os.path.splitext(file)[0]
                        # If bg, we might want to keep the subdirectory info in the name if needed, 
                        # but user asked for "Pine forest sheet_0_0" style etc.
                        # For now, let's keep it simple or use full path logic if main.py supports it.
                        
                        if is_chest and name == "TX Chest Animation":
                            # Coordinates: user notation colNxrowM (1-indexed), actual pixel = (col-1)*32, (row-1)*32
                            # Icon row is one row above each chest's animation rows.
                            # Wood:  icon=1x0(col1,row0) -> NO row 0 in 1-indexed. 
                            # Interpret: col N -> pixel x = (N-1)*32; row M -> pixel y = (M-1)*32
                            #   Wood   closed: 1x1 -> x=0, y=0
                            #   Iron   closed: 1x3 -> x=0, y=64
                            #   Silver closed: 1x5 -> x=0, y=128
                            #   Gold   closed: 1x7 -> x=0, y=192
                            # Icon cells (1x0 etc.): row 0 doesn't exist in 1-indexed, so use closed frame as icon too.
                            # Based on user: 1x1 closed, and 1x0 as combined icon.
                            # Reinterpret: rows are 0-indexed => 1x1 = x=32,y=32; 1x0=x=32,y=0
                            # => Each tile cell = 32px. col=1->x=(1)*32=32, row=0->y=0*32=0
                            chest_defs = {
                                'Wood Chest':   {'top_row': 0},
                                'Iron Chest':   {'top_row': 2},
                                'Silver Chest': {'top_row': 4},
                                'Gold Chest':   {'top_row': 6},
                            }
                            for c_name, cfg in chest_defs.items():
                                cx = 32 # Skip col 0
                                ty_top = cfg['top_row'] * 32
                                ty_bot = (cfg['top_row'] + 1) * 32
                                if cx + 32 <= img.get_width() and ty_bot + 32 <= img.get_height():
                                    # Grab 32x64 area
                                    chest_surf = pygame.Surface((32, 64), pygame.SRCALPHA)
                                    chest_surf.blit(img.subsurface(pygame.Rect(cx, ty_top, 32, 32)), (0, 0))
                                    chest_surf.blit(img.subsurface(pygame.Rect(cx, ty_bot, 32, 32)), (0, 32))
                                    
                                    # Store the 32x64 raw surface
                                    dictionary[f"{c_name}_closed"] = chest_surf
                                    # For icon, scale to fit the 64x64 button without squashing
                                    # Since it's 32x64, we can scale to say 32x64 and center it in a 64x64 surf
                                    icon_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                                    scaled_chest = pygame.transform.scale(chest_surf, (32, 64))
                                    icon_surf.blit(scaled_chest, (16, 0)) # Center horizontally
                                    dictionary[f"{c_name}_icon"] = icon_surf
                                else:
                                    s = pygame.Surface((TILE_SIZE, TILE_SIZE))
                                    fb_colors = {'Wood Chest': (139,90,43), 'Iron Chest': (120,120,120), 'Silver Chest': (180,180,200), 'Gold Chest': (220,180,50)}
                                    s.fill(fb_colors.get(c_name, (150,100,50)))
                                    dictionary[f"{c_name}_icon"] = s
                                    dictionary[f"{c_name}_closed"] = s
                        elif is_spritesheet:
                            w, h = img.get_size()
                            for y in range(0, h, 32):
                                for x in range(0, w, 32):
                                    if x + 32 <= w and y + 32 <= h:
                                        rect = pygame.Rect(x, y, 32, 32)
                                        sub_img = img.subsurface(rect)
                                        if sub_img.get_bounding_rect().width > 0:
                                            scaled_img = pygame.transform.scale(sub_img, (TILE_SIZE, TILE_SIZE))
                                            dictionary[f"{name}_{x//32}_{y//32}"] = scaled_img
                        elif not is_chest:
                            if is_bg:
                                dictionary[name] = img # Don't scale BGs in editor either, keep raw
                            else:
                                img = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))
                                dictionary[name] = img
                    except Exception as e:
                        print(f"Failed to load {file}: {e}")

# --- Camera ---
class Camera:
    def __init__(self):
        self.scroll = pygame.math.Vector2(0, 0)
        self.zoom = 1.0
        self.speed = 600

    def update(self, dt):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: self.scroll.y -= self.speed * dt / self.zoom
        if keys[pygame.K_s]: self.scroll.y += self.speed * dt / self.zoom
        if keys[pygame.K_a]: self.scroll.x -= self.speed * dt / self.zoom
        if keys[pygame.K_d]: self.scroll.x += self.speed * dt / self.zoom

    def apply_zoom(self, amount, mouse_pos):
        old_zoom = self.zoom
        self.zoom += amount
        self.zoom = max(0.2, min(self.zoom, 3.0))
        if old_zoom != self.zoom:
            # Zoom towards mouse cursor
            mouse_x_before = (mouse_pos[0] / old_zoom) + self.scroll.x
            mouse_y_before = (mouse_pos[1] / old_zoom) + self.scroll.y
            mouse_x_after = (mouse_pos[0] / self.zoom) + self.scroll.x
            mouse_y_after = (mouse_pos[1] / self.zoom) + self.scroll.y
            self.scroll.x -= (mouse_x_after - mouse_x_before)
            self.scroll.y -= (mouse_y_after - mouse_y_before)

    def screen_to_world(self, pos, parallax=1.0):
        # World = (Screen / Zoom) + (Scroll * Parallax)
        x = (pos[0] / self.zoom) + self.scroll.x * parallax
        y = (pos[1] / self.zoom) + self.scroll.y * parallax
        return x, y

    def world_to_screen(self, x, y, parallax=1.0):
        # Screen = round((World - Scroll * Parallax) * Zoom)
        sx = round((x - self.scroll.x * parallax) * self.zoom)
        sy = round((y - self.scroll.y * parallax) * self.zoom)
        return sx, sy

# --- UI Components ---
class UIButton:
    def __init__(self, x, y, w, h, text, action=None, active=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.action = action
        self.active = active
        self.hovered = False

    def draw(self, surface):
        color = COLORS['button_active'] if self.active else (COLORS['button_hover'] if self.hovered else COLORS['button'])
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, (20,20,20), self.rect, 1, border_radius=4)
        
        text_surf = font.render(self.text, True, COLORS['text'] if not self.active else (255,255,255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

class UIPanel:
    def __init__(self, editor):
        self.editor = editor
        self.rect = pygame.Rect(WIDTH - PANEL_WIDTH, 0, PANEL_WIDTH, HEIGHT)
        self.buttons = []
        self.setup_ui()
        self.tile_rects = []
        self.scroll_y = 0
        self.update_palette_rects()

    def setup_ui(self):
        self.buttons.clear()
        start_x, start_y = self.rect.x + 10, 10
        
        # File Ops
        self.buttons.append(UIButton(start_x, start_y, 75, 30, "New", self.cmd_new))
        self.buttons.append(UIButton(start_x + 85, start_y, 75, 30, "Load", self.cmd_load))
        self.buttons.append(UIButton(start_x + 170, start_y, 75, 30, "Save", self.cmd_save))
        self.buttons.append(UIButton(start_x + 255, start_y, 75, 30, "Save As", self.cmd_save_as))
        
        start_y += 40
        # Map Size
        self.buttons.append(UIButton(start_x, start_y, 160, 30, f"Map W: {self.editor.state['map_width']}", self.cmd_set_width))
        self.buttons.append(UIButton(start_x + 170, start_y, 160, 30, f"Map H: {self.editor.state['map_height']}", self.cmd_set_height))
        
        start_y += 40
        # Layers 0-7
        layer_names = ["BG 1", "BG 2", "BG 3", "Passable", "Items", "Enemies", "Ground", "Foregnd"]
        for i in range(8):
            btn_x = start_x + (i % 4) * 85
            btn_y = start_y + (i // 4) * 35
            btn = UIButton(btn_x, btn_y, 80, 30, str(i) + ":" + layer_names[i], lambda i=i: self.set_layer(i))
            if i == self.editor.current_layer: btn.active = True
            self.buttons.append(btn)
            
        start_y += 80
        # Tileset Dropdown
        ts_name = self.editor.tileset_names[self.editor.current_tileset_idx]
        self.buttons.append(UIButton(start_x, start_y, 250, 30, f"Tileset: {ts_name[:15]}", self.cmd_cycle_tileset))
        
        start_y += 40
        # Tools
        tools = ["Draw", "Erase", "Select", "Rotate"]
        for i, t in enumerate(tools):
            btn_x = start_x + (i % 3) * 110
            btn_y = start_y + (i // 3) * 35
            btn = UIButton(btn_x, btn_y, 105, 30, t, lambda t=t: self.set_tool(t))
            if t == self.editor.current_tool: btn.active = True
            self.buttons.append(btn)
            
        start_y += 75
        # Entity Spawns
        entities = ["Player", "Enemy", "Exit", "Warp", "Label"]
        for i, t in enumerate(entities):
            btn_x = start_x + (i % 3) * 110
            btn_y = start_y + (i // 3) * 35
            btn = UIButton(btn_x, btn_y, 105, 30, t, lambda t=t: self.set_tool(t))
            if t == self.editor.current_tool: btn.active = True
            self.buttons.append(btn)

        start_y += 40
        # Chest Tool
        btn = UIButton(start_x, start_y, 105, 30, "Chest", lambda: self.set_tool("Chest"))
        if self.editor.current_tool == "Chest": btn.active = True
        self.buttons.append(btn)

        # If Chest tool active, show chest type selector
        if self.editor.current_tool == "Chest":
            start_y += 38
            chest_types = ["Wood Chest", "Iron Chest", "Silver Chest", "Gold Chest"]
            for i, ct in enumerate(chest_types):
                btn_x = start_x + (i % 2) * 165
                btn_y = start_y + (i // 2) * 70
                btn = UIButton(btn_x, btn_y, 160, 64, ct, lambda ct=ct: self.set_chest_type(ct))
                if ct == self.editor.selected_chest_type: btn.active = True
                self.buttons.append(btn)

        # Background Layer Properties (shown when layer 0-2 is selected)
        is_bg_layer = self.editor.current_layer in [0, 1, 2]
        if is_bg_layer:
            start_y += 10
            bg = self.editor.state.get('bg_layers', {}).get(self.editor.current_layer, {})
            self.buttons.append(UIButton(start_x, start_y, 118, 26, f"Parallax: {bg.get('parallax', 1.0)}", self.cmd_bg_parallax))
            start_y += 32

        self.palette_start_y = start_y + (190 if self.editor.current_tool == "Chest" else 50)

    def cmd_new(self):
        self.editor.state = {
            'map_width': 10, 'map_height': 10,
            'layers': {i: {} for i in range(8)},
            'bg_layers': {i: {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0, 'parallax': 1.0} for i in range(3)},
            'entities': {'player_spawn': None, 'exit': None, 'enemies': {}, 'chests': {}}
        }
        self.editor.action_history.clear()
        self.editor.save_history()
        self.editor.current_file = None
        self.setup_ui()

    def cmd_load(self):
        root = _get_tk_root()
        os.makedirs("levels", exist_ok=True)
        initial_dir = os.path.abspath("levels")
        filepath = filedialog.askopenfilename(parent=root, initialdir=initial_dir, filetypes=[("JSON files", "*.json")])
        if filepath:
            with open(filepath, 'r') as f:
                data = json.load(f)
                # Convert string keys back to int for layers
                formatted = {
                    'map_width': data.get('map_width', 10),
                    'map_height': data.get('map_height', 10),
                    'layers': {int(k): v for k, v in data.get('layers', {}).items()},
                    'bg_layers': {int(k): v for k, v in data.get('bg_layers', {}).items()} if 'bg_layers' in data else {i: {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0} for i in range(3)},
                    'entities': data.get('entities', {'player_spawn': None, 'exit': None, 'enemies': {}, 'chests': {}, 'portals': {}, 'labels': {}})
                }
                # Ensure missing keys in entities exist
                ent = formatted['entities']
                for k in ['portals', 'labels', 'enemies', 'chests']:
                    if k not in ent: ent[k] = {}
                self.editor.state = formatted
                self.editor.current_file = filepath
                self.editor.action_history.clear()
                self.editor.save_history()
                self.setup_ui()

    def cmd_save(self):
        if self.editor.current_file:
            with open(self.editor.current_file, 'w') as f:
                json.dump(self.editor.state, f, indent=4)
            print(f"Saved to {self.editor.current_file}")
        else:
            self.cmd_save_as()

    def cmd_save_as(self):
        root = _get_tk_root()
        os.makedirs("levels", exist_ok=True)
        initial_dir = os.path.abspath("levels")
        filepath = filedialog.asksaveasfilename(parent=root, initialdir=initial_dir, defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if filepath:
            self.editor.current_file = filepath
            self.cmd_save()

    def cmd_set_width(self):
        root = _get_tk_root()
        val = simpledialog.askinteger("Input", "Map Width:", parent=root, initialvalue=self.editor.state['map_width'])
        if val and val > 0:
            self.editor.state['map_width'] = val
            self.setup_ui()
            self.editor.save_history()

    def cmd_set_height(self):
        root = _get_tk_root()
        val = simpledialog.askinteger("Input", "Map Height:", parent=root, initialvalue=self.editor.state['map_height'])
        if val and val > 0:
            self.editor.state['map_height'] = val
            self.setup_ui()
            self.editor.save_history()

    def cmd_cycle_tileset(self):
        self.editor.current_tileset_idx = (self.editor.current_tileset_idx + 1) % len(self.editor.tileset_names)
        self.scroll_y = 0
        self.setup_ui()

    def _bg_prop_dialog(self, title, prompt, key, is_int=True):
        root = _get_tk_root()
        layer = self.editor.current_layer
        bg = self.editor.state['bg_layers'].setdefault(layer, {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0})
        if is_int:
            val = simpledialog.askinteger(title, prompt, parent=root, initialvalue=bg.get(key, 0))
        else:
            val = simpledialog.askfloat(title, prompt, parent=root, initialvalue=bg.get(key, 1.0))
        if val is not None:
            bg[key] = val
            self.editor.save_history()
            self.setup_ui()

    def cmd_select_bg_image(self):
        root = _get_tk_root()
        # Use standard file dialog to avoid freezing
        initial_dir = os.path.abspath("assets/backgrond")
        if not os.path.exists(initial_dir): os.makedirs(initial_dir, exist_ok=True)
        
        filepath = filedialog.askopenfilename(
            parent=root, 
            initialdir=initial_dir,
            title="Select Background Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg")]
        )
        
        if filepath:
            try:
                img_name = os.path.splitext(os.path.basename(filepath))[0]
                # Load it into assets if not present
                if img_name not in self.editor.assets.tiles:
                    img = pygame.image.load(filepath).convert_alpha()
                    # Scale according to panel settings or keep raw? 
                    # Existing editor logic scales tiles to TILE_SIZE, but BGs are usually larger.
                    # We'll store the raw image for BGs.
                    self.editor.assets.tiles[img_name] = img
                
                layer = self.editor.current_layer
                self.editor.state.setdefault('bg_layers', {})
                self.editor.state['bg_layers'].setdefault(layer, {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0, 'parallax': 1.0})
                self.editor.state['bg_layers'][layer]['image'] = img_name
                self.editor.save_history()
                self.setup_ui()
            except Exception as e:
                print(f"Failed to load background {filepath}: {e}")

    def cmd_clear_bg(self):
        layer = self.editor.current_layer
        if 'bg_layers' in self.editor.state and layer in self.editor.state['bg_layers']:
            self.editor.state['bg_layers'][layer]['image'] = None
            self.editor.save_history()
            self.setup_ui()

    def cmd_bg_offset_x(self): self._bg_prop_dialog("BG Offset", "Offset X (px):", "offset_x")
    def cmd_bg_offset_y(self): self._bg_prop_dialog("BG Offset", "Offset Y (px):", "offset_y")
    def cmd_bg_tile_w(self): self._bg_prop_dialog("BG Tile Size", "Tile Width (px):", "tile_w")
    def cmd_bg_parallax(self): self._bg_prop_dialog("BG Parallax", "Scroll Factor (1.0=Normal, 0.1=Slow):", "parallax", is_int=False)
    def cmd_bg_tile_h(self): self._bg_prop_dialog("BG Tile Size", "Tile Height (px):", "tile_h")

    def set_layer(self, layer):
        self.editor.current_layer = layer
        self.setup_ui()

    def set_tool(self, tool):
        self.editor.current_tool = tool
        self.setup_ui()

    def set_chest_type(self, ct):
        self.editor.selected_chest_type = ct
        self.setup_ui()

    def update_palette_rects(self):
        self.tile_rects = []
        if self.editor.current_tool == 'Chest':
            return  # Chest type selection is via buttons, not palette
        else:
            ts = self.editor.tileset_names[self.editor.current_tileset_idx]
            if ts == "All":
                assets = list(self.editor.assets.tiles.keys())
            else:
                assets = [k for k in self.editor.assets.tiles.keys() if k.startswith(ts)]
        
        cols = 4
        size = 70
        start_x = self.rect.x + 20
        start_y = self.palette_start_y - self.scroll_y
        
        for i, name in enumerate(assets):
            x = start_x + (i % cols) * size
            y = start_y + (i // cols) * size
            self.tile_rects.append({"rect": pygame.Rect(x, y, 64, 64), "name": name})

    def handle_event(self, event):
        mouse_pos = pygame.mouse.get_pos()
        if not self.rect.collidepoint(mouse_pos):
            return False

        if event.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                b.hovered = b.rect.collidepoint(mouse_pos)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Buttons
                for b in self.buttons:
                    if b.rect.collidepoint(mouse_pos) and b.action:
                        b.action()
                        return True
                # Palette
                for t in self.tile_rects:
                    if t['rect'].collidepoint(mouse_pos):
                        self.editor.selected_tile = t['name']
                        return True
            # Scroll palette
            elif event.button == 4: # Up
                self.scroll_y = max(0, self.scroll_y - 20)
                self.update_palette_rects()
            elif event.button == 5: # Down
                self.scroll_y += 20
                self.update_palette_rects()

        return True

    def draw(self, surface):
        self.rect.x = WIDTH - PANEL_WIDTH
        self.rect.height = HEIGHT
        pygame.draw.rect(surface, COLORS['panel'], self.rect)
        pygame.draw.line(surface, (20,20,20), (self.rect.x, 0), (self.rect.x, HEIGHT), 2)

        for b in self.buttons:
            # Sync button x position on resize
            diff = self.rect.x - (WIDTH - PANEL_WIDTH) # this is usually 0 if handled well
            b.draw(surface)

        # Draw Palette (tile palette only for non-Chest tool)
        if self.editor.current_tool != 'Chest':
            self.update_palette_rects()
            clip_rect = pygame.Rect(self.rect.x, self.palette_start_y, PANEL_WIDTH, HEIGHT - self.palette_start_y)
            surface.set_clip(clip_rect)
            
            assets_dict = self.editor.assets.tiles
            
            for t in self.tile_rects:
                if t['name'] in assets_dict:
                    surface.blit(assets_dict[t['name']], t['rect'])
                if t['name'] == self.editor.selected_tile:
                    pygame.draw.rect(surface, COLORS['highlight'], t['rect'], 3)
                    
            surface.set_clip(None)
        else:
            # Draw chest type buttons with images drawn inside them
            chest_types = ["Wood Chest", "Iron Chest", "Silver Chest", "Gold Chest"]
            for btn in self.buttons:
                for ct in chest_types:
                    if btn.text == ct and f"{ct}_icon" in self.editor.assets.chests:
                        surface.blit(self.editor.assets.chests[f"{ct}_icon"], (btn.rect.x + 2, btn.rect.y + 2))

# --- Editor Application ---
class LevelEditor:
    def __init__(self):
        self.assets = AssetManager()
        self.camera = Camera()
        
        self.state = {
            'map_width': 10,
            'map_height': 10,
            'layers': {i: {} for i in range(8)},
            'bg_layers': {i: {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0, 'parallax': 1.0} for i in range(3)},
            'entities': {
                'player_spawn': None,
                'exit': None,
                'enemies': {},
                'chests': {},
                'portals': {},
                'labels': {}
            }
        }
        
        self.current_layer = 6 # Default to ground layer
        self.current_tool = "Draw"
        self.selected_tile = list(self.assets.tiles.keys())[0] if self.assets.tiles else None
        self.selected_chest_type = "Wood Chest"  # Default chest type
        
        self.action_history = []
        self.history_index = -1
        
        # Tileset dropdown setup
        all_tile_keys = self.assets.tiles.keys()
        self.tileset_names = ["All"] + sorted(list(set([k.rsplit('_', 2)[0] for k in all_tile_keys if '_' in k])))
        self.current_tileset_idx = 0
        
        self.save_history()
        
        self.current_file = None
        self.ui = UIPanel(self)

    def save_history(self):
        # Truncate future history if we did something after undos
        self.action_history = self.action_history[:self.history_index+1]
        self.action_history.append(copy.deepcopy(self.state))
        self.history_index += 1
        if len(self.action_history) > 50: # Limit history
            self.action_history.pop(0)
            self.history_index -= 1

    def undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.state = copy.deepcopy(self.action_history[self.history_index])

    def redo(self):
        if self.history_index < len(self.action_history) - 1:
            self.history_index += 1
            self.state = copy.deepcopy(self.action_history[self.history_index])

    def configure_entity(self, etype, pos_key):
        root = _get_tk_root()
        if etype == 'enemy':
            hp = simpledialog.askinteger("Enemy HP", "HP:",
                                         initialvalue=self.state['entities']['enemies'][pos_key].get('hp', 100),
                                         parent=root)
            if hp:
                self.state['entities']['enemies'][pos_key]['hp'] = hp
                self.state['entities']['enemies'][pos_key].pop('attack', None)
                self.save_history()

        if etype == 'chest':
            top = tk.Toplevel(root)
            top.title("Chest Configuration")
            top.resizable(False, False)

            chest_data = self.state['entities']['chests'][pos_key]
            cur_items = chest_data.get('item_drops', {})
            
            tk.Label(top, text="Item Drops (toggle on/off + chance %):", font=('Arial', 10, 'bold')).grid(
                row=0, column=0, columnspan=3, padx=8, pady=(8,4), sticky='w')
            
            all_items = ["Knife", "Gun", "Potion", "Armor"]
            item_vars = {}       # name -> (BooleanVar, StringVar)
            for row_idx, name in enumerate(all_items, start=1):
                cur = cur_items.get(name, {})
                bv = tk.BooleanVar(value=cur.get('enabled', name == 'Knife'))
                sv = tk.StringVar(value=str(cur.get('chance', 50)))
                tk.Checkbutton(top, text=name, variable=bv, font=('Arial', 10)).grid(
                    row=row_idx, column=0, padx=8, sticky='w')
                tk.Label(top, text="%:").grid(row=row_idx, column=1, sticky='e')
                tk.Entry(top, textvariable=sv, width=5).grid(row=row_idx, column=2, padx=(2, 8), pady=2, sticky='w')
                item_vars[name] = (bv, sv)
            
            # Gun ammo field
            ammo_row = len(all_items) + 1
            tk.Label(top, text="Gun Ammo:", font=('Arial', 10, 'bold')).grid(row=ammo_row, column=0, padx=8, pady=4, sticky='w')
            ammo_var = tk.StringVar(value=str(chest_data.get('ammo', 3)))
            tk.Entry(top, textvariable=ammo_var, width=5).grid(row=ammo_row, column=1, columnspan=2, padx=(2,8), sticky='w')
            
            confirmed = [False]
            def on_ok():
                confirmed[0] = True
                top.destroy()
            
            tk.Button(top, text="✔ Confirm", command=on_ok, bg='#4CAF50', fg='white', width=12).grid(
                row=ammo_row + 1, column=0, columnspan=3, pady=10)
            
            top.transient(root)
            top.grab_set()
            top.lift()
            # Non-blocking wait - pump pygame events while tkinter runs
            while top.winfo_exists():
                try: root.update()
                except tk.TclError: break
                pygame.event.pump()
            
            if confirmed[0]:
                drops = {}
                for name, (bv, sv) in item_vars.items():
                    try: pct = max(0, min(100, int(sv.get())))
                    except: pct = 50
                    drops[name] = {'enabled': bv.get(), 'chance': pct}
                chest_data['item_drops'] = drops
                try: chest_data['ammo'] = max(1, int(ammo_var.get()))
                except: chest_data['ammo'] = 3
                self.save_history()

        if etype == 'warp':
            root = _get_tk_root()
            pid = simpledialog.askinteger("Portal ID", "New ID:", 
                                         initialvalue=self.state['entities']['portals'][pos_key].get('id', 0),
                                         parent=root)
            if pid is not None:
                # Check if this ID is already used twice elsewhere
                count = 0
                for p_key, pdata in self.state['entities']['portals'].items():
                    if p_key != pos_key and pdata.get('id') == pid: count += 1
                
                if count >= 2:
                    tk.messagebox.showwarning("Warning", f"ID {pid} is already used twice!", parent=root)
                else:
                    self.state['entities']['portals'][pos_key]['id'] = pid
                    self.save_history()

        if etype == 'label':
            root = _get_tk_root()
            text = simpledialog.askstring("Label Text", "New Text:",
                                         initialvalue=self.state['entities']['labels'][pos_key].get('text', ""),
                                         parent=root)
            if text:
                self.state['entities']['labels'][pos_key]['text'] = text
                self.save_history()

    def process_canvas_click(self, grid_pos, button):
        gx, gy = grid_pos
        if gx < 0 or gx >= self.state['map_width'] or gy < 0 or gy >= self.state['map_height']: return
        
        pos_key = f"{gx},{gy}"
        changed = False

        if self.current_tool == "Draw":
            if button == 1 and self.selected_tile:
                current_val = self.state['layers'][self.current_layer].get(pos_key)
                current_type = current_val.get('type') if isinstance(current_val, dict) else current_val
                if current_type != self.selected_tile:
                    self.state['layers'][self.current_layer][pos_key] = self.selected_tile
                    changed = True
            elif button == 3: # Right click erase
                if pos_key in self.state['layers'][self.current_layer]:
                    del self.state['layers'][self.current_layer][pos_key]
                    changed = True

        elif self.current_tool == "Erase":
            if button == 1:
                # Erase tile on current layer
                if pos_key in self.state['layers'][self.current_layer]:
                    del self.state['layers'][self.current_layer][pos_key]
                    changed = True
                # Erase entity at position
                for e_type in ['enemies', 'chests']:
                    if pos_key in self.state['entities'][e_type]:
                        del self.state['entities'][e_type][pos_key]
                        changed = True
                if self.state['entities']['player_spawn'] == [gx, gy]:
                    self.state['entities']['player_spawn'] = None
                    changed = True
                if self.state['entities']['exit'] == [gx, gy]:
                    self.state['entities']['exit'] = None
                    changed = True
                if pos_key in self.state['entities'].get('portals', {}):
                    del self.state['entities']['portals'][pos_key]
                    changed = True
                if pos_key in self.state['entities'].get('labels', {}):
                    del self.state['entities']['labels'][pos_key]
                    changed = True

        elif self.current_tool == "Rotate":
            if button == 1:
                tile_val = self.state['layers'][self.current_layer].get(pos_key)
                if tile_val:
                    if isinstance(tile_val, dict):
                        tile_val['rot'] = (tile_val.get('rot', 0) - 90) % 360
                    else:
                        self.state['layers'][self.current_layer][pos_key] = {'type': tile_val, 'rot': 270}
                    changed = True

        elif self.current_tool == "Player" and button == 1:
            if self.state['entities']['player_spawn'] != [gx, gy]:
                self.state['entities']['player_spawn'] = [gx, gy]
                changed = True

        elif self.current_tool == "Exit" and button == 1:
            if self.state['entities']['exit'] != [gx, gy]:
                self.state['entities']['exit'] = [gx, gy]
                changed = True

        elif self.current_tool == "Enemy" and button == 1:
            if pos_key not in self.state['entities']['enemies']:
                self.state['entities']['enemies'][pos_key] = {'hp': 100, 'attack': 10}
                changed = True

        elif self.current_tool == "Chest" and button == 1:
            ct = self.selected_chest_type
            key_closed = f"{ct}_closed"
            if pos_key not in self.state['entities']['chests'] or self.state['entities']['chests'][pos_key].get('type') != ct:
                self.state['entities']['chests'][pos_key] = {'type': ct, 'items': 'Knife', 'chance': 100}
                changed = True

        elif self.current_tool == "Select" and button == 1:
            if pos_key in self.state['entities']['enemies']:
                self.configure_entity('enemy', pos_key)
            elif pos_key in self.state['entities']['chests']:
                self.configure_entity('chest', pos_key)
            elif pos_key in self.state['entities']['portals']:
                self.configure_entity('warp', pos_key)
            elif pos_key in self.state['entities']['labels']:
                self.configure_entity('label', pos_key)

        elif self.current_tool == "Warp" and button == 1:
            if pos_key not in self.state['entities']['portals']:
                root = _get_tk_root()
                pid = simpledialog.askinteger("Portal ID", "ID (Integer):", parent=root)
                if pid is not None:
                    # Check how many times this ID is used
                    count = 0
                    for pdata in self.state['entities']['portals'].values():
                        if pdata.get('id') == pid: count += 1
                    
                    if count >= 2:
                        tk.messagebox.showwarning("Warning", f"ID {pid} is already used twice!", parent=root)
                    else:
                        self.state['entities']['portals'][pos_key] = {'id': pid}
                        changed = True

        elif self.current_tool == "Label" and button == 1:
            if pos_key not in self.state['entities']['labels']:
                root = _get_tk_root()
                text = simpledialog.askstring("Label Text", "Enter Label Text:", parent=root)
                if text:
                    self.state['entities']['labels'][pos_key] = {'text': text}
                    changed = True

        if changed:
            self.save_history()

    def handle_events(self):
        global WIDTH, HEIGHT, screen
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
                
            if event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                self.ui.setup_ui()

            # Handle Keyboard
            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                if event.key == pygame.K_z and mods & pygame.KMOD_CTRL:
                    if mods & pygame.KMOD_SHIFT:
                        self.redo()
                    else:
                        self.undo()

            # Pass to UI first
            ui_handled = self.ui.handle_event(event)
            
            if not ui_handled:
                # Zoom via scroll wheel
                if event.type == pygame.MOUSEWHEEL:
                    self.camera.apply_zoom(event.y * 0.1, pygame.mouse.get_pos())

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not self.ui.rect.collidepoint(event.pos):
                        # Get parallax factor for current layer
                        fac = 1.0
                        if self.current_layer in [0, 1, 2]:
                            bg_cfg = self.state.get('bg_layers', {}).get(self.current_layer, {})
                            fac = float(bg_cfg.get('parallax', 1.0))
                            
                        wx, wy = self.camera.screen_to_world(event.pos, fac)
                        gx = int(wx // TILE_SIZE)
                        gy = int(wy // TILE_SIZE)
                        if self.current_tool not in ["Draw", "Erase"]:
                            self.process_canvas_click((gx, gy), 1)
                    
        # Continuous mouse hold handling for Draw and Erase only
        if not self.ui.rect.collidepoint(pygame.mouse.get_pos()):
            mouse_buttons = pygame.mouse.get_pressed()
            if mouse_buttons[0] or mouse_buttons[2]:
                mx, my = pygame.mouse.get_pos()
                # Get parallax factor for current layer
                fac = 1.0
                if self.current_layer in [0, 1, 2]:
                    bg_cfg = self.state.get('bg_layers', {}).get(self.current_layer, {})
                    fac = float(bg_cfg.get('parallax', 1.0))
                    
                wx, wy = self.camera.screen_to_world((mx, my), fac)
                grid_x = int(wx // TILE_SIZE)
                grid_y = int(wy // TILE_SIZE)
                if self.current_tool in ["Draw", "Erase"]:
                    self.process_canvas_click((grid_x, grid_y), 1 if mouse_buttons[0] else 3)

        return True

    def draw(self, surface):
        surface.fill(COLORS['bg'])
        # Get parallax factor for grid and background layers
        grid_fac = 1.0
        if self.current_layer in [0, 1, 2]:
            bg_cfg = self.state.get('bg_layers', {}).get(self.current_layer, {})
            grid_fac = float(bg_cfg.get('parallax', 1.0))

        # Draw Grid Background
        for x in range(self.state['map_width']):
            for y in range(self.state['map_height']):
                world_x = x * TILE_SIZE
                world_y = y * TILE_SIZE
                # Manual world_to_screen with parallax factor & boundary rounding
                screen_x = round((world_x - self.camera.scroll.x * grid_fac) * self.camera.zoom)
                screen_y = round((world_y - self.camera.scroll.y * grid_fac) * self.camera.zoom)
                next_sx = round(((x + 1) * TILE_SIZE - self.camera.scroll.x * grid_fac) * self.camera.zoom)
                next_sy = round(((y + 1) * TILE_SIZE - self.camera.scroll.y * grid_fac) * self.camera.zoom)
                sw = next_sx - screen_x
                sh = next_sy - screen_y
                
                rect = pygame.Rect(screen_x, screen_y, sw, sh)
                pygame.draw.rect(surface, (40, 40, 40), rect, 1)

        # Draw Background Layers (0-2) as tiled images
        map_pixel_w = self.state['map_width'] * TILE_SIZE
        map_pixel_h = self.state['map_height'] * TILE_SIZE
        bg_layers_data = self.state.get('bg_layers', {})
        # Background Image Layers (Deprecated - No longer drawing full images)

        # Draw Layers
        for layer_idx in range(8):
            # Dim unselected layers slightly for focus, except below current layer
            alpha = 255 if layer_idx == self.current_layer else 150
            
            for key, tile_data in self.state['layers'][layer_idx].items():
                gx, gy = map(int, key.split(','))
                tile_name = tile_data['type'] if isinstance(tile_data, dict) else tile_data
                rot = tile_data.get('rot', 0) if isinstance(tile_data, dict) else 0
                
                if tile_name in self.assets.tiles:
                    img = self.assets.tiles[tile_name]
                    if rot != 0:
                        img = pygame.transform.rotate(img, rot)
                    
                    world_x, world_y = gx * TILE_SIZE, gy * TILE_SIZE
                    
                    # Apply Parallax if layer 0, 1, 2
                    fac = 1.0
                    if layer_idx in [0, 1, 2]:
                        bg_cfg = self.state.get('bg_layers', {}).get(layer_idx, {})
                        fac = float(bg_cfg.get('parallax', 1.0))
                    
                    # Manual world_to_screen with parallax factor & boundary rounding
                    screen_x = round((world_x - self.camera.scroll.x * fac) * self.camera.zoom)
                    screen_y = round((world_y - self.camera.scroll.y * fac) * self.camera.zoom)
                    next_sx = round((world_x + TILE_SIZE - self.camera.scroll.x * fac) * self.camera.zoom)
                    next_sy = round((world_y + TILE_SIZE - self.camera.scroll.y * fac) * self.camera.zoom)
                    sw = next_sx - screen_x
                    sh = next_sy - screen_y
                    
                    scaled_img = pygame.transform.scale(img, (sw, sh))
                    if alpha < 255:
                        scaled_img.set_alpha(alpha)
                    surface.blit(scaled_img, (screen_x, screen_y))

        # Draw Entities
        for e_type in ['chests', 'enemies', 'player_spawn', 'exit', 'portals', 'labels']:
            data = self.state['entities'].get(e_type)
            if not data: continue
                        # Unified entity drawing
            if e_type == 'player_spawn' and data:
                gx, gy = data
                self._draw_entity_marker(surface, gx, gy, (0, 255, 0), "P")
            elif e_type == 'exit' and data:
                gx, gy = data
                self._draw_entity_marker(surface, gx, gy, (255, 0, 0), "E")
            elif e_type == 'enemies':
                anim_frame = (pygame.time.get_ticks() // 100) % 10 # 10 FPS preview
                for key, e_data in data.items():
                    gx, gy = map(int, key.split(','))
                    if self.assets.wizard_frames:
                        img = self.assets.wizard_frames[anim_frame]
                        sx, sy = self.camera.world_to_screen(gx * TILE_SIZE, (gy + 1) * TILE_SIZE - 64)
                        svec = self.camera.world_to_screen((gx + 1) * TILE_SIZE, (gy + 1) * TILE_SIZE)
                        # We want it aligned to the grid, 2 tiles high
                        sw = svec[0] - sx
                        sh = (svec[1] - sy) * 2 # Wizard display is roughly 2 tiles high
                        # Actually 64x64 is 2x2 tiles. 
                        # sy = (gy+1)*32 - 64 = gy-1 tile top.
                        sx, sy = self.camera.world_to_screen(gx * TILE_SIZE, (gy - 1) * TILE_SIZE)
                        svec_br = self.camera.world_to_screen((gx + 2) * TILE_SIZE, (gy + 1) * TILE_SIZE)
                        sw = svec_br[0] - sx
                        sh = svec_br[1] - sy
                        
                        scaled = pygame.transform.scale(img, (sw, sh))
                        surface.blit(scaled, (sx, sy))
                    else:
                        self._draw_entity_marker(surface, gx, gy, (255, 50, 50), f"HP:{e_data.get('hp', 100)}")
            elif e_type == 'chests':
                for key, c_data in data.items():
                    gx, gy = map(int, key.split(','))
                    ct = c_data.get('type', 'Wood Chest')
                    closed_key = f"{ct}_closed"
                    if closed_key in self.assets.chests:
                        img = self.assets.chests[closed_key]
                        
                        # Use unified rounding for entity position and size
                        screen_x, screen_y = self.camera.world_to_screen(gx * TILE_SIZE, (gy - 1) * TILE_SIZE)
                        next_sx = self.camera.world_to_screen((gx + 1) * TILE_SIZE, (gy + 1) * TILE_SIZE)[0]
                        next_sy = self.camera.world_to_screen((gx + 1) * TILE_SIZE, (gy + 1) * TILE_SIZE)[1]
                        
                        scaled_w = round(TILE_SIZE * self.camera.zoom)
                        scaled_h = round(TILE_SIZE * 2 * self.camera.zoom)
                        # To be perfectly precise with tiles:
                        sx, sy = self.camera.world_to_screen(gx * TILE_SIZE, (gy - 1) * TILE_SIZE)
                        sx2, sy2 = self.camera.world_to_screen((gx + 1) * TILE_SIZE, (gy + 1) * TILE_SIZE)
                        scaled_w = sx2 - sx
                        scaled_h = sy2 - sy
                        
                        scaled_img = pygame.transform.scale(img, (scaled_w, scaled_h))
                        surface.blit(scaled_img, (sx, sy))

                        # Draw item indicator
                        item = c_data.get('items', '?')
                        chance = c_data.get('chance', 100)
                        if self.camera.zoom > 0.5:
                            label = font.render(f"{item[:1]} {chance}%", True, (255,255,255))
                            lx, ly = sx + 2, sy + 2
                            surface.blit(label, (lx, ly))
                        self._draw_entity_marker(surface, gx, gy, (255, 128, 0), f"{ct[:1]}C")
            elif e_type == 'portals':
                for key, p_data in data.items():
                    gx, gy = map(int, key.split(','))
                    pid = p_data.get('id', 0)
                    self._draw_entity_marker(surface, gx, gy, (200, 0, 255), f"W({pid})")
            elif e_type == 'labels':
                for key, l_data in data.items():
                    gx, gy = map(int, key.split(','))
                    text = l_data.get('text', "")
                    sx, sy = self.camera.world_to_screen(gx * TILE_SIZE, gy * TILE_SIZE)
                    if self.camera.zoom > 0.3:
                        lab = font_large.render(text, True, (255, 255, 100))
                        surface.blit(lab, (sx, sy))
                        pygame.draw.rect(surface, (255, 255, 255), (sx-2, sy-2, lab.get_width()+4, lab.get_height()+4), 1)

        # Draw Hover Highlight
        mouse_pos = pygame.mouse.get_pos()
        if not self.ui.rect.collidepoint(mouse_pos):
            # Use parallax factor for highlight
            fac = 1.0
            if self.current_layer in [0, 1, 2]:
                bg_cfg = self.state.get('bg_layers', {}).get(self.current_layer, {})
                fac = float(bg_cfg.get('parallax', 1.0))
                
            wx, wy = self.camera.screen_to_world(mouse_pos, fac)
            gx = int(wx // TILE_SIZE)
            gy = int(wy // TILE_SIZE)
            if 0 <= gx < self.state['map_width'] and 0 <= gy < self.state['map_height']:
                sx, sy = self.camera.world_to_screen(gx * TILE_SIZE, gy * TILE_SIZE, fac)
                sz = TILE_SIZE * self.camera.zoom
                pygame.draw.rect(surface, COLORS['highlight'], (sx, sy, sz, sz), max(1, int(2 * self.camera.zoom)))

        # Draw UI
        self.ui.draw(surface)

        # Draw HUD info
        info = f"Tool: {self.current_tool} | Layer: {self.current_layer} | History: {self.history_index+1}/{len(self.action_history)}"
        info_surf = font_bold.render(info, True, (255, 255, 255))
        surface.blit(info_surf, (10, 10))

    def _draw_entity_marker(self, surface, gx, gy, color, text):
        sx, sy = self.camera.world_to_screen(gx * TILE_SIZE, gy * TILE_SIZE)
        sz = TILE_SIZE * self.camera.zoom
        rect = pygame.Rect(sx, sy, sz, sz)
        s = pygame.Surface((sz, sz))
        s.set_alpha(150)
        s.fill(color)
        surface.blit(s, (sx, sy))
        pygame.draw.rect(surface, (255,255,255), rect, 2)
        
        # Render text centered if zoomed enough
        if self.camera.zoom > 0.5:
            ts = font.render(text, True, (255, 255, 255))
            tr = ts.get_rect(center=rect.center)
            surface.blit(ts, tr)

    def run(self):
        dt = 0
        running = True
        while running:
            running = self.handle_events()
            self.camera.update(dt)
            self.draw(screen)
            pygame.display.flip()
            dt = clock.tick(FPS) / 1000.0

if __name__ == "__main__":
    editor = LevelEditor()
    editor.run()
    pygame.quit()
    sys.exit()
