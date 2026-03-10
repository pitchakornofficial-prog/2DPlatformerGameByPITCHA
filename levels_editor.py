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
        self.load_assets("assets/tiles", self.tiles, is_spritesheet=True)
        self.load_assets("assets/box", self.chests, is_spritesheet=False, is_chest=True)
        self._load_items()

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

    def load_assets(self, path, dictionary, is_spritesheet=False, is_chest=False):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            return
        for file in os.listdir(path):
            if file.endswith((".png", ".jpg")):
                try:
                    img = pygame.image.load(os.path.join(path, file)).convert_alpha()
                    name = os.path.splitext(file)[0]
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
                            'Wood Chest':   {'icon': (32, 0),   'closed': (32, 32)},
                            'Iron Chest':   {'icon': (32, 64),  'closed': (32, 96)},
                            'Silver Chest': {'icon': (32, 128), 'closed': (32, 160)},
                            'Gold Chest':   {'icon': (32, 192), 'closed': (32, 224)},
                        }
                        for c_name, coords in chest_defs.items():
                            for kind, (cx, cy) in coords.items():
                                if cx + 32 <= img.get_width() and cy + 32 <= img.get_height():
                                    sub_img = img.subsurface(pygame.Rect(cx, cy, 32, 32))
                                    scaled_img = pygame.transform.scale(sub_img, (TILE_SIZE, TILE_SIZE))
                                    dictionary[f"{c_name}_{kind}"] = scaled_img
                                else:
                                    # Fallback colored placeholder
                                    s = pygame.Surface((TILE_SIZE, TILE_SIZE))
                                    fb_colors = {'Wood Chest': (139,90,43), 'Iron Chest': (120,120,120), 'Silver Chest': (180,180,200), 'Gold Chest': (220,180,50)}
                                    s.fill(fb_colors.get(c_name, (150,100,50)))
                                    dictionary[f"{c_name}_{kind}"] = s
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

    def screen_to_world(self, pos):
        x = (pos[0] / self.zoom) + self.scroll.x
        y = (pos[1] / self.zoom) + self.scroll.y
        return x, y

    def world_to_screen(self, x, y):
        sx = (x - self.scroll.x) * self.zoom
        sy = (y - self.scroll.y) * self.zoom
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
        entities = ["Player", "Enemy", "Exit"]
        for i, t in enumerate(entities):
            btn = UIButton(start_x + i * 110, start_y, 105, 30, t, lambda t=t: self.set_tool(t))
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
            img_name = bg.get('image') or '-- None --'
            short = img_name[:18] if img_name else '-- None --'
            self.buttons.append(UIButton(start_x, start_y, 250, 28, f"BG Img: {short}", self.cmd_select_bg_image))
            start_y += 34
            self.buttons.append(UIButton(start_x, start_y, 118, 26, f"OffX: {bg.get('offset_x', 0)}", self.cmd_bg_offset_x))
            self.buttons.append(UIButton(start_x + 125, start_y, 118, 26, f"OffY: {bg.get('offset_y', 0)}", self.cmd_bg_offset_y))
            start_y += 32
            self.buttons.append(UIButton(start_x, start_y, 118, 26, f"TileW: {bg.get('tile_w', 64)}", self.cmd_bg_tile_w))
            self.buttons.append(UIButton(start_x + 125, start_y, 118, 26, f"TileH: {bg.get('tile_h', 64)}", self.cmd_bg_tile_h))
            start_y += 32

        self.palette_start_y = start_y + (190 if self.editor.current_tool == "Chest" else 50)

    def cmd_new(self):
        self.editor.state = {
            'map_width': 10, 'map_height': 10,
            'layers': {i: {} for i in range(8)},
            'bg_layers': {i: {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0} for i in range(3)},
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
                    'entities': data.get('entities', {'player_spawn': None, 'exit': None, 'enemies': {}, 'chests': {}})
                }
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
        top = tk.Toplevel(root)
        top.title("Select Background Image")
        tile_names = list(self.editor.assets.tiles.keys())
        selected = [self.editor.state['bg_layers'].get(self.editor.current_layer, {}).get('image')]
        lb = tk.Listbox(top, height=15, width=40, selectmode=tk.SINGLE)
        for name in tile_names:
            lb.insert(tk.END, name)
        if selected[0] in tile_names:
            idx = tile_names.index(selected[0])
            lb.select_set(idx)
            lb.see(idx)
        lb.pack(padx=5, pady=5)
        def on_ok():
            sel = lb.curselection()
            selected[0] = tile_names[sel[0]] if sel else None
            top.destroy()
        def on_clear():
            selected[0] = None
            top.destroy()
        btn_frame = tk.Frame(top)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="OK", command=on_ok, bg='#4CAF50', fg='white', width=10).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(btn_frame, text="Clear", command=on_clear, width=10).pack(side=tk.LEFT, padx=5, pady=5)
        top.transient(root); top.grab_set()
        while top.winfo_exists():
            try: root.update()
            except tk.TclError: break
            pygame.event.pump()
        layer = self.editor.current_layer
        self.editor.state.setdefault('bg_layers', {})
        self.editor.state['bg_layers'].setdefault(layer, {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0})
        self.editor.state['bg_layers'][layer]['image'] = selected[0]
        self.editor.save_history()
        self.setup_ui()

    def cmd_bg_offset_x(self): self._bg_prop_dialog("BG Offset", "Offset X (px):", "offset_x")
    def cmd_bg_offset_y(self): self._bg_prop_dialog("BG Offset", "Offset Y (px):", "offset_y")
    def cmd_bg_tile_w(self): self._bg_prop_dialog("BG Tile Size", "Tile Width (px):", "tile_w")
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
            'bg_layers': {i: {'image': None, 'offset_x': 0, 'offset_y': 0, 'tile_w': 64, 'tile_h': 64, 'rot': 0} for i in range(3)},
            'entities': {
                'player_spawn': None,
                'exit': None,
                'enemies': {},
                'chests': {}
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

                # Single-click canvas action (Rotate, Select, Player, Enemy, Exit, Chest)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not self.ui.rect.collidepoint(event.pos):
                        wx, wy = self.camera.screen_to_world(event.pos)
                        gx = int(wx // TILE_SIZE)
                        gy = int(wy // TILE_SIZE)
                        if self.current_tool not in ["Draw", "Erase"]:
                            self.process_canvas_click((gx, gy), 1)
                    
        # Continuous mouse hold handling for Draw and Erase only
        if not self.ui.rect.collidepoint(pygame.mouse.get_pos()):
            mouse_buttons = pygame.mouse.get_pressed()
            if mouse_buttons[0] or mouse_buttons[2]:
                mx, my = pygame.mouse.get_pos()
                wx, wy = self.camera.screen_to_world((mx, my))
                grid_x = int(wx // TILE_SIZE)
                grid_y = int(wy // TILE_SIZE)
                if self.current_tool in ["Draw", "Erase"]:
                    self.process_canvas_click((grid_x, grid_y), 1 if mouse_buttons[0] else 3)

        return True

    def draw(self, surface):
        surface.fill(COLORS['bg'])

        # Draw Grid Background
        for x in range(self.state['map_width']):
            for y in range(self.state['map_height']):
                world_x = x * TILE_SIZE
                world_y = y * TILE_SIZE
                screen_x, screen_y = self.camera.world_to_screen(world_x, world_y)
                scaled_size = TILE_SIZE * self.camera.zoom
                
                rect = pygame.Rect(screen_x, screen_y, scaled_size, scaled_size)
                pygame.draw.rect(surface, COLORS['grid'], rect, 1)

        # Draw Background Layers (0-2) as tiled images
        map_pixel_w = self.state['map_width'] * TILE_SIZE
        map_pixel_h = self.state['map_height'] * TILE_SIZE
        bg_layers_data = self.state.get('bg_layers', {})
        for layer_idx in range(3):
            bg = bg_layers_data.get(layer_idx, {})
            img_name = bg.get('image')
            if not img_name or img_name not in self.assets.tiles:
                continue
            base_img = self.assets.tiles[img_name]
            tw = max(1, int(bg.get('tile_w', 64)))
            th = max(1, int(bg.get('tile_h', 64)))
            off_x = int(bg.get('offset_x', 0))
            off_y = int(bg.get('offset_y', 0))
            alpha_val = 255 if layer_idx == self.current_layer else 130
            tile_surf = pygame.transform.scale(base_img, (tw, th))
            # Tile across the full map, plus one extra tile in each direction
            cols = map_pixel_w // tw + 2
            rows = map_pixel_h // th + 2
            for row in range(rows):
                for col in range(cols):
                    wx = off_x + col * tw
                    wy = off_y + row * th
                    sx, sy = self.camera.world_to_screen(wx, wy)
                    sw = int(tw * self.camera.zoom)
                    sh = int(th * self.camera.zoom)
                    scaled_tile = pygame.transform.scale(base_img, (sw, sh))
                    if alpha_val < 255:
                        scaled_tile.set_alpha(alpha_val)
                    surface.blit(scaled_tile, (sx, sy))

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
                    screen_x, screen_y = self.camera.world_to_screen(gx * TILE_SIZE, gy * TILE_SIZE)
                    scaled_size = int(TILE_SIZE * self.camera.zoom)
                    scaled_img = pygame.transform.scale(img, (scaled_size, scaled_size))
                    if alpha < 255:
                        scaled_img.set_alpha(alpha)
                    surface.blit(scaled_img, (screen_x, screen_y))

        # Draw Entities
        for e_type in ['chests', 'enemies', 'player_spawn', 'exit']:
            data = self.state['entities'][e_type]
            if not data: continue
            
            if e_type == 'player_spawn':
                gx, gy = data
                self._draw_entity_marker(surface, gx, gy, (30, 144, 255), "PLAYER")
            elif e_type == 'exit':
                gx, gy = data
                self._draw_entity_marker(surface, gx, gy, (50, 205, 50), "EXIT")
            elif e_type == 'enemies':
                for key, e_data in data.items():
                    gx, gy = map(int, key.split(','))
                    self._draw_entity_marker(surface, gx, gy, (220, 30, 30), f"HP:{e_data['hp']}")
            elif e_type == 'chests':
                for key, c_data in data.items():
                    gx, gy = map(int, key.split(','))
                    ct = c_data.get('type', 'Wood Chest')
                    closed_key = f"{ct}_closed"
                    if closed_key in self.assets.chests:
                        img = self.assets.chests[closed_key]
                        screen_x, screen_y = self.camera.world_to_screen(gx * TILE_SIZE, gy * TILE_SIZE)
                        scaled_size = int(TILE_SIZE * self.camera.zoom)
                        scaled_img = pygame.transform.scale(img, (scaled_size, scaled_size))
                        surface.blit(scaled_img, (screen_x, screen_y))
                        # Draw item indicator
                        item = c_data.get('items', '?')
                        chance = c_data.get('chance', 100)
                        if self.camera.zoom > 0.5:
                            label = font.render(f"{item[:1]} {chance}%", True, (255,255,255))
                            lx, ly = screen_x + 2, screen_y + 2
                            surface.blit(label, (lx, ly))
                    else:
                        self._draw_entity_marker(surface, gx, gy, (255, 128, 0), f"{ct[:1]}C")

        # Draw Hover Highlight
        mouse_pos = pygame.mouse.get_pos()
        if not self.ui.rect.collidepoint(mouse_pos):
            wx, wy = self.camera.screen_to_world(mouse_pos)
            gx = int(wx // TILE_SIZE)
            gy = int(wy // TILE_SIZE)
            if 0 <= gx < self.state['map_width'] and 0 <= gy < self.state['map_height']:
                sx, sy = self.camera.world_to_screen(gx * TILE_SIZE, gy * TILE_SIZE)
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
