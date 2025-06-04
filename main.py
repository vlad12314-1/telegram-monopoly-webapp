import asyncio
import logging
import random
import sys
from os import getenv

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логов
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Инициализация бота
TOKEN = getenv("7775775971:AAHbXc4VaJxsa3K1H4eQKoGOxzp6PWNA_Lw")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранение игровых данных
games = {}


class SimpleMonopolyGame:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = []
        self.money = {}
        self.positions = {}
        self.current_player = 0
        self.properties = {
            1: {"name": "Улица 1", "price": 100, "owner": None},
            3: {"name": "Улица 2", "price": 150, "owner": None},
            5: {"name": "Вокзал", "price": 200, "owner": None}
        }

    def add_player(self, user_id, username):
        if user_id not in self.players:
            self.players.append(user_id)
            self.money[user_id] = 1000
            self.positions[user_id] = 0
            return f"{username} присоединился к игре!"
        return f"{username} уже в игре!"

    async def roll_dice(self, user_id):
        if user_id != self.players[self.current_player]:
            return "Сейчас не ваш ход!"

        dice = random.randint(1, 6)
        self.positions[user_id] = (self.positions[user_id] + dice) % 8

        # Обработка клетки
        result = await self.handle_position(user_id)

        # Переход хода
        self.current_player = (self.current_player + 1) % len(self.players)

        return (
            f"🎲 Выпало: {dice}\n"
            f"➡️ Новая позиция: {self.get_position_name(self.positions[user_id])}\n"
            f"💰 Ваш баланс: {self.money[user_id]}$\n"
            f"{result}"
        )

    def get_position_name(self, pos):
        if pos in self.properties:
            return self.properties[pos]["name"]
        positions = {
            0: "Старт",
            2: "Налог",
            4: "Шанс",
            6: "Тюрьма"
        }
        return positions.get(pos, f"Клетка {pos}")

    async def handle_position(self, user_id):
        pos = self.positions[user_id]

        if pos == 2:  # Налог
            self.money[user_id] -= 100
            return "💸 Вы платите налог 100$"

        elif pos == 6:  # Тюрьма
            return "🚨 Вы попали в тюрьму! Пропустите ход."

        elif pos == 4:  # Шанс
            action = random.choice(["Получите 50$", "Заплатите 50$"])
            if "Получите" in action:
                self.money[user_id] += 50
            else:
                self.money[user_id] -= 50
            return f"🎴 Карточка: {action}"

        elif pos in self.properties:
            prop = self.properties[pos]
            if prop["owner"] is None:
                return f"🏠 {prop['name']} доступно для покупки (/buy)"
            elif prop["owner"] != user_id:
                rent = prop["price"] // 2
                self.money[user_id] -= rent
                self.money[prop["owner"]] += rent
                return f"🏠 Вы платите аренду {rent}$"

        return ""


@dp.message(CommandStart())
async def start_command(message: Message) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🎮 Играть в Монополию",
                web_app=WebAppInfo(url="https://vlad12314-1.github.io/telegram-monopoly-webapp/")
            )]
        ]
    )

    await message.answer(
        f"Привет, {html.bold(message.from_user.full_name)}!\n"
        "Давайте сыграем в упрощенную Монополию!",
        reply_markup=keyboard
    )


@dp.message(Command("newgame"))
async def new_game(message: Message):
    games[message.chat.id] = SimpleMonopolyGame(message.chat.id)
    await message.answer(
        "Новая игра создана!\n"
        "Используйте /join чтобы присоединиться\n"
        "Когда все готовы - /startgame"
    )


@dp.message(Command("join"))
async def join_game(message: Message):
    if message.chat.id not in games:
        await message.answer("Сначала создайте игру (/newgame)")
        return

    result = games[message.chat.id].add_player(
        message.from_user.id,
        message.from_user.full_name
    )
    await message.answer(result)


@dp.message(Command("startgame"))
async def start_game(message: Message):
    if message.chat.id not in games:
        await message.answer("Сначала создайте игру (/newgame)")
        return

    game = games[message.chat.id]
    if len(game.players) < 2:
        await message.answer("Нужно минимум 2 игрока!")
        return

    await message.answer(
        "Игра началась!\n"
        f"Первым ходит игрок {game.current_player + 1}\n"
        "Используйте /roll для броска кубиков"
    )


@dp.message(Command("roll"))
async def roll_dice(message: Message):
    if message.chat.id not in games:
        await message.answer("Сначала создайте игру (/newgame)")
        return

    result = await games[message.chat.id].roll_dice(message.from_user.id)
    await message.answer(result)


@dp.message(Command("buy"))
async def buy_property(message: Message):
    if message.chat.id not in games:
        await message.answer("Сначала создайте игру (/newgame)")
        return

    game = games[message.chat.id]
    user_id = message.from_user.id
    pos = game.positions[user_id]

    if pos not in game.properties:
        await message.answer("Здесь нельзя купить недвижимость")
        return

    prop = game.properties[pos]
    if prop["owner"] is not None:
        await message.answer("Эта собственность уже куплена")
        return

    if game.money[user_id] < prop["price"]:
        await message.answer("Недостаточно денег!")
        return

    game.money[user_id] -= prop["price"]
    prop["owner"] = user_id
    await message.answer(f"Вы купили {prop['name']} за {prop['price']}$")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
