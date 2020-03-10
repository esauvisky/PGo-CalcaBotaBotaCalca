#!/usr/bin/env python3.7
import argparse
import asyncio
import logging
import operator
import os.path
import re
from sys import platform

import yaml
from colorlog import ColoredFormatter

from pokemonlib import PokemonGo


def in_func(a, b):
    return a in b

def not_in_func(a, b):
    return a not in b

ops = {
    'lt': operator.lt,
    'le': operator.le,
    'eq': operator.eq,
    'ne': operator.ne,
    'ge': operator.ge,
    'gt': operator.gt,
    'in': in_func,
    'not_in': not_in_func,
}

logger = logging.getLogger('ivcheck')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = ColoredFormatter('%(log_color)s[%(asctime)s] %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s', datefmt='%I:%M:%S %p')
ch.setFormatter(formatter)
logger.addHandler(ch)

#JGF07feb2020 - old:  RE_CALCY_IV = re.compile(r"^.\/i       (\(\s*\d+\)){0,1}: Received values: Id: -{0,1}\d+ {0,1}\({0,1}(?P<name>[^\(\)]+){0,1}\){0,1}, Nr: (?P<id>-{0,1}\d+), CP: (?P<cp>-{0,1}\d+), Max HP: (?P<max_hp>-{0,1}\d+), Dust cost: (?P<dust_cost>-{0,1}\d+), Level: (?P<level>\-{0,1}[\d\.]+), FastMove (?P<fast_move>.+), SpecialMove (?P<special_move>.+), SpecialMove2 (?P<special_move2>.+), Gender (?P<gender>.+), CatchYear (?P<catch_year>.+), Favorite: (?P<favorite>(false|true)), Level-up (true|false):$")
RE_CALCY_IV = re.compile(r"^.\/j\s*\(\s*\d+\): Received values: Id\(s\): (?P<name>\w+[-. \W+\w+]*) \((?P<id>\d+[,\d+]*)\), CP: (?P<cp>-{0,1}\d+), HP: (?P<max_hp>-{0,1}\d+), Level\(s\): (?P<level>\-{0,1}[\d\.]+), Dust: (?P<dust_cost>-{0,1}\d+), FastMove: (?P<fast_move>\w+[- \w+]*), SpecialMove: (?P<special_move>\w+[- \w+]*), SpecialMove2: (?P<special_move2>\w+[- \w+]*), Gender: (?P<gender>\w+), Lucky: (?:YES|NO), CatchYear: (?P<catch_year>\w+), Favorite: (?P<favorite>(?:false|true)), TLevel-up: (?:true|false)$")
RE_RED_BAR = re.compile(r"^.+\(\s*\d+\): Screenshot #\d has red error box at the top of the screen$")
RE_SUCCESS = re.compile(r"^.+\(\s*\d+\): calculateScanOutputData finished after \d+ms$")
RE_SCAN_INVALID = re.compile(r"^.+\(\s*\d+\): Scan invalid .+$")
RE_SCAN_TOO_SOON = re.compile(r"^.+\(\s*\d+\): Detected power-up screen$")
RE_OLD_BASE_STATS = re.compile(r"^.+\(\s*\d+\): Using legacy fallback for.+$")

NAME_MAX_LEN = 12

NUMBER_SETS = [
    [chr(9450)] + [chr(i) for i in range(9312, 9332)] + [chr(i) for i in range(12881, 12896)] + [chr(i) for i in range(12977, 12992)],  # white circled digits
    [chr(9471)] + [chr(i) for i in range(10102, 10112)] + [chr(i) for i in range(9451, 9461)],  # blank circled digits
    [chr(8304)] + [chr(185)] + [chr(178)] + [chr(179)] + [chr(i) for i in range(8308, 8314)],  # superscripted digits
    [chr(i) for i in range(8320, 8329)],  # subscripted digits: "???"
    [chr(i) for i in range(48, 58)] + [chr(i) for i in range(65, 71)]  # hexadecimal *digits* (yes, they are digits.)
]

CALCY_STRING = '\xa0'*NAME_MAX_LEN + '$CatchDate$|$Lucky$|$ATT$|$DEF$|$HP$|$Gender$|$Trade$|$IV%Min$|$IV%Max$|$AttIV$|$DefIV$|$HpIV$|$FaMove$|$SpMove$|$Appraised$|$Legacy$'

def gender_filter(c):
    if c == chr(9794):
        return 'M'
    elif c == chr(9792):
        return 'F'
    return 'U'

def int_filter(c):
    try:
        return int(c)
    except ValueError:
        pass
    for number_set in NUMBER_SETS:
        try:
            chars = [number_set.index(char) for char in c]
        except ValueError:
            pass
        else:
            return int(''.join(map(str, chars)))
    raise ValueError('Unrecognised number format %s', c)

def bool_filter(c):
    if c:
        return True
    return False

def appraise_filter(c):
    if c == chr(167):
        return True
    return False

CALCY_VARIABLES = [
    ['catch_year', None],
    ['lucky', bool_filter],
    ['attack', int_filter],
    ['defense', int_filter],
    ['hp', int_filter],
    ['gender', gender_filter],
    ['trade', bool_filter],
    ['iv_min', int_filter],
    ['iv_max', int_filter],
    ['attack_iv', int_filter],
    ['defense_iv', int_filter],
    ['hp_iv', int_filter],
    ['fast_move', None],
    ['charge_move', None],
    ['appraised', appraise_filter],
    ['legacy', bool_filter],
]

CALCY_SUCCESS = 0
CALCY_RED_BAR = 1
CALCY_SCAN_INVALID = 2
CALCY_SCAN_TOO_SOON = 3
CALCY_OLD_BASE_STATS = 4

class Loader(yaml.SafeLoader):
    def __init__(self, stream):
        self._root = os.path.split(stream.name)[0]
        super(Loader, self).__init__(stream)

    def include(self, node):
        filename = os.path.join(self._root, self.construct_scalar(node))
        with open(filename, 'r') as f:
            return yaml.load(f, Loader)

Loader.add_constructor('!include', Loader.include)

class Main:
    def __init__(self, args):
        self.args = args
        self.use_fallback_screenshots = False

    async def tap(self, location):
        await self.p.tap(*self.config['locations'][location])
        if location in self.config['waits']:
            logger.info('Waiting ' + str(self.config['waits'][location]) + ' seconds after ' + str(self.config['locations'][location]) + '...')
            await asyncio.sleep(self.config['waits'][location])

    async def tap_and_hold(self, location, duration):
        await self.p.swipe(
            self.config['locations'][location][0],
            self.config['locations'][location][1],
            self.config['locations'][location][0],
            self.config['locations'][location][1],
            duration
        )
        if location in self.config['waits']:
            logger.info('Waiting ' + str(self.config['waits'][location]) + ' seconds after ' + str(self.config['locations'][location]) + '...')
            await asyncio.sleep(self.config['waits'][location])

    async def swipe(self, location, duration):
        await self.p.swipe(
            self.config['locations'][location][0],
            self.config['locations'][location][1],
            self.config['locations'][location][2],
            self.config['locations'][location][3],
            duration
        )
        if location in self.config['waits']:
            logger.info('Waiting ' + str(self.config['waits'][location]) + ' seconds after ' + str(self.config['locations'][location]) + '...')
            await asyncio.sleep(self.config['waits'][location])

    async def setup(self):
        self.p = PokemonGo()
        if self.args.device_id is None:
            await self.p.get_device()
        else:
            await self.p.set_device(self.args.device_id)
        if self.args.copy_calcy:
            await self.p.send_intent("clipper.set", extra_values=[["text", CALCY_STRING]])
            return False

        path = "config.yaml"
        device_path = await self.p.get_device()+".yaml"
        if self.args.config is None and os.path.exists(device_path):
            path = device_path
        elif self.args.config is not None:
            path = self.args.config

        with open(path, "r") as f:
            self.config = yaml.load(f, Loader)
        await self.p.start_logcat()

    async def check_name_length(self, name, strip_numberset = False):
        name_size = len(name)
        name_true_size = len(name.encode('utf-8')) / 2

        if name_true_size > 12 or name_size > 12:
            logger.error("Final string '%s' total size is too big: %s chars long, %s ascii chars long.", name, name_size, name_true_size)
            if strip_numberset:
                name = name.translate({ord(c): None for c in ''.join(NUMBER_SETS[2])})
                logger.warning("Removed superscripted IV.")
                name_size = len(name)
                name_true_size = len(name.encode('utf-8')) / 2

            if chr(189) in name:
                name = name.replace(chr(189), '')
                logger.warning("Removed character " + chr(189) + ", new name is %s", name)
                name_size = len(name)
                name_true_size = len(name.encode('utf-8')) / 2

            if name_true_size >= 12.5 or name_size > 12:
                for _ in range(0,4):
                    name = re.sub(r"(.+)([A-Za-z])(.+)", r'\1\3', name)
                    logger.warning("Stripping last letter, new name is %s", name)
                    name_size = len(name)
                    name_true_size = len(name.encode('utf-8')) / 2
                    if name_true_size <= 12 and name_size <= 12:
                        break

            if name_true_size > 12 or name_size > 12:
                logger.error("Resetting pokemon name with prefix, otherwise we'd get stuck! Other actions will still apply.")
                name = '! LENGTH'
            else:
                logger.warning("Managed to shorten pokemon's name, continuing...")

        logger.debug('Final string \'%s\' total real size: %s chars long.', name, name_true_size)
        return name

    async def start(self):
        if await self.setup() is False:
            return
        count = 0
        num_errors = 0
        # num_errors_too_soon = 0
        while True:
            # This loop also needs refactoring
            blacklist = False
            state, values = await self.check_pokemon()

            if values and values["name"] in self.config["blacklist"]:
                blacklist = True
            elif state == CALCY_SUCCESS:
                num_errors = 0
            elif state == CALCY_RED_BAR:
                continue
            elif state == CALCY_SCAN_INVALID or state == CALCY_OLD_BASE_STATS:
                num_errors += 1
                if state == CALCY_OLD_BASE_STATS:
                    await self.p.key('SHIFT TAB')
                    await self.p.key('ENTER')
                    await asyncio.sleep(0.5)
                if num_errors < args.max_retries:
                    await asyncio.sleep(0.1)  # waits a bit between each scan, otherwise goes too fast
                                              # sometimes the pokemon takes around a second to make the arc-level visible
                    continue
                num_errors = 0
            # if state == CALCY_SCAN_TOO_SOON or (state == CALCY_SCAN_INVALID and num_errors == 0):
            #     num_errors_too_soon += 1
            #     logger.error("Failed %s times in a row.", args.max_retries * num_errors_too_soon)
            #     if num_errors_too_soon == 2:
            #         logger.critical("Doesn't look like we can't do much. Moving on!")
            #         num_errors_too_soon = 0
            #         await self.tap('next')
            #         continue
            #     logger.warning("Trying to close a potencially stuck rename dialog...")
            #     await self.tap('rename_ok')

            values["success"] = True if state == CALCY_SUCCESS else False
            values["blacklist"] = blacklist
            values["appraised"] = True if values.get("appraised", False) is True else False
            actions = await self.get_actions(values)

            if "appraise" in actions:
                await self.tap("pokemon_menu_button")
                await self.tap("appraise_button")
                await self.tap("continue_appraisal")
                await self.p.send_intent("tesmath.calcy.ACTION_ANALYZE_SCREEN", "tesmath.calcy/.intents.IntentReceiver", extra_values=[["silentMode", True], ["--user", self.args.user]])
                await asyncio.sleep(0.2)
                await self.tap("dismiss_calcy")
                # await self.tap("continue_appraisal") # takes too long, we only need to wait a lot before the stats
                await self.tap("dismiss_calcy")
                values["appraised"] = True
                clipboard, clipboard_values = await self.get_data_from_clipboard()
                values = {**values, **clipboard_values}
                values["calcy"] = clipboard
                actions = await self.get_actions(values)

            if "get_moves" in actions:
                # If calcyiv already has both moves, then skip this action
                if values['fast_move'] == '' or values['charge_move'] == '' or values['fast_move'] == 'err' or values['charge_move'] == 'err':
                    logger.warning("Scrolling down...")
                    await self.swipe('scroll_to_moves', 500)
                    moves_state, moves_values = await self.check_pokemon()
                    if 'calcy' in moves_values:
                        values['calcy'] = moves_values['calcy']
                    logger.warning("Scrolling up again...")
                    await self.swipe('scroll_to_top', 500)

            if "replace" in actions:
                if values["success"] is False:
                    await self.p.key('SHIFT TAB')
                    await self.p.key('ENTER')
                    await asyncio.sleep(0.5)

                new_chr = actions["replace"]

                await self.tap('rename')
                await self.p.key('COPY')
                old_name = await self.p.get_clipboard()
                old_chr = old_name[:1]
                logger.info('Replacing first character %s with %s', old_chr, new_chr)
                new_name = new_chr + old_name[1:]

                final_name = await self.check_name_length(new_name)
                await self.p.send_intent("clipper.set", extra_values=[["text", final_name]])

                if args.touch_paste:
                    await self.tap_and_hold('edit_box', 600)
                    await self.tap('paste')
                else:
                    await self.p.key('PASTE')  # Paste into rename

                await self.p.key('TAB')
                await self.p.key('ENTER')

                await self.tap('rename_ok')

            if "rename" in actions:
                if values["success"] is False:
                    await self.p.key('SHIFT TAB')
                    await self.p.key('ENTER')
                    await asyncio.sleep(0.5)
                await self.tap('rename')
                if not (actions.get("rename", "{calcy}") == "{calcy}" or ('calcy' in actions["rename"] and len(actions["rename"]) == 1)): # Don't bother setting clipboard if we don't need to change it
                                                                                                                                          # also now allows users to forget to enclose {calcy} in quotes.
                    # Allows stripping superscripted IV to shorten the name
                    strip_numberset = False
                    if 'calcystrip' in actions["rename"]:
                        actions["rename"] = actions["rename"].replace("{calcystrip}", "{calcy}")
                        strip_numberset = True

                    name = actions["rename"].format(**values)
                    final_name = await self.check_name_length(name, strip_numberset)
                    await self.p.send_intent("clipper.set", extra_values=[["text", final_name]])

                if args.touch_paste:
                    await self.tap_and_hold('edit_box', 600)
                    await self.tap('paste')
                else:
                    await self.p.key('PASTE')  # Paste into rename

                await self.p.key('TAB')
                await self.p.key('ENTER')
                await self.tap('rename_ok')

            if "favorite" in actions:
                if not await self.check_favorite():
                    logger.info('Favoriting pokemon...')
                    await self.tap('favorite_button')
            count += 1
            if args.stop_after is not None and count >= args.stop_after:
                logger.info("Stop_after reached, stopping")
                return
            await self.tap('next')


    async def get_data_from_clipboard(self):
        clipboard = await self.p.get_clipboard()
        logger.debug('Device clipboard is: %s', clipboard)

        try:
            calcy, data = clipboard.split('\xa0'*NAME_MAX_LEN)
        except ValueError as e:
            logger.critical('Received clipboard data that does not contain 12 non-breaking spaces, did you run --copy-calcy and paste onto the end of your calcy rename settings? Clipboard data follows:')
            logger.critical(repr(clipboard), exc_info=true)
            raise
        data = data.split('|')
        values = {}
        for i, item in enumerate(CALCY_VARIABLES):
            name, function = item
            if function is None:
                values[name] = data[i]
            else:
                try:
                    values[name] = function(data[i])
                except:
                    values[name] = ''
        values['iv_avg'] = int((values['iv_min'] + values['iv_max']) / 2)
        values['iv'] = values['iv_min'] if values['iv_min'] == values['iv_max'] else None

        return calcy, values

    async def check_favorite(self):
        """Searches the favorite_button_box area for
        yellow pixels, and returns True if more than
        40% of the pixels are indeed yellow. Also, if
        the first check results in 0%, it checks twice,
        in case some pok??mon might have covered the
        favorite button.

        Returns:
            bool -- True if pok??mon was already favorited, False otherwise
        """

        ratio = None
        for _ in range(0, 2):
            screencap = await self.p.screencap()
            crop = screencap.crop(self.config['locations']['favorite_button_box'])
            rgb_im = crop.convert('RGB')
            width, height = rgb_im.size
            colors = [
                (244, 192, 13),
                (239, 182, 8),
                (246, 193, 14),
                (240, 184, 9),
                (248, 198, 16),
                (241, 184, 10),
                (243, 188, 11),
                (244, 191, 13),
                (242, 188, 11),
                (242, 186, 10),
                (243, 189, 11),
                (244, 191, 12),
                (243, 189, 12),
                (241, 186, 10),
                (247, 197, 15),
                (247, 196, 15),
                (244, 190, 12),
                (245, 193, 13),
                (246, 194, 14),
                (246, 195, 14),
                (241, 185, 10),
                (240, 183, 9),
                (242, 187, 11),
                (245, 192, 13),
            ]
            color_count = 0
            total_count = 0
            for x in range(1, width):
                for y in range(1, height):
                    c = rgb_im.getpixel((x, y))
                    if c in colors:
                        color_count += 1
                    total_count += 1

            ratio = color_count / total_count
            if color_count != 0:
                break

        logger.debug('Found %s yellow pixels from a total of %s pixels (%i%%).', color_count, total_count, 100 * ratio)
        return ratio > 0.4

    async def get_actions(self, values):
        for ruleset in self.config["actions"]:
            conditions = ruleset.get("conditions", {})
            # Check if we need to read the clipboard
            passed = True
            for key, item in conditions.items():
                operator = None
                if "__" in key:
                    key, operator = key.split("__")

                if isinstance(values[key], str):
                    if values[key].isnumeric():
                        values[key] = int(values[key])
                    else:
                        try:
                            values[key] = float(values[key])
                        except ValueError:
                            pass

                if key not in values:
                    passed = False
                    break
                if operator is not None:
                    if operator not in ops:
                        raise Exception("Unknown operator {}".format(operator))
                    operation = ops.get(operator)
                    if not operation(values[key], item):
                        passed = False
                        break
                elif values[key] != conditions[key]:
                    passed = False
                    break
            if passed:
                logger.debug('Condition matched against ' + str(ruleset.get("conditions", {})))
                return ruleset.get("actions", {})
        return {}

    async def check_pokemon(self):
        await self.p.send_intent("tesmath.calcy.ACTION_ANALYZE_SCREEN", "tesmath.calcy/.intents.IntentReceiver", extra_values=[["silentMode", True], ["--user", self.args.user]])
        red_bar = False
        values = {}
        while True:
            # TODO: This block's logic is not trivial, maybe a refactoring would help
            line = await self.p.read_logcat()
            if args.verbose:
                logger.debug("logcat line received: %s", line)

            match = RE_RED_BAR.match(line)
            if match:
                logger.error("RE_RED_BAR matched")
                red_bar = True

            match = RE_SCAN_INVALID.match(line)
            if match:
                if red_bar:
                    logger.error("RE_SCAN_INVALID matched and red_bar is True")
                    return CALCY_RED_BAR, values
                logger.error("RE_SCAN_INVALID matched, raising CalcyIVError")
                return CALCY_SCAN_INVALID, values

            match = RE_SCAN_TOO_SOON.match(line)
            if match:
                values = None
                logger.error("RE_SCAN_TOO_SOON matched, we're probably going too fast or you have some overlay covering values.")
                logger.error("If you get this error often, try raising 'waits -> rename_ok' in config.yaml")
                return CALCY_SCAN_TOO_SOON, values

            match = RE_OLD_BASE_STATS.match(line)
            if match:
                values = None
                logger.error("RE_OLD_BASE_STATS matched, this is either an old pokemon or a scan error.")
                return CALCY_OLD_BASE_STATS, values

            match = RE_CALCY_IV.match(line)
            if match:
                values = match.groupdict()
                state = CALCY_SUCCESS
                if values["name"] == 'err':
                    logger.error("Got 'err' as name, we're probably going too fast. If you get this error often, try raising 'waits -> rename_ok' in config.yaml")
                    return CALCY_SCAN_TOO_SOON, values
                elif values["cp"] == "-1" or values["level"] == "-1.0":
                    logger.error("Couldnt detect CP (got %s) or arc-level (got %s)", values["cp"], values["level"])
                elif red_bar is True:
                    logger.error("RE_CALCY_IV matched and red_bar is True")
                    state = CALCY_RED_BAR
                    return state, values
                else:
                    try:
                        clipboard, clipboard_values = await self.get_data_from_clipboard()
                    except:
                        return CALCY_OLD_BASE_STATS, values
                    values = {**values, **clipboard_values}
                    values["calcy"] = clipboard
                    logger.warning(values)
                    return state, values


if __name__ == '__main__':
    if platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    parser = argparse.ArgumentParser(description='Pokemon go renamer')
    parser.add_argument('--device-id', type=str, default=None,
                        help='Optional, if not specified the phone is automatically detected. Useful only if you have multiple phones connected. Use adb devices to get a list of ids.')
    parser.add_argument('--max-retries', type=int, default=5,
                        help='Maximum retries, set to 0 for unlimited.')
    parser.add_argument('--config', type=str, default=None,
                        help='Config file location.')
    parser.add_argument('--touch-paste', default=False, action='store_true',
                        help='Use touch instead of keyevent for paste.')
    parser.add_argument('--user', type=int, default=0,
                        help='Use a cloned CalcyIV from a different phone user. Useful for sandboxing apps like Island, where you could run two instances simultaneously.')
    parser.add_argument('--pid-name', default=None, type=str,
                        help='Create pid file')
    parser.add_argument('--pid-dir', default=None, type=str,
                        help='Change default pid directory')
    parser.add_argument('--stop-after', default=None, type=int,
                        help='Stop after X pokemon')
    parser.add_argument('--copy-calcy', default=False, action='store_true',
                        help='Copy calcy IV renaming string')
    parser.add_argument('--verbose', '-v', default=False, action='store_true',
                        help='Enables dumping of the device logcat. Spams quite a lot.')
    args = parser.parse_args()
    if args.pid_name is not None:
        from pid import PidFile
        with PidFile(args.pid_name, args.pid_dir) as p:
            asyncio.run(Main(args).start())
    else:
        asyncio.run(Main(args).start())

