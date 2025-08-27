import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
from urllib.parse import unquote
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация
BOT_TOKEN = ''  # Замени на токен своего бота

# Создаем бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def format_number(num):
    """Форматирует числа с сокращениями K и M"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.0f}M" if num % 1_000_000 == 0 else f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.0f}K" if num % 1_000 == 0 else f"{num / 1_000:.1f}K"
    else:
        return str(num)

def format_timestamp(timestamp):
    """Форматирует timestamp в читаемый вид"""
    dt = datetime.fromtimestamp(timestamp / 1000)
    return dt.strftime('%d.%m, %H:%M:%S')

def extract_rune_id(input_text):
    """Извлекает runeId из различных форматов"""
    # Если это URL
    if 'app.radfi.co/virtual-mint/' in input_text:
        try:
            start = input_text.find('virtual-mint/') + 13
            end = input_text.find('?', start) if '?' in input_text[start:] else len(input_text)
            return unquote(input_text[start:end])
        except:
            return None
    
    # Если это прямой ID вида 911957:2229
    if ':' in input_text and input_text.replace(':', '').replace('%3A', '').isdigit():
        return unquote(input_text)
    
    return None

def format_number(num):
    """Форматирует числа с сокращениями K и M"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.0f}M" if num % 1_000_000 == 0 else f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.0f}K" if num % 1_000 == 0 else f"{num / 1_000:.1f}K"
    else:
        return str(num)
    """Форматирует timestamp в читаемый вид"""
    dt = datetime.fromtimestamp(timestamp / 1000)
    return dt.strftime('%d.%m, %H:%M:%S')

async def get_all_unconfirmed_mints(rune_id, limit=None):
    """Получает ВСЕ неподтверждённые транзакции для токена"""
    try:
        from urllib.parse import quote
        encoded_rune_id = quote(rune_id)
        all_mints = []
        page = 1
        total_pages = 1
        
        print(f"🔍 Начинаю сбор неподтверждённых транзакций для {rune_id}...")
        if limit:
            print(f"📊 Ограничение: {limit} транзакций")
        
        async with aiohttp.ClientSession() as session:
            while page <= total_pages and (not limit or len(all_mints) < limit):
                url = f"https://api.radfi.org/api/vm-transactions?page={page}&pageSize=100&sort=-timestamp&state_eq=allInMempool&runeId_eq={encoded_rune_id}"
                
                print(f"📄 Загружаю страницу {page}/{total_pages}...")
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == "1":
                            mints = data.get('data', [])
                            meta_data = data.get('metaData', {})
                            
                            if page == 1:
                                total_pages = meta_data.get('totalPages', 1)
                                total_items = meta_data.get('totalItems', 0)
                                actual_limit = min(limit, total_items) if limit else total_items
                                print(f"📊 Найдено {total_items} неподтверждённых транзакций, показываю {actual_limit}")
                            
                            # Если есть лимит, обрезаем до нужного количества
                            if limit and len(all_mints) + len(mints) > limit:
                                remaining = limit - len(all_mints)
                                mints = mints[:remaining]
                            
                            all_mints.extend(mints)
                            page += 1
                            
                            # Если достигли лимита, прекращаем загрузку
                            if limit and len(all_mints) >= limit:
                                break
                                
                            # Небольшая задержка между запросами
                            if page <= total_pages:
                                await asyncio.sleep(0.1)
                        else:
                            break
                    else:
                        print(f"❌ Ошибка HTTP: {response.status}")
                        break
        
        print(f"✅ Загружено {len(all_mints)} неподтверждённых транзакций")
        
        return {
            'data': all_mints,
            'total_count': len(all_mints)
        }
        
    except Exception as e:
        print(f"❌ Ошибка при получении данных: {e}")
        return None

def split_message(text, max_length=1900):
    """Разбивает длинное сообщение на части"""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ''
    lines = text.split('\n')
    
    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
        else:
            current_chunk += line + '\n'
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user.name} запущен!')
    print('🟡 Бот показывает ВСЕ неподтверждённые транзакции')
    print('Доступные команды:')
    print('!unconfirmed <runeId> [количество] - Список неподтверждённых транзакций')
    print('!prices <runeId> - Объёмы по ценам')
    print('!minthelp - Помощь')

@bot.command(name='unconfirmed')
async def unconfirmed_command(ctx, *, args: str = None):
    """Показывает неподтверждённые транзакции для токена. Можно указать количество в конце."""
    if not args:
        await ctx.reply('Пожалуйста, укажи runeId или ссылку. Пример: `!unconfirmed 911957:2229` или `!unconfirmed 911957:2229 10`')
        return
    
    # Разбираем аргументы
    parts = args.strip().split()
    input_text = parts[0]
    limit = None
    
    # Проверяем, указано ли количество
    if len(parts) > 1:
        try:
            limit = int(parts[-1])  # Берём последний аргумент как число
            if limit <= 0:
                await ctx.reply('Количество должно быть положительным числом!')
                return
            # Если число валидное, убираем его из input_text
            input_text = ' '.join(parts[:-1])
        except ValueError:
            # Если последний аргумент не число, считаем что лимита нет
            input_text = args.strip()
    
    rune_id = extract_rune_id(input_text)
    
    if not rune_id:
        await ctx.reply('Не удалось определить runeId. Поддерживаемые форматы:\n- `911957:2229`\n- `https://app.radfi.co/virtual-mint/911957:2229`')
        return
    
    # Показываем, что бот работает
    if limit:
        loading_message = await ctx.reply(f'🔍 Собираю {limit} последних неподтверждённых транзакций...')
    else:
        loading_message = await ctx.reply('🔍 Собираю ВСЕ неподтверждённые транзакции... Это может занять несколько секунд...')
    
    result = await get_all_unconfirmed_mints(rune_id, limit)
    
    if not result:
        await loading_message.edit(content='❌ Не удалось получить данные. Проверь правильность runeId.')
        return
    
    all_mints = result['data']
    total_count = result['total_count']
    
    if not all_mints:
        await loading_message.edit(content='✅ Отлично! Нет неподтверждённых транзакций для этого токена - все минты подтверждены.')
        return
    
    # Создаем детальный отчет
    if limit:
        response = f"**🟡 {total_count} ПОСЛЕДНИХ НЕПОДТВЕРЖДЁННЫХ ТРАНЗАКЦИЙ для токена {rune_id}**\n"
    else:
        response = f"**🟡 ВСЕ НЕПОДТВЕРЖДЁННЫЕ ТРАНЗАКЦИИ для токена {rune_id}**\n"
    response += f"📊 Показано: **{total_count}** неподтверждённых транзакций\n"
    response += f"⏰ Данные на: {format_timestamp(datetime.now().timestamp() * 1000)}\n\n"
    
    total_sats = 0
    total_tokens = 0
    
    for index, mint in enumerate(all_mints):
        # API возвращает количество в базовых единицах (smallest unit)
        # Для Runes нужно разделить на 10,000 чтобы получить реальное количество токенов
        mempool_count_raw = mint.get('requestsInMempoolCount', 0)
        sats_amount = mint.get('satsNewRequests', 0)
        
        # Реальное количество токенов (API даёт в наименьших единицах)
        real_tokens = mempool_count_raw * 10000
        
        # Правильный расчёт цены за токен в сатоши
        sats_per_token = sats_amount / real_tokens if real_tokens > 0 else 0
        
        total_sats += sats_amount
        total_tokens += real_tokens
        
        # Компактный формат - одна строчка на транзакцию без ссылок
        response += f"**{index + 1}.** {format_timestamp(mint.get('timestamp', 0))} | {format_number(real_tokens)} токенов | {sats_per_token:.3f} sats\n"
    
    # Добавляем итоговую статистику
    avg_sats_per_token = total_sats / total_tokens if total_tokens > 0 else 0
    response += f"\n**📈 СТАТИСТИКА:**\n"
    response += f"💎 Токенов: {format_number(total_tokens)} | 💰 Сумма: {total_sats:,} sats | 📊 Средняя цена: {avg_sats_per_token:.3f} sats\n"
    
    # Разбиваем на части, если сообщение слишком длинное
    chunks = split_message(response)
    
    # Отправляем первое сообщение
    await loading_message.edit(content=chunks[0])
    
    # Отправляем остальные части
    for chunk in chunks[1:]:
        await ctx.send(chunk)
        await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями

@bot.command(name='prices')
async def prices_command(ctx, *, args: str = None):
    """Показывает суммированные объёмы по ценам для неподтверждённых транзакций"""
    if not args:
        await ctx.reply('Пожалуйста, укажи runeId или ссылку. Пример: `!prices 911957:2229`')
        return
    
    # Разбираем аргументы (аналогично команде unconfirmed)
    parts = args.strip().split()
    input_text = parts[0]
    
    rune_id = extract_rune_id(input_text)
    
    if not rune_id:
        await ctx.reply('Не удалось определить runeId. Поддерживаемые форматы:\n- `911957:2229`\n- `https://app.radfi.co/virtual-mint/911957:2229`')
        return
    
    # Показываем, что бот работает
    loading_message = await ctx.reply('🔍 Анализирую цены неподтверждённых транзакций...')
    
    result = await get_all_unconfirmed_mints(rune_id, None)  # Получаем все транзакции
    
    if not result:
        await loading_message.edit(content='❌ Не удалось получить данные. Проверь правильность runeId.')
        return
    
    all_mints = result['data']
    
    if not all_mints:
        await loading_message.edit(content='✅ Нет неподтверждённых транзакций для этого токена.')
        return
    
    # Группируем по ценам
    price_groups = {}
    
    for mint in all_mints:
        mempool_count_raw = mint.get('requestsInMempoolCount', 0)
        sats_amount = mint.get('satsNewRequests', 0)
        
        # Для расчёта цены используем полное количество
        real_tokens = mempool_count_raw * 10000
        sats_per_token = sats_amount / real_tokens if real_tokens > 0 else 0
        
        # Округляем цену до 3 знаков для группировки
        price_key = round(sats_per_token, 3)
        
        # Но для отображения используем исходное количество (делим на 10000)
        display_tokens = mempool_count_raw
        
        if price_key in price_groups:
            price_groups[price_key] += display_tokens
        else:
            price_groups[price_key] = display_tokens
    
    # Сортируем по цене (по убыванию)
    sorted_prices = sorted(price_groups.items(), key=lambda x: x[0], reverse=True)
    
    # Создаем отчет
    response = f"**💰 ОБЪЁМЫ ПО ЦЕНАМ для токена {rune_id}**\n"
    response += f"⏰ Данные на: {format_timestamp(datetime.now().timestamp() * 1000)}\n\n"
    
    total_tokens = 0
    
    for price, tokens in sorted_prices:
        total_tokens += tokens
        response += f"**{price:.3f} sats** → {format_number(tokens)}\n"
    
    response += f"\n**📈 ИТОГО:**\n"
    response += f"💎 Общее количество токенов: {format_number(total_tokens)}\n"
    
    # Разбиваем на части, если сообщение слишком длинное
    chunks = split_message(response)
    
    # Отправляем первое сообщение
    await loading_message.edit(content=chunks[0])
    
    # Отправляем остальные части
    for chunk in chunks[1:]:
        await ctx.send(chunk)
        await asyncio.sleep(0.5)
async def minthelp_command(ctx):
    """Показывает справку по командам"""
    embed = discord.Embed(
        title="🤖 RadFi Unconfirmed Mint Tracker",
        color=0xffaa00
    )
    
    embed.add_field(
        name="!unconfirmed <runeId/url> [количество]",
        value="Показывает неподтверждённые транзакции для токена\nПримеры:\n• `!unconfirmed 911957:2229` - все транзакции\n• `!unconfirmed 911957:2229 10` - только 10 последних",
        inline=False
    )
    
    embed.add_field(
        name="!minthelp",
        value="Показывает это сообщение с командами",
        inline=False
    )
    
    embed.add_field(
        name="🟡 Что показывают команды:",
        value="• **!unconfirmed** - список всех неподтверждённых транзакций\n• **!prices** - объёмы токенов по ценовым уровням\n• Все данные только для транзакций в мемпуле",
        inline=False
    )
    
    embed.add_field(
        name="Поддерживаемые форматы:",
        value="• `911957:2229`\n• `https://app.radfi.co/virtual-mint/911957:2229`",
        inline=False
    )
    
    embed.set_footer(text="Бот автоматически загружает все страницы с неподтверждёнными транзакциями")
    embed.timestamp = datetime.utcnow()
    
    await ctx.reply(embed=embed)

# Запуск бота
if __name__ == "__main__":
    bot.run(BOT_TOKEN)