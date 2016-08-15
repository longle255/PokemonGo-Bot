import threading
from socketIO_client import SocketIO, BaseNamespace


class WebsocketRemoteControl(object):


    def __init__(self, bot):
        self.bot = bot
        self.host, port_str = self.bot.config.websocket_server_url.split(':')
        self.port = int(port_str)
        self.sio = SocketIO(self.host, self.port)
        self.sio.on(
            'bot:process_request:{}'.format(self.bot.config.username),
            self.on_remote_command
        )
        self.thread = threading.Thread(target=self.process_messages)

    def start(self):
        self.thread.start()
        return self

    def process_messages(self):
        self.sio.wait()
    
    def on_remote_command(self, command):
        name = command['name']
        command_handler = getattr(self, name, None)
        if not hasattr(self.bot,'_player'):
          self.sio.emit(
                'bot:send_reply',
                {
                    'response': '',
                    'command': 'bot_is_not_ready',
                    'account': self.bot.config.username
                }
            ) 
        if not command_handler or not callable(command_handler):
            self.sio.emit(
                'bot:send_reply',
                {
                    'response': '',
                    'command': 'command_not_found',
                    'account': self.bot.config.username
                }
            )
            return
        if 'args' in command:
            command_handler(command['args'])
            return
        command_handler()


    def evolve_pokemon(self, data):
      # print data
      height = data['height']
      weight = data['weight']
      creation_time = data['creation_time_ms']
      pokemon = self.find_pokemon_by_stats(height, weight, creation_time)
      if pokemon is None:
          return self.sio.emit(
              'bot:send_reply',
              {
                  'result': False,
                  'command': 'evolve_pokemon',
                  'account': self.bot.config.username,
                  'message': 'Can\'t find the pokemon {pokemon}' 
              }
          )
      pokemon_id = pokemon['id']
      response_dict = self.bot.api.evolve_pokemon(pokemon_id=pokemon_id)
      result = response_dict.get('responses', {}).get('EVOLVE_POKEMON', {}).get('result', 0)
      pokemon = response_dict.get('responses', {}).get('EVOLVE_POKEMON', {}).get('evolved_pokemon_data')
      candy = response_dict.get('responses', {}).get('EVOLVE_POKEMON', {}).get('candy_awarded')
      experience = response_dict.get('responses', {}).get('EVOLVE_POKEMON', {}).get('experience_awarded')
      if result == 1: # Request success
          self.sio.emit(
              'bot:send_reply',
              {
                  'result': {
                    'pokemon': pokemon,
                    'candy': candy,
                    'experience': experience
                  },
                  'command': 'evolve_pokemon',
                  'account': self.bot.config.username,
                  'message': 'Evolved {pokemon}.' 
              }
          )
      else:
          self.sio.emit(
              'bot:send_reply',
              {
                  'result': False,
                  'command': 'evolve_pokemon',
                  'account': self.bot.config.username,
                  'message': 'Favorite {pokemon} failed.'
              }
          )

    def favorite_pokemon(self, data):
      # print data
      height = data['height']
      weight = data['weight']
      creation_time = data['creation_time_ms']
      favorite = data['favorite']
      pokemon = self.find_pokemon_by_stats(height, weight, creation_time)
      if pokemon is None:
          return self.sio.emit(
              'bot:send_reply',
              {
                  'result': False,
                  'command': 'favorite_pokemon',
                  'account': self.bot.config.username,
                  'message': 'Can\'t find the pokemon {pokemon}' 
              }
          )
      pokemon_id = pokemon['id']
      response_dict = self.bot.api.set_favorite_pokemon(pokemon_id=pokemon_id,  is_favorite=favorite)
      result = response_dict.get('responses', {}).get('SET_FAVORITE_POKEMON', {}).get('result', 0)
      print response_dict
      if result == 1: # Request success
          self.sio.emit(
              'bot:send_reply',
              {
                  'result': True,
                  'command': 'favorite_pokemon',
                  'account': self.bot.config.username,
                  'message': 'Favorited {pokemon}.' 
              }
          )
      else:
          self.sio.emit(
              'bot:send_reply',
              {
                  'result': False,
                  'command': 'favorite_pokemon',
                  'account': self.bot.config.username,
                  'message': 'Favorite {pokemon} failed.'
              }
          )

    def eggs_list(self, data):
      request = self.bot.api.create_request()
      request.get_player()
      request.get_inventory()
      response_dict = request.call()
      inv = reduce(
          dict.__getitem__,
          ["responses", "GET_INVENTORY", "inventory_delta", "inventory_items"],
          response_dict
      )
      eggs = []
      incubators = []
      km_walked = {}
      for inv_data in inv:
          inv_data = inv_data.get("inventory_item_data", {})
          if "pokemon_data" in inv_data:
            pokemon = inv_data.get("pokemon_data", {})
            if (pokemon.get('is_egg', False)):
              eggs.append(pokemon)
          elif "egg_incubators" in inv_data:
            incubators = inv_data.get('egg_incubators').get('egg_incubator')
          elif 'player_stats' in inv_data:
            km_walked = inv_data.get('player_stats',{}).get('km_walked')

      self.sio.emit(
          'bot:send_reply',
          {
              'result': {
                'eggs': eggs,
                'egg_incubators': incubators,
                'km_walked': km_walked
              },
              'command': 'eggs_list',
              'account': self.bot.config.username
          }
      )
    def inventory_list(self, data):
      request = self.bot.api.create_request()
      request.get_player()
      request.get_inventory()
      response_dict = request.call()
      inv = reduce(
          dict.__getitem__,
          ["responses", "GET_INVENTORY", "inventory_delta", "inventory_items"],
          response_dict
      )
      inventory = {}
      for inv_data in inv:
          inv_data = inv_data.get("inventory_item_data", {})
          if "item" in inv_data:
            item = inv_data.get("item",{})
            inventory[item.get('item_id')] = item.get('count')
      self.sio.emit(
          'bot:send_reply',
          {
              'result': inventory,
              'command': 'inventory_list',
              'account': self.bot.config.username
          }
      )
    def pokemon_list(self, data):
        request = self.bot.api.create_request()
        request.get_player()
        request.get_inventory()
        response_dict = request.call()
        inv = reduce(
            dict.__getitem__,
            ["responses", "GET_INVENTORY", "inventory_delta", "inventory_items"],
            response_dict
        )
        pokemons = []
        candy = []
        eggs = []
        for inv_data in inv:
            inv_data = inv_data.get("inventory_item_data", {})
            if "pokemon_data" in inv_data:
              pokemon = inv_data.get("pokemon_data", {})
              if (pokemon.get('is_egg', False)):
                eggs.append(pokemon)
              else:
                pokemons.append(pokemon)
            elif "candy" in inv_data:
              candy.append(inv_data.get('candy'))            

        emit_object = {
            "pokemon": pokemons,
            "candy": candy,
            "eggs_count": len(eggs)
        }
        self.sio.emit(
            'bot:send_reply',
            {
                'result': emit_object,
                'command': 'pokemon_list',
                'account': self.bot.config.username
            }
        )

    def get_pokemon_setting(self, data):
      request = self.bot.api.create_request()
      templates = request.download_item_templates().call()
      templates = templates.get('responses',{}).get('DOWNLOAD_ITEM_TEMPLATES',{}).get('item_templates',{})
      pokemon_settings = [t.get("pokemon_settings") for t in templates if "pokemon_settings" in t]
      pokemon_settings = sorted(pokemon_settings, key=lambda p: p.get("pokemon_id"))
      self.sio.emit(
          'bot:send_reply',
          {
              'result': pokemon_settings,
              'command': 'get_pokemon_setting',
              'account': self.bot.config.username
          }
      )

    def bot_initialized(self, data):
        request = self.bot.api.create_request()
        request.get_player()
        request.get_inventory()
        response_dict = request.call()
        inventory_items = response_dict['responses'].get('GET_INVENTORY', {}).get('inventory_delta', {}).get('inventory_items', {})
        player_info = response_dict['responses'].get('GET_PLAYER', {})
        player={}
        storage = {
          'max_pokemon_storage': player_info.get('player_data').get('max_pokemon_storage'),
          'max_item_storage': player_info.get('player_data').get('max_item_storage')
        }
        coordinates=self.bot.position
        if inventory_items:
            pokecount = 0
            itemcount = 1
            for item in inventory_items:
                # print('item {}'.format(item))
                playerdata = item.get('inventory_item_data', {}).get('player_stats')
                if playerdata:
                  player = {
                      "level": playerdata.get('level'),
                      "unique_pokedex_entries": playerdata.get('unique_pokedex_entries'),
                      "pokemons_captured": playerdata.get('pokemons_captured'),
                      "next_level_xp": playerdata.get('next_level_xp'),
                      "prev_level_xp": playerdata.get('prev_level_xp'),
                      "experience": playerdata.get('experience'),
                  }
                  break
                  
        self.sio.emit(
            'bot:send_reply',
            {
                'result': {
                  'player': player,
                  'storage':storage,
                  'coordinates':coordinates
                },
                'command': 'bot_initialized',
                'account': self.bot.config.username
            }
        )
    def get_player_stats(self, data):
        request = self.bot.api.create_request()
        request.get_player()
        request.get_inventory()
        response_dict = request.call()
        inventory_items = response_dict['responses'].get('GET_INVENTORY', {}).get('inventory_delta', {}).get('inventory_items', {})
        player={}
        if inventory_items:
            pokecount = 0
            itemcount = 1
            for item in inventory_items:
                # print('item {}'.format(item))
                playerdata = item.get('inventory_item_data', {}).get('player_stats')
                if playerdata:
                  player = {
                      "level": playerdata.get('level'),
                      "unique_pokedex_entries": playerdata.get('unique_pokedex_entries'),
                      "pokemons_captured": playerdata.get('pokemons_captured'),
                      "next_level_xp": playerdata.get('next_level_xp'),
                      "prev_level_xp": playerdata.get('prev_level_xp'),
                      "experience": playerdata.get('experience')
                  }
                  break
                  
        self.sio.emit(
            'bot:send_reply',
            {
                'result': player,
                'command': 'get_player_stats',
                'account': self.bot.config.username
            }
        )
        
    def discard_item(self, data):
        item_id = data['item_id']
        count = data['count']
        response_dict_recycle = self.bot.api.recycle_inventory_item(
            item_id=item_id,
            count=count
        )
        result = response_dict_recycle.get('responses', {}).get('RECYCLE_INVENTORY_ITEM', {}).get('result', 0)
        if result == 1: # Request success
            self.sio.emit(
                'bot:send_reply',
                {
                    'result': True,
                    'command': 'discard_item',
                    'account': self.bot.config.username
                }
            )
        else:
            self.sio.emit(
                'bot:send_reply',
                {
                    'result': False,
                    'command': 'discard_item',
                    'account': self.bot.config.username
                }
            )

    def transfer_pokemon(self, data):
        # print data
        height = data['height']
        weight = data['weight']
        creation_time = data['creation_time_ms']
        pokemon = self.find_pokemon_by_stats(height, weight, creation_time)
        if pokemon is None:
            return self.sio.emit(
                'bot:send_reply',
                {
                    'result': False,
                    'command': 'transfer_pokemon',
                    'account': self.bot.config.username,
                    'message': 'Can\'t find the pokemon {pokemon}' 
                }
            )
        pokemon_id = pokemon['id']
        response_dict = self.bot.api.release_pokemon(pokemon_id=pokemon_id)
        result = response_dict.get('responses', {}).get('RELEASE_POKEMON', {}).get('result', 0)
        print response_dict
        if result == 1: # Request success
            self.sio.emit(
                'bot:send_reply',
                {
                    'result': True,
                    'command': 'transfer_pokemon',
                    'account': self.bot.config.username,
                    'message': 'Exchanged {pokemon} for candy.' 
                }
            )
        else:
            self.sio.emit(
                'bot:send_reply',
                {
                    'result': False,
                    'command': 'transfer_pokemon',
                    'account': self.bot.config.username,
                    'message': 'Exchanged {pokemon} failed.'
                }
            )

    def find_pokemon_by_stats(self, height, weight, creation_time):
        pokemon_groups = self._release_pokemon_get_groups()
        for i in pokemon_groups:
            if (i['height_m']==height and i['weight_kg']==weight and i['creation_time_ms']==creation_time):
                return i
        return None

    def _release_pokemon_get_groups(self):
        pokemon_groups = []
        request = self.bot.api.create_request()
        request.get_player()
        request.get_inventory()
        inventory_req = request.call()

        if inventory_req.get('responses', False) is False:
            return pokemon_groups

        inventory_dict = inventory_req['responses']['GET_INVENTORY']['inventory_delta']['inventory_items']

        for pokemon in inventory_dict:
            try:
                reduce(dict.__getitem__, [
                    "inventory_item_data", "pokemon_data", "pokemon_id"
                ], pokemon)
            except KeyError:
                continue

            pokemon_data = pokemon['inventory_item_data']['pokemon_data']

            # pokemon in fort, so we cant transfer it
            if 'deployed_fort_id' in pokemon_data and pokemon_data['deployed_fort_id']:
                continue

            # favorite pokemon can't transfer in official game client
            if pokemon_data.get('favorite', 0) is 1:
                continue


            pokemon_groups.append(pokemon_data)

        return pokemon_groups