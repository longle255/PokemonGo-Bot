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

    def get_player_info(self):
        request = self.bot.api.create_request()
        request.get_player()
        request.get_inventory()
        response_dict = request.call()
        inventory = response_dict['responses'].get('GET_INVENTORY', {})
        player_info = response_dict['responses'].get('GET_PLAYER', {})
        self.sio.emit(
            'bot:send_reply',
            {
                'result': {'inventory': inventory, 'player': player_info},
                'command': 'get_player_info',
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
        pokemon_name = data['pokemon_name']
        iv = data['iv']
        cp = data['cp']
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
                    'message': 'Can\'t find the pokemon {pokemon} [CP {cp}] [IV {iv}].' 
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
                    'message': 'Exchanged {pokemon} [CP {cp}] [IV {iv}] for candy.' 
                }
            )
        else:
            self.sio.emit(
                'bot:send_reply',
                {
                    'result': False,
                    'command': 'transfer_pokemon',
                    'account': self.bot.config.username,
                    'message': 'Exchanged {pokemon} [CP {cp}] [IV {iv}] failed.'
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