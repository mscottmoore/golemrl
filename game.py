import libtcodpy as libtcod
from config import *
import logging
import yaml
from thing import Thing
from player import Player
from inputhandler import InputHandler
from creature import Creature
from breed import Breed
from golem import Golem
from bodypart import BodyPart
from trait import Trait
from ai import AI
from dungeon import Dungeon
from console import Console
from messagelog import MessageLog
from rng import RNG
from material import Material

class Game:
    def __init__(self):
        self.rng = RNG()
        self.player = None
        self.things = []
        self.dungeon = None
        self.message_log = None
        self.menu = None
        self.breeds = {}
        self.materials = {}

        self.map_con = Console("Dungeon Map",MAP_X,MAP_Y,MAP_W,MAP_H)
        self.panel_con = Console("Side Panel",PANEL_X,PANEL_Y,PANEL_W,PANEL_H)
        self.log_con = Console("Message Log",LOG_X,LOG_Y,LOG_W,LOG_H)

        self.state = STATE_PLAYING

    @property
    def depth(self):
        return self.player.depth
    @property
    def cur_level(self):
        return self.player.level

    @property
    def living_things(self):
        return filter(lambda thing: thing.creature and thing.creature.alive, self.things)

    def add_thing(self,thing):
        thing.owner = self
        self.things.append(thing)

    def next_id(self):
        next_id = 0
        id_list = [thing.thing_id for thing in self.things]
        while True:
            if next_id not in id_list:
                return next_id
            else:
                next_id += 1

    def load_materials(self):
        materials_file = open('data/materials.yaml')
        self.materials = yaml.load(materials_file)
        materials_file.close()
        for name in self.materials:
            self.materials[name]['color'] = eval('libtcod.' + self.materials[name]['color'])
            self.materials[name]['written_color'] = eval('libtcod.' + self.materials[name]['written_color'])
            self.materials[name] = Material(name,**self.materials[name])

    def load_traits(self):
        traits_file = open('data/traits.yaml')
        self.traits = yaml.load(traits_file)
        traits_file.close()
        for trait_id in self.traits:
            if 'modifiers' in self.traits[trait_id]:
                for modifier in self.traits[trait_id]['modifiers']:
                    self.traits[trait_id][modifier+'_mod'] = self.traits[trait_id]['modifiers'][modifier]
                del self.traits[trait_id]['modifiers']
            self.traits[trait_id] = Trait(trait_id,**self.traits[trait_id])
        for trait_id in self.traits:
            trait = self.traits[trait_id]
            if trait.replaces:
                trait.replaces = self.traits[trait.replaces]
            if not trait.cancels: trait.cancels=[]
            for i in range(len(trait.cancels)):
                trait.cancels[i] = self.traits[trait.cancels[i]]

            if trait.cost:
                new_cost = {}
                for material in trait.cost:
                    new_cost[self.materials[material]] = trait.cost[material]
                trait.cost = new_cost

            if trait.removal_cost:
                new_removal_cost = {}
                for material in trait.removal_cost:
                    new_removal_cost[self.materials[material]] = trait.removal_cost[material]
                trait.removal_cost = new_removal_cost
                
    def load_breeds(self):
        breeds_file = open('data/breeds.yaml')
        self.breeds = yaml.load(breeds_file)
        breeds_file.close()
        for name in self.breeds:
            color = 'libtcod.' + self.breeds[name]['color'].strip().replace(' ','_')
            self.breeds[name]['color'] = eval(color)

            new_materials_dict = {}
            for material in self.breeds[name]['materials']:
                proper_material = self.materials[material]
                new_materials_dict[proper_material] = self.breeds[name]['materials'][material]
            self.breeds[name]['materials'] = new_materials_dict

            self.breeds[name] = Breed(name, **self.breeds[name])
            self.breeds[name].owner = self

    def clear_all(self):
        for thing in self.things:
            thing.clear(self.player.x,
                        self.player.y,
                        self.map_con)

    def get_thing(self,thing_id):
        for thing in self.things:
            if thing.thing_id == thing_id:
                return thing

    def get_things_at(self,x,y):
        things_at_pos = []
        for thing in self.things:
            if thing.pos == (x,y):
                things_at_pos.append(thing)
        return things_at_pos

    def render_panel(self):
        self.panel_con.clear()
        self.panel_con.draw_border(True,C_BORDER,C_BORDER_BKGND)

        y = 2
        for part_name in ['Head','Torso','L Arm','R Arm','L Leg','R Leg']:
            part = self.player.creature.body_parts[part_name]
            x = 2
            color = libtcod.white
            for char in '%s: %i/%i'%(part.name,part.health,part.max_health):
                self.panel_con.put_char(x,y,char,color)
                if char == ':':
                    color = libtcod.light_red
                x += 1
            y += 1

        y += 1
        for material in sorted(self.player.materials):
            color = material.written_color
            x = 2
            for char in '%s: %i'%(material,self.player.materials[material]):
                self.panel_con.put_char(x,y,char,color)
                x += 1
            y += 1

    def render_all(self):
        player_x = self.player.x
        player_y = self.player.y

        self.dungeon.render(player_x, player_y, self.map_con)
        for thing in self.things:
            if thing != self.player:
                thing.render(player_x, player_y, self.map_con)
        for thing in self.living_things: #draw living creatures on top
            if thing != self.player:
                thing.render(player_x, player_y, self.map_con)
        self.player.render(player_x, player_y, self.map_con)
        self.map_con.draw_border(True,C_BORDER,C_BORDER_BKGND)
        #self.map_con.blit()
        if self.menu:
            self.menu.render(self.map_con)
        self.map_con.blit()

        self.message_log.render(self.log_con)
        self.log_con.blit()

        self.render_panel()
        self.panel_con.blit()

    def play(self):
        key = libtcod.Key()
        mouse = libtcod.Mouse()

        while not libtcod.console_is_window_closed():
            libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
            self.clear_all()

            self.state = self.player.input_handler(key,mouse,self.menu)
            if self.menu and self.state != STATE_MENU:
                self.menu = None

            if self.state == STATE_PLAYING:
                for thing in self.things:
                    thing.update()
                self.state = STATE_PAUSED

            self.dungeon.update()

            self.render_all()
            libtcod.console_flush()

def new_game(seed = 0xDEADBEEF):
    game = Game()
    game.load_materials()
    game.load_traits()
    game.load_breeds()

    player_file = open('data/player.yaml')
    player_data = yaml.load(player_file)
    player_name = player_data.keys()[0]
    player_data = player_data[player_name]
    player_file.close()
    player_data['color'] = eval('libtcod.%s' % player_data['color'])
    for part_name in player_data['body_parts']:
        player_data['body_parts'][part_name] = BodyPart(part_name,**player_data['body_parts'][part_name])

    player_creature = Golem(player_name,**player_data)

    player = Player(0,
                    0, 0, 0, False, True,
                    creature = player_creature)

    player.input_handler = InputHandler()
    player.input_handler.owner = player
    for name in game.materials:
        player.materials[game.materials[name]] = 0
    game.player = player
    game.add_thing(player)

    message_log = MessageLog()
    message_log.owner = game
    player.add_observer(message_log)
    player.input_handler.add_observer(message_log)
    game.message_log = message_log

    dungeon = Dungeon(seed)
    dungeon.owner = game
    game.dungeon = dungeon
    player.add_observer(dungeon)
    start_pos = game.dungeon.generate_level(0)
    player.move_to(*start_pos)

    return game

def load_game(file_name):
    pass

def save_game(file_name):
    pass
