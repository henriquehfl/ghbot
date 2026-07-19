import os
import re
import random
import asyncio
import discord
import yt_dlp
import requests
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'force_ipv4': True,
}

YDL_PLAYLIST_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'force_ipv4': True,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ar 48000 -ac 2',
}

EMBED_COLOR = 0x9B59B6

queues = {}
afk_tasks = {}
current_song = {}
loop_mode = {}
volume_level = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def create_embed(title, description="", color=EMBED_COLOR):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="GhBot 🎶")
    return embed


async def extract_info_with_fallback(ydl_opts, url, download=False):
    def sync_extract():
        cookies_file = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        opts = ydl_opts.copy()
        
        if os.path.exists(cookies_file):
            opts['cookiefile'] = cookies_file
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download), ydl

        opts_with_browser = opts.copy()
        opts_with_browser['cookiesfrombrowser'] = ('chrome', 'firefox', 'edge', 'brave', 'opera')
        try:
            ydl = yt_dlp.YoutubeDL(opts_with_browser)
            info = ydl.extract_info(url, download=download)
            return info, ydl
        except Exception:
            ydl = yt_dlp.YoutubeDL(opts)
            info = ydl.extract_info(url, download=download)
            return info, ydl

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_extract)


def resolve_music_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    if "spotify.com" in url:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            m = re.search(r'<title>(.*?) \| Spotify</title>', r.text)
            if m:
                clean_query = m.group(1).replace(" - song and lyrics by ", " - ").replace(" - song by ", " - ")
                return f"ytsearch1:{clean_query}"
        except Exception as e:
            print(f"Erro ao extrair do Spotify: {e}")

    elif "deezer.com" in url:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            m = re.search(r'<title>(.*?) \| Deezer</title>', r.text)
            if m:
                return f"ytsearch1:{m.group(1)}"
        except Exception as e:
            print(f"Erro ao extrair do Deezer: {e}")

    return url


async def afk_timer(ctx):
    await asyncio.sleep(300)
    if ctx.voice_client and not ctx.voice_client.is_playing():
        guild_id = ctx.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
        if guild_id in afk_tasks:
            del afk_tasks[guild_id]
        if guild_id in current_song:
            del current_song[guild_id]
        await ctx.voice_client.disconnect()
        await ctx.send(embed=create_embed("💤 Desconectado", "Saí por inatividade de 5 minutos."))


async def play_song(ctx, url_or_query, video_info=None):
    guild_id = ctx.guild.id

    if guild_id in afk_tasks and not afk_tasks[guild_id].done():
        afk_tasks[guild_id].cancel()

    try:
        if video_info is None:
            info, ydl = await extract_info_with_fallback(YDL_OPTIONS, url_or_query, download=False)
            if 'entries' in info:
                entries = info['entries']
                if not entries:
                    await ctx.send(embed=create_embed("😕 Sem resultados", "Não encontrei nenhum resultado para essa busca."))
                    return
                video = entries[0]
            else:
                video = info
        else:
            video = video_info

        audio_url = video['url']
        titulo = video['title']
        extractor = video.get('extractor', '')
        webpage_url = video.get('webpage_url', url_or_query)

        current_song[guild_id] = {'title': titulo, 'url': webpage_url}

        if 'soundcloud' in extractor.lower():
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f'{guild_id}.opus')

            dl_opts = {**YDL_OPTIONS, 'outtmpl': temp_file.replace('.opus', '.%(ext)s')}
            info, ydl = await extract_info_with_fallback(dl_opts, url_or_query, download=True)
            if 'entries' in info:
                video = info['entries'][0]
            else:
                video = info
            downloaded_file = ydl.prepare_filename(video)

            source = discord.FFmpegPCMAudio(downloaded_file, options='-ar 48000 -ac 2')
            vol = volume_level.get(guild_id, 0.5)
            source = discord.PCMVolumeTransformer(source, volume=vol)

            def after_play(error, file=downloaded_file):
                try:
                    if os.path.exists(file):
                        os.remove(file)
                except Exception:
                    pass
                check_queue(ctx)

            ctx.voice_client.play(source, after=after_play)
        else:
            source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
            vol = volume_level.get(guild_id, 0.5)
            source = discord.PCMVolumeTransformer(source, volume=vol)
            ctx.voice_client.play(source, after=lambda e: check_queue(ctx))

        await ctx.send(embed=create_embed("🎶 Tocando agora", f"**{titulo}**"))

    except Exception as e:
        await ctx.send(embed=create_embed("❌ Erro", f"Erro ao tentar tocar a música: {e}", color=0xE74C3C))
        check_queue(ctx)


def check_queue(ctx):
    asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)


async def play_next(ctx):
    guild_id = ctx.guild.id

    if loop_mode.get(guild_id, False) and guild_id in current_song:
        await play_song(ctx, current_song[guild_id]['url'])
        return

    if guild_id in queues and len(queues[guild_id]) > 0:
        next_song = queues[guild_id].pop(0)
        await play_song(ctx, next_song['url'])
    else:
        if guild_id in current_song:
            del current_song[guild_id]
        await ctx.send(embed=create_embed("💤 Fila vazia", "Use `!play` para adicionar mais músicas."))
        
        if guild_id in afk_tasks and not afk_tasks[guild_id].done():
            afk_tasks[guild_id].cancel()
        afk_tasks[guild_id] = bot.loop.create_task(afk_timer(ctx))


@bot.event
async def on_ready():
    print(f"Estou online! Conectado como {bot.user}")


@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(embed=create_embed("🏓 Pong!", f"Latência: **{latency}ms**"))


@bot.command()
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send(embed=create_embed("❌ Erro", "Você precisa estar em um canal de voz!", color=0xE74C3C))
        return
    channel = ctx.author.voice.channel
    await channel.connect()
    await ctx.send(embed=create_embed("🔊 Conectado", f"Entrei no canal: **{channel.name}**"))

    guild_id = ctx.guild.id
    if guild_id in afk_tasks and not afk_tasks[guild_id].done():
        afk_tasks[guild_id].cancel()
    afk_tasks[guild_id] = bot.loop.create_task(afk_timer(ctx))


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in afk_tasks and not afk_tasks[guild_id].done():
            afk_tasks[guild_id].cancel()
            if guild_id in afk_tasks:
                del afk_tasks[guild_id]
        if guild_id in queues:
            queues[guild_id].clear()
        if guild_id in current_song:
            del current_song[guild_id]
        loop_mode[guild_id] = False
        await ctx.voice_client.disconnect()
        await ctx.send(embed=create_embed("👋 Desconectado", "Saí do canal e limpei a fila!"))
    else:
        await ctx.send(embed=create_embed("❌ Erro", "Eu não estou em nenhum canal de voz!", color=0xE74C3C))


@bot.command()
async def play(ctx, *, search: str):
    if not ctx.voice_client:
        if not ctx.author.voice:
            await ctx.send(embed=create_embed("❌ Erro", "Você precisa estar conectado a um canal de voz!", color=0xE74C3C))
            return
        await ctx.author.voice.channel.connect()

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    search_query = search.strip()
    if any(domain in search_query for domain in ["youtube.com", "youtu.be", "soundcloud.com", "spotify.com", "deezer.com"]):
        if not search_query.startswith(("http://", "https://")):
            search_query = "https://" + search_query
        if "list=" in search_query:
            playlist_id_match = re.search(r"[?&]list=([^&]+)", search_query)
            if playlist_id_match:
                search_query = f"https://www.youtube.com/playlist?list={playlist_id_match.group(1)}"

    if "youtube.com/playlist" in search_query:
        await ctx.send(embed=create_embed("📋 Carregando playlist...", "Aguarde enquanto adiciono as músicas."))

        try:
            info, ydl = await extract_info_with_fallback(YDL_PLAYLIST_OPTIONS, search_query, download=False)
            if 'entries' not in info:
                await ctx.send(embed=create_embed("❌ Erro", "Não consegui carregar essa playlist.", color=0xE74C3C))
                return

            count = 0
            for entry in info['entries']:
                if entry:
                    video_url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    video_title = entry.get('title', 'Título desconhecido')
                    queues[guild_id].append({'url': video_url, 'title': video_title})
                    count += 1

            await ctx.send(embed=create_embed("✅ Playlist adicionada", f"**{count}** músicas foram adicionadas à fila!"))

            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                if queues[guild_id]:
                    next_song = queues[guild_id].pop(0)
                    await play_song(ctx, next_song['url'])
            return

        except Exception as e:
            await ctx.send(embed=create_embed("❌ Erro", f"Erro ao carregar playlist: {e}", color=0xE74C3C))
            return

    resolved_url = resolve_music_url(search_query)
    await ctx.send(embed=create_embed("🔍 Buscando...", "Procurando sua música, aguarde..."))

    try:
        info, ydl = await extract_info_with_fallback(YDL_OPTIONS, resolved_url, download=False)
        if 'entries' in info:
            entries = info['entries']
            if not entries:
                await ctx.send(embed=create_embed("😕 Sem resultados", "Não encontrei nenhum resultado para essa busca."))
                return
            video = entries[0]
        else:
            video = info

        titulo = video['title']
        original_url = video['webpage_url']

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            queues[guild_id].append({'url': original_url, 'title': titulo})
            await ctx.send(embed=create_embed("📝 Adicionado à fila", f"**{titulo}**\nPosição: `#{len(queues[guild_id])}`"))
        else:
            await play_song(ctx, original_url, video_info=video)

    except Exception as e:
        await ctx.send(embed=create_embed("❌ Erro", f"Erro ao processar o pedido: {e}", color=0xE74C3C))


@bot.command()
async def skip(ctx):
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        ctx.voice_client.stop()
        await ctx.send(embed=create_embed("⏭️ Pulada!", "Avançando para a próxima música..."))
    else:
        await ctx.send(embed=create_embed("❌ Erro", "Não há nenhuma música tocando no momento.", color=0xE74C3C))


@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send(embed=create_embed("⏸️ Pausado", "Use `!resume` para continuar."))
    else:
        await ctx.send(embed=create_embed("❌ Erro", "Não há nenhuma música tocando agora.", color=0xE74C3C))


@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send(embed=create_embed("▶️ Retomado", "A música voltou a tocar!"))
    else:
        await ctx.send(embed=create_embed("❌ Erro", "A música não está pausada.", color=0xE74C3C))


@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    if guild_id not in queues or len(queues[guild_id]) == 0:
        await ctx.send(embed=create_embed("🏜️ Fila vazia", "Não há músicas na fila. Use `!play` para adicionar!"))
        return

    song_list = ""
    for i, song in enumerate(queues[guild_id][:15], start=1):
        song_list += f"`{i}.` {song['title']}\n"

    if len(queues[guild_id]) > 15:
        song_list += f"\n*...e mais {len(queues[guild_id]) - 15} músicas.*"

    embed = create_embed("📋 Fila de Reprodução", song_list)
    embed.set_footer(text=f"Total: {len(queues[guild_id])} músicas | GhBot 🎶")
    await ctx.send(embed=embed)


@bot.command()
async def stop(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        queues[guild_id].clear()
    if guild_id in current_song:
        del current_song[guild_id]
    loop_mode[guild_id] = False
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send(embed=create_embed("🛑 Parado", "Música parada e fila limpa!"))
    else:
        await ctx.send(embed=create_embed("❌ Erro", "Eu não estou tocando nada no momento.", color=0xE74C3C))


@bot.command()
async def nowplaying(ctx):
    guild_id = ctx.guild.id
    if guild_id in current_song and ctx.voice_client and ctx.voice_client.is_playing():
        song = current_song[guild_id]
        embed = create_embed("🎵 Tocando agora", f"**{song['title']}**")
        looping = "✅ Ativado" if loop_mode.get(guild_id, False) else "❌ Desativado"
        vol = int(volume_level.get(guild_id, 0.5) * 100)
        embed.add_field(name="🔁 Loop", value=looping, inline=True)
        embed.add_field(name="🔊 Volume", value=f"{vol}%", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(embed=create_embed("🔇 Nada tocando", "Nenhuma música está tocando agora."))


@bot.command()
async def shuffle(ctx):
    guild_id = ctx.guild.id
    if guild_id not in queues or len(queues[guild_id]) < 2:
        await ctx.send(embed=create_embed("❌ Erro", "A fila precisa ter pelo menos 2 músicas para embaralhar!", color=0xE74C3C))
        return
    random.shuffle(queues[guild_id])
    await ctx.send(embed=create_embed("🔀 Fila embaralhada!", f"**{len(queues[guild_id])}** músicas foram reorganizadas aleatoriamente."))


@bot.command()
async def remove(ctx, pos: int):
    guild_id = ctx.guild.id
    if guild_id not in queues or len(queues[guild_id]) == 0:
        await ctx.send(embed=create_embed("❌ Erro", "A fila está vazia!", color=0xE74C3C))
        return
    if pos < 1 or pos > len(queues[guild_id]):
        await ctx.send(embed=create_embed("❌ Erro", f"Posição inválida! Use um número entre 1 e {len(queues[guild_id])}.", color=0xE74C3C))
        return
    removed = queues[guild_id].pop(pos - 1)
    await ctx.send(embed=create_embed("🗑️ Removida", f"**{removed['title']}** foi removida da fila."))


@bot.command()
async def volume(ctx, vol: int):
    guild_id = ctx.guild.id
    if vol < 0 or vol > 100:
        await ctx.send(embed=create_embed("❌ Erro", "O volume deve estar entre **0** e **100**.", color=0xE74C3C))
        return

    volume_level[guild_id] = vol / 100.0

    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = vol / 100.0

    await ctx.send(embed=create_embed("🔊 Volume ajustado", f"Volume definido para **{vol}%**"))


@bot.command()
async def loop(ctx):
    guild_id = ctx.guild.id
    loop_mode[guild_id] = not loop_mode.get(guild_id, False)
    status = "✅ **Ativado**" if loop_mode[guild_id] else "❌ **Desativado**"
    await ctx.send(embed=create_embed("🔁 Modo Loop", f"Loop: {status}"))


@bot.command()
async def comandos(ctx):
    embed = create_embed("📖 Lista de Comandos")

    embed.add_field(
        name="📢 Conexão",
        value=(
            "`!join` — Entra no seu canal de voz\n"
            "`!leave` — Desconecta e limpa a fila"
        ),
        inline=False
    )
    embed.add_field(
        name="🎵 Player",
        value=(
            "`!play <link/pesquisa>` — Toca do YouTube, Spotify, Deezer ou SoundCloud\n"
            "`!pause` — Pausa a música\n"
            "`!resume` — Retoma a música pausada\n"
            "`!skip` — Pula para a próxima\n"
            "`!stop` — Para tudo e limpa a fila\n"
            "`!nowplaying` — Mostra a música atual"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Fila",
        value=(
            "`!queue` — Mostra a fila de reprodução\n"
            "`!shuffle` — Embaralha a fila\n"
            "`!remove <nº>` — Remove uma música da fila"
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Configuração",
        value=(
            "`!volume <0-100>` — Ajusta o volume\n"
            "`!loop` — Liga/desliga repetição da música atual"
        ),
        inline=False
    )
    embed.add_field(
        name="ℹ️ Geral",
        value=(
            "`!ping` — Testa a latência do bot\n"
            "`!comandos` — Mostra esta lista"
        ),
        inline=False
    )

    await ctx.send(embed=embed)


token = os.getenv("DISCORD_TOKEN")
bot.run(token)
